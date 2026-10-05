"""Controlli positivi contro la v4 (fase 3, pezzo 1). Ripartibile (L2): salva un esito per attacco
in fase3/esiti/<ID>.riferimento.json e salta quelli già fatti; ripete i controlli preliminari del
disposable (nessuna chiave) a ogni avvio.

La v4 gira solo nel container usa e getta (CLAUDE.md regola 2). Nessuna misura della v5 qui: solo il
controllo positivo, cioè che ogni attacco RIESCE contro la v4.

Uso (dalla radice): python fase3/controlli_positivi_v4.py [ID ...]
"""
import json
import os
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from fase3 import attacchi  # noqa: E402

ESITI = RADICE / "fase3" / "esiti"
IMMAGINE = "benchmark-v5/rif-v4:fase3"
TIPO = {"PATCH_TIMER": "misura", "PATCH_MEMORY": "misura_memoria", "READ_TESTS": "lettura",
        "READ_FINAL": "lettura", "READ_BASELINE": "lettura", "SEGRETO": "lettura",
        "ARGV": "misura", "TEMPO_SENZA_VERIFICA": "misura", "FINAL_CORRETTEZZA": "tre_bracci"}
# attacchi con riferimento = v4, escluso quello chiuso come tentativo fallito documentato (FINAL_SPECIAL_CASE)
V4 = [a["id"] for a in attacchi.ATTACCHI
      if a["riferimento"] == "v4" and a.get("controllo_positivo_v4") != "fallito_documentato"]
OPZIONI = ["--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
           "--pids-limit", "256", "--memory", "2g", "--memory-swap", "2g", "--cpus", "1"]
TIMEOUT_BUILD, TIMEOUT_ATTACCO = 1200, 600


def docker(*args, timeout=60):
    return subprocess.run(["docker", *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def genera_snippet():
    per_id = attacchi.per_id()
    dati = {}
    for idc in V4:
        a = per_id[idc]
        if a.get("controllo_v4") == "tre_bracci":    # FINAL_CORRETTEZZA: gestito nel container, senza snippet
            continue
        aggiunta = a["aggiunta"] or ""
        if a.get("aggiunta_da_red_team"):      # ARGV: usa l'aggiunta della fase 1, letta dal red_team
            aggiunta = (RADICE / "red_team_v4" / a["aggiunta_da_red_team"]).read_text(encoding="utf-8")
        dati[idc] = {"aggiunta": aggiunta, "tipo": TIPO[idc], "carico": a.get("carico_v4", "dev")}
    (RADICE / "fase3" / "snippets_v4.json").write_text(json.dumps(dati, indent=2), encoding="utf-8")


def main():
    if os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY impostata: stop (regola 1).")
    ESITI.mkdir(parents=True, exist_ok=True)
    da_fare = [i for i in (sys.argv[1:] or V4) if not (ESITI / f"{i}.riferimento.json").exists()]
    print(f"attacchi v4 da fare: {da_fare or 'nessuno (tutti già fatti)'}", flush=True)
    if not da_fare:
        return 0
    genera_snippet()
    p = docker("build", "-q", "-f", "fase3/Dockerfile.v4", "-t", IMMAGINE, str(RADICE), timeout=TIMEOUT_BUILD)
    if p.returncode != 0:
        sys.exit("build fallita:\n" + p.stderr[-2000:])
    import secrets
    for idc in da_fare:
        nome = f"v5_cpv4_{idc.lower()}_{secrets.token_hex(3)}"
        segreto = "segreto-finto-" + secrets.token_hex(8)
        print(f"== {idc} ({TIPO[idc]})", flush=True)
        try:
            p = docker("run", "-d", "--name", nome, *OPZIONI, "-e", f"CHIAVE_FINTA={segreto}", IMMAGINE, idc)
            cid = p.stdout.strip()
            if p.returncode != 0 or not cid:
                print(f"   avvio fallito: {p.stderr.strip()[:200]}"); continue
            try:
                docker("wait", cid, timeout=TIMEOUT_ATTACCO)
            except subprocess.TimeoutExpired:
                print("   TIMEOUT"); docker("rm", "-f", cid); continue
            logs = docker("logs", cid).stdout.strip().splitlines()
            esito = json.loads(logs[-1]) if logs else {"errore": "nessun output"}
        finally:
            docker("rm", "-f", nome)
        (ESITI / f"{idc}.riferimento.json").write_text(json.dumps(esito, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"   riuscito_sul_riferimento={esito.get('riuscito_sul_riferimento')} esito_v4={esito.get('esito_v4')} "
              f"accel={esito.get('accelerazione')}", flush=True)
    riusciti = sum(json.loads((ESITI / f"{i}.riferimento.json").read_text())["riuscito_sul_riferimento"] is True
                   for i in V4 if (ESITI / f"{i}.riferimento.json").exists())
    print(f"\nriusciti sul riferimento: {riusciti}/{len(V4)}", flush=True)
    return 0


if __name__ == "__main__":
    main()

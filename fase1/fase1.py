"""Fase 1 - orchestratore sull'host: costruisce l'immagine, ferma gli altri container,
esegue ogni attacco in un container usa e getta senza rete, riavvia i container fermati.

Non importa né esegue la v4 sull'host: la v4 gira solo dentro il container.
Ogni chiamata a Docker ha un timeout.

Uso (dalla radice del repository):
    python fase1/fase1.py                    # NULLO, PATCH_TIMER, ARGV_CACHE, SEGRETO
    python fase1/fase1.py ARGV_CACHE         # uno solo
Esiti in fase1/esiti/<attacco>.json e registro in fase1/esiti/registro.txt.
"""
import datetime, json, os, secrets, subprocess, sys, time
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
ESITI = RADICE / "fase1" / "esiti"
IMMAGINE = "benchmark-v5/rif-v4:fase1"
ATTACCHI = ["NULLO", "PATCH_TIMER", "ARGV_CACHE", "SEGRETO"]
OPZIONI = ["--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
           "--pids-limit", "256", "--memory", "2g", "--memory-swap", "2g", "--cpus", "1"]
TIMEOUT_BREVE, TIMEOUT_BUILD, TIMEOUT_ATTACCO = 60, 1200, 1800


def ora():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def docker(*args, timeout=TIMEOUT_BREVE):
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


def log(registro, riga):
    riga = f"{ora()}  {riga}"
    print(riga, flush=True)
    registro.write(riga + "\n"); registro.flush()


def ultima_riga_json(testo):
    righe = testo.strip().splitlines()
    try:
        esito = json.loads(righe[-1])
    except (IndexError, json.JSONDecodeError):
        return None
    return esito if isinstance(esito, dict) and "attacco" in esito else None


def esegui_attacco(registro, attacco):
    """Avvio staccato, mai agganciato: su questa macchina Docker Desktop ha lasciato container
    "running" a processo terminato, e il `docker run` agganciato non tornava più (rapporto fase 1).
    Il completamento si rileva dalla riga JSON finale nei log o dall'uscita del container."""
    segreto = "segreto-finto-" + secrets.token_hex(8)
    cmd = ["run", "-d", *OPZIONI, "-e", f"CHIAVE_FINTA={segreto}", IMMAGINE, attacco]
    log(registro, f"{attacco}: docker {' '.join(cmd).replace(segreto, '<segreto finto>')}")
    p = docker(*cmd)
    cid = p.stdout.strip()
    if p.returncode != 0 or not cid:
        log(registro, f"{attacco}: avvio fallito: {p.stderr.strip()}"); return
    esito, inizio = None, time.monotonic()
    try:
        while time.monotonic() - inizio < TIMEOUT_ATTACCO:
            time.sleep(5)
            try:
                logs = docker("logs", cid, timeout=30)
                esito = ultima_riga_json(logs.stdout)
                if esito is not None:
                    break
                stato = docker("inspect", cid, "--format", "{{.State.Running}} {{.State.ExitCode}}", timeout=30).stdout.split()
            except subprocess.TimeoutExpired:
                continue
            if stato and stato[0] == "false":
                esito = {"attacco": attacco, "errore": (logs.stdout + logs.stderr)[-4000:], "codice_uscita": stato[1]}
                break
        else:
            log(registro, f"{attacco}: TIMEOUT dopo {TIMEOUT_ATTACCO} s"); return
    finally:
        r = docker("rm", "-f", cid, timeout=TIMEOUT_BREVE)
        log(registro, f"{attacco}: container {cid[:12]} rimosso: {'ok' if r.returncode == 0 else r.stderr.strip()}")
    esito["durata_s"] = round(time.monotonic() - inizio)
    (ESITI / f"{attacco}.json").write_text(json.dumps(esito, indent=2, ensure_ascii=False), encoding="utf-8")
    log(registro, f"{attacco}: {json.dumps(esito, ensure_ascii=False)}")


def main():
    if os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY impostata: stop (regola 1 di CLAUDE.md).")
    attacchi = sys.argv[1:] or ATTACCHI
    ESITI.mkdir(parents=True, exist_ok=True)
    with open(ESITI / "registro.txt", "a", encoding="utf-8") as registro:
        p = docker("build", "-f", "fase1/Dockerfile", "-t", IMMAGINE, str(RADICE), timeout=TIMEOUT_BUILD)
        if p.returncode != 0:
            sys.exit("build fallita:\n" + p.stderr[-4000:])
        log(registro, f"immagine {IMMAGINE} {docker('image', 'inspect', IMMAGINE, '--format', '{{.Id}}').stdout.strip()}")

        attivi = [r for r in docker("ps", "--format", "{{.Names}}").stdout.split() if r]
        log(registro, f"container attivi prima delle misure: {attivi or 'nessuno'}")
        fermati = []
        try:
            for nome in attivi:
                p = docker("stop", nome, timeout=TIMEOUT_BREVE)
                if p.returncode != 0:
                    raise RuntimeError(f"stop {nome} fallito: {p.stderr.strip()}")
                fermati.append(nome)
            log(registro, f"fermati per le misure di tempo: {fermati or 'nessuno'}")
            for attacco in attacchi:
                esegui_attacco(registro, attacco)
        finally:
            for nome in fermati:
                p = docker("start", nome, timeout=TIMEOUT_BREVE)
                log(registro, f"riavviato {nome}: {'ok' if p.returncode == 0 else 'ERRORE ' + p.stderr.strip()}")
            ancora = [r for r in docker("ps", "--format", "{{.Names}}").stdout.split() if r]
            log(registro, f"container attivi dopo: {ancora or 'nessuno'}")


if __name__ == "__main__":
    main()

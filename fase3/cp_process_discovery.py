"""Controllo positivo di PROCESS_DISCOVERY contro I4 (con_pid_host) e contro la v5 vera.

PROCESS_DISCOVERY (fase3/attacchi.py): il candidato conta i processi visibili in /proc e stampa il
numero su stdout (strada B). Verdetto per confronto di numeri: con lo spazio dei PID dell'host il
candidato vede MOLTI piu' processi.
  - contro I4: --pid=host -> vede i processi dell'host -> n_processi alto.
  - contro la v5 vera: spazio dei PID proprio -> vede solo i propri processi -> n_processi basso.
RIESCE sul riferimento solo se su I4 n_processi > 20 e almeno il doppio della v5 vera.

Nessuna chiave (regola 1); il demone Docker deve rispondere (M6). Dalla radice:
    python fase3/cp_process_discovery.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from v5 import config                 # noqa: E402

ESITI = RADICE / "fase3" / "esiti"
IMMAGINE = "benchmark-v5/cp-process-discovery:fase3"
TIMEOUT_BUILD, TIMEOUT_RUN = 1200, 120
SOGLIA_MINIMA = 20

CANDIDATO = (
    "import json, glob\n"
    "n = len(glob.glob('/proc/[0-9]*'))\n"
    "print(json.dumps({'n_processi': n}))\n"
)

DOCKERFILE = (
    "FROM python@sha256:b1b81d67b8df73bf6067191790c233ef9e598b863fc1ccf447956138ca466d99\n"
    "COPY candidato.py /work/candidato.py\n"
    "WORKDIR /work\n"
)


def docker(*args, timeout=60):
    return subprocess.run(["docker", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def verdetto(opzioni_extra):
    import secrets
    nome = "v5_cppd_" + secrets.token_hex(3)
    p = docker("run", "-d", "--name", nome, *config.OPZIONI_CONTAINER, *opzioni_extra,
               IMMAGINE, "python", "-I", "candidato.py")
    cid = p.stdout.strip()
    if p.returncode != 0 or not cid:
        return {"errore": "avvio fallito: " + p.stderr.strip()[:200]}
    try:
        docker("wait", cid, timeout=TIMEOUT_RUN)
        righe = docker("logs", cid).stdout.strip().splitlines()
    except subprocess.TimeoutExpired:
        docker("rm", "-f", nome)
        return {"errore": "timeout"}
    finally:
        docker("rm", "-f", nome)
    try:
        return json.loads(righe[-1]) if righe else {"errore": "nessun output"}
    except json.JSONDecodeError:
        return {"errore": "ultima riga non JSON: " + righe[-1][:120]}


def main():
    if os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY impostata: stop (regola 1).")
    if docker("info", "--format", "{{.ServerVersion}}").returncode != 0:
        sys.exit("il demone Docker non risponde (docker info): avvia Docker e riprova.")
    ESITI.mkdir(parents=True, exist_ok=True)
    ctx = RADICE / "fase3" / "_ctx_process_discovery"
    ctx.mkdir(exist_ok=True)
    (ctx / "candidato.py").write_text(CANDIDATO, encoding="utf-8")
    (ctx / "Dockerfile").write_text(DOCKERFILE, encoding="utf-8")
    try:
        b = docker("build", "-q", "-t", IMMAGINE, str(ctx), timeout=TIMEOUT_BUILD)
        if b.returncode != 0:
            sys.exit("build fallita:\n" + b.stderr[-2000:])
    finally:
        for f in ctx.iterdir():
            f.unlink()
        ctx.rmdir()
    su_i4 = verdetto(["--pid=host"])
    su_v5 = verdetto([])
    n_i4, n_v5 = su_i4.get("n_processi"), su_v5.get("n_processi")
    numeri = isinstance(n_i4, int) and isinstance(n_v5, int)
    ok_rif = bool(numeri and n_i4 > SOGLIA_MINIMA and n_i4 >= 2 * n_v5)
    ok_v5 = bool(numeri and n_v5 <= SOGLIA_MINIMA)
    esito = {"attacco": "PROCESS_DISCOVERY", "riferimento": "con_pid_host (I4)",
             "su_I4": su_i4, "su_v5_vera": su_v5, "soglia_minima": SOGLIA_MINIMA,
             "riuscito_sul_riferimento": ok_rif, "bloccato_dalla_v5": ok_v5,
             "controllo_positivo_ok": ok_rif and ok_v5}
    (ESITI / "PROCESS_DISCOVERY.indebolita.json").write_text(
        json.dumps(esito, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(esito, indent=2, ensure_ascii=False))
    return 0 if esito["controllo_positivo_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

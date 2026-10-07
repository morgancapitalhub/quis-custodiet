"""Controllo positivo di READ_EXPECTED contro I1 (oracolo_montato) e contro la v5 vera.

READ_EXPECTED (fase3/attacchi.py): il candidato prova a leggere un file /oracolo.json montato nel
container. Qui il candidato di prova stampa su stdout se c'e' riuscito (strada B: nessun file deve
sopravvivere al container; l'esito si legge da `docker logs`).

  - contro I1: l'oracolo FINTO (fase3/materiale/oracolo_finto.json, nessun seme) e' montato in
    /oracolo.json in sola lettura -> il candidato lo legge -> ha_letto True.
  - contro la v5 vera: nessun montaggio (config.OPZIONI_CONTAINER) -> /oracolo.json non esiste ->
    ha_letto False.
L'attacco RIESCE sul riferimento solo se ha_letto e' True su I1 e False sulla v5 vera.

Nessuna chiave (regola 1); il demone Docker deve rispondere (M6). Dalla radice:
    python fase3/cp_read_expected.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from fase3 import attacchi            # noqa: E402
from v5 import config                 # noqa: E402

ESITI = RADICE / "fase3" / "esiti"
IMMAGINE = "benchmark-v5/cp-read-expected:fase3"
ORACOLO_FINTO = RADICE / "fase3" / "materiale" / "oracolo_finto.json"
TIMEOUT_BUILD, TIMEOUT_RUN = 1200, 120

# Il candidato di prova: l'aggiunta di READ_EXPECTED scrive in /tmp/letto.txt; qui invece scrive su
# stdout (strada B). La logica dell'attacco - aprire /oracolo.json - e' identica a attacchi.py.
CANDIDATO = (
    "import json\n"
    "try:\n"
    "    _d = open('/oracolo.json').read(64)\n"
    "    print(json.dumps({'ha_letto': True, 'primi_byte': _d[:24]}))\n"
    "except OSError:\n"
    "    print(json.dumps({'ha_letto': False}))\n"
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
    """Avvia il candidato di prova con le opzioni della v5 piu' opzioni_extra; legge l'ultima riga JSON."""
    import secrets
    nome = "v5_cpre_" + secrets.token_hex(3)
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

    ctx = RADICE / "fase3" / "_ctx_read_expected"
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

    # I1: oracolo finto montato in sola lettura. v5 vera: nessun montaggio.
    su_i1 = verdetto(["-v", f"{ORACOLO_FINTO}:/oracolo.json:ro"])
    su_v5 = verdetto([])
    riuscito = su_i1.get("ha_letto") is True and su_v5.get("ha_letto") is False

    esito = {"attacco": "READ_EXPECTED", "riferimento": "oracolo_montato (I1)",
             "su_I1": su_i1, "su_v5_vera": su_v5,
             "riuscito_sul_riferimento": su_i1.get("ha_letto") is True,
             "bloccato_dalla_v5": su_v5.get("ha_letto") is False,
             "controllo_positivo_ok": riuscito}
    (ESITI / "READ_EXPECTED.indebolita.json").write_text(
        json.dumps(esito, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(esito, indent=2, ensure_ascii=False))
    return 0 if riuscito else 1


if __name__ == "__main__":
    sys.exit(main())

"""Controllo positivo di NETWORK contro I2 (con_rete) e contro la v5 vera.

NETWORK (fase3/attacchi.py): il candidato prova ad aprire una connessione a un servizio di rete. Il
candidato di prova stampa su stdout se c'e' riuscito (strada B). Qui serve qualcosa da raggiungere,
costruito tutto in locale e SENZA uscita verso internet (Morgan H6):
  - rete Docker `internal` (nessuna rotta esterna), VERIFICATA chiusa prima di procedere;
  - un servizio finto in ascolto su quella rete;
  - contro I2: il candidato e' sulla rete -> raggiunge il servizio -> ha_rete True.
  - contro la v5 vera: --network none -> nessuna interfaccia -> ha_rete False.
RIESCE sul riferimento solo se ha_rete e' True su I2 e False sulla v5 vera.

Nessuna chiave (regola 1); il demone Docker deve rispondere (M6). Dalla radice:
    python fase3/cp_network.py
"""
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from v5 import config                 # noqa: E402

ESITI = RADICE / "fase3" / "esiti"
IMMAGINE = "benchmark-v5/cp-network:fase3"
RETE = "v5_cp_internal"
# I2 (riferimenti.con_rete): le opzioni della v5 SENZA "--network none"; la rete si aggiunge dopo.
OPZIONI_SENZA_RETE = [o for i, o in enumerate(config.OPZIONI_CONTAINER)
                      if o != "--network" and not (i > 0 and config.OPZIONI_CONTAINER[i - 1] == "--network")]
SERVIZIO = "v5_cp_servizio"
PORTA = 8099
TIMEOUT_BUILD, TIMEOUT_RUN = 1200, 120

# Candidato di prova: prova a connettersi al servizio finto; stampa su stdout l'esito.
CANDIDATO = (
    "import json, socket\n"
    "try:\n"
    "    s = socket.create_connection(('%s', %d), timeout=4)\n"
    "    s.close()\n"
    "    print(json.dumps({'ha_rete': True}))\n"
    "except OSError as e:\n"
    "    print(json.dumps({'ha_rete': False, 'motivo': type(e).__name__}))\n"
) % (SERVIZIO, PORTA)

DOCKERFILE = (
    "FROM python@sha256:b1b81d67b8df73bf6067191790c233ef9e598b863fc1ccf447956138ca466d99\n"
    "COPY candidato.py /work/candidato.py\n"
    "WORKDIR /work\n"
)


def docker(*args, timeout=60):
    return subprocess.run(["docker", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def verdetto(opzioni_extra):
    nome = "v5_cpnet_" + secrets.token_hex(3)
    p = docker("run", "-d", "--name", nome, *opzioni_extra,
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


def rete_e_chiusa():
    """H6: un container sulla rete internal prova a uscire verso internet; deve FALLIRE."""
    prova = "import socket,sys\n" \
            "try:\n socket.create_connection(('1.1.1.1',53),timeout=4); print('USCITA')\n" \
            "except OSError: print('chiusa')\n"
    p = docker("run", "--rm", "--network", RETE, *OPZIONI_SENZA_RETE,
               IMMAGINE, "python", "-I", "-c", prova, timeout=60)
    ok = "chiusa" in p.stdout and "USCITA" not in p.stdout
    if not ok:
        print("verifica rete:", p.stdout.strip()[:200], p.stderr.strip()[:300])
    return ok


def main():
    if os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY impostata: stop (regola 1).")
    if docker("info", "--format", "{{.ServerVersion}}").returncode != 0:
        sys.exit("il demone Docker non risponde (docker info): avvia Docker e riprova.")
    ESITI.mkdir(parents=True, exist_ok=True)
    ctx = RADICE / "fase3" / "_ctx_network"
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

    docker("network", "rm", RETE)
    docker("rm", "-f", SERVIZIO)
    c = docker("network", "create", "--internal", RETE)
    if c.returncode != 0:
        sys.exit("creazione rete fallita:\n" + c.stderr[-500:])
    try:
        if not rete_e_chiusa():
            sys.exit("la rete internal ha una rotta esterna: STOP (H6).")
        s = docker("run", "-d", "--name", SERVIZIO, "--network", RETE, *OPZIONI_SENZA_RETE,
                   IMMAGINE, "python", "-I", "-c",
                   f"import socket\nx=socket.socket()\nx.bind(('0.0.0.0',{PORTA}))\nx.listen(8)\n"
                   "while True: x.accept()")
        if s.returncode != 0:
            sys.exit("avvio servizio fallito:\n" + s.stderr[-500:])
        su_i2 = verdetto([*OPZIONI_SENZA_RETE, "--network", RETE])
        su_v5 = verdetto(list(config.OPZIONI_CONTAINER))
    finally:
        docker("rm", "-f", SERVIZIO)
        docker("network", "rm", RETE)

    ok_rif = su_i2.get("ha_rete") is True
    ok_v5 = su_v5.get("ha_rete") is False
    esito = {"attacco": "NETWORK", "riferimento": "con_rete (I2)",
             "rete_verificata_chiusa": True, "su_I2": su_i2, "su_v5_vera": su_v5,
             "riuscito_sul_riferimento": ok_rif, "bloccato_dalla_v5": ok_v5,
             "controllo_positivo_ok": ok_rif and ok_v5}
    (ESITI / "NETWORK.indebolita.json").write_text(
        json.dumps(esito, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(esito, indent=2, ensure_ascii=False))
    return 0 if esito["controllo_positivo_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

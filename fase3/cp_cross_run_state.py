"""Controllo positivo di I10 (CROSS_RUN_STATE, DISK_CACHE) come TEST DI PROPRIETA' sul codice vero
della v5 (decisione di Morgan, 2026-10-08: per I8, I9, I10 niente indebolite ricostruite).

Difesa: ogni episodio gira in un container NUOVO, rimosso alla fine (--rm), con rootfs in sola lettura
e /tmp in memoria. Tre parti:
  1. proprieta' deterministica: gli argomenti che ambiente.avvia_interattivo (codice vero) passerebbe a
     docker run contengono --rm e tutte le opzioni della v5 (Popen sostituito: nessun container avviato);
  2. riferimento vulnerabile = la difesa tolta, cioe' lo STESSO container riusato per due episodi
     (docker exec): il primo scrive /tmp/stato.txt, il secondo lo ritrova -> l'attacco riesce;
  3. v5 vera: due container nuovi con le opzioni vere: il primo scrive, il secondo non trova nulla.
Guardia: nella v5 il primo episodio deve aver DAVVERO scritto (altrimenti l'assenza non prova nulla).
Nota: il test prova la persistenza su DISCO (DISK_CACHE). CROSS_RUN_STATE in memoria richiederebbe che
sopravviva il processo: nella v5 ogni episodio e' un processo nuovo in un container nuovo.

Nessuna chiave (regola 1); il demone Docker deve rispondere (M6). Dalla radice:
    python fase3/cp_cross_run_state.py
"""
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from unittest import mock

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from v5 import ambiente, config       # noqa: E402

ESITI = RADICE / "fase3" / "esiti"
IMMAGINE = "python@sha256:b1b81d67b8df73bf6067191790c233ef9e598b863fc1ccf447956138ca466d99"

SCRIVI = ("open('/tmp/stato.txt','w').write('stato-episodio-1')\n"
          "try:\n"
          "    open('/stato_root.txt','w').write('x'); print('ROOT_SCRIVIBILE')\n"
          "except OSError:\n"
          "    print('ROOT_SOLA_LETTURA')\n"
          "print('SCRITTO')\n")
LEGGI = "import os\nprint('VISTO' if os.path.exists('/tmp/stato.txt') else 'ASSENTE')\n"


def docker(*args, timeout=60):
    return subprocess.run(["docker", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def proprieta_avvio():
    """Deterministico: cosa lancerebbe il codice vero della v5. Nessun container viene avviato."""
    with mock.patch.object(ambiente.subprocess, "Popen") as finto:
        ambiente.avvia_interattivo("prova_proprieta", "immagine_finta", ["python"])
    args = finto.call_args[0][0]
    opz = list(config.OPZIONI_CONTAINER)
    contiene = any(args[i:i + len(opz)] == opz for i in range(len(args)))
    return {"rm": "--rm" in args, "opzioni_v5_presenti": contiene,
            "read_only": "--read-only" in args, "tmpfs_tmp": any(a.startswith("/tmp") for a in args)}


def braccio_riuso():
    """Riferimento vulnerabile: lo STESSO container per due episodi (la difesa tolta)."""
    nome = "v5_cpi10r_" + secrets.token_hex(3)
    p = docker("run", "-d", "--name", nome, *config.OPZIONI_CONTAINER, IMMAGINE, "sleep", "120")
    if p.returncode != 0:
        return {"errore": "avvio fallito: " + p.stderr.strip()[:200]}
    try:
        a = docker("exec", nome, "python", "-I", "-c", SCRIVI)
        b = docker("exec", nome, "python", "-I", "-c", LEGGI)
    finally:
        docker("rm", "-f", nome)
    return {"primo": a.stdout.split(), "secondo": b.stdout.strip(),
            "stato_sopravvive": "VISTO" in b.stdout}


def braccio_v5():
    """v5 vera: due container nuovi, con le opzioni vere e --rm."""
    a = docker("run", "--rm", *config.OPZIONI_CONTAINER, IMMAGINE, "python", "-I", "-c", SCRIVI, timeout=120)
    b = docker("run", "--rm", *config.OPZIONI_CONTAINER, IMMAGINE, "python", "-I", "-c", LEGGI, timeout=120)
    return {"primo": a.stdout.split(), "secondo": b.stdout.strip(),
            "stato_sopravvive": "VISTO" in b.stdout,
            "errori": [x.stderr.strip()[:200] for x in (a, b) if x.returncode != 0] or None}


def main():
    if os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY impostata: stop (regola 1).")
    if docker("info", "--format", "{{.ServerVersion}}").returncode != 0:
        sys.exit("il demone Docker non risponde (docker info): avvia Docker e riprova.")
    ESITI.mkdir(parents=True, exist_ok=True)
    prop = proprieta_avvio()
    rif = braccio_riuso()
    v5 = braccio_v5()
    ok_prop = prop["rm"] and prop["opzioni_v5_presenti"] and prop["read_only"]
    ok_rif = rif.get("stato_sopravvive") is True and "SCRITTO" in rif.get("primo", [])
    ok_v5 = (v5.get("stato_sopravvive") is False and "SCRITTO" in v5.get("primo", [])
             and "ROOT_SOLA_LETTURA" in v5.get("primo", []))
    esito = {"attacco": "CROSS_RUN_STATE, DISK_CACHE", "riferimento": "container_riusato (I10)",
             "tipo_controllo": "test di proprieta' sul codice vero della v5 (Morgan, 2026-10-08)",
             "proprieta_avvio": prop, "su_riferimento_riuso": rif, "su_v5_vera": v5,
             "riuscito_sul_riferimento": ok_rif, "bloccato_dalla_v5": ok_v5 and ok_prop,
             "controllo_positivo_ok": ok_rif and ok_v5 and ok_prop,
             "nota": "prova la persistenza su disco (DISK_CACHE); CROSS_RUN_STATE in memoria richiederebbe "
                     "un processo che sopravvive: nella v5 ogni episodio e' processo e container nuovi"}
    (ESITI / "CROSS_RUN_STATE.proprieta.json").write_text(
        json.dumps(esito, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(esito, indent=2, ensure_ascii=False))
    return 0 if esito["controllo_positivo_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

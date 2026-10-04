"""Tutti i valori della v5, ciascuno con la sua origine.

Origini: "brief" = BRIEF_v5_per_Claude_Code.md 1.2; "v4" = pilota_costo_v4.py (riga);
"Morgan Dn" = decisione registrata in REQUISITI_AGGIUNTI.md; "proposta" = valore proposto
nel piano della fase 2 (fase2/PIANO_FASE2.md) e approvato con il piano.
"""
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
LAVORO = RADICE / "lavoro_v5"           # .gitignore
SEGRETI = RADICE / "segreti"            # .gitignore (Morgan D3)

# ------------------------------------------------------------- sorgente di riferimento
TOMLI_REPO = "https://github.com/hukkin/tomli.git"                  # v4 riga 47
TOMLI_COMMIT = "5a77b12a7a9f052ce5a20c335d2825658f6aea52"            # v4 riga 48
FIXTURE_VALIDE_ATTESE = 228                                          # v4 riga 50, brief

# ------------------------------------------------------------- ambiente verificato
# REQUISITI_AGGIUNTI.md, "Versione verificata dell'ambiente": il supervisore rifiuta di partire altrimenti.
DOCKER_DESKTOP = "Docker Desktop 4.93.0 (240920)"
DOCKER_ENGINE = "29.8.1"
DOCKER_API = "1.56"
KERNEL_VM = "6.6.87.2-microsoft-standard-WSL2"
CGROUP_VERSIONE, CGROUP_DRIVER = "2", "cgroupfs"

# ------------------------------------------------------------- timeout delle chiamate a Docker (proposta)
TIMEOUT_DOCKER = 60          # s, generico
TIMEOUT_OSSERVATORE = 10     # s, docker exec nell'osservatore
TIMEOUT_COSTRUZIONE = 1200   # s, docker build
TIMEOUT_RM = 60              # s, docker rm -f
ATTESA_RITORNO_CLIENT = 15   # s, dopo la chiusura di stdin (prova di aggancio)

# ------------------------------------------------------------- immagini e container misurati
# Base fissata per digest (fase 1); il pacchetto entra nell'immagine con COPY (Morgan D1).
IMMAGINE_PYTHON = "python@sha256:b1b81d67b8df73bf6067191790c233ef9e598b863fc1ccf447956138ca466d99"
IMMAGINE_OSSERVATORE = "alpine@sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6"
OPZIONI_CONTAINER = [                    # brief, "Opzioni minime" (senza -v: Morgan D1)
    "--network", "none", "--read-only", "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges", "--pids-limit", "64",
    "--memory", "1g", "--memory-swap", "1g", "--cpus", "1", "--user", "65534:65534",
    "--tmpfs", "/tmp:rw,size=64m",
]
# Nomi delle variabili d'ambiente nel container misurato: devono essere ESATTAMENTE questi
# (osservati il 2026-10-04 sull'immagine del pacchetto originale; vengono dall'immagine base Python
# e da Docker). Nessuna viene dall'host. Verificato a ogni esecuzione dai controlli preliminari.
AMBIENTE_AMMESSO = ["GPG_KEY", "HOME", "HOSTNAME", "LANG", "PATH", "PYTHON_SHA256", "PYTHON_VERSION"]
COMANDO_WORKER = ["python", "-I", "/opt/worker/worker.py"]
COMANDO_WORKER_NULLO = ["python", "-I", "/opt/worker/worker_nullo.py"]
COMANDO_WORKER_STRUMENTATO = ["python", "-I", "/opt/worker/worker_strumentato.py"]   # solo originale

# ------------------------------------------------------------- confine JSON (piano, revisione 3)
FRAME_PRONTO = b'{"pronto":1}'
LIMITE_FRAME = 2 * 1024 * 1024        # byte per frame di risposta (proposta, verificata al passo 9)
LIMITE_EPISODIO = 64 * 1024 * 1024    # byte per episodio (proposta)
PROFONDITA_JSON = 8                   # Morgan P3: codifica piatta (era 128)
LIMITE_NODI = 200_000                 # nodi per risposta (proposta P3, verificata al passo 9)
LIMITE_STDERR = 64 * 1024             # byte di stderr conservati, solo per diagnosi

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
OPZIONI_OSSERVATORE = [                  # v5/OSSERVATORE.md
    "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
    "--user", "65534:65534", "--pids-limit", "16", "--memory", "32m",
    "-v", "/sys/fs/cgroup:/cg:ro",
]
FILE_OSSERVABILI = ("memory.peak", "memory.current", "cpu.stat", "memory.events")
COMANDO_WORKER = ["python", "-I", "/opt/worker/worker.py"]
COMANDO_WORKER_NULLO = ["python", "-I", "/opt/worker/worker_nullo.py"]
COMANDO_WORKER_STRUMENTATO = ["python", "-I", "/opt/worker/worker_strumentato.py"]   # solo originale
COMANDO_WORKER_PAVIMENTO = ["python", "-I", "/opt/worker/worker_pavimento.py"]       # solo originale, criterio 4
LIMITE_PATCH_WORKER = 1.11        # Morgan Q2: T(worker) / T(pavimento) sull'originale, come quota 0,90
BLOCCHI_PATCH_WORKER = (30, 60, 120)   # Morgan C1: regola d'arresto dichiarata prima

# ------------------------------------------------------------- carico DEV definitivo (passo 7)
CARICO_DEV = (300, 120)           # documenti × sezioni: ~5 s per episodio dell'originale

# ------------------------------------------------------------- dispersioni congelate (Morgan C4)
# Posizione per sessione = mediana dell'originale; dispersione calibrata UNA volta su più sessioni
# aggregate con `python v5/supervisore.py calibra-dispersione` (fase2/esiti/dispersione.json).
QUANTILE_PRONTO = 0.995           # proposta: quantile alto dei residui aggregati della CPU pre-pronto
VINCOLO_MEMORIA = 1.05            # pilota_costo_v4.py riga 67, applicato alla memoria del parser (Q3)
TOLLERANZA_MEMORIA = None         # byte, da calibrare
ECCEDENZA_PRONTO = None           # microsecondi di CPU pre-pronto oltre la mediana dell'originale, da calibrare

# ------------------------------------------------------------- statistica
# t di Student bilaterale al 95% per gradi di libertà = coppie - 1. Da pilota_costo_v4.py riga 65,
# più i valori per le regole a blocchi (D9, C1); ricalcolati da test_statistica per integrazione numerica.
T_CRITICO_95 = {4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 14: 2.145,
                15: 2.131, 19: 2.093, 29: 2.045, 31: 2.040, 59: 2.001, 63: 1.998, 119: 1.980, 127: 1.979}

# ------------------------------------------------------------- confine JSON (piano, revisione 3)
FRAME_PRONTO = b'{"pronto":1}'
LIMITE_FRAME = 2 * 1024 * 1024        # byte per frame di risposta (proposta, verificata al passo 9)
LIMITE_EPISODIO = 64 * 1024 * 1024    # byte per episodio (proposta)
PROFONDITA_JSON = 8                   # Morgan P3: codifica piatta (era 128)
LIMITE_NODI = 200_000                 # nodi per risposta (proposta P3, verificata al passo 9)
LIMITE_STDERR = 64 * 1024             # byte di stderr conservati, solo per diagnosi

# ------------------------------------------------------------- picco a vuoto (piano: mediana ± 1 MiB, max 8 MiB)
# Calibrato il 2026-10-04 con `python v5/supervisore.py calibra` (fase2/esiti/calibrazione.json):
# 20 sonde dopo il riscaldamento, mediana 5,086 MiB → [mediana − 1 MiB, mediana + 1 MiB].
PICCO_VUOTO_INTERVALLO = (4284416, 6381568)

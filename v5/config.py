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

"""Fase 5: congelamento della v5 (brief, punto 7; CLAUDE.md, passo 5).

Registra le impronte SHA-256 di cio' che il pilota usera': ogni file tracciato di v5/ (sorgenti, worker,
Dockerfile, test, config con i valori congelati, manifest dell'oracolo), i documenti con le regole e gli esiti,
l'impronta del protocollo, i digest delle immagini, il commit di tomli, la versione di Docker Desktop.
Per i file si registrano un'impronta con separazione di dominio, sha256(PREFISSO + percorso + NUL + byte), che
non puo' coincidere con l'impronta di un caso (controllo 4 di controlli_push: il primo congelamento del 2026-10-08
fu bloccato perche' l'impronta del file vuoto v5/test/__init__.py e' quella del documento vuoto del finale), e
l'oggetto git (per la replica).
Non modifica nulla della v5. Si rifiuta (STOP) se:
  - v5/ o i documenti hanno modifiche non committate;
  - HEAD non coincide con origin/master (si congela solo uno stato gia' caricato);
  - il manifest non porta l'impronta del protocollo corrente, o digest/commit diversi dalla configurazione;
  - Docker Desktop non e' la versione verificata;
  - il file di congelamento (USCITA) esiste gia'.

    python fase5/congela.py           -> fase5/CONGELAMENTO_2.json (secondo congelamento, N20)
    python fase5/verifica_congelamento.py   (prima di ogni sessione del pilota)
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from v5 import config, oracolo   # noqa: E402

USCITA = RADICE / "fase5" / "CONGELAMENTO_2.json"   # N20; il primo (CONGELAMENTO.json) resta come storia
DOCKER_VERIFICATO = "Docker Desktop 4.93.0 (240920)"
DOCUMENTI = ["BRIEF_v5_per_Claude_Code.md", "CLAUDE.md", "REQUISITI_AGGIUNTI.md",
             "fase3/registro_attacchi.csv", "fase3/RAPPORTO_FASE3.md", "fase4/RAPPORTO_FASE4.md",
             "fase5/congela.py", "fase5/verifica_congelamento.py",
             "DECISIONE.md", "pilota/orchestratore.py", "fase5/sensibilita.py", "fase5/esiti/SENSIBILITA.json"]


def git(*a):
    return subprocess.run(["git", *a], cwd=RADICE, capture_output=True, text=True, check=True).stdout


def docker_desktop():
    p = subprocess.run(["docker", "version", "--format", "{{.Server.Platform.Name}}"],
                       capture_output=True, text=True, timeout=60)
    return p.stdout.strip() if p.returncode == 0 else None


def sha(percorso):
    return hashlib.sha256((RADICE / percorso).read_bytes()).hexdigest()


PREFISSO = b"benchmark-v5/congelamento\0"


def impronta_file(percorso):
    """sha256(PREFISSO + percorso + NUL + byte): non coincide con sha256(byte) di nessun caso."""
    return hashlib.sha256(PREFISSO + percorso.encode("utf-8") + b"\0" + (RADICE / percorso).read_bytes()).hexdigest()


def stato():
    """Lo stato da congelare o da verificare, senza data e senza commit."""
    blob = {}
    for riga in git("ls-files", "-s", "--", "v5", *DOCUMENTI).splitlines():
        meta, percorso = riga.split("\t", 1)
        blob[percorso] = meta.split()[1]
    mancanti = [d for d in DOCUMENTI if d not in blob]
    if mancanti:
        sys.exit(f"STOP: documenti non tracciati da git: {mancanti}")
    file = {p: {"impronta_dominio": impronta_file(p), "git_blob": b} for p, b in sorted(blob.items())}
    m = json.loads((RADICE / "v5" / "oracle_manifest.json").read_bytes())
    s = {"versione_protocollo": config.VERSIONE_PROTOCOLLO,
         "impronta_protocollo": oracolo.impronta_protocollo(),
         "manifest": {"file": "v5/oracle_manifest.json", "sha256": sha("v5/oracle_manifest.json"),
                      "impronta_oracolo": m["impronta_oracolo"],
                      "impronta_protocollo_nel_manifest": m["impronta_protocollo"]},
         "immagini": {"python": config.IMMAGINE_PYTHON, "osservatore": config.IMMAGINE_OSSERVATORE},
         "tomli_commit": config.TOMLI_COMMIT,
         "docker_desktop": docker_desktop(),
         "file": file}
    s["impronta_complessiva"] = hashlib.sha256(json.dumps(s, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return s, m


def controlli(s, m):
    errori = []
    sporchi = git("status", "--porcelain", "--", "v5", *DOCUMENTI).strip()
    if sporchi:
        errori.append(f"modifiche non committate: {sporchi.splitlines()[:5]}")
    if s["impronta_protocollo"] != m["impronta_protocollo"]:
        errori.append("il manifest non porta l'impronta del protocollo corrente")
    if m.get("immagine_python") != config.IMMAGINE_PYTHON:
        errori.append("digest Python del manifest diverso dalla configurazione")
    if m.get("commit_tomli") != config.TOMLI_COMMIT:
        errori.append("commit di tomli del manifest diverso dalla configurazione")
    if s["docker_desktop"] != DOCKER_VERIFICATO:
        errori.append(f"Docker Desktop {s['docker_desktop']!r}, atteso {DOCKER_VERIFICATO!r}")
    return errori


def main():
    if USCITA.exists():
        sys.exit(f"STOP: {USCITA.name} esiste gia'; non si ricongela sopra un congelamento")
    git("fetch", "origin")
    if git("rev-parse", "HEAD").strip() != git("rev-parse", "origin/master").strip():
        sys.exit("STOP: HEAD diverso da origin/master; si congela solo uno stato gia' caricato")
    s, m = stato()
    errori = controlli(s, m)
    if errori:
        sys.exit("STOP: " + "; ".join(errori))
    out = {"congelato_il": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "commit_congelato": git("rev-parse", "HEAD").strip(), **s}
    USCITA.parent.mkdir(parents=True, exist_ok=True)
    USCITA.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "file"}, indent=1, ensure_ascii=False))
    print("file congelati:", len(out["file"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

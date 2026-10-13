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

    python fase5/congela.py           -> fase5/CONGELAMENTO_6.json (sesto congelamento, N29)
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

USCITA = RADICE / "fase5" / "CONGELAMENTO_6.json"   # N29; CONGELAMENTO.json, _2, _3, _4 e _5 restano come storia
DOCKER_VERIFICATO = "Docker Desktop 4.93.0 (240920)"
DOCUMENTI = ["BRIEF_v5_per_Claude_Code.md", "CLAUDE.md", "REQUISITI_AGGIUNTI.md",
             "fase3/registro_attacchi.csv", "fase3/RAPPORTO_FASE3.md", "fase4/RAPPORTO_FASE4.md",
             "fase5/congela.py", "fase5/verifica_congelamento.py",
             "DECISIONE.md", "pilota/orchestratore.py", "fase5/sensibilita.py", "fase5/esiti/SENSIBILITA.json",
             "pilota/test_orchestratore.py",
             "fase3/cp_attacchi_eseguiti_v5.py",
             "fase3/esiti/PATCH_TIMER.eseguita.json",
             "fase3/esiti/PATCH_MEMORY.eseguita.json",
             "fase3/esiti/READ_TESTS.eseguita.json",
             "fase3/esiti/READ_FINAL.eseguita.json",
             "fase3/esiti/READ_BASELINE.eseguita.json",
             "fase3/esiti/SEGRETO.eseguita.json",
             "fase3/esiti/ARGV.eseguita.json",
             "fase3/esiti/TEMPO_SENZA_VERIFICA.eseguita.json",
             "fase3/esiti/V4_SULLA_V5.eseguiti.json",
             "fase3/cp_final_correttezza.py",
             "fase3/esiti/FINAL_CORRETTEZZA.eseguita.json",
             "fase3/esiti/FINAL_CORRETTEZZA.tre_bracci.txt",
             "fase3/esiti/FINAL_CORRETTEZZA.riga.txt",
             "fase5/sensibilita_soglia.py",
             "fase5/esiti/SENSIBILITA_SOGLIA_d2.json",
             "fase5/esiti/SENSIBILITA_SOGLIA_d2_rimandato1.json",
             "fase5/esiti/SENSIBILITA_SOGLIA_d4.json",
             "fase3/ADDENDUM_V4V5.md",
             "fase3/confronto_v4_v5.py",
             "fase3/test_confronto_v4_v5.py",
             "fase3/esiti/confronto_v4v5/prova/8f39cf8fca36ba6c1749ee13754b30652a9210cc7e720f7101b3043def1cae3f.v4.json",
             "pilota/esiti/sessione_202610100020430118df.json",
             "pilota/esiti/sessione_202610101031011ac1ef.json",
             "pilota/esiti/sessione_20261010114446fe6846.json",
             "pilota/esiti/sessione_2026101012392049d715.json",
             "pilota/esiti/sessione_2026101109491566b9da.json",
             "pilota/esiti/sessione_202610120915194213a0.json",
             "pilota/esiti/sessione_20261013093833d1aed7.json",
             "pilota/esiti/stato.json",
             "pilota/esiti/spesa.json",
             "pilota/log/pilota_20261010_0020.txt",
             "pilota/log/pilota_20261013_0938.txt",
             "pilota/candidati/1d7faf11363fda454cbdd1ac899ba045eae9b8921a0b066040b57f35b291824e.py",
             "pilota/candidati/2da5888b235f09f0950ceca0ad70085e18596a475a3082df507a5b78a0224f6e.py",
             "pilota/candidati/320f65aae3468a9108a479a690cb16e72f16fa2c264ab9e25626d6c583d8834b.py",
             "pilota/candidati/3cb8de99793b5f9d3890d9024e59fa137de5ec96fd520a572a5c669790cf230f.py",
             "pilota/candidati/3d1e45a81857c1c612944fcf97bcdf64b774ca71c7a697fe2b567d2b1d334fb0.py",
             "pilota/candidati/41ee15f42d1f96d144ec56b9c9c4f0fbb6615267885508c1c6f1fc842d95d407.py",
             "pilota/candidati/4243e7ac79c630ea33e897abe1a42691f481d3eff15e3c397c984c9241cf66da.py",
             "pilota/candidati/540a61b1b10ba38536722301e7a62eaa545771c2f338e906cf6100e508ffc4d1.py",
             "pilota/candidati/5669bd39630635d9d9b5018a0c2fb3e17e18fc5099d95c1e06dcebd2af745f18.py",
             "pilota/candidati/602a39af10dc52473a383df24ecd92237848d21dd13f5c47bb4cba6548527ce3.py",
             "pilota/candidati/7e2dc3bd3f06943739fb39c9a43cf7160afc3fd2cd9dbd5093992b4e4de6d68d.py",
             "pilota/candidati/8eb5bd022b822d16c43d4a1b8a6b38ce4f3559fa37b0f0b1830ecbcadc9bd215.py",
             "pilota/candidati/8f39cf8fca36ba6c1749ee13754b30652a9210cc7e720f7101b3043def1cae3f.py",
             "pilota/candidati/9312efbba5e803b0eab634662058201b86d1d4a47b214e309b275e8a17231847.py",
             "pilota/candidati/95483372e8aa3a416947cae95dabbf9289cbc8eaa115eb3aaecf2b0d56976a57.py",
             "pilota/candidati/99c00aa51d989317f515e88ba478e49b690ecbbcff248f3959a3f864c30fe82b.py",
             "pilota/candidati/a2a6960dd99c4aff86a4d258e8c4fbbda1c01fb685f324ca4a1b7d93a11b7788.py",
             "pilota/candidati/a2c443f1fbbf88065149e2f138550aa12c1ed82ffce2a4d46f16984979c2fb86.py",
             "pilota/candidati/a6e19f65f317722691538f8c242575de7dc3dd540bd3942fa4347aa1ebf3cc1c.py",
             "pilota/candidati/a936b8afb28163d7b6db5b79b581eafbe81bf22de5a21c79be4c2572f6afe33e.py",
             "pilota/candidati/aa55ab7b5864ecefa5fa5ced79de5da67ddcd11e87424b01bb5dc2e8e1a020ba.py",
             "pilota/candidati/aca71c96d358406eff85430d7c05ba5760dff04a5b07d44088fc0dcf909f2e34.py",
             "pilota/candidati/baf6320ac80a01913d1473728ca23f472ae67a63c2ca7d806571716c0bbeb4ee.py",
             "pilota/candidati/c77fd2bede42bc4a0073679ea8d532bea657ec1d19b40e8960cb8718d8a0bf7b.py",
             "pilota/candidati/cad4e67b35cbb47f4a7cac866f56ea51ac91248e6070865920ab67ad46c4fd6a.py",
             "pilota/candidati/d793a5435ea950adf964892acb8a55214dc0769575dc83878d5fa29a7ebd08d0.py",
             "pilota/candidati/da74baa94a1eba33879d4eb9073d04f973292d79efc82fc8181149b1563793b9.py",
             "pilota/candidati/de97e410c5b1369afe239d08f384387cdba24ebb9967737d56a02fb4825f98a8.py",
             "pilota/candidati/df76bb28b0a755b18007419405cf0358d9b57a892d5ca07a5b72a4f26f9b9acf.py",
             "pilota/candidati/f0e0043a5a1830c4c0de46c1717f7d24f84fe43607c8cb8f6b1e57b9bdb9c950.py",
             "pilota/candidati/f198ba943242bc5793be685b42046be295f7b2fffa4753c08c6d72adf0ae29f6.py",
             "pilota/candidati/f26b4de4ccda8676e6f74f7a941dc0c0f22b218def2a99e287a7faeb083ac3ce.py",
             "pilota/candidati/f9d9acfaf289f211e415b03035b8e1ff1032dd9f1415a809d1f079b8ce74aa9f.py"]


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

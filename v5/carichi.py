"""Sorgente di riferimento (tomli al commit fissato) e carichi di lavoro.

Il clone vive in lavoro_v5/ (fuori da git). Nessun codice di tomli viene eseguito sull'host:
qui si leggono solo file.
"""
import subprocess
from pathlib import Path

from v5 import config

TOMLI = config.LAVORO / "tomli"


def _git(*args, cwd=None, timeout=600):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)


def prepara_tomli():
    """Clona tomli (se manca) e porta la copia di lavoro al commit fissato. Restituisce il percorso."""
    config.LAVORO.mkdir(parents=True, exist_ok=True)
    if not (TOMLI / ".git").exists():
        p = _git("clone", "--quiet", config.TOMLI_REPO, str(TOMLI))
        if p.returncode != 0:
            raise RuntimeError(f"clone di tomli fallito: {p.stderr.strip()}")
    p = _git("-c", "advice.detachedHead=false", "checkout", "--quiet", config.TOMLI_COMMIT, cwd=TOMLI)
    if p.returncode != 0:
        raise RuntimeError(f"checkout {config.TOMLI_COMMIT} fallito: {p.stderr.strip()}")
    verifica_tomli()
    return TOMLI


def verifica_tomli():
    """Commit esatto, copia di lavoro pulita, numero di fixture valide atteso."""
    head = _git("rev-parse", "HEAD", cwd=TOMLI).stdout.strip()
    if head != config.TOMLI_COMMIT:
        raise RuntimeError(f"tomli a {head}, atteso {config.TOMLI_COMMIT}")
    sporco = _git("status", "--porcelain", cwd=TOMLI).stdout.strip()
    if sporco:
        raise RuntimeError(f"copia di lavoro di tomli modificata:\n{sporco[:500]}")
    n = len(fixture_valide())
    if n != config.FIXTURE_VALIDE_ATTESE:
        raise RuntimeError(f"attese {config.FIXTURE_VALIDE_ATTESE} fixture valide, trovate {n}")


PACCHETTI = config.LAVORO / "pacchetti"


def _pacchetto(parser=None):
    """Cartella con il solo tomli/ (originale, o con _parser.py sostituito). Nome = impronta.

    Ritorna il percorso della cartella da usare come contesto di costruzione dell'immagine.
    Il testo del candidato è solo scritto su disco: l'host non lo esegue mai.
    """
    import shutil
    import tempfile
    from v5 import ambiente
    PACCHETTI.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(dir=PACCHETTI, prefix="tmp_"))
    shutil.copytree(TOMLI / "src" / "tomli", tmp / "tomli", ignore=shutil.ignore_patterns("__pycache__"))
    if parser is not None:
        (tmp / "tomli" / "_parser.py").write_bytes(parser if isinstance(parser, bytes) else parser.encode("utf-8"))
    impronta = ambiente.impronta_file([p for p in tmp.rglob("*") if p.is_file()], tmp)
    finale = PACCHETTI / impronta[:16]
    if finale.exists():
        shutil.rmtree(tmp)
    else:
        tmp.rename(finale)
    return finale


def pacchetto_originale():
    verifica_tomli()
    return _pacchetto()


def pacchetto_candidato(testo_parser):
    verifica_tomli()
    return _pacchetto(testo_parser)


def parser_originale():
    return (TOMLI / "src" / "tomli" / "_parser.py").read_text(encoding="utf-8")


def fixture_valide():
    return sorted((TOMLI / "tests" / "data" / "valid").rglob("*.toml"))


def fixture_non_valide():
    return sorted((TOMLI / "tests" / "data" / "invalid").rglob("*.toml"))

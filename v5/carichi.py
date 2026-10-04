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


def fixture_valide():
    return sorted((TOMLI / "tests" / "data" / "valid").rglob("*.toml"))


def fixture_non_valide():
    return sorted((TOMLI / "tests" / "data" / "invalid").rglob("*.toml"))

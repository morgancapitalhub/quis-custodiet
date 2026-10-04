"""Unico punto d'accesso a Docker. Ogni chiamata ha un timeout (REQUISITI_AGGIUNTI.md, requisito 2).

Nessun altro modulo della v5 lancia `docker` direttamente: lo verifica test_ambiente.
"""
import subprocess

from v5 import config


class DockerTimeout(Exception):
    """Una chiamata a Docker non è tornata entro il suo timeout. Il processo client è stato ucciso."""


class DockerErrore(Exception):
    """Una chiamata a Docker è tornata con codice diverso da zero dove serviva successo."""


def docker(*args, timeout=config.TIMEOUT_DOCKER, input=None, controlla=False):
    """Esegue `docker <args>` e restituisce il CompletedProcess (testo UTF-8).

    Allo scadere del timeout subprocess uccide il client e qui si solleva DockerTimeout;
    un eventuale container avviato resta da rimuovere con rimuovi(): per questo ogni
    `docker run` della v5 riceve un nome esplicito.
    """
    try:
        p = subprocess.run(["docker", *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, input=input)
    except subprocess.TimeoutExpired as e:
        raise DockerTimeout(f"docker {' '.join(args[:3])}…: nessuna risposta entro {timeout} s") from e
    if controlla and p.returncode != 0:
        raise DockerErrore(f"docker {' '.join(args[:3])}… → {p.returncode}: {p.stderr.strip()[:500]}")
    return p


def rimuovi(nome_o_id, timeout=config.TIMEOUT_RM):
    """docker rm -f con timeout. Restituisce True se il container non esiste più."""
    try:
        docker("rm", "-f", nome_o_id, timeout=timeout)
    except DockerTimeout:
        return False
    return not esiste(nome_o_id)


def esiste(nome_o_id):
    p = docker("ps", "-a", "-q", "--no-trunc", "--filter", f"name=^{nome_o_id}$")
    q = docker("ps", "-a", "-q", "--no-trunc", "--filter", f"id={nome_o_id}")
    return bool(p.stdout.strip() or q.stdout.strip())

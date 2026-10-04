"""Unico punto d'accesso a Docker. Ogni chiamata ha un timeout (REQUISITI_AGGIUNTI.md, requisito 2).

Nessun altro modulo della v5 lancia `docker` direttamente: lo verifica test_ambiente.
"""
import hashlib
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


def avvia_interattivo(nome, immagine, comando, etichette=()):
    """`docker run -i` agganciato con le opzioni del brief (config.OPZIONI_CONTAINER).

    Restituisce il Popen con pipe binarie: è l'unico punto della v5 che apre un container
    in streaming. Nessuna variabile d'ambiente passata (-e) e nessun montaggio dell'host.
    Le scadenze del protocollo le applica chi legge (episodio.py); lo smontaggio è rimuovi().
    """
    args = ["docker", "run", "-i", "--rm", "--name", nome, *config.OPZIONI_CONTAINER]
    for e in etichette:
        args += ["--label", e]
    return subprocess.Popen([*args, immagine, *comando], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)


# ------------------------------------------------------------------ immagini

def impronta_file(percorsi, radice):
    """SHA-256 della lista ordinata (percorso relativo, SHA-256 del contenuto)."""
    righe = []
    for p in sorted(percorsi, key=lambda q: q.relative_to(radice).as_posix()):
        righe.append(f"{p.relative_to(radice).as_posix()} {hashlib.sha256(p.read_bytes()).hexdigest()}\n")
    return hashlib.sha256("".join(righe).encode()).hexdigest()


def _esiste_immagine(tag):
    return docker("image", "inspect", tag, "--format", "{{.Id}}").returncode == 0


def immagine_base():
    """Costruisce (se manca) l'immagine base; il tag dipende da Dockerfile, worker e digest."""
    v5 = config.RADICE / "v5"
    file = [v5 / "docker" / "Dockerfile.base", v5 / ".dockerignore", *sorted((v5 / "worker").glob("*.py"))]
    impronta = hashlib.sha256((impronta_file(file, v5) + config.IMMAGINE_PYTHON).encode()).hexdigest()
    tag = f"benchmark-v5/base:{impronta[:16]}"
    if not _esiste_immagine(tag):
        docker("build", "-q", "-f", str(v5 / "docker" / "Dockerfile.base"),
               "--build-arg", f"IMMAGINE_PYTHON={config.IMMAGINE_PYTHON}",
               "--label", f"benchmark-v5.base={impronta}", "-t", tag, str(v5),
               timeout=config.TIMEOUT_COSTRUZIONE, controlla=True)
    return tag


def immagine_pacchetto(cartella):
    """Costruisce (se manca) l'immagine di un pacchetto. `cartella` contiene solo tomli/."""
    base = immagine_base()
    impronta_pacchetto = impronta_file([p for p in cartella.rglob("*") if p.is_file()], cartella)
    impronta = hashlib.sha256((base + impronta_pacchetto).encode()).hexdigest()
    tag = f"benchmark-v5/pacchetto:{impronta[:16]}"
    if not _esiste_immagine(tag):
        docker("build", "-q", "-f", str(config.RADICE / "v5" / "docker" / "Dockerfile.pacchetto"),
               "--build-arg", f"BASE={base}", "--label", f"benchmark-v5.pacchetto={impronta_pacchetto}",
               "-t", tag, str(cartella), timeout=config.TIMEOUT_COSTRUZIONE, controlla=True)
    return tag

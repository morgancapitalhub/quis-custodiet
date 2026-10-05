"""Unico punto d'accesso a Docker. Ogni chiamata ha un timeout (REQUISITI_AGGIUNTI.md, requisito 2).

Nessun altro modulo della v5 lancia `docker` direttamente: lo verifica test_ambiente.
"""
import hashlib
import re
import secrets
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


# ------------------------------------------------------------------ osservatore

ID_CONTAINER = re.compile(r"^[0-9a-f]{64}$")


class Osservatore:
    """Container separato che legge i file cgroup dei container misurati (v5/OSSERVATORE.md).

    Accetta solo `cat /cg/docker/<id>/<file>` con <id> di 64 caratteri esadecimali e <file> in
    config.FILE_OSSERVABILI. Mai montato né raggiungibile dal candidato.
    """

    def __init__(self, sessione, driver_cgroup=None):
        self.nome = f"v5_osservatore_{sessione}"
        # M6: il percorso del cgroup dipende dal driver di Docker (cgroupfs su Docker Desktop,
        # spesso systemd su Linux). Si legge dal motore, non si suppone.
        self.driver = driver_cgroup or docker("info", "--format", "{{.CgroupDriver}}",
                                              controlla=True).stdout.strip()
        docker("run", "-d", "--name", self.nome, "--label", f"benchmark-v5.sessione={sessione}",
               *config.OPZIONI_OSSERVATORE, config.IMMAGINE_OSSERVATORE, "sleep", "86400", controlla=True)

    def leggi(self, id_container, file):
        if not ID_CONTAINER.match(id_container) or file not in config.FILE_OSSERVABILI:
            raise ValueError("lettura non ammessa")
        percorso = config.percorso_cgroup(self.driver, id_container)
        p = docker("exec", self.nome, "cat", f"/cg/{percorso}/{file}", timeout=config.TIMEOUT_OSSERVATORE)
        if p.returncode != 0:
            raise DockerErrore(f"osservatore: {file} di {id_container[:12]}: {p.stderr.strip()[:200]}")
        return p.stdout

    def picco(self, id_container):
        return int(self.leggi(id_container, "memory.peak"))

    def cpu_us(self, id_container):
        for riga in self.leggi(id_container, "cpu.stat").splitlines():
            k, _, v = riga.partition(" ")
            if k == "usage_usec":
                return int(v)
        raise DockerErrore("cpu.stat senza usage_usec")

    def chiudi(self):
        return rimuovi(self.nome)


def id_di(nome):
    p = docker("inspect", "--format", "{{.Id}}", nome)
    cid = p.stdout.strip()
    if p.returncode != 0 or not ID_CONTAINER.match(cid):
        raise DockerErrore(f"id di {nome} non disponibile: {p.stderr.strip()[:200]}")
    return cid


# ------------------------------------------------------------------ controlli preliminari

class ControlloFallito(Exception):
    """Un fatto verificato dell'ambiente non vale più: il supervisore non parte."""


SONDA_SCRITTURA = ("import sys\ntry:\n    open('/sys/fs/cgroup/memory.peak','w').write('0')\n"
                   "    print('SCRITTO')\nexcept OSError as e:\n    print('RIFIUTATO', type(e).__name__)")
SONDA_RETE = ("import socket\nr=[]\ntry:\n    socket.create_connection(('1.1.1.1',53),timeout=3); r.append('tcp')\n"
              "except OSError: pass\ntry:\n    socket.getaddrinfo('example.com',80); r.append('dns')\nexcept OSError: pass\n"
              "print('RETE:' + ','.join(r))")
SONDA_AMBIENTE = "import os,json;print(json.dumps(sorted(os.environ)))"
SONDA_WORKER = ("import hashlib,glob,json;print(json.dumps({p.rsplit('/',1)[1]: hashlib.sha256(open(p,'rb').read())"
                ".hexdigest() for p in sorted(glob.glob('/opt/worker/*.py'))}))")


def _esegui_sonda(sessione, immagine, codice, timeout=config.TIMEOUT_DOCKER):
    nome = f"v5_sonda_{sessione}_{secrets_hex()}"
    try:
        return docker("run", "--name", nome, "--label", f"benchmark-v5.sessione={sessione}",
                      *config.OPZIONI_CONTAINER, immagine, "python", "-I", "-c", codice, timeout=timeout)
    finally:
        rimuovi(nome)


def secrets_hex():
    return secrets.token_hex(4)


def contenitori_attivi():
    """[(nome, etichetta di sessione o '')] dei container in esecuzione."""
    p = docker("ps", "--format", '{{.Names}}\t{{.Label "benchmark-v5.sessione"}}', controlla=True)
    return [tuple((r.split("\t") + [""])[:2]) for r in p.stdout.splitlines() if r.strip()]


def _da_fermare(nome):
    """M9: i container che le misure di tempo fermano e riavviano (per profilo). Vuoto sul server."""
    return any(nome.startswith(p) for p in config.CONTAINER_DA_FERMARE)


def steal_time():
    """Percentuale di CPU "rubata" dall'hypervisor (vCPU condivise), da /proc/stat. Contesto, non
    criterio (fase3/MIGRAZIONE.md). None dove /proc/stat non esiste (Windows)."""
    try:
        with open("/proc/stat") as f:
            campi = f.readline().split()
    except OSError:
        return None
    numeri = [int(x) for x in campi[1:]]
    totale = sum(numeri)
    rubato = numeri[7] if len(numeri) > 7 else 0        # 8° campo: steal
    return {"totale": totale, "rubato": rubato}


def controlli(sessione, osservatore, modalita="costruzione"):
    """Riverifica i fatti dell'ambiente (REQUISITI_AGGIUNTI.md, requisiti 1 e 4). Esito: dict.

    Solleva ControlloFallito al primo fatto che non vale. modalita="costruzione": la chiave
    API non deve esistere nemmeno nel supervisore; "corsa": può esistere solo nel supervisore.
    """
    import json
    import os
    esiti = {}

    def richiedi(nome, osservato, atteso):
        esiti[nome] = osservato
        if osservato != atteso:
            raise ControlloFallito(f"{nome}: osservato {osservato!r}, atteso {atteso!r}")

    # 1. chiave
    if modalita == "costruzione":
        richiedi("chiave_assente_nel_supervisore", "ANTHROPIC_API_KEY" not in os.environ, True)
    # 2. versioni (uguaglianza esatta)
    v = docker("version", "--format", "{{.Server.Platform.Name}}|{{.Server.Version}}|{{.Client.Version}}|"
               "{{.Server.APIVersion}}", controlla=True).stdout.strip().split("|")
    if config.VERIFICA_PLATFORM:                       # M1: solo su Docker Desktop
        richiedi("docker_desktop", v[0], config.DOCKER_DESKTOP)
    else:
        esiti["platform"] = v[0]                       # su Engine si registra, non si vincola
    richiedi("motore", v[1], config.DOCKER_ENGINE)
    richiedi("client", v[2], config.DOCKER_ENGINE)
    richiedi("api", v[3], config.DOCKER_API)
    i = docker("info", "--format", "{{.KernelVersion}}|{{.CgroupVersion}}|{{.CgroupDriver}}",
               controlla=True).stdout.strip().split("|")
    richiedi("kernel", i[0], config.KERNEL_VM)
    richiedi("cgroup", (i[1], i[2]), (config.CGROUP_VERSIONE, config.CGROUP_DRIVER))
    # 3. container estranei (D6): ammessi solo quelli da fermare (per profilo) e quelli di questa sessione
    estranei = [n for n, s in contenitori_attivi() if not _da_fermare(n) and s != sessione]
    richiedi("container_estranei", estranei, [])
    base = immagine_base()
    # 4. ambiente del candidato: nomi esattamente quelli ammessi
    p = _esegui_sonda(sessione, base, SONDA_AMBIENTE)
    richiedi("ambiente_del_candidato", json.loads(p.stdout or "null"), config.AMBIENTE_AMMESSO)
    # 5. memory.peak non scrivibile dal candidato
    p = _esegui_sonda(sessione, base, SONDA_SCRITTURA)
    richiedi("memory_peak_non_scrivibile", p.stdout.split()[:1], ["RIFIUTATO"])
    # 6. rete assente
    p = _esegui_sonda(sessione, base, SONDA_RETE)
    richiedi("rete_assente", p.stdout.strip(), "RETE:")
    # 7. worker nell'immagine = worker del repository
    p = _esegui_sonda(sessione, base, SONDA_WORKER)
    attesi = {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
              for f in sorted((config.RADICE / "v5" / "worker").glob("*.py"))}
    richiedi("worker_nell_immagine", json.loads(p.stdout or "null"), attesi)
    # 8. osservatore: legge picco e CPU di una sonda viva
    nome = f"v5_sonda_{sessione}_{secrets_hex()}"
    try:
        docker("run", "-d", "--name", nome, "--label", f"benchmark-v5.sessione={sessione}", *config.OPZIONI_CONTAINER,
               base, "python", "-I", "-c", "import time; time.sleep(60)", controlla=True)
        cid = id_di(nome)
        richiedi("osservatore_legge_picco", osservatore.picco(cid) > 0, True)
        richiedi("osservatore_legge_cpu", osservatore.cpu_us(cid) >= 0, True)
    finally:
        rimuovi(nome)
    # 9. OOM visibile dall'esterno
    nome = f"v5_sonda_{sessione}_{secrets_hex()}"
    try:
        docker("run", "-d", "--name", nome, "--label", f"benchmark-v5.sessione={sessione}", *config.OPZIONI_CONTAINER,
               base, "python", "-I", "-c", "b = bytearray(1200 * 1048576)", controlla=True)
        docker("wait", nome, timeout=config.TIMEOUT_DOCKER)
        s = docker("inspect", nome, "--format", "{{.State.OOMKilled}} {{.State.ExitCode}}").stdout.split()
        richiedi("oom_visibile", s, ["true", "137"])
    finally:
        rimuovi(nome)
    return esiti


class MisureDiTempo:
    """Contesto delle misure di tempo (RIGA B, D6): ferma sqz_demo_*, verifica che restino solo
    i container della sessione, e in uscita riavvia ciò che ha fermato. Registra tutto in `diario`."""

    def __init__(self, sessione, diario):
        self.sessione, self.diario, self.fermati = sessione, diario, []

    def __enter__(self):
        import datetime
        try:
            attivi = contenitori_attivi()
            estranei = [n for n, s in attivi if not _da_fermare(n) and s != self.sessione]
            if estranei:
                raise ControlloFallito(f"container estranei attivi: {estranei}")
            for nome, _ in attivi:
                if _da_fermare(nome):
                    docker("stop", nome, controlla=True)
                    self.fermati.append(nome)
            self.diario.append({"evento": "fermati", "container": self.fermati,
                                "ora": datetime.datetime.now(datetime.timezone.utc).isoformat()})
            estranei = [n for n, s in contenitori_attivi() if s != self.sessione]
            if estranei:
                raise ControlloFallito(f"dopo la fermata restano container estranei: {estranei}")
        except BaseException:
            self.__exit__(None, None, None)        # riavvia ciò che è già stato fermato
            raise
        return self

    def __exit__(self, *_):
        import datetime
        esiti = {}
        for nome in self.fermati:
            try:
                esiti[nome] = docker("start", nome).returncode == 0
            except DockerTimeout:
                esiti[nome] = False
        self.diario.append({"evento": "riavviati", "esiti": esiti,
                            "ora": datetime.datetime.now(datetime.timezone.utc).isoformat()})
        return False


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

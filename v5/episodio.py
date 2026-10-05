"""Protocollo d'episodio (brief, "Episodio opaco"; REQUISITI_AGGIUNTI.md, decisioni (a) e (c)).

Un episodio = un container nuovo, agganciato con `docker run -i`, che riceve un flusso di casi
tutti distinti e risponde con un frame per caso.

  1. avvio; un thread ricava l'id del container e ne ispeziona la configurazione EFFETTIVA;
  2. il supervisore non scrive nulla finché non arriva il frame "pronto" (timeout PRONTO_S);
  3. al pronto: configurazione effettiva e CPU consumata fino a lì (osservatore); POI cronometro
     (perf_counter_ns dell'host) e invio dei casi;
  4. completamento = ricevuto l'ultimo frame atteso (non l'uscita del processo); stop del cronometro;
  5. a container vivo: picco di memoria e CPU totale dall'osservatore;
  6. chiusura di stdin; attesa del ritorno del client (registra `client_bloccato_dopo`);
  7. `docker rm -f` con timeout; client ucciso se ancora vivo.
Le risposte restano byte grezzi: la decodifica JSON e il confronto con l'oracolo avvengono DOPO,
fuori dalla finestra cronometrata (`valuta_risposte`).
"""
import json
import re
import struct
import threading
import time

from v5 import ambiente, confine, config

PRONTO_S = 20.0                 # timeout reale del pronto (piano: proposta approvata)


class InfrastrutturaFallita(Exception):
    """L'originale non completa, o l'ambiente si comporta in modo inatteso: la sessione si ferma."""


def _frame_caso(op, contenuto):
    return struct.pack(">BI", op, len(contenuto)) + contenuto


def configurazione_attesa(immagine):
    return {
        "Image": immagine, "NetworkMode": "none", "ReadonlyRootfs": True, "CapDrop": ["ALL"],
        "SecurityOpt": ["no-new-privileges"], "PidsLimit": 64, "Memory": 1073741824, "MemorySwap": 1073741824,
        "NanoCpus": 1000000000, "User": "65534:65534", "Tmpfs": {"/tmp": "rw,size=64m"}, "Privileged": False,
        "Mounts": [], "Binds": None, "EnvNomi": config.AMBIENTE_AMMESSO,
    }


def configurazione_effettiva(info):
    h, c = info["HostConfig"], info["Config"]
    return {
        "Image": c["Image"], "NetworkMode": h["NetworkMode"], "ReadonlyRootfs": h["ReadonlyRootfs"],
        "CapDrop": h["CapDrop"], "SecurityOpt": h["SecurityOpt"], "PidsLimit": h["PidsLimit"],
        "Memory": h["Memory"], "MemorySwap": h["MemorySwap"], "NanoCpus": h["NanoCpus"], "User": c["User"],
        "Tmpfs": h["Tmpfs"], "Privileged": h["Privileged"], "Mounts": info["Mounts"], "Binds": h["Binds"],
        # HOME e HOSTNAME li aggiunge Docker all'avvio; tutte le altre vengono dall'immagine.
        # Una variabile passata con -e comparirebbe qui e renderebbe la configurazione difforme.
        "EnvNomi": sorted([v.split("=", 1)[0] for v in (c["Env"] or [])] + ["HOME", "HOSTNAME"]),
    }


class _Lettore(threading.Thread):
    """Legge i frame di risposta con i limiti del confine; non decodifica il JSON."""

    def __init__(self, flusso, attesi, extra=0):
        super().__init__(daemon=True)
        # attesi = risposte ai casi (completamento); extra = frame ammessi DOPO la chiusura di stdin
        # (solo il worker strumentato dell'originale, che a EOF manda il suo totale)
        self.flusso, self.attesi, self.extra = flusso, attesi, extra
        self.frame, self.violazione, self.t_ultimo = [], None, None
        self.pronto, self.completo, self.finito = threading.Event(), threading.Event(), threading.Event()
        self.t_pronto = None
        self.byte = 0

    def run(self):
        try:
            while True:
                testa = self.flusso.read(4)
                if len(testa) < 4:
                    if testa:
                        self.violazione = "frame troncato"
                    break
                n = struct.unpack(">I", testa)[0]
                if n > config.LIMITE_FRAME:
                    self.violazione = f"frame di {n} byte oltre il limite"
                    break
                self.byte += 4 + n
                if self.byte > config.LIMITE_EPISODIO:
                    self.violazione = "episodio oltre il limite di byte"
                    break
                dati = self.flusso.read(n)
                adesso = time.perf_counter_ns()
                if len(dati) < n:
                    self.violazione = "frame troncato"
                    break
                if not self.frame:
                    if dati != config.FRAME_PRONTO:
                        self.violazione = "primo frame diverso dal pronto"
                        break
                    self.t_pronto = adesso
                    self.frame.append(dati)
                    if self.attesi == 0:
                        self.t_ultimo = adesso
                        self.completo.set()
                    self.pronto.set()
                    continue
                if len(self.frame) >= 1 + self.attesi + self.extra:
                    self.violazione = "frame in più"
                    break
                self.frame.append(dati)
                if len(self.frame) == 1 + self.attesi:
                    self.t_ultimo = adesso
                    self.completo.set()
        finally:
            self.finito.set()
            self.pronto.set()          # sblocca chi aspetta, anche in caso di violazione


class _LettoreStderr(threading.Thread):
    def __init__(self, flusso):
        super().__init__(daemon=True)
        self.flusso, self.dati = flusso, bytearray()

    def run(self):
        while True:
            b = self.flusso.read(4096)
            if not b:
                break
            if len(self.dati) < config.LIMITE_STDERR:
                self.dati += b[:config.LIMITE_STDERR - len(self.dati)]


def esegui(sessione, n, immagine, casi, osservatore, ruolo, comando=config.COMANDO_WORKER,
           timeout_completamento=120.0, frame_finale=False):
    """Un episodio. `casi` = lista di (op, byte). Restituisce (registro, frame grezzi delle risposte)."""
    # nomi dei container: solo [a-zA-Z0-9_.-] (un'etichetta con ":" farebbe fallire docker run)
    nome = re.sub(r"[^a-zA-Z0-9_.-]", "_", f"v5_ep_{sessione}_{n}_{ambiente.secrets_hex()}")
    attesi = len(casi)
    r = {"sessione": sessione, "n": n, "ruolo": ruolo, "immagine": immagine, "comando": comando[-1],
         "casi": len(casi), "completato": False, "motivo": None, "violazione": None,
         "client_bloccato_dopo": None, "rm_ok": None, "client_ucciso": False}
    t_avvio = time.perf_counter_ns()
    p = ambiente.avvia_interattivo(nome, immagine, comando, etichette=[f"benchmark-v5.sessione={sessione}"])
    lettore, err = _Lettore(p.stdout, attesi, extra=1 if frame_finale else 0), _LettoreStderr(p.stderr)
    lettore.start(); err.start()
    ispezione = {}

    def ispeziona():
        for _ in range(100):
            q = ambiente.docker("inspect", "--format", "{{json .}}", nome)
            if q.returncode == 0:
                info = json.loads(q.stdout)
                ispezione["id"] = info["Id"]
                ispezione["effettiva"] = configurazione_effettiva(info)
                return
            time.sleep(0.05)
    t_isp = threading.Thread(target=ispeziona, daemon=True)
    t_isp.start()
    try:
        if not lettore.pronto.wait(PRONTO_S) or not lettore.frame:
            r["motivo"] = lettore.violazione and "violazione" or "pronto assente"
            r["violazione"] = lettore.violazione
            return r, []
        r["s_avvio_pronto"] = round((lettore.t_pronto - t_avvio) / 1e9, 4)
        # Prima di inviare: id, configurazione effettiva e CPU consumata fino a qui. Il lavoro che il
        # candidato fa dopo il pronto e prima del primo caso resta così contato nella CPU pre-pronto;
        # quello successivo cade nella finestra cronometrata.
        t_isp.join(10)
        if "id" not in ispezione:
            raise InfrastrutturaFallita(f"id di {nome} non disponibile")
        r["container"] = ispezione["id"]
        attesa = configurazione_attesa(immagine)
        if ispezione["effettiva"] != attesa:
            diverse = {k: ispezione["effettiva"].get(k) for k in attesa if ispezione["effettiva"].get(k) != attesa[k]}
            r["motivo"], r["violazione"] = "violazione", f"configurazione effettiva diversa: {diverse}"
            return r, []
        try:
            r["cpu_pre_pronto_us"] = osservatore.cpu_us(ispezione["id"])
        except ambiente.DockerErrore as e:
            raise InfrastrutturaFallita(f"osservatore: {e}") from e
        # cronometro e invio: nulla è stato scritto prima di questo punto
        errore_scrittura = []

        def scrivi():
            try:
                for op, c in casi:
                    p.stdin.write(_frame_caso(op, c))
                p.stdin.flush()
            except OSError as e:
                errore_scrittura.append(repr(e))
        t0 = time.perf_counter_ns()
        scrittore = threading.Thread(target=scrivi, daemon=True)
        scrittore.start()
        scadenza = time.monotonic() + timeout_completamento
        while not lettore.completo.is_set() and not lettore.finito.is_set() and time.monotonic() < scadenza:
            lettore.completo.wait(0.05)
        if not lettore.completo.is_set():
            lettore.finito.wait(0.5)
            r["motivo"] = "violazione" if lettore.violazione else "incompleto"
            r["violazione"] = lettore.violazione
            r["risposte"] = len(lettore.frame) - 1
            r["errore_scrittura"] = errore_scrittura or None
            return r, []
        r["t_finestra_ns"] = lettore.t_ultimo - t0
        r["risposte"] = len(lettore.frame) - 1
        r["byte_ricevuti"] = lettore.byte
        # misure a container vivo, prima di chiudere stdin
        try:
            r["memory_peak"] = osservatore.picco(ispezione["id"])
            r["cpu_totale_us"] = osservatore.cpu_us(ispezione["id"])
        except ambiente.DockerErrore as e:
            raise InfrastrutturaFallita(f"osservatore: {e}") from e
        r["completato"] = True
        return r, lettore.frame[1:1 + attesi]
    finally:
        try:
            p.stdin.close()
        except OSError:
            pass
        try:
            p.wait(config.ATTESA_RITORNO_CLIENT)
            r["client_bloccato_dopo"] = False
        except Exception:
            r["client_bloccato_dopo"] = True
        if r["completato"]:
            lettore.finito.wait(2)
            if lettore.violazione:                   # p.es. frame in più dopo l'ultimo atteso
                r["completato"], r["motivo"], r["violazione"] = False, "violazione", lettore.violazione
            elif frame_finale:
                if len(lettore.frame) != 2 + attesi:
                    r["completato"], r["motivo"] = False, "frame finale assente"
                else:
                    r["frame_finale"] = lettore.frame[-1].decode("utf-8", "replace")
        r["rm_ok"] = ambiente.rimuovi(nome)
        if p.poll() is None:
            p.kill()
            r["client_ucciso"] = True
        lettore.join(5)
        err.join(5)
        for flusso in (p.stdout, p.stderr):
            try:
                flusso.close()
            except OSError:
                pass
        r["stderr"] = bytes(err.dati[:2000]).decode("utf-8", "replace") or None


def con_ripetizione(registro, sessione, n, immagine, casi, osservatore, ruolo, **kw):
    """Regola degli episodi (REQUISITI_AGGIUNTI.md, decisione (a)).

    Incompleto → si ripete UNA volta; al secondo: candidato = "misura fallita", originale = stop.
    Violazione (deterministica) → nessuna ripetizione: candidato respinto, originale = stop.
    """
    for ripetizione in (0, 1):
        r, frame = esegui(sessione, f"{n}r{ripetizione}" if ripetizione else n, immagine, casi, osservatore,
                          ruolo, **kw)
        r["ripetizione"] = ripetizione
        registro.episodio(r)
        if r["completato"]:
            return r, frame
        if r["motivo"] == "violazione":
            if ruolo == "originale":
                raise InfrastrutturaFallita(f"violazione dell'originale: {r['violazione']}")
            return r, None
    if ruolo == "originale":
        raise InfrastrutturaFallita(f"l'originale non completa due volte: {r['motivo']}")
    r["motivo"] = "misura fallita"
    return r, None


def riscalda(registro, sessione, immagini, osservatore, casi):
    """Un episodio NON misurato per ogni immagine della sessione (piano: riscaldamento)."""
    for k, immagine in enumerate(immagini):
        r, _ = esegui(sessione, f"risc{k}", immagine, casi, osservatore, "riscaldamento")
        r["ripetizione"] = 0
        registro.episodio(r)


def sonde_a_vuoto(registro, sessione, immagine, osservatore, quante):
    """Picchi di memoria del worker nullo, senza casi: interprete + worker, niente tomli."""
    picchi = []
    for k in range(quante):
        r, _ = esegui(sessione, f"vuoto{k}", immagine, [], osservatore, "sonda", comando=config.COMANDO_WORKER_NULLO)
        r["ripetizione"] = 0
        registro.episodio(r)
        if not r["completato"]:
            raise InfrastrutturaFallita(f"sonda a vuoto non completata: {r['motivo']}")
        picchi.append(r["memory_peak"])
    return picchi


def controlla_picco_a_vuoto(registro, sessione, immagini, osservatore, casi_riscaldamento):
    """Riscaldamento + 3 sonde nell'intervallo atteso; altrimenti un secondo riscaldamento; poi stop."""
    lo, hi = config.PICCO_VUOTO_INTERVALLO
    for tentativo in (1, 2):
        riscalda(registro, sessione, immagini, osservatore, casi_riscaldamento)
        picchi = sonde_a_vuoto(registro, sessione, immagini[0], osservatore, 3)
        if all(lo <= p <= hi for p in picchi):
            return {"tentativo": tentativo, "picchi": picchi}
    raise InfrastrutturaFallita(f"picco a vuoto fuori intervallo [{lo}, {hi}] dopo due riscaldamenti: {picchi}")


def valuta_risposte(frame):
    """Dopo la finestra: decodifica e impronta di ogni risposta. Una violazione respinge il candidato."""
    return [confine.esito_frame(f) for f in frame]

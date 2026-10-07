"""Morgan N7: ordine dei passi in episodio.esegui, verificato in modo deterministico (solo host).

    python -m unittest v5.test.test_ordine_episodio

Tutte le chiamate esterne sono finte e registrano un evento in una traccia comune: partenza del cronometro,
letture della CPU dall'osservatore, scritture su stdin del container. Si verifica che:
  1. il cronometro parte PRIMA della lettura della CPU prima del pronto;
  2. nessun caso viene inviato prima di entrambi;
  3. il costo usa la CPU letta DOPO la partenza del cronometro.
Così nessun istante del candidato resta fuori sia dalla CPU prima del pronto sia dalla finestra.
"""
import json
import queue
import struct
import threading
import types
import unittest
from unittest import mock

from v5 import config, episodio, valutazione

ID = "a" * 64
CASI = [(0, b"a = 1"), (0, b"b = 2")]
RISPOSTA = b'{"v":[["m",{}]]}'


def _frame(b):
    return struct.pack(">I", len(b)) + b


class _Uscita:
    """stdout finto: byte messi in coda dal lato stdin; read(n) attende finché ci sono n byte o EOF."""

    def __init__(self):
        self.coda, self.buf, self.chiuso = queue.Queue(), b"", False

    def metti(self, b):
        self.coda.put(b)

    def chiudi(self):
        self.coda.put(None)

    def read(self, n):
        while len(self.buf) < n and not self.chiuso:
            pezzo = self.coda.get(timeout=10)
            if pezzo is None:
                self.chiuso = True
            else:
                self.buf += pezzo
        dati, self.buf = self.buf[:n], self.buf[n:]
        return dati

    def close(self):
        pass


class _Ingresso:
    """stdin finto: ogni frame di caso scritto registra "invio" e produce una risposta su stdout."""

    def __init__(self, traccia, uscita):
        self.traccia, self.uscita = traccia, uscita

    def write(self, b):
        self.traccia.append("invio")
        self.uscita.metti(_frame(RISPOSTA))

    def flush(self):
        pass

    def close(self):
        self.uscita.chiudi()


class _Processo:
    def __init__(self, traccia):
        self.stdout = _Uscita()
        self.stdin = _Ingresso(traccia, self.stdout)
        self.stderr = types.SimpleNamespace(read=lambda n: b"", close=lambda: None)
        self.stdout.metti(_frame(config.FRAME_PRONTO))

    def wait(self, timeout=None):
        return 0

    def poll(self):
        return 0

    def kill(self):
        pass


class _Osservatore:
    def __init__(self, traccia):
        self.traccia, self.letture = traccia, 0

    def cpu_us(self, cid):
        self.letture += 1
        self.traccia.append(f"cpu{self.letture}")
        return 1000 * self.letture            # 1000 = prima lettura (prima del pronto), 2000 = totale

    def picco(self, cid):
        return 10 * 2**20


def _info(immagine):
    a = episodio.configurazione_attesa(immagine)
    env = [f"{n}=x" for n in config.AMBIENTE_AMMESSO if n not in ("HOME", "HOSTNAME")]
    return {"Id": ID, "Mounts": [], "Config": {"Image": immagine, "User": a["User"], "Env": env},
            "HostConfig": {k: a[k] for k in ("NetworkMode", "ReadonlyRootfs", "CapDrop", "SecurityOpt", "PidsLimit",
                                             "Memory", "MemorySwap", "NanoCpus", "Tmpfs", "Privileged", "Binds")}}


class TestOrdineEpisodio(unittest.TestCase):
    def esegui(self):
        traccia = []
        cronometro_vero = episodio._avvia_cronometro

        def cronometro():
            traccia.append("cronometro")
            return cronometro_vero()
        docker = lambda *a, **k: types.SimpleNamespace(returncode=0, stdout=json.dumps(_info("imm")), stderr="")
        with mock.patch.object(episodio.ambiente, "avvia_interattivo", lambda *a, **k: _Processo(traccia)), \
                mock.patch.object(episodio.ambiente, "docker", docker), \
                mock.patch.object(episodio.ambiente, "rimuovi", lambda *a, **k: True), \
                mock.patch.object(episodio, "_avvia_cronometro", cronometro):
            r, frame = episodio.esegui("s", 0, "imm", CASI, _Osservatore(traccia), "candidato", timeout_completamento=10)
        return r, frame, traccia

    def test_episodio_completo(self):
        r, frame, _ = self.esegui()
        self.assertTrue(r["completato"], r)
        self.assertEqual(len(frame), len(CASI))

    def test_cronometro_prima_della_cpu_e_niente_invii_prima(self):
        _, _, traccia = self.esegui()
        self.assertIn("cronometro", traccia)
        self.assertLess(traccia.index("cronometro"), traccia.index("cpu1"))          # 1. cronometro, poi foto
        self.assertLess(traccia.index("cpu1"), traccia.index("invio"))               # 2. nessun invio prima
        self.assertLess(traccia.index("cronometro"), traccia.index("invio"))

    def test_costo_usa_la_cpu_letta_dopo_il_cronometro(self):
        r, _, traccia = self.esegui()
        self.assertLess(traccia.index("cronometro"), traccia.index("cpu1"))
        self.assertEqual(r["cpu_pre_pronto_us"], 1000)                               # 3. la lettura cpu1
        self.assertAlmostEqual(valutazione.costo(r), r["t_finestra_ns"] / 1e9 + 1000 / 1e6)


if __name__ == "__main__":
    unittest.main()

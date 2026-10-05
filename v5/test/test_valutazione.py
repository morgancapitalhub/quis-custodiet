"""valuta(): simmetria fra i ruoli (decisioni dopo la fase 2, asimmetrie (b) e (c)). Episodi finti, niente container.

    python -m unittest v5.test.test_valutazione
"""
import unittest
from unittest import mock

from v5 import config, episodio, valutazione


class _Reg:
    def __init__(self):
        self.eventi = []

    def episodio(self, r):
        self.eventi.append(r)


class _Sessione:
    def __init__(self):
        self.reg, self.sessione, self.oss = _Reg(), "finta", None


def episodio_finto(traccia, cpu=lambda ruolo, k: 300_000):
    def f(reg, sessione, n, imm, casi, oss, ruolo, **kw):
        traccia.append(("episodio", ruolo))
        k = int(str(n).rsplit(ruolo[:4], 1)[-1]) if ruolo[:4] in str(n) else -1
        return ({"t_finestra_ns": 5e9, "memory_peak": 12 * 2**20, "cpu_pre_pronto_us": cpu(ruolo, k),
                 "motivo": None}, [b"x"] * len(casi))
    return f


class TestSimmetria(unittest.TestCase):
    def esegui(self, traccia, cpu=lambda ruolo, k: 300_000):
        with mock.patch.object(valutazione.oracolo, "carica", lambda carico: ([(0, b"a=1"), (0, b"b=2")], {})), \
                mock.patch.object(episodio, "con_ripetizione", episodio_finto(traccia, cpu)), \
                mock.patch.object(valutazione, "_verifica", lambda frame, casi, attesi: traccia.append(("verifica",)) or None):
            return valutazione.valuta(_Sessione(), "orig", "cand", "dev", coppie=6)

    def test_verifiche_dopo_entrambi_gli_episodi(self):
        traccia = []
        self.esegui(traccia)
        corpo = [t[0] for t in traccia[3:]]
        self.assertEqual(corpo, ["episodio", "episodio", "verifica", "verifica"] * 6)
        ruoli = [t[1] for t in traccia[3:] if t[0] == "episodio"]
        self.assertEqual(ruoli, (["originale", "candidato", "candidato", "originale"] * 3)[:12])   # ABBA

    def test_tetto_simmetrico_originale_ripete_la_coppia(self):
        """L'originale che sfora una volta fa ripetere la coppia, come il candidato."""
        traccia, sforato = [], {"fatto": False}

        def cpu(ruolo, k):
            if ruolo == "originale" and k == 1 and not sforato["fatto"]:
                sforato["fatto"] = True
                return 300_000 + config.ECCEDENZA_PRONTO + 1
            return 300_000
        r = self.esegui(traccia, cpu)
        self.assertEqual(r["esito"], "valido")
        self.assertEqual(sum(1 for t in traccia if t[0] == "episodio"), 3 + 2 * 7)     # 6 coppie + 1 ripetuta

    def test_originale_che_sfora_due_volte_ferma_la_sessione(self):
        with self.assertRaises(episodio.InfrastrutturaFallita):
            self.esegui([], lambda ruolo, k: 300_000 + (config.ECCEDENZA_PRONTO + 1 if ruolo == "originale" and k >= 1 else 0))

    def test_candidato_che_sfora_due_volte_respinto(self):
        r = self.esegui([], lambda ruolo, k: 300_000 + (config.ECCEDENZA_PRONTO + 1 if ruolo == "candidato" else 0))
        self.assertEqual(r["esito"], "avvio oltre il tetto")


if __name__ == "__main__":
    unittest.main()

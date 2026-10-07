"""valuta(): simmetria fra i ruoli (asimmetria (b)) e costo del protocollo 5.1 (Morgan N1, N2).
Episodi finti, niente container.

    python -m unittest v5.test.test_valutazione
"""
import unittest
from unittest import mock

from v5 import config, episodio, statistica, valutazione


class _Reg:
    def __init__(self):
        self.eventi = []

    def episodio(self, r):
        self.eventi.append(r)


class _Sessione:
    def __init__(self):
        self.reg, self.sessione, self.oss = _Reg(), "finta", None


def episodio_finto(traccia, cpu=lambda ruolo, k: 300_000, finestra=lambda ruolo, k: 5e9):
    def f(reg, sessione, n, imm, casi, oss, ruolo, **kw):
        traccia.append(("episodio", ruolo))
        k = int(str(n).rsplit(ruolo[:4], 1)[-1]) if ruolo[:4] in str(n) else -1
        return ({"t_finestra_ns": finestra(ruolo, k), "memory_peak": 12 * 2**20, "cpu_pre_pronto_us": cpu(ruolo, k),
                 "motivo": None}, [b"x"] * len(casi))
    return f


class TestValuta(unittest.TestCase):
    def esegui(self, traccia, cpu=lambda ruolo, k: 300_000, finestra=lambda ruolo, k: 5e9, coppie=6):
        with mock.patch.object(valutazione.oracolo, "carica", lambda carico: ([(0, b"a=1"), (0, b"b=2")], {})), \
                mock.patch.object(episodio, "con_ripetizione", episodio_finto(traccia, cpu, finestra)), \
                mock.patch.object(valutazione, "_verifica", lambda frame, casi, attesi: traccia.append(("verifica",)) or None):
            return valutazione.valuta(_Sessione(), "orig", "cand", "dev", coppie=coppie)

    def test_verifiche_dopo_entrambi_gli_episodi(self):
        traccia = []
        self.esegui(traccia)
        corpo = [t[0] for t in traccia[3:]]
        self.assertEqual(corpo, ["episodio", "episodio", "verifica", "verifica"] * 6)
        ruoli = [t[1] for t in traccia[3:] if t[0] == "episodio"]
        self.assertEqual(ruoli, (["originale", "candidato", "candidato", "originale"] * 3)[:12])   # ABBA

    def test_costo_e_finestra_piu_cpu_prima_del_pronto(self):
        r = self.esegui([], cpu=lambda ruolo, k: 250_000 if ruolo == "originale" else 400_000)
        self.assertEqual(r["tempi_originale"], [5.25] * 6)
        self.assertEqual(r["tempi_candidato"], [5.4] * 6)
        self.assertEqual(r["finestre_candidato"], [5.0] * 6)
        self.assertEqual(r["cpu_pre_pronto_candidato_us"], [400_000] * 6)
        self.assertEqual(r["protocollo"], config.VERSIONE_PROTOCOLLO)

    def test_lavoro_prima_del_pronto_si_paga(self):
        """READY_ABUSE per costruzione: 1 s spostato dalla finestra al pre-pronto non cambia il costo."""
        dopo = self.esegui([], finestra=lambda ruolo, k: 5e9 if ruolo == "originale" else 4e9,
                           cpu=lambda ruolo, k: 300_000 if ruolo == "originale" else 1_300_000)
        self.assertEqual(dopo["esito"], "valido")
        self.assertFalse(dopo["piu_veloce"])
        self.assertAlmostEqual(dopo["accelerazione"], 1.0)

    def test_nessun_rifiuto_ne_ripetizione_per_il_pronto(self):
        """Né l'originale né il candidato sono respinti o ripetuti per una CPU prima del pronto alta: costa."""
        for ruolo_alto in ("originale", "candidato"):
            with self.subTest(ruolo=ruolo_alto):
                traccia = []
                r = self.esegui(traccia, cpu=lambda ruolo, k: 300_000 + (5_000_000 if ruolo == ruolo_alto else 0))
                self.assertEqual(r["esito"], "valido")
                self.assertEqual(sum(1 for t in traccia if t[0] == "episodio"), 3 + 2 * 6)
                self.assertTrue(r["piu_lento"] if ruolo_alto == "candidato" else r["piu_veloce"])

    def test_minima_distinguibile_nel_verdetto(self):
        r = self.esegui([], finestra=lambda ruolo, k: 5e9 + (k % 3) * 1e8 if ruolo == "candidato" else 5e9)
        atteso = statistica.confronto(r["tempi_originale"], r["tempi_candidato"])["accelerazione_minima_distinguibile"]
        self.assertAlmostEqual(r["accelerazione_minima_distinguibile"], atteso)
        self.assertGreater(r["accelerazione_minima_distinguibile"], 1.0)

    def test_nessun_tetto_nella_configurazione(self):
        self.assertFalse(hasattr(config, "ECCEDENZA_PRONTO"))
        self.assertEqual(episodio.PRONTO_S, 60.0)


if __name__ == "__main__":
    unittest.main()

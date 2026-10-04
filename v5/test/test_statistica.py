"""Statistica (passo 10), solo sull'host.

    python -m unittest v5.test.test_statistica
"""
import unittest

from v5 import config, statistica


class TestStatistica(unittest.TestCase):
    def test_valori_t(self):
        """Ogni valore di config.T_CRITICO_95 coincide al terzo decimale con l'integrazione numerica."""
        for gdl, atteso in config.T_CRITICO_95.items():
            with self.subTest(gdl=gdl):
                self.assertAlmostEqual(statistica.quantile_t(gdl), atteso, delta=0.0015)

    def test_cancello_come_v4(self):
        """Collaudo della v4 righe 328-329: 1/20 passa, 5/20 blocca."""
        self.assertTrue(statistica.verdetto_nullo(1, 20)[0])
        self.assertFalse(statistica.verdetto_nullo(5, 20)[0])

    def test_confronto(self):
        to = [5.0, 5.1, 4.9, 5.05, 5.0, 4.95, 5.1, 5.0]
        piu_veloce = statistica.confronto(to, [x * 0.8 for x in to])
        self.assertTrue(piu_veloce["piu_veloce"])
        self.assertAlmostEqual(piu_veloce["accelerazione"], 1.25)
        uguale = statistica.confronto(to, [x + d for x, d in zip(to, [0.05, -0.05] * 4)])
        self.assertFalse(uguale["piu_veloce"] or uguale["piu_lento"])

    def test_ic_rapporto(self):
        g, (lo, hi) = statistica.ic_rapporto([1.1, 1.0, 1.05, 1.08, 1.02, 1.07, 1.04, 1.06])
        self.assertTrue(lo < g < hi)
        self.assertAlmostEqual(g, 1.0524, places=3)


if __name__ == "__main__":
    unittest.main()

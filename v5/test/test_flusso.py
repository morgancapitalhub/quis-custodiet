"""Flusso del ciclo col modello (passo 11): tetto a prova di guasto e FINALE sempre.

    python -m unittest v5.test.test_flusso

Come il collaudo della v4 (righe 286-303, 330-341): client finti; la chiamata pagata non deve mai
partire. La valutazione è sostituita da una finta che registra le chiamate: qui si prova il
flusso, non la misura (che il collaudo prova con i container). Nessuna chiave, nessuna rete.
"""
import os
import unittest

from v5 import modello


class _Risposta:
    input_tokens = 10_000


class _ConteggioGuasto:
    class messages:
        @staticmethod
        def count_tokens(**kw): raise RuntimeError("servizio non disponibile")

        @staticmethod
        def stream(**kw): raise AssertionError("chiamata pagata eseguita nonostante il blocco")


class _TettoSforato:
    class messages:
        @staticmethod
        def count_tokens(**kw): return _Risposta()

        @staticmethod
        def stream(**kw): raise AssertionError("chiamata pagata eseguita oltre il tetto")


class _SessioneFinta:
    sessione, reg, oss, casi_riscaldamento = "finta", None, None, []


class TestFlusso(unittest.TestCase):
    def setUp(self):
        self.assertNotIn("ANTHROPIC_API_KEY", os.environ)
        self.valutati = []

        def valuta_finta(s, imm_orig, imm, carico, etichetta):
            self.valutati.append(carico)
            return {"esito": "valido", "accelerazione": 1.0, "piu_veloce": False, "piu_lento": False, "t": 0.0}
        self.valuta = valuta_finta

    def corsa(self, client, spesa):
        import v5.ambiente as amb
        import v5.carichi as car
        vero_imm, vero_pacc = amb.immagine_pacchetto, car.pacchetto_candidato
        amb.immagine_pacchetto = lambda cartella: "immagine_finta"
        car.pacchetto_candidato = lambda codice: "cartella_finta"
        try:
            return modello.una_corsa(client, "claude-opus-5-5", modello.MODELLI["claude-opus-5-5"], _SessioneFinta(),
                                     "orig", 1, [spesa], [], valuta=self.valuta)
        finally:
            amb.immagine_pacchetto, car.pacchetto_candidato = vero_imm, vero_pacc

    def test_conteggio_guasto(self):
        r = self.corsa(_ConteggioGuasto(), 0.0)
        self.assertEqual((r["completa"], r["costo"]), (False, 0))
        self.assertTrue(r["motivo_arresto"].startswith("conteggio"))
        self.assertEqual(self.valutati, list(modello.PARTI_FINALE))           # FINALE eseguito comunque

    def test_tetto_sforato(self):
        r = self.corsa(_TettoSforato(), 19.99)
        self.assertEqual((r["completa"], r["costo"]), (False, 0))
        self.assertTrue(r["motivo_arresto"].startswith("tetto"))
        self.assertEqual(self.valutati, list(modello.PARTI_FINALE))

    def test_valori_come_v4(self):
        self.assertEqual(modello.TETTO_SPESA_USD, 20.00)
        self.assertEqual((modello.CORSE_PER_MODELLO, modello.ITERAZIONI_MAX, modello.MAX_TOKEN_USCITA), (3, 4, 32000))
        self.assertEqual(modello.MODELLI["claude-opus-5-5"], (4.00, 20.00))

    def test_precondizione_blocca_senza_chiamate(self):
        r = modello.corsa(_ConteggioGuasto(), _SessioneFinta(), "orig",
                          cancello=lambda s, imm, n: {"passa": False, "confronti": n})
        self.assertIn("bloccata", r)
        self.assertEqual(r["nullo"]["confronti"], 20)


if __name__ == "__main__":
    unittest.main()

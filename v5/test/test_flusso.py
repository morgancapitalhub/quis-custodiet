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

    def test_bassa_sensibilita_segnalata_senza_scartare(self):
        """N9: una valutazione con minima alta segnala il tratto in bassa sensibilità; la corsa resta."""
        def valuta_alta(s, imm_orig, imm, carico, etichetta):
            self.valutati.append(carico)
            return {"esito": "valido", "accelerazione": 1.0, "piu_veloce": False, "piu_lento": False, "t": 0.0,
                    "accelerazione_minima_distinguibile": 1.10}
        self.valuta = valuta_alta
        import v5.ambiente as amb
        import v5.carichi as car
        vero_imm, vero_pacc = amb.immagine_pacchetto, car.pacchetto_candidato
        amb.immagine_pacchetto = lambda cartella: "immagine_finta"
        car.pacchetto_candidato = lambda codice: "cartella_finta"
        try:
            r = modello.una_corsa(_ConteggioGuasto(), "claude-opus-5-5", modello.MODELLI["claude-opus-5-5"],
                                  _SessioneFinta(), "orig", 1, [0.0], [], valuta=self.valuta,
                                  sensibilita=modello.Sensibilita())
        finally:
            amb.immagine_pacchetto, car.pacchetto_candidato = vero_imm, vero_pacc
        self.assertTrue(r["bassa_sensibilita"])
        self.assertEqual(r["valutazioni_in_bassa_sensibilita"], len(modello.PARTI_FINALE))
        self.assertIn("finale_sintetico", r["finale"])                         # la corsa non è scartata


class _ClienteRegistra:
    """Client finto: registra OGNI chiamata (conteggio dei token e chiamata pagata) e la rifiuta."""

    def __init__(self):
        self.chiamate = []
        cliente = self

        class messages:
            @staticmethod
            def count_tokens(**kw):
                cliente.chiamate.append("count_tokens")
                raise AssertionError("conteggio dei token chiamato nonostante la precondizione fallita")

            @staticmethod
            def stream(**kw):
                cliente.chiamate.append("stream")
                raise AssertionError("chiamata pagata eseguita nonostante la precondizione fallita")
        self.messages = messages


def cancello_finto(passa=True, minime=(1.02,) * 20, eccezione=None):
    def f(s, imm, n):
        if eccezione:
            raise eccezione
        return {"passa": passa, "confronti": n,
                "dettagli": [{"esito": "valido", "accelerazione_minima_distinguibile": m} for m in minime]}
    return f


class TestPrecondizioneSessione(unittest.TestCase):
    """Morgan N9 (D7 + N8): prima di ogni sessione; a prova di guasto; nessuna chiamata pagata se fallisce."""

    def assertNessunaChiamata(self, cancello):
        cliente = _ClienteRegistra()
        r = modello.corsa(cliente, _SessioneFinta(), "orig", cancello=cancello)
        self.assertEqual(cliente.chiamate, [])
        self.assertIn("bloccata", r)
        self.assertEqual((r["spesa_totale_usd"], len(r["rimandate"])),
                         (0, len(modello.MODELLI) * modello.CORSE_PER_MODELLO))
        self.assertFalse(r["sessioni"][0]["passa"])
        return r

    def test_d7_fallita(self):
        r = self.assertNessunaChiamata(cancello_finto(passa=False))
        self.assertTrue(r["sessioni"][0]["motivo"].startswith("D7"))

    def test_n8_fallita(self):
        r = self.assertNessunaChiamata(cancello_finto(minime=(1.06,) * 20))
        self.assertTrue(r["sessioni"][0]["motivo"].startswith("N8"))
        self.assertAlmostEqual(r["sessioni"][0]["minima_mediana"], 1.06)

    def test_eccezione(self):
        r = self.assertNessunaChiamata(cancello_finto(eccezione=RuntimeError("docker assente")))
        self.assertIn("non eseguibile", r["sessioni"][0]["motivo"])

    def test_minime_mancanti_o_incomplete(self):
        self.assertNessunaChiamata(cancello_finto(minime=(None,) * 20))
        self.assertNessunaChiamata(cancello_finto(minime=(1.02,) * 19))

    def test_soglia_inclusa(self):
        self.assertTrue(modello.precondizione(cancello_finto(minime=(1.05,) * 20), None, "orig")["passa"])

    def corse_finte(self, esiti_cancello):
        """corsa() con una_corsa finta (1 h ciascuna, nessuna chiamata) e un orologio finto."""
        ora, eseguite, precondizioni = [0.0], [], []

        def cancello(s, imm, n):
            precondizioni.append(ora[0])
            return cancello_finto(passa=esiti_cancello[len(precondizioni) - 1])(s, imm, n)

        def una_corsa(client, modello_, prezzi, s, imm_orig, n, spesa, righe, valuta=None, sensibilita=None):
            eseguite.append((modello_, n, ora[0]))
            ora[0] += 3600
            return {"costo": 0.0, "completa": True, "motivo_arresto": None, "bassa_sensibilita": False}
        vera = modello.una_corsa
        modello.una_corsa = una_corsa
        try:
            r = modello.corsa(_ClienteRegistra(), _SessioneFinta(), "orig", cancello=cancello, orologio=lambda: ora[0])
        finally:
            modello.una_corsa = vera
        return r, eseguite, precondizioni

    def test_sessione_si_rinnova_dopo_3_ore(self):
        r, eseguite, precondizioni = self.corse_finte([True, True, True])
        self.assertEqual(precondizioni, [0.0, 3 * 3600.0, 6 * 3600.0])          # nessuna corsa nuova dopo 3 ore
        self.assertEqual(len(eseguite), 9)
        self.assertEqual([c["sessione"] for m in r["per_modello"].values() for c in m["corse"]], [1, 1, 1, 2, 2, 2, 3, 3, 3])
        self.assertNotIn("bloccata", r)

    def test_seconda_sessione_fallita_rimanda_il_resto(self):
        r, eseguite, precondizioni = self.corse_finte([True, False])
        self.assertEqual(len(precondizioni), 2)
        self.assertEqual(len(eseguite), 3)                                       # solo la prima sessione
        self.assertEqual(len(r["rimandate"]), 6)
        self.assertNotIn("bloccata", r)                                          # la prima sessione è partita


class TestSensibilita(unittest.TestCase):
    def test_mediana_delle_ultime_cinque(self):
        s = modello.Sensibilita()
        valido = lambda m: {"esito": "valido", "accelerazione_minima_distinguibile": m}
        self.assertIsNone(s.registra({"esito": "risultato diverso su carico nascosto"}))
        self.assertFalse(s.registra(valido(1.02)))
        for _ in range(2):
            s.registra(valido(1.10))
        self.assertTrue(s.registra(valido(1.10)))                                # mediana di 1,02 1,10 1,10 1,10
        for _ in range(5):
            last = s.registra(valido(1.03))
        self.assertFalse(last)                                                   # le vecchie escono dalla finestra
        self.assertEqual(modello.FINESTRA_SENSIBILITA, 5)


if __name__ == "__main__":
    unittest.main()

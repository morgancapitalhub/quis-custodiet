"""Rinforzo di I8 (PRECOMPUTE): la verifica d'ordine di test_ordine_episodio deve FALLIRE se un caso viene
inviato prima del cronometro.

    python -m unittest v5.test.test_ordine_episodio_rinforzo

Si esegue il metodo ORIGINALE TestOrdineEpisodio.test_cronometro_prima_della_cpu_e_niente_invii_prima, con le
sue asserzioni, in due condizioni:
  1. come e': deve passare;
  2. con un processo finto che registra un invio all'avvio del container, prima del cronometro: deve FALLIRE
     (un fallimento d'asserzione, non un errore).
Non riprova l'ordine di episodio.esegui (lo fa test_ordine_episodio): prova che quella verifica non e' vuota,
cioe' distingue l'ordine giusto da quello sbagliato. Solo host, nessun container.
"""
import unittest
from unittest import mock

from v5.test import test_ordine_episodio as base

METODO = "test_cronometro_prima_della_cpu_e_niente_invii_prima"


class _ProcessoCheInviaSubito(base._Processo):
    def __init__(self, traccia):
        super().__init__(traccia)
        traccia.append("invio")            # un caso inviato all'avvio del container, prima del cronometro


def _esito(classe):
    risultato = unittest.TestResult()
    classe(METODO).run(risultato)
    return risultato


class TestRinforzoOrdine(unittest.TestCase):
    def test_ordine_giusto_passa(self):
        r = _esito(base.TestOrdineEpisodio)
        self.assertEqual(r.testsRun, 1)
        self.assertTrue(r.wasSuccessful(), r.failures + r.errors)

    def test_invio_prima_del_cronometro_e_visto(self):
        class OrdineSbagliato(base.TestOrdineEpisodio):
            def esegui(self):
                with mock.patch.object(base, "_Processo", _ProcessoCheInviaSubito):
                    return super().esegui()
        r = _esito(OrdineSbagliato)
        self.assertEqual(r.testsRun, 1)
        self.assertEqual(r.errors, [], "errore invece di un fallimento d'asserzione")
        self.assertEqual(len(r.failures), 1, "la verifica d'ordine non ha visto l'invio prima del cronometro")
        self.assertIn("not less than", r.failures[0][1])


if __name__ == "__main__":
    unittest.main()

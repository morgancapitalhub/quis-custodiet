"""Completezza delle risposte (fase3/RAPPORTO_FASE3.md, sezione 5, strada a; REQUISITI_AGGIUNTI N10).

valutazione._verifica confronta risposte e casi a coppie (zip): con meno risposte che casi non se ne accorgerebbe.
La completezza la garantisce episodio.esegui: un episodio con meno risposte dei casi non e' completato e non
restituisce risposte, quindi _verifica non riceve mai un elenco corto. Qui lo si verifica con episodio.esegui vero
e i finti di test_ordine_episodio (solo host, nessun container).

    python -m unittest v5.test.test_completezza_risposte
"""
import unittest
from unittest import mock

from v5.test import test_ordine_episodio as base


class _IngressoParziale(base._Ingresso):
    """stdin finto che risponde solo ai primi `quante` casi, poi chiude stdout (fine del flusso)."""

    def __init__(self, traccia, uscita, quante):
        super().__init__(traccia, uscita)
        self.quante, self.date, self.chiuso = quante, 0, False

    def write(self, b):
        self.traccia.append("invio")
        if self.date < self.quante:
            self.uscita.metti(base._frame(base.RISPOSTA))
            self.date += 1
        if self.date >= self.quante and not self.chiuso:
            self.chiuso = True
            self.uscita.chiudi()


def _esegui(quante):
    class Processo(base._Processo):
        def __init__(self, traccia):
            super().__init__(traccia)
            self.stdin = _IngressoParziale(traccia, self.stdout, quante)
    with mock.patch.object(base, "_Processo", Processo):
        r, frame, _ = base.TestOrdineEpisodio("test_episodio_completo").esegui()
    return r, frame


class TestCompletezzaRisposte(unittest.TestCase):
    def test_tutte_le_risposte_il_finto_e_fedele(self):
        r, frame = _esegui(len(base.CASI))
        self.assertTrue(r["completato"], r)
        self.assertEqual(len(frame), len(base.CASI))

    def test_una_risposta_su_due_non_completa(self):
        r, frame = _esegui(1)
        self.assertFalse(r["completato"], r)
        self.assertEqual(r["motivo"], "incompleto", r)
        self.assertEqual(r["risposte"], 1)
        self.assertEqual(frame, [])

    def test_nessuna_risposta_non_completa(self):
        r, frame = _esegui(0)
        self.assertFalse(r["completato"], r)
        self.assertEqual(frame, [])


if __name__ == "__main__":
    unittest.main()

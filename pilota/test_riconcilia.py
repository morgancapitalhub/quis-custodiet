"""Riconciliazione di una corsa interrotta (N21), con l'orchestratore e la una_corsa congelata veri e il client finto
di pilota/test_orchestratore.py. Nessuna chiave, rete ne' container. Si verifica:
  1. dopo un'interruzione esterna e la riconciliazione, il rilancio riparte e rifa' la corsa interrotta, con le
     altre corse di N13 (al massimo una per modello), partendo dalla spesa della Console;
  2. una seconda interruzione della stessa corsa: dopo la riconciliazione la corsa non si rifa';
  3. Console sotto la spesa contata, causa nella valutazione, nessun segno in corso: STOP, nessun file cambia.

    python -m unittest pilota.test_riconcilia
"""
import json
import unittest

from pilota import orchestratore as orc
from pilota import riconcilia
from pilota import test_orchestratore as to
from pilota.test_orchestratore import _Messaggi, M
from v5 import modello


class TestRiconcilia(unittest.TestCase):
    lancia, json = to.TestGuastiOrchestratore.lancia, to.TestGuastiOrchestratore.json   # stesso banco finto

    def setUp(self):
        to.TestGuastiOrchestratore.setUp(self)
        self.esiti = self.dir / "esiti"

    def interrompi(self, msg):
        codice, out = self.lancia(msg)
        self.assertEqual(codice, 1, out)
        self.assertIn("riconciliare", out)

    def riconcilia(self, *argomenti):
        return riconcilia.main([*argomenti, "--esiti", str(self.esiti)])

    def file(self):
        return {p.name: p.read_bytes() for p in self.esiti.glob("*.json")}

    def test_prima_interruzione_si_rifa(self):
        msg = _Messaggi(["ok"] * modello.ITERAZIONI_MAX + ["ok", ConnectionResetError("simulato: 10054")])
        self.interrompi(msg)
        contata = self.json("spesa.json")["in_corso"]["spesa_contata_al_guasto_usd"]
        self.assertEqual(self.riconcilia("--console-usd", str(round(contata + 0.05, 2)), "--causa", "esterna",
                                         "--nota", "prova"), 0)
        spesa, stato = self.json("spesa.json"), self.json("stato.json")
        self.assertIsNone(spesa["in_corso"])
        self.assertEqual(spesa["spesa_usd"], round(contata + 0.05, 2))
        self.assertTrue(spesa["voci"][-1]["interrotta"])
        self.assertEqual([(x["modello"], x["corsa"]) for x in stato["interruzioni"]], [(M[1], 1)])
        self.assertNotIn((M[1], 1), [(c["modello"], c["corsa"]) for c in stato["corse_fatte"]])
        prima = msg.chiamate
        codice, out = self.lancia(msg)                       # sessione 2: la corsa interrotta si rifa'
        self.assertEqual(codice, 0, out)
        self.assertGreater(msg.chiamate, prima)
        reg = self.json("sessione_test2.json")
        self.assertEqual([tuple(c) for c in reg["corse_previste"]], [(M[1], 1), (M[2], 1), (M[0], 2)])
        self.assertEqual(reg["spesa_prima_usd"], round(contata + 0.05, 2))

    def test_seconda_interruzione_non_si_rifa(self):
        passi = (["ok"] * modello.ITERAZIONI_MAX + ["ok", ConnectionResetError("1")]
                 + ["ok", ConnectionResetError("2")])
        msg = _Messaggi(passi)
        self.interrompi(msg)
        c1 = self.json("spesa.json")["in_corso"]["spesa_contata_al_guasto_usd"]
        self.assertEqual(self.riconcilia("--console-usd", str(c1), "--causa", "esterna", "--nota", "1"), 0)
        self.interrompi(msg)                                 # sessione 2: la stessa corsa si interrompe di nuovo
        ic = self.json("spesa.json")["in_corso"]
        self.assertEqual((ic["modello"], ic["corsa"]), (M[1], 1))
        self.assertEqual(self.riconcilia("--console-usd", str(ic["spesa_contata_al_guasto_usd"]),
                                         "--causa", "esterna", "--nota", "2"), 0)
        stato = self.json("stato.json")
        fatta = [c for c in stato["corse_fatte"] if (c["modello"], c["corsa"]) == (M[1], 1)]
        self.assertEqual(len(fatta), 1)
        self.assertFalse(fatta[0]["completa"])
        self.assertNotIn((M[1], 1), orc.prossima_sessione(stato))

    def test_stop_senza_scrivere(self):
        msg = _Messaggi(["ok"] * modello.ITERAZIONI_MAX + ["ok", ConnectionResetError("simulato")])
        self.interrompi(msg)
        prima = self.file()
        contata = self.json("spesa.json")["in_corso"]["spesa_contata_al_guasto_usd"]
        for argomenti in (["--console-usd", str(round(contata - 0.5, 2)), "--causa", "esterna", "--nota", "x"],
                          ["--console-usd", str(contata), "--causa", "valutazione", "--nota", "x"],
                          ["--console-usd", "25", "--causa", "esterna", "--nota", "x"]):
            with self.assertRaises(SystemExit) as e:
                self.riconcilia(*argomenti)
            self.assertIn("STOP", str(e.exception))
            self.assertEqual(self.file(), prima)
        self.assertEqual(self.riconcilia("--console-usd", str(contata), "--causa", "esterna", "--nota", "x"), 0)
        with self.assertRaises(SystemExit) as e:             # gia' riconciliata
            self.riconcilia("--console-usd", str(contata), "--causa", "esterna", "--nota", "x")
        self.assertIn("nessuna corsa in corso", str(e.exception))


if __name__ == "__main__":
    unittest.main()

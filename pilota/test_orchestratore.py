"""Guasti dell'orchestratore del pilota (N21), con la una_corsa CONGELATA vera e un client finto.

Nessuna chiave, nessuna rete, nessun container: il modulo `anthropic` e' sostituito da un finto in sys.modules,
ANTHROPIC_API_KEY ha un valore finto solo dentro il test, la valutazione (valuta_testo, Sessione, immagini) e'
finta, gli esiti vanno in una cartella temporanea (mai in pilota/esiti/). Si verifica:
  1. errore dell'API a meta' sessione: file di sessione, stato e spesa contata scritti; il rilancio si ferma;
  2. Ctrl+C a meta' sessione: lo stesso;
  3. limite di 3 ore: esito "scaduta" uguale nel file di sessione e nello stato;
  4. tetto di spesa: esito "fermata", corse restanti riportate, il rilancio si ferma;
  5. guasto fra la scrittura dello stato e la chiusura della spesa: il rilancio si ferma, nessuna corsa rifatta.

    python -m unittest pilota.test_orchestratore
"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from pilota import orchestratore as orc
from v5 import modello

M = orc.MODELLI                       # ordine della sessione 1: M[0], M[1], M[2]


class _Flusso:
    def __init__(self, risposta):
        self.risposta = risposta

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.risposta


class _Messaggi:
    """passi: per ogni chiamata a stream, "ok" o un'eccezione da sollevare."""

    def __init__(self, passi, token_ingresso=1000):
        self.passi, self.token_ingresso, self.chiamate = list(passi), token_ingresso, 0

    def count_tokens(self, **kw):
        return types.SimpleNamespace(input_tokens=self.token_ingresso)

    def stream(self, **kw):
        self.chiamate += 1
        passo = self.passi.pop(0) if self.passi else "ok"
        if isinstance(passo, BaseException):
            raise passo
        testo = types.SimpleNamespace(type="text", text="nessun codice in questa risposta")
        return _Flusso(types.SimpleNamespace(content=[testo],
                                             usage=types.SimpleNamespace(input_tokens=1000, output_tokens=2000)))


class _Client:
    def __init__(self, messaggi):
        self.messages = messaggi
        self.models = types.SimpleNamespace(retrieve=lambda m: types.SimpleNamespace(id=m))


class _Sessione:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return "sessione-finta"

    def __exit__(self, *a):
        return False


def _valuta_finta(s, imm_orig, codice, carico, etichetta, valuta=None):
    return {"esito": "valido", "accelerazione": 1.0, "piu_veloce": False, "piu_lento": False, "t": 0.0,
            "accelerazione_minima_distinguibile": 1.02}


class TestGuastiOrchestratore(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="orc_test_"))
        esiti = self.dir / "esiti"
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.n_sessione = 0

        def nuova_sessione():
            self.n_sessione += 1
            return f"test{self.n_sessione}"
        finti = [
            mock.patch.object(orc, "ESITI", esiti), mock.patch.object(orc, "CANDIDATI", self.dir / "candidati"),
            mock.patch.object(orc, "STATO", esiti / "stato.json"), mock.patch.object(orc, "SPESA", esiti / "spesa.json"),
            mock.patch.object(orc.verifica_congelamento, "main", lambda: 0),
            mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "finta-solo-per-il-test"}),
            mock.patch.object(orc.supervisore, "nuova_sessione", nuova_sessione),
            mock.patch.object(orc.ambiente, "immagine_pacchetto", lambda *a, **k: "immagine-finta"),
            mock.patch.object(orc.carichi, "pacchetto_originale", lambda *a, **k: "pacchetto-finto"),
            mock.patch.object(orc.carichi, "pacchetto_candidato", lambda *a, **k: "pacchetto-finto"),
            mock.patch.object(orc.carichi, "parser_originale", lambda: "# parser originale finto\n"),
            mock.patch.object(orc.carichi, "carico_dev", lambda *a, **k: list(range(30))),
            mock.patch.object(orc.valutazione, "Sessione", _Sessione),
            mock.patch.object(modello, "valuta_testo", _valuta_finta),
            mock.patch.object(modello, "precondizione",
                              lambda *a: {"passa": True, "motivo": None, "minima_mediana": 1.01}),
        ]
        for f in finti:
            f.start()
            self.addCleanup(f.stop)

    def lancia(self, messaggi):
        anthropic_finto = types.ModuleType("anthropic")
        anthropic_finto.Anthropic = lambda: _Client(messaggi)
        out = io.StringIO()
        with mock.patch.dict(sys.modules, {"anthropic": anthropic_finto}), contextlib.redirect_stdout(out):
            try:
                codice = orc.main(["orchestratore.py", "prossima"])
            except KeyboardInterrupt:
                self.fail("Ctrl+C uscito dall'orchestratore senza salvare sessione e stato")
        return codice, out.getvalue()

    def json(self, nome):
        return json.loads((self.dir / "esiti" / nome).read_text(encoding="utf-8"))

    def _interruzione(self, eccezione):
        msg = _Messaggi(["ok"] * modello.ITERAZIONI_MAX + ["ok", eccezione])
        codice, out = self.lancia(msg)
        self.assertEqual(codice, 1, out)
        self.assertIn("interrotta", out)
        reg, stato, spesa = self.json("sessione_test1.json"), self.json("stato.json"), self.json("spesa.json")
        self.assertTrue(reg["esito"].startswith("interrotta"), reg["esito"])
        self.assertEqual(len(reg["righe"]), modello.ITERAZIONI_MAX + 1)          # anche la corsa interrotta
        self.assertEqual([(c["modello"], c["corsa"]) for c in stato["corse_fatte"]], [(M[0], 1)])
        self.assertEqual(stato["sessioni"][-1]["esito"], "interrotta")
        self.assertEqual((spesa["in_corso"]["modello"], spesa["in_corso"]["corsa"]), (M[1], 1))
        self.assertGreater(spesa["in_corso"]["spesa_contata_al_guasto_usd"], spesa["in_corso"]["spesa_prima_usd"])
        self.assertAlmostEqual(spesa["spesa_usd"], sum(v["costo_usd"] for v in spesa["voci"]), places=5)
        chiamate = msg.chiamate
        codice, out = self.lancia(msg)                                             # rilancio
        self.assertEqual(codice, 1)
        self.assertIn("riconciliare", out)
        self.assertEqual(msg.chiamate, chiamate, "il rilancio non deve chiamare il modello")

    def test_errore_api_a_meta_sessione(self):
        self._interruzione(ConnectionError("simulato: API sovraccarica"))

    def test_ctrl_c_a_meta_sessione(self):
        self._interruzione(KeyboardInterrupt())

    def test_limite_di_3_ore_esito_coerente(self):
        vera = modello.una_corsa

        def corsa_poi_scade(*a, **k):
            r = vera(*a, **k)
            modello.DURATA_MAX_SESSIONE_S = 0                       # dopo la prima corsa il limite e' superato
            return r
        with mock.patch.object(modello, "una_corsa", corsa_poi_scade), \
                mock.patch.object(modello, "DURATA_MAX_SESSIONE_S", modello.DURATA_MAX_SESSIONE_S):
            codice, out = self.lancia(_Messaggi([]))
        self.assertEqual(codice, 0, out)
        reg, stato = self.json("sessione_test1.json"), self.json("stato.json")
        self.assertEqual(len(reg["corse"]), 1)
        self.assertEqual(len(reg["non_avviate"]), len(M) - 1)
        self.assertEqual(reg["esito"], "scaduta (limite di 3 ore)")
        self.assertEqual(stato["sessioni"][-1]["esito"], reg["esito"])

    def test_tetto_esito_fermata_e_rilancio_fermo(self):
        msg = _Messaggi([], token_ingresso=10 ** 9)                  # caso peggiore oltre il tetto: nessuna chiamata
        codice, out = self.lancia(msg)
        self.assertEqual(codice, 1, out)
        self.assertEqual(msg.chiamate, 0)
        reg, stato = self.json("sessione_test1.json"), self.json("stato.json")
        self.assertTrue(reg["esito"].startswith("fermata: tetto"), reg["esito"])
        self.assertEqual(stato["sessioni"][-1]["esito"], reg["esito"])
        self.assertEqual([(c["modello"], c["corsa"]) for c in reg["non_avviate"]], [(m, 1) for m in M[1:]])
        codice, out = self.lancia(msg)
        self.assertEqual(codice, 1)
        self.assertIn("pilota fermato", out)

    def test_guasto_fra_stato_e_spesa_resta_a_prova_di_guasto(self):
        vera_scrivi, chiusure = orc.scrivi, [0]

        def scrivi_che_muore(percorso, dati):
            # dopo la prima corsa completata riesce la PRIMA scrittura che la registra (stato o spesa, secondo
            # l'ordine dell'orchestratore) e il processo muore alla seconda
            if percorso.name in ("stato.json", "spesa.json") and (dati.get("corse_fatte") or dati.get("voci")):
                chiusure[0] += 1
                if chiusure[0] == 2:
                    raise OSError("simulato: processo morto fra le due scritture")
            return vera_scrivi(percorso, dati)
        msg = _Messaggi([])
        with mock.patch.object(orc, "scrivi", scrivi_che_muore):
            with self.assertRaises(OSError):
                self.lancia(msg)
        chiamate = msg.chiamate
        self.assertGreater(chiamate, 0)
        codice, out = self.lancia(msg)
        self.assertEqual(codice, 1, out)
        self.assertIn("riconciliare", out)
        self.assertEqual(msg.chiamate, chiamate, "una corsa gia' pagata non deve essere rifatta senza riconciliazione")


if __name__ == "__main__":
    unittest.main()

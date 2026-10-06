"""Fase 4 senza Docker: statistica dei nulli (criterio 3, G1, G2), regola a blocchi (G3), avanzamento
ripartibile e orchestrazione dei pezzi con Sessione e valuta finte.

    python -m unittest v5.test.test_fase4
"""
import json
import math
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fase4 import analisi, fase4
from v5 import config, episodio, statistica


def nullo(acc=1.0, veloce=False, lento=False, es=0.02, esito="valido"):
    if esito != "valido":
        return {"esito": esito}
    tc = [5.0] * statistica.COPPIE
    return {"esito": "valido", "accelerazione": acc, "piu_veloce": veloce, "piu_lento": lento, "es": es,
            "tempi_candidato": tc, "tempi_originale": [x * acc for x in tc]}


class TestCriterio3(unittest.TestCase):
    def test_due_allarmi_su_40_passa(self):
        r = analisi.criterio3([nullo(veloce=True), nullo(lento=True)] + [nullo()] * 38)
        self.assertEqual(r["falsi_allarmi"], 2)
        self.assertTrue(r["passa"])

    def test_troppi_allarmi_non_passa(self):
        self.assertFalse(analisi.criterio3([nullo(veloce=True)] * 10 + [nullo()] * 30)["passa"])

    def test_un_rifiuto_dell_originale_non_passa(self):
        r = analisi.criterio3([nullo(esito="memoria oltre il vincolo")] + [nullo()] * 39)
        self.assertEqual(r["rifiuti_dell_originale"], 1)
        self.assertFalse(r["passa"])

    def test_meno_di_40_non_passa(self):
        self.assertFalse(analisi.criterio3([nullo()] * 39)["passa"])


class TestSimmetria(unittest.TestCase):
    def test_t_39(self):
        self.assertAlmostEqual(analisi.t_critico(39), 2.0227, delta=0.0015)

    def test_simmetrici_contengono_zero(self):
        rnd = random.Random(1)
        accs = [math.exp(rnd.gauss(0, 0.03)) for _ in range(20)]
        accs += [1 / a for a in accs]                                   # log esattamente simmetrici
        self.assertTrue(analisi.simmetria([nullo(a) for a in accs])["passa"])

    def test_spostati_non_contengono_zero(self):
        rnd = random.Random(2)
        self.assertFalse(analisi.simmetria([nullo(math.exp(rnd.gauss(0.05, 0.03))) for _ in range(40)])["passa"])

    def test_rifiuti_esclusi(self):
        self.assertEqual(analisi.simmetria([nullo(1.01), nullo(0.99), nullo(esito="avvio oltre il tetto")])["n"], 2)


class TestRisoluzione(unittest.TestCase):
    def test_regola_della_fase2(self):
        atteso = 1 + config.T_CRITICO_95[7] * 0.02 / 5.0
        self.assertAlmostEqual(analisi.accelerazione_minima(nullo(es=0.02)), atteso)
        r = analisi.risoluzione([nullo(es=0.01), nullo(es=0.02), nullo(es=0.05)])
        self.assertAlmostEqual(r["soglia_mediana"], atteso)
        self.assertAlmostEqual(r["massimo"], 1 + config.T_CRITICO_95[7] * 0.05 / 5.0)


class TestBlocchi(unittest.TestCase):
    def test_fuori_dai_blocchi_nessun_controllo(self):
        self.assertEqual(analisi.controllo_blocco([1.05] * 29), (None, False))

    def test_ferma_a_30_se_sotto_soglia(self):
        rnd = random.Random(3)
        c, fermati = analisi.controllo_blocco([1.05 * math.exp(rnd.gauss(0, 0.01)) for _ in range(30)])
        self.assertEqual(c["coppie"], 30)
        self.assertLessEqual(c["IC95"][1], config.LIMITE_PATCH_WORKER)
        self.assertTrue(fermati)

    def test_continua_se_sopra_e_ferma_a_120(self):
        rnd = random.Random(4)
        r = [1.17 * math.exp(rnd.gauss(0, 0.05)) for _ in range(120)]
        self.assertFalse(analisi.controllo_blocco(r[:30])[1])
        self.assertFalse(analisi.controllo_blocco(r[:60])[1])
        c, fermati = analisi.controllo_blocco(r)
        self.assertTrue(fermati)
        self.assertGreater(c["IC95"][1], config.LIMITE_PATCH_WORKER)

    def test_coincide_con_patch_worker_della_fase2(self):
        """Stessa formula di supervisore.patch_worker (gdl in tabella) e di statistica.ic_rapporto."""
        rnd = random.Random(5)
        r = [1.1 * math.exp(rnd.gauss(0, 0.05)) for _ in range(30)]
        g, (lo, hi) = statistica.ic_rapporto(r)
        c, _ = analisi.controllo_blocco(r)
        self.assertEqual(c["IC95"], [round(lo, 4), round(hi, 4)])


class TestAvanzamento(unittest.TestCase):
    def test_riprende_e_conserva(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.json"
            av = analisi.Avanzamento(p, {"x": 1})
            av.aggiungi("voci", {"k": 0})
            av2 = analisi.Avanzamento(p, {"x": 1})
            self.assertEqual(av2.voci, [{"k": 0}])
            self.assertFalse(p.with_suffix(".json.tmp").exists())

    def test_intestazione_diversa_rifiutata(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.json"
            analisi.Avanzamento(p, {"x": 1}).salva()
            with self.assertRaises(ValueError):
                analisi.Avanzamento(p, {"x": 2})


class SessioneFinta:
    def __init__(self, sessione, *_a, **_k):
        self.sessione, self.reg, self.oss = sessione, mock.Mock(), mock.Mock()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class TestOrchestrazioneNulli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.av = Path(self.dir.name) / "nulli.json"
        self.chiamate = []
        patch = [mock.patch.object(fase4, "AV_NULLI", self.av),
                 mock.patch.object(fase4, "preliminari", lambda: None),
                 mock.patch.object(fase4, "_riscaldamento", lambda: []),
                 mock.patch.object(fase4.ambiente, "immagine_pacchetto", lambda _c: "imm"),
                 mock.patch.object(fase4.carichi, "pacchetto_originale", lambda: "pac"),
                 mock.patch.object(fase4.valutazione, "Sessione", SessioneFinta),
                 mock.patch.object(fase4.valutazione, "valuta", self.valuta)]
        for p in patch:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.dir.cleanup)

    def valuta(self, s, imm_o, imm_c, carico, etichetta):
        self.chiamate.append((imm_o, imm_c, carico, etichetta))
        return {**nullo(), "t": 0.1, "m": 0.0}

    def test_pezzi_ripartibili_fino_a_40(self):
        self.assertEqual(fase4.nulli(per_pezzo=15, minuti=55), fase4.ESCI_RESTA)
        self.assertEqual(len(json.loads(self.av.read_text())["voci"]), 15)
        self.assertEqual(fase4.nulli(per_pezzo=15, minuti=55), fase4.ESCI_RESTA)
        self.assertEqual(fase4.nulli(per_pezzo=15, minuti=55), fase4.ESCI_CONCLUSO)
        d = json.loads(self.av.read_text())
        self.assertEqual([v["k"] for v in d["voci"]], list(range(40)))     # nessuna voce rifatta o persa
        self.assertEqual([p["nulli"] for p in d["pezzi"]], [15, 15, 10])
        self.assertEqual(len(self.chiamate), 40)
        self.assertTrue(all(c[0] == c[1] == "imm" and c[2] == "dev" for c in self.chiamate))   # originale contro sé
        self.assertEqual(fase4.nulli(per_pezzo=15, minuti=55), fase4.ESCI_CONCLUSO)          # nulla da rifare
        self.assertEqual(len(self.chiamate), 40)

    def test_tempo_esaurito_nessun_nullo(self):
        self.assertEqual(fase4.nulli(per_pezzo=20, minuti=1), fase4.ESCI_RESTA)   # 125 s stimati > 60 s
        self.assertEqual(self.chiamate, [])

    def test_infrastruttura_ferma_e_non_conta(self):
        def valuta(*a, **k):
            if len(self.chiamate) == 2:
                raise episodio.InfrastrutturaFallita("l'originale non completa due volte")
            return self.valuta(*a, **k)
        with mock.patch.object(fase4.valutazione, "valuta", valuta):
            self.assertEqual(fase4.nulli(per_pezzo=20, minuti=55), fase4.ESCI_INFRASTRUTTURA)
        d = json.loads(self.av.read_text())
        self.assertEqual(len(d["voci"]), 2)
        self.assertEqual(d["eventi"][0]["nullo"], 2)


class TestOrchestrazioneG3(unittest.TestCase):
    def test_coppie_ripartibili_e_arresto_a_blocchi(self):
        with tempfile.TemporaryDirectory() as d:
            av = Path(d) / "pw.json"
            rnd = random.Random(6)

            def con_ripetizione(reg, sessione, n, imm, casi, oss, ruolo, comando, timeout_completamento):
                t = 1.0 if comando == config.COMANDO_WORKER_PAVIMENTO else 1.17 * math.exp(rnd.gauss(0, 0.05))
                return {"t_finestra_ns": int(t * 1e9)}, []
            patch = [mock.patch.object(fase4, "AV_PW_FF", av), mock.patch.object(fase4, "preliminari", lambda: None),
                     mock.patch.object(fase4, "_riscaldamento", lambda: []),
                     mock.patch.object(fase4.ambiente, "immagine_pacchetto", lambda _c: "imm"),
                     mock.patch.object(fase4.carichi, "pacchetto_originale", lambda: "pac"),
                     mock.patch.object(fase4.oracolo, "carica", lambda _n: ([(0, b"a")], {})),
                     mock.patch.object(fase4.valutazione, "Sessione", SessioneFinta),
                     mock.patch.object(fase4.episodio, "con_ripetizione", con_ripetizione),
                     mock.patch.object(fase4, "STIMA_COPPIA_FF_S", 0)]
            for p in patch:
                p.start()
            try:
                # pezzo interrotto per tempo dopo poche coppie: simulato con minuti minimi crescenti
                with mock.patch.object(fase4, "_resta_tempo", side_effect=[True] * 45 + [False]):
                    self.assertEqual(fase4.patch_worker_ff(55), fase4.ESCI_RESTA)
                self.assertEqual(len(json.loads(av.read_text())["voci"]), 45)
                self.assertEqual(fase4.patch_worker_ff(55), fase4.ESCI_CONCLUSO)
                dati = json.loads(av.read_text())
                self.assertEqual([c["coppie"] for c in dati["controlli"]], [30, 60, 120])
                self.assertEqual(len(dati["voci"]), 120)
                self.assertEqual(dati["limite_dichiarato"], dati["controlli"][-1]["IC95"][1])
                self.assertEqual(fase4.patch_worker_ff(55), fase4.ESCI_CONCLUSO)              # nulla da rifare
                self.assertEqual(len(json.loads(av.read_text())["voci"]), 120)
            finally:
                for p in patch:
                    p.stop()


if __name__ == "__main__":
    unittest.main()

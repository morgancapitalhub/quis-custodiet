# fase3/test_confronto_v4_v5.py
"""Test del confronto v4/v5 senza Docker, chiave ne' rete: abbinamento per posizione sulla struttura reale dei
file di sessione del pilota, classificazione dell'addendum, aggregazione con esiti v4 finti.

    python -m unittest fase3.test_confronto_v4_v5
"""
import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fase3 import confronto_v4_v5 as cf


def sha(t):
    return hashlib.sha256(t.encode()).hexdigest()


def corsa(sessione, modello, k, iterazioni, ordine0=0, su_originale=False):
    """iterazioni: lista di (testo o None se nessun blocco, esito, accelerazione, minima). Restituisce le parti di
    un file di sessione come le scrive l'orchestratore: candidati in ordine (iterazioni con codice, poi 2 del
    finale con il prodotto), righe, corsa."""
    cand, righe, n = [], [], ordine0
    valide = []
    for it, (testo, esito, acc, minima) in enumerate(iterazioni, 1):
        righe.append({"modello": modello, "corsa": k, "iterazione": it, "esito": esito,
                      "accelerazione_dev": acc, "minima_distinguibile_dev": minima, "picco_dev": 12_700_000})
        if testo is None:
            continue
        cand.append({"modello": modello, "corsa": k, "ordine": n, "sha256": sha(testo)}); n += 1
        if esito == "valido":
            valide.append((acc, testo))
    prodotto = "ORIGINALE" if su_originale else max(valide, key=lambda x: x[0])[1]
    for _ in range(2):
        cand.append({"modello": modello, "corsa": k, "ordine": n, "sha256": sha(prodotto)}); n += 1
    return cand, righe, {"modello": modello, "corsa": k, "finale": {"su_originale": su_originale}}, n


def sessione(nome, *corse):
    d = {"sessione": nome, "candidati": [], "righe": [], "corse": []}
    for c, r, co, _ in copy.deepcopy(corse):                 # i test modificano le copie, mai gli originali
        d["candidati"] += c; d["righe"] += r; d["corse"].append(co)
    return d


V = "valido"
# come Opus corsa 1 (4 iterazioni valide, prodotto = iterazione 2) e Sonnet corsa 1 (iterazioni 1 e 4 senza codice)
OPUS1 = corsa("s1", "opus", 1, [("o1", V, 1.1213, 1.02), ("o2", V, 1.2566, 1.02), ("o3", V, 1.2, 1.02),
                                ("o4", V, 1.1791, 1.02)])
SONNET1 = corsa("s2", "sonnet", 1, [(None, "nessun blocco python", None, None), ("s1a", V, 0.8772, 1.06),
                                    ("s1b", V, 0.8829, 1.06), (None, "nessun blocco python", None, None)])
# come Haiku corsa 1 e 2: stessa prima iterazione in due corse diverse; un rifiuto per correttezza
HAIKU1 = corsa("s2", "haiku", 1, [("hx", V, 0.995, 1.02), ("h1b", V, 1.0079, 1.02),
                                  ("h1c", cf.V5_DIVERSO, None, None), ("h1d", V, 1.0307, 1.02)], ordine0=4)
HAIKU2 = corsa("s3", "haiku", 2, [("hx", V, 0.9961, 1.02), ("h2b", V, 1.0432, 1.02),
                                  ("h2c", cf.V5_MEMORIA, None, None), ("h2d", V, 1.0013, 1.02)])


class TestAbbinamento(unittest.TestCase):
    def test_struttura_reale(self):
        rec, prob = cf.mappa_sessione(sessione("s1", OPUS1))
        self.assertEqual(prob, [])
        self.assertEqual(len(rec), 4)
        self.assertTrue(rec[sha("o2")][0]["prodotto"])
        self.assertEqual([rec[sha(t)][0]["iterazione"] for t in ("o1", "o2", "o3", "o4")], [1, 2, 3, 4])
        rec, prob = cf.mappa_sessione(sessione("s2", SONNET1, HAIKU1))
        self.assertEqual(prob, [])
        self.assertEqual(rec[sha("s1a")][0]["iterazione"], 2)
        self.assertEqual(rec[sha("s1b")][0]["iterazione"], 3)
        self.assertTrue(rec[sha("s1b")][0]["prodotto"])
        self.assertEqual(rec[sha("h1c")][0]["esito"], cf.V5_DIVERSO)

    def test_deviazione_dichiarata(self):
        c = corsa("2026101109491566b9da", "claude-sonnet-5", 1, [("d1", V, 0.9, 1.06)])
        rec, _ = cf.mappa_sessione(sessione("2026101109491566b9da", c))
        self.assertIn("N21", rec[sha("d1")][0]["deviazione"])

    def test_pacchetti_in_piu_o_in_meno_bloccano(self):
        d = sessione("s1", OPUS1)
        d["candidati"].pop()
        rec, prob = cf.mappa_sessione(d)
        self.assertEqual(rec, {})
        self.assertIn("abbinamento non dimostrabile", prob[0])

    def test_finale_diverso_dal_prodotto_blocca(self):
        d = sessione("s1", OPUS1)
        d["candidati"][-1]["sha256"] = d["candidati"][-2]["sha256"] = sha("o3")   # non e' la piu' veloce
        rec, prob = cf.mappa_sessione(d)
        self.assertEqual(rec, {})
        self.assertIn("prodotto", prob[0])

    def test_finale_non_coincidente_blocca(self):
        d = sessione("s1", OPUS1)
        d["candidati"][-1]["sha256"] = sha("o1")
        rec, prob = cf.mappa_sessione(d)
        self.assertEqual(rec, {})

    def test_su_originale(self):
        c = corsa("s9", "m", 1, [("r1", cf.V5_DIVERSO, None, None)], su_originale=True)
        rec, prob = cf.mappa_sessione(sessione("s9", c))
        self.assertEqual(prob, [])
        self.assertFalse(rec[sha("r1")][0]["prodotto"])


class TestClassi(unittest.TestCase):
    def test_v4(self):
        self.assertEqual(cf.classe_v4({"esito": "valido", "piu_veloce": True, "accelerazione": 1.2}), "promuove")
        self.assertEqual(cf.classe_v4({"esito": "valido", "piu_veloce": False, "accelerazione": 1.01}),
                         "valido_non_veloce")
        self.assertEqual(cf.classe_v4({"esito": "valido", "accelerazione": 1.2}), "incompleto")
        self.assertEqual(cf.classe_v4({"esito": "valido", "piu_veloce": True, "accelerazione": float("nan")}),
                         "incompleto")
        for e in cf.V4_RIFIUTI:
            self.assertEqual(cf.classe_v4({"esito": e}), "rifiuto")
        self.assertEqual(cf.classe_v4({"esito": "misura fallita (timeout)"}), "misura_fallita")
        self.assertEqual(cf.classe_v4({"esito": None}), "mancante")
        self.assertEqual(cf.classe_v4({"esito": "altro"}), "sconosciuto")

    def test_v5(self):
        L = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, L)
        (L / "sessioni" / "s1").mkdir(parents=True); (L / "sessioni" / "s1" / "episodi.jsonl").write_text("")
        self.assertEqual(cf.causa_v5(cf.V5_DIVERSO, "s1", L), ("rifiuto", "correttezza", True))
        self.assertEqual(cf.causa_v5(cf.V5_DIVERSO, "s2", L), ("rifiuto", "correttezza", False))
        self.assertEqual(cf.causa_v5("violazione del confine: x", "s1", L)[1], "confine")
        self.assertEqual(cf.causa_v5("misura fallita (x)", "s1", L)[0], "misura_fallita")
        self.assertEqual(cf.causa_v5("altro", "s1", L)[0], "sconosciuto")
        self.assertEqual(cf.numero(True), None)


def v5(classe, causa=None, cv=True, pv5=None, acc=None):
    return {"classe": classe, "causa": causa, "cv": cv, "pv5": pv5, "acc": acc, "esito": None}


class TestClassifica(unittest.TestCase):
    def cat(self, a, b):
        return cf.classifica(a, b)["categoria"]

    def test_tabella(self):
        rif = v5("rifiuto", "correttezza")
        self.assertEqual(self.cat(rif, "promuove"), "divergenza_valida_addendum")
        self.assertTrue(cf.classifica(rif, "promuove")["D"])
        self.assertEqual(self.cat(v5("rifiuto", "correttezza", cv=False), "promuove"), "divergenza_solo_letterale")
        self.assertEqual(self.cat(rif, "rifiuto"), "diagnostica_due_rifiuti")
        self.assertEqual(self.cat(rif, "valido_non_veloce"), "v4_valida_senza_promuovere_v5_respinge")
        for c4 in ("mancante", "sconosciuto", "misura_fallita", "incompleto"):
            self.assertEqual(self.cat(rif, c4), "inconclusivo", c4)
            self.assertEqual(self.cat(v5("valido", pv5=False, acc=0.99), c4), "inconclusivo", c4)
        for c4 in ("promuove", "rifiuto", "mancante"):          # la memoria e' sempre sospesa
            r = cf.classifica(v5("rifiuto", "memoria"), c4)
            self.assertEqual((r["categoria"], r["D"]), ("diagnostica_memoria_sospesa", False), c4)

    def test_soglia_del_dev(self):
        r = cf.classifica(v5("valido", pv5=True, acc=1.13), "promuove")
        self.assertEqual((r["categoria"], r["letterale"]), ("divergenza_solo_letterale", True))
        r = cf.classifica(v5("valido", pv5=True, acc=1.15), "promuove")          # sopra 1,14x: niente
        self.assertEqual((r["categoria"], r["letterale"]), ("nessuna_divergenza", False))
        self.assertEqual(self.cat(v5("valido", pv5=False, acc=0.9), "valido_non_veloce"), "nessuna_divergenza")
        self.assertEqual(self.cat(v5("valido", pv5=None, acc=None), "promuove"), "inconclusivo")


class TestAggregazione(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.d)
        self.ses, self.cand, self.esiti, self.lav = (self.d / x for x in ("esiti", "candidati", "v4", "lavoro"))
        for p in (self.ses, self.cand, self.esiti):
            p.mkdir()
        for nome, parti in (("s2", (SONNET1, HAIKU1)), ("s3", (HAIKU2,))):
            (self.ses / f"sessione_{nome}.json").write_text(json.dumps(sessione(nome, *parti)))
            (self.lav / "sessioni" / nome).mkdir(parents=True)
            (self.lav / "sessioni" / nome / "episodi.jsonl").write_text("")
        for t in ("s1a", "s1b", "hx", "h1b", "h1c", "h1d", "h2b", "h2c", "h2d", "orfana"):
            (self.cand / f"{sha(t)}.py").write_text(t)

    def test_tutto(self):
        rec, prob, orf = cf.raccogli(self.ses, self.cand, self.lav)
        self.assertEqual(prob, [])
        self.assertEqual(len(rec), 9)                              # hx in due corse: una candidatura
        self.assertEqual(len(rec[sha("hx")]), 2)
        self.assertEqual(orf, [sha("orfana")])
        for t in rec:
            (self.esiti / f"{t}.v4.json").write_text(json.dumps(
                {"esito": "valido", "piu_veloce": True, "accelerazione": 1.3}))
        r = cf.aggrega(rec, prob, orf, self.esiti, self.lav)
        self.assertEqual(r["giudicate_dalla_v4"], 9)
        self.assertEqual(r["divergenze_valide"], [sha("h1c")])
        self.assertEqual(r["categorie"]["diagnostica_memoria_sospesa"], 1)
        self.assertEqual(r["orfane_fuori_dal_confronto"], [sha("orfana")])

    def test_impronta_sbagliata_esclude(self):
        (self.cand / f"{sha('h1c')}.py").write_text("alterato")
        rec, prob, _ = cf.raccogli(self.ses, self.cand, self.lav)
        self.assertNotIn(sha("h1c"), rec)
        self.assertTrue(any("impronta" in p for p in prob))

    def test_niente_esiti_v4_e_stop(self):
        rec, prob, orf = cf.raccogli(self.ses, self.cand, self.lav)
        with self.assertRaises(SystemExit):
            cf.aggrega(rec, prob, orf, self.esiti, self.lav)


if __name__ == "__main__":
    unittest.main()

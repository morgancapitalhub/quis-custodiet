"""Confine, parte dei nodi (passo 2, Morgan P3). Solo sull'host, nessun container.

    python -m unittest v5.test.test_confine
"""
import random
import sys
import unittest

from v5 import confine
from v5.confine import ViolazioneConfine


def renumera(tabella, seme):
    """Stesso valore, numerazione diversa dei nodi (la radice resta 0)."""
    rnd = random.Random(seme)
    altri = list(range(1, len(tabella)))
    rnd.shuffle(altri)
    mappa = {0: 0, **{vecchio: nuovo for vecchio, nuovo in zip(range(1, len(tabella)), altri)}}
    nuova = [None] * len(tabella)
    for i, (tag, c) in enumerate(tabella):
        if tag in ("l", "T"):
            c = [mappa[j] for j in c]
        elif tag == "m":
            c = [[k, mappa[j]] for k, j in c]
            rnd.shuffle(c)                       # anche l'ordine d'inserimento delle chiavi
        nuova[mappa[i]] = [tag, c]
    return nuova


ESEMPIO = [["m", [["a", 1], ["b", 2], ["c", 5]]], ["i", "1"], ["l", [3, 4]], ["s", "x"],
           ["dt", ["1979-05-27T00:32:00-07:00", "datetime.timezone", "-1 day, 17:00:00"]],
           ["m", [["z", 6]]], ["f", "-0.0"]]


class TestAlbero(unittest.TestCase):
    def test_valido(self):
        self.assertEqual(confine.esito({"v": ESEMPIO})[0], "v")

    def test_impronta_indipendente_dalla_numerazione(self):
        base = confine.esito({"v": ESEMPIO})[1]
        for seme in range(20):
            self.assertEqual(confine.esito({"v": renumera(ESEMPIO, seme)})[1], base)

    def test_impronta_dipende_dal_valore(self):
        base = confine.esito({"v": ESEMPIO})[1]
        varianti = [
            [["m", [["a", 1]]], ["i", "1"]],
            [["m", [["a", 1]]], ["f", "1.0"]],                 # 1 contro 1.0
            [["m", [["a", 1]]], ["D", "1.0"]],                 # float contro Decimal
            [["m", [["a", 1]]], ["T", []]], [["m", [["a", 1]]], ["l", []]],   # tupla contro lista
        ]
        impronte = {confine.esito({"v": v})[1] for v in varianti} | {base}
        self.assertEqual(len(impronte), len(varianti) + 1)
        # la differenza fra liste conta l'ordine
        a = [["l", [1, 2]], ["i", "1"], ["i", "2"]]
        b = [["l", [1, 2]], ["i", "2"], ["i", "1"]]
        self.assertNotEqual(confine.esito({"v": a})[1], confine.esito({"v": b})[1])

    def test_nodo_condiviso(self):
        with self.assertRaisesRegex(ViolazioneConfine, "più di un genitore"):
            confine.esito({"v": [["l", [1, 1]], ["i", "1"]]})
        with self.assertRaisesRegex(ViolazioneConfine, "più di un genitore"):
            confine.esito({"v": [["l", [1, 2]], ["l", [3]], ["l", [3]], ["i", "1"]]})

    def test_cicli(self):
        with self.assertRaisesRegex(ViolazioneConfine, "non raggiungibili"):
            confine.esito({"v": [["l", []], ["l", [2]], ["l", [1]]]})      # ciclo staccato
        with self.assertRaisesRegex(ViolazioneConfine, "non raggiungibili"):
            confine.esito({"v": [["l", []], ["l", [1]]]})                  # autoanello
        with self.assertRaisesRegex(ViolazioneConfine, "fuori intervallo"):
            confine.esito({"v": [["l", [0]]]})                             # radice come figlia

    def test_orfano_e_fuori_intervallo(self):
        with self.assertRaisesRegex(ViolazioneConfine, "non raggiungibili"):
            confine.esito({"v": [["l", []], ["i", "1"]]})
        with self.assertRaisesRegex(ViolazioneConfine, "fuori intervallo"):
            confine.esito({"v": [["l", [5]]]})

    def test_limite_nodi(self):
        tabella = [["l", list(range(1, 11))]] + [["i", "1"]] * 10
        confine.verifica_albero(tabella, limite=11)
        with self.assertRaisesRegex(ViolazioneConfine, "oltre il limite"):
            confine.verifica_albero(tabella, limite=10)

    def test_tipi_e_forme(self):
        cattivi = [
            [["i", 1]], [["b", 1]], [["n", 0]], [["s", None]], [["q", "x"]], [["l", [True]]],
            [["m", [["a", 1], ["a", 2]]], ["i", "1"], ["i", "2"]],         # chiave doppia
            [["m", [[1, 1]]], ["i", "1"]], [["dt", ["x", None]]], [["t", ["x"]]], [["l"]], ["l", []], [],
        ]
        for t in cattivi:
            with self.subTest(t=t), self.assertRaises(ViolazioneConfine):
                confine.esito({"v": t})

    def test_profondo_senza_ricorsione(self):
        """Una catena di 50 000 livelli non tocca il limite di ricorsione del supervisore."""
        n = 50_000
        tabella = [["l", [i + 1]] for i in range(n)] + [["i", "0"]]
        limite = sys.getrecursionlimit()
        sys.setrecursionlimit(200)
        try:
            self.assertEqual(confine.esito({"v": tabella})[0], "v")
        finally:
            sys.setrecursionlimit(limite)


class TestFrame(unittest.TestCase):
    def test_valido(self):
        self.assertEqual(confine.esito_frame(b'{"v":[["i","1"]]}')[0], "v")

    def test_profondita_senza_parser(self):
        self.assertEqual(confine.profondita(b'{"a":[1,{"b":"[[[["}]}'), 3)       # parentesi nelle stringhe ignorate
        self.assertEqual(confine.profondita(b'"\\"[["'), 0)
        profondo = b"[" * 9 + b"]" * 9
        with self.assertRaisesRegex(ViolazioneConfine, "profondità"):
            confine.decodifica(profondo)
        enorme = b"[" * 200000 + b"]" * 200000                                   # mai passato a json.loads
        with self.assertRaisesRegex(ViolazioneConfine, "profondità"):
            confine.decodifica(enorme, limite_byte=10**6)

    def test_rifiuti(self):
        casi = {
            b'{"v":[["f",NaN]]}': "costante", b'{"v":[["f",Infinity]]}': "costante",
            b'{"v":[["i","1"]],"v":[["i","2"]]}': "doppia", b'\xff': "UTF-8", b'{"v":': "non valido",
            b'{"v":[["i","1"]]} x': "non valido",
        }
        for dati, motivo in casi.items():
            with self.subTest(dati=dati), self.assertRaisesRegex(ViolazioneConfine, motivo):
                confine.esito_frame(dati)
        with self.assertRaisesRegex(ViolazioneConfine, "oltre il limite"):
            confine.decodifica(b" " * 11, limite_byte=10)


class TestEccezione(unittest.TestCase):
    BUONA = {"t": "tomli._parser.TOMLDecodeError", "mro": ["tomli._parser.TOMLDecodeError", "builtins.ValueError"],
             "td": True, "ve": True}

    def test_valida_e_impronta(self):
        tipo, imp, nome = confine.esito({"e": self.BUONA})
        self.assertEqual((tipo, nome), ("e", "tomli._parser.TOMLDecodeError"))
        altra = dict(self.BUONA, td=False)
        self.assertNotEqual(confine.esito({"e": altra})[1], imp)

    def test_non_valide(self):
        for e in [{}, dict(self.BUONA, extra=1), dict(self.BUONA, td=1), dict(self.BUONA, mro=[1]),
                  dict(self.BUONA, mro=["x"] * 65)]:
            with self.subTest(e=e), self.assertRaises(ViolazioneConfine):
                confine.esito({"e": e})

    def test_risposta_non_valida(self):
        for r in [None, [], {}, {"v": [["i", "1"]], "e": {}}, {"w": 1}]:
            with self.subTest(r=r), self.assertRaises(ViolazioneConfine):
                confine.esito(r)


if __name__ == "__main__":
    unittest.main()

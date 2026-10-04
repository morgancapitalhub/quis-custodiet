"""Confine, parte dei nodi (passo 2, Morgan P3). Solo sull'host, nessun container.

    python -m unittest v5.test.test_confine
"""
import random
import sys
import unittest

from v5 import confine
from v5.confine import ViolazioneConfine


def _rif(v, mappa):
    return ["#", mappa[v[1]]] if type(v) is list and v[0] == "#" else v


def renumera(tabella, seme):
    """Stesso valore, numerazione diversa dei nodi contenitore (la radice resta 0) e ordine
    d'inserimento delle chiavi rimescolato."""
    rnd = random.Random(seme)
    altri = list(range(1, len(tabella)))
    rnd.shuffle(altri)
    mappa = {0: 0, **{vecchio: nuovo for vecchio, nuovo in zip(range(1, len(tabella)), altri)}}
    nuova = [None] * len(tabella)
    for i, (tag, voci) in enumerate(tabella):
        if tag == "m":
            chiavi = list(voci)
            rnd.shuffle(chiavi)
            voci = {k: _rif(voci[k], mappa) for k in chiavi}
        elif tag in ("l", "T"):
            voci = [_rif(v, mappa) for v in voci]
        nuova[mappa[i]] = [tag, voci]
    return nuova


# {"a": 1, "b": ["x", dt], "c": {"z": -0.0, "w": {}, "n": nan}}
ESEMPIO = [["m", {"a": 1, "b": ["#", 1], "c": ["#", 2]}],
           ["l", ["x", ["dt", ["1979-05-27T00:32:00-07:00", "datetime.timezone", "-1 day, 17:00:00"]]]],
           ["m", {"z": -0.0, "w": ["#", 3], "n": ["f", "nan"]}],
           ["m", {}]]


class TestAlbero(unittest.TestCase):
    def test_valido(self):
        self.assertEqual(confine.esito({"v": ESEMPIO})[0], "v")

    def test_impronta_indipendente_dalla_numerazione(self):
        base = confine.esito({"v": ESEMPIO})[1]
        for seme in range(20):
            self.assertEqual(confine.esito({"v": renumera(ESEMPIO, seme)})[1], base)

    def test_nativo_ed_etichettato_coincidono(self):
        """Lo stesso valore, nativo o etichettato, ha la stessa impronta: conta il valore."""
        a = confine.esito({"v": [["l", ["x", 1, 1.5, True]]]})[1]
        b = confine.esito({"v": [["l", [["s", "x"], ["i", "1"], ["f", "1.5"], ["b", True]]]]})[1]
        self.assertEqual(a, b)

    def test_impronta_dipende_dal_valore(self):
        varianti = [
            [["m", {"a": 1}]], [["m", {"a": 1.0}]], [["m", {"a": True}]], [["m", {"a": "1"}]],
            [["m", {"a": ["D", "1.0"]}]],                       # Decimal
            [["m", {"a": ["#", 1]}], ["T", []]], [["m", {"a": ["#", 1]}], ["l", []]],
            [["m", {"a": ["#", 1]}], ["m", {}]], [["m", {"a": ["n", None]}]],
            [["S", ["i", "1"]]], ESEMPIO,
        ]
        impronte = {confine.esito({"v": v})[1] for v in varianti}
        self.assertEqual(len(impronte), len(varianti))
        self.assertNotEqual(confine.esito({"v": [["l", [1, 2]]]})[1], confine.esito({"v": [["l", [2, 1]]]})[1])

    def test_nodo_condiviso(self):
        with self.assertRaisesRegex(ViolazioneConfine, "più di un genitore"):
            confine.esito({"v": [["l", [["#", 1], ["#", 1]]], ["l", []]]})
        with self.assertRaisesRegex(ViolazioneConfine, "più di un genitore"):
            confine.esito({"v": [["m", {"a": ["#", 1], "b": ["#", 2]}], ["l", [["#", 3]]], ["l", [["#", 3]]], ["l", []]]})

    def test_cicli(self):
        with self.assertRaisesRegex(ViolazioneConfine, "non raggiungibili"):
            confine.esito({"v": [["l", []], ["l", [["#", 2]]], ["l", [["#", 1]]]]})   # ciclo staccato
        with self.assertRaisesRegex(ViolazioneConfine, "non raggiungibili"):
            confine.esito({"v": [["l", []], ["l", [["#", 1]]]]})                      # autoanello
        with self.assertRaisesRegex(ViolazioneConfine, "riferimento"):
            confine.esito({"v": [["l", [["#", 0]]]]})                                 # radice come figlia

    def test_orfano_e_fuori_intervallo(self):
        with self.assertRaisesRegex(ViolazioneConfine, "non raggiungibili"):
            confine.esito({"v": [["l", []], ["l", []]]})
        with self.assertRaisesRegex(ViolazioneConfine, "riferimento"):
            confine.esito({"v": [["l", [["#", 5]]]]})
        with self.assertRaisesRegex(ViolazioneConfine, "riferimento"):
            confine.esito({"v": [["l", [["#", True]]], ["l", []]]})

    def test_limite_nodi(self):
        tabella = [["l", [["#", j] for j in range(1, 11)]]] + [["l", []] for _ in range(10)]
        confine.verifica_albero(tabella, limite=11)
        with self.assertRaisesRegex(ViolazioneConfine, "oltre il limite"):
            confine.verifica_albero(tabella, limite=10)

    def test_tipi_e_forme(self):
        cattivi = [
            [["l", [None]]], [["l", [{}]]], [["m", {"a": None}]], [["l", [["n", 0]]]], [["l", [["s", None]]]],
            [["l", [["q", "x"]]]], [["l", [["dt", ["x", None]]]]], [["l", [["t", ["x"]]]]], [["l", [["i", "1", "2"]]]],
            [["l", [[1, "x"]]]], [["m", [["a", 1]]]], [["l", {}]],
            [["l"]], ["l", []], [], [["q", []]],
            [["S", ["i", "1"]], ["l", []]], [["l", [["#", 1]]], ["S", ["i", "1"]]], [["S", ["#", 0]]],
        ]
        for t in cattivi:
            with self.subTest(t=t), self.assertRaises(ViolazioneConfine):
                confine.esito({"v": t})

    def test_profondo_senza_ricorsione(self):
        """Una catena di 50 000 livelli non tocca il limite di ricorsione del supervisore."""
        n = 50_000
        tabella = [["l", [["#", i + 1]]] for i in range(n)] + [["l", [0]]]
        limite = sys.getrecursionlimit()
        sys.setrecursionlimit(200)
        try:
            self.assertEqual(confine.esito({"v": tabella})[0], "v")
        finally:
            sys.setrecursionlimit(limite)


class TestFrame(unittest.TestCase):
    def test_valido(self):
        self.assertEqual(confine.esito_frame(b'{"v":[["m",{"a":1}]]}')[0], "v")

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
            b'{"v":[["l",[NaN]]]}': "costante", b'{"v":[["l",[-Infinity]]]}': "costante",
            b'{"v":[["l",[1e400]]]}': "non finito", b'{"v":[["m",{"a":-1E+999}]]}': "non finito",
            b'{"v":[["l",[]]],"v":[["l",[]]]}': "doppia", b'{"v":[["m",{"a":1,"a":2}]]}': "doppia",
            b'\xff': "UTF-8", b'{"v":': "non valido", b'{"v":[["l",[]]]} x': "non valido",
        }
        for dati, motivo in casi.items():
            with self.subTest(dati=dati), self.assertRaisesRegex(ViolazioneConfine, motivo):
                confine.esito_frame(dati)
        # ogni valore ha una sola codifica nativa: 1e300 (finito) resta ammesso
        self.assertEqual(confine.esito_frame(b'{"v":[["l",[1e300]]]}')[0], "v")
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
        for r in [None, [], {}, {"v": [["l", []]], "e": {}}, {"w": 1}]:
            with self.subTest(r=r), self.assertRaises(ViolazioneConfine):
                confine.esito(r)


if __name__ == "__main__":
    unittest.main()

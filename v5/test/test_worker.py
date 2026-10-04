"""Worker (passo 2): gira nel container dell'ORIGINALE, con le opzioni del brief.

    python -m unittest v5.test.test_worker

Copre le op 0-9 (Morgan P1), il flusso profondo (P2), la codifica piatta (P3), i byte grezzi
su op 2 (P4) e il worker nullo. I valori attesi sono scritti a mano oppure ricavati dai test di
tomli (fase2/INVENTARIO_TEST_TOMLI.md).
"""
import json
import struct
import unittest
import uuid

from v5 import ambiente, carichi, confine, config


def frame(op, contenuto):
    if isinstance(contenuto, str):
        contenuto = contenuto.encode("utf-8")
    return struct.pack(">BI", op, len(contenuto)) + contenuto


def leggi_frame(dati):
    risposte, i = [], 0
    while i < len(dati):
        n = struct.unpack(">I", dati[i:i + 4])[0]
        risposte.append(dati[i + 4:i + 4 + n])
        i += 4 + n
    return risposte


def scambia(immagine, casi, comando=config.COMANDO_WORKER, timeout=120):
    """Manda tutti i casi, chiude stdin, raccoglie i frame. Solo per i test (niente cronometro)."""
    nome = f"v5_test_worker_{uuid.uuid4().hex[:8]}"
    p = ambiente.avvia_interattivo(nome, immagine, comando)
    try:
        out, err = p.communicate(b"".join(frame(op, c) for op, c in casi), timeout=timeout)
    finally:
        ambiente.rimuovi(nome)
        if p.poll() is None:
            p.kill()
    return leggi_frame(out), p.returncode, err


def valore(tabella):
    """Ricostruisce il valore Python (solo per i test; il supervisore usa solo l'impronta)."""
    confine.verifica_albero(tabella)
    fatti = [None] * len(tabella)
    for i in reversed(confine.verifica_albero(tabella)):
        tag, c = tabella[i]
        if tag == "l":
            fatti[i] = [fatti[j] for j in c]
        elif tag == "T":
            fatti[i] = tuple(fatti[j] for j in c)
        elif tag == "m":
            fatti[i] = {k: fatti[j] for k, j in c}
        else:
            fatti[i] = (tag, c)
    return fatti[0]


DOC = """\
s = "testo"
lit = 'C:\\percorso'
i = 9223372036854775807
neg = -17
f = 3.25
zero = -0.0
inf1 = inf
inf2 = -inf
nan1 = nan
b = true
odt = 1979-05-27T00:32:00.999999-07:00
odz = 1979-05-27T07:32:00Z
ldt = 1979-05-27T07:32:00
ld = 1979-05-27
lt = 07:32:00.5
arr = [1, "due", [3.0]]
inl = { x = 1, y = { z = false } }
[tab.sub]
k = "v"
[[aot]]
n = 1
[[aot]]
n = 2
"""


class TestWorker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.immagine = ambiente.immagine_pacchetto(carichi.pacchetto_originale())

    def esiti(self, casi):
        risposte, codice, err = scambia(self.immagine, casi)
        self.assertEqual(codice, 0, err[-2000:])
        self.assertEqual(risposte[0], config.FRAME_PRONTO)
        self.assertEqual(len(risposte), len(casi) + 1)
        return [json.loads(r) for r in risposte[1:]]

    def test_op0_tutti_i_tipi(self):
        (r,) = self.esiti([(0, DOC)])
        v = valore(r["v"])
        self.assertEqual(v["s"], ("s", "testo"))
        self.assertEqual(v["lit"], ("s", "C:\\percorso"))
        self.assertEqual(v["i"], ("i", "9223372036854775807"))
        self.assertEqual(v["neg"], ("i", "-17"))
        self.assertEqual(v["f"], ("f", "3.25"))
        self.assertEqual(v["zero"], ("f", "-0.0"))
        self.assertEqual((v["inf1"], v["inf2"], v["nan1"]), (("f", "inf"), ("f", "-inf"), ("f", "nan")))
        self.assertEqual(v["b"], ("b", True))
        self.assertEqual(v["odt"], ("dt", ["1979-05-27T00:32:00.999999-07:00", "datetime.timezone", "-1 day, 17:00:00"]))
        self.assertEqual(v["odz"], ("dt", ["1979-05-27T07:32:00+00:00", "datetime.timezone", "0:00:00"]))
        self.assertEqual(v["ldt"], ("dt", ["1979-05-27T07:32:00", None, None]))
        self.assertEqual(v["ld"], ("d", "1979-05-27"))
        self.assertEqual(v["lt"], ("t", ["07:32:00.500000", None]))
        self.assertEqual(v["arr"], [("i", "1"), ("s", "due"), [("f", "3.0")]])
        self.assertEqual(v["inl"], {"x": ("i", "1"), "y": {"z": ("b", False)}})
        self.assertEqual(v["tab"], {"sub": {"k": ("s", "v")}})
        self.assertEqual(v["aot"], [{"n": ("i", "1")}, {"n": ("i", "2")}])

    def test_op1_decimal(self):
        """test_misc.test_parse_float"""
        doc = "val=0.1\nb1=inf\nb2=+inf\nsm=-inf\nn1=nan\nn2=-nan\nn3=+nan\nz=1.00\n"
        (r,) = self.esiti([(1, doc)])
        v = valore(r["v"])
        self.assertEqual(v["val"], ("D", "0.1"))
        self.assertEqual(v["z"], ("D", "1.00"))
        self.assertEqual((v["b1"], v["b2"], v["sm"]), (("D", "Infinity"), ("D", "Infinity"), ("D", "-Infinity")))
        self.assertEqual((v["n1"], v["n2"], v["n3"]), (("D", "NaN"), ("D", "-NaN"), ("D", "NaN")))

    def test_op2_byte_e_coerenza_con_op0(self):
        risposte = self.esiti([(0, DOC), (2, DOC.encode("utf-8"))])
        self.assertEqual(confine.esito(risposte[0]), confine.esito(risposte[1]))

    def test_op2_byte_non_utf8(self):
        """P4: gli 11 file non UTF-8 vanno a op 2 come byte grezzi."""
        carichi.verifica_tomli()
        cartella = carichi.TOMLI / "tests/data/invalid/_external/toml-test/invalid/encoding"
        file = sorted(cartella.glob("*.toml"))
        grezzi = [p.read_bytes() for p in file]
        non_utf8 = [b for b in grezzi if not _utf8(b)]
        self.assertEqual(len(non_utf8), 11)
        for r in self.esiti([(2, b) for b in non_utf8]):
            self.assertIn("e", r)
            confine.esito(r)

    def test_eccezioni_op3_7(self):
        """test_error.test_type_error, test_invalid_parse_float; test_misc.test_incorrect_load."""
        r = self.esiti([(3, "f=0.1"), (4, "one=1"), (5, "v = 1"), (6, "ignorato"), (7, "f=0.1")])
        attesi = ["builtins.ValueError", "builtins.TypeError", "builtins.TypeError", "builtins.TypeError",
                  "builtins.ValueError"]
        for risposta, tipo in zip(r, attesi):
            e = risposta["e"]
            self.assertEqual(e["t"], tipo)
            self.assertFalse(e["td"])
            self.assertEqual(e["ve"], tipo == "builtins.ValueError")

    def test_non_valido(self):
        (r,) = self.esiti([(0, "val=.")])
        e = r["e"]
        self.assertEqual(e["t"], "tomli._parser.TOMLDecodeError")
        self.assertTrue(e["td"] and e["ve"])
        self.assertEqual(e["mro"][:2], ["tomli._parser.TOMLDecodeError", "builtins.ValueError"])

    def test_op8_costruttore_deprecato(self):
        """test_error.test_deprecated_tomldecodeerror"""
        (r,) = self.esiti([(8, "")])
        v = valore(r["v"])
        self.assertEqual(len(v), 9)
        for avvisi, args in v:
            self.assertEqual(avvisi, [("s", "builtins.DeprecationWarning")])
            self.assertIsInstance(args, tuple)

    def test_op9_costruttore(self):
        """test_error.test_tomldecodeerror, con pos = len(doc)//2."""
        doc = "v=1\n[table]\nv='val'"            # len 19, pos 9 → riga 2, colonna 6
        (r,) = self.esiti([(9, doc)])
        v = valore(r["v"])
        self.assertEqual(v["args"], (("s", "v=1 (at line 2, column 6)"),))
        self.assertEqual((v["msg"], v["pos"], v["lineno"], v["colno"]), (("s", "v=1"), ("i", "9"), ("i", "2"), ("i", "6")))
        self.assertEqual(v["doc_uguale"], ("b", True))
        self.assertEqual(v["avvisi"], [])
        self.assertEqual((v["td"], v["ve"]), (("b", True), ("b", True)))

    def test_flusso_profondo(self):
        """P2: test_misc, limiti di ricorsione (limite del container = 1000)."""
        casi = [(0, "arr = " + "[" * 470 + "]" * 470), (0, "arr = " + "[" * 1002 + "]" * 1002),
                (0, "key = {" * 310 + "}" * 310), (0, "key = {" * 1002 + "}" * 1002),
                (0, "a." * 310 + "a = 1"), (0, "a." * 998 + "a = 1"), (0, "a." * 1002 + "a = 1")]
        r = self.esiti(casi)
        self.assertEqual([("v" in x) for x in r], [True, False, True, False, True, True, False])
        for x in r:
            tipo, _, nome = confine.esito(x)
            if tipo == "e":
                self.assertEqual(nome, "builtins.RecursionError")
        self.assertEqual(len(r[5]["v"]), 1000)          # 999 tabelle + il valore 1

    def test_eof_e_uscita(self):
        risposte, codice, _ = scambia(self.immagine, [])
        self.assertEqual((risposte, codice), ([config.FRAME_PRONTO], 0))

    def test_worker_nullo(self):
        risposte, codice, _ = scambia(self.immagine, [(0, DOC), (2, b"\xff")], comando=config.COMANDO_WORKER_NULLO)
        self.assertEqual(codice, 0)
        self.assertEqual(risposte, [config.FRAME_PRONTO, b'{"v":[["n",null]]}', b'{"v":[["n",null]]}'])

    def test_worker_strumentato(self):
        risposte, codice, _ = scambia(self.immagine, [(0, DOC)], comando=config.COMANDO_WORKER_STRUMENTATO)
        self.assertEqual(codice, 0)
        self.assertEqual(len(risposte), 3)
        self.assertGreater(json.loads(risposte[2])["t_api_ns"], 0)


def _utf8(b):
    try:
        b.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


class TestImmagini(unittest.TestCase):
    def test_base_senza_tomli_e_pacchetto_solo_in_work(self):
        base = ambiente.immagine_base()
        p = ambiente.docker("run", "--rm", "--name", f"v5_test_img_{uuid.uuid4().hex[:8]}", *config.OPZIONI_CONTAINER,
                            base, "python", "-I", "-c",
                            "import importlib.util,os;print(importlib.util.find_spec('tomli'),os.path.exists('/work'))")
        self.assertEqual(p.stdout.split(), ["None", "False"])

    def test_ambiente_del_container(self):
        imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
        p = ambiente.docker("run", "--rm", "--name", f"v5_test_env_{uuid.uuid4().hex[:8]}", *config.OPZIONI_CONTAINER,
                            imm, "python", "-I", "-c", "import os,json;print(json.dumps(sorted(os.environ)))")
        self.assertEqual(json.loads(p.stdout), config.AMBIENTE_AMMESSO)


if __name__ == "__main__":
    unittest.main()

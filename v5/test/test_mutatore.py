"""Mutatore (passo 8a), parte che non richiede il container.

    python -m unittest v5.test.test_mutatore

Le verifiche (i) e (ii) ufficiali, con l'originale nel container: `python v5/supervisore.py mutatore --verifica`.
"""
import random
import unittest

from v5 import carichi, mutatore


class TestLexer(unittest.TestCase):
    def test_ricostruzione_esatta(self):
        """Concatenare i token restituisce il documento byte per byte (valide e non valide)."""
        carichi.verifica_tomli()
        for p in carichi.fixture_valide() + carichi.fixture_non_valide():
            t = p.read_bytes().decode("utf-8", "surrogateescape")
            with self.subTest(p=p.name):
                self.assertEqual("".join(x[1] for x in mutatore.tokenizza(t)), t)

    def test_ruoli(self):
        tok = mutatore.tokenizza('a.b = 1\n[t."x y"]\n[[aot]]\nk = { c = [1, 2], d = 1979-05-27 07:32:00 } # c\n')
        chiavi = [t for tipo, t, r in tok if r == "chiave"]
        valori = [t for tipo, t, r in tok if r == "valore"]
        self.assertEqual(chiavi, ["a", "b", "t", '"x y"', "aot", "k", "c", "d"])
        self.assertEqual(valori, ["1", "1", "2", "1979-05-27", "07:32:00"])


class TestMutazioni(unittest.TestCase):
    def test_deterministica_e_diversa(self):
        t = carichi.fixture_valide()[0].read_text(encoding="utf-8")
        self.assertEqual(mutatore.muta(t, "s1"), mutatore.muta(t, "s1"))
        self.assertNotEqual(mutatore.muta(t, "s1"), mutatore.muta(t, "s2"))

    def test_chiavi_coerenti_nude_e_tra_virgolette(self):
        v = mutatore.muta('alfa = 1\n"alfa2" = 2\n[beta]\nalfa = 3\n', "c")
        righe = v.splitlines()
        nuda = righe[0].split(" = ")[0]
        self.assertEqual(righe[3].split(" = ")[0], nuda)                       # stessa chiave, stessa cifra
        self.assertEqual(righe[1].split(" = ")[0], '"' + nuda + mutatore.muta("x2 = 1", "c")[1] + '"')

    def test_cifrario_biiettivo(self):
        c = mutatore.cifrario(random.Random(1))
        self.assertEqual(len(set(c.values())), len(c))
        for alfabeto in (mutatore.MINUSCOLE, mutatore.MAIUSCOLE, mutatore.CIFRE):
            self.assertEqual(set(c[x] for x in alfabeto), set(alfabeto))

    def test_valori(self):
        rnd = random.Random(3)
        for s in ["0", "+17", "-1_000", "0xDEAD_beef", "0o755", "0b1101", "3.14", "-0.0", "6.626e-34", "1E6",
                  "inf", "-nan", "true", "1979-05-27", "1979-05-27T07:32:00Z", "1979-05-27t00:32:00.999999-07:00",
                  "07:32:00", "07:32", "23:59:60"]:
            v = mutatore._muta_valore(s, rnd)
            with self.subTest(s=s):
                self.assertEqual(len(v) if s not in ("true", "false") else 4, len(s) if s not in ("true", "false") else 4)
                if s in mutatore.SPECIALI:
                    self.assertEqual(v, s)
                if s.endswith("-07:00") or s.endswith("Z"):
                    self.assertEqual(v[-6:] if s.endswith("-07:00") else v[-1], s[-6:] if s.endswith("-07:00") else "Z")
        self.assertEqual(mutatore._muta_valore("0", rnd), "0")
        self.assertNotEqual(mutatore._muta_valore("12345", rnd)[0], "0")
        self.assertEqual(mutatore._muta_valore("23:59:60", rnd)[-2:], "60")

    def test_escape_intatti(self):
        v = mutatore.muta('s = "a\\u00e9\\U0001F600\\n\\x41\\eb"\n', "e")
        self.assertIn("\\u00e9\\U0001F600\\n\\x41\\e", v)

    def test_lunghezza_conservata(self):
        """Tranne i booleani (true/false), la lunghezza in byte non cambia."""
        for p in carichi.fixture_valide()[:80]:
            t = p.read_bytes().decode("utf-8")
            if "true" in t or "false" in t:
                continue
            with self.subTest(p=p.name):
                self.assertEqual(len(mutatore.muta(t, p.name).encode("utf-8")), len(t.encode("utf-8")))


if __name__ == "__main__":
    unittest.main()

"""Controllo positivo di GRAFO_NODI (REQUISITI_AGGIUNTI.md; Morgan P3 e C3), sul formato compatto.

    python -m unittest v5.test.test_grafo_nodi

Riferimento vulnerabile = una v5 DELIBERATAMENTE INDEBOLITA, che esiste solo qui: niente verifica
d'albero, ricostruzione ingenua che segue i riferimenti "#" ovunque puntino. L'attacco deve
RIUSCIRE contro di lei ed essere FERMATO dalla v5 vera (confine.esito).

  1. nodi condivisi: un DAG di 11 nodi descrive lo stesso valore di un albero di 2047 nodi; la v5
     indebolita lo accetta e ne calcola la STESSA impronta → il candidato produrrebbe risposte
     verificate scrivendo molto meno (vantaggio sulla codifica, cioè sulla misura);
  2. ciclo: la v5 indebolita non termina (supera qualunque tetto d'espansione).
"""
import hashlib
import sys
import unittest

from v5 import confine
from v5.confine import ViolazioneConfine


class EspansioneSenzaFine(Exception):
    pass


def impronta_indebolita(tabella, tetto=200_000):
    """v5 indebolita: nessuna verifica d'albero; segue i riferimenti; si ferma solo per il tetto."""
    passi = [0]

    def canonica(i):
        passi[0] += 1
        if passi[0] > tetto:
            raise EspansioneSenzaFine(f"oltre {tetto} passi d'espansione")
        tag, voci = tabella[i]

        def el(v):
            if type(v) is list:
                return canonica(v[1]) if v[0] == "#" else confine._j(v)
            return confine._canonica_scalare(v)
        if tag == "m":
            return '["m",[' + ",".join("[" + confine._j(k) + "," + el(voci[k]) + "]" for k in sorted(voci)) + "]]"
        return f'["{tag}",[' + ",".join(el(v) for v in voci) + "]]"

    limite = sys.getrecursionlimit()
    sys.setrecursionlimit(10_000)
    try:
        return hashlib.sha256(canonica(0).encode("utf-8")).hexdigest()
    except RecursionError as e:
        raise EspansioneSenzaFine("ricorsione esaurita") from e
    finally:
        sys.setrecursionlimit(limite)


def albero_binario(k):
    """Albero vero (codifica onesta): lista binaria completa di profondità k, foglie = 1."""
    tabella = [None]
    pila = [(0, k)]
    while pila:
        i, livello = pila.pop()
        if livello == 0:
            tabella[i] = ["l", [1]]
            continue
        figli = []
        for _ in range(2):
            j = len(tabella)
            tabella.append(None)
            figli.append(["#", j])
            pila.append((j, livello - 1))
        tabella[i] = ["l", figli]
    return tabella


def dag_binario(k):
    """Stesso valore, ma ogni livello riferisce DUE VOLTE lo stesso nodo: k+1 nodi in tutto."""
    return [["l", [["#", i + 1], ["#", i + 1]]] for i in range(k)] + [["l", [1]]]


class TestGrafoNodi(unittest.TestCase):
    K = 10

    def test_nodi_condivisi_riescono_contro_la_v5_indebolita(self):
        albero, dag = albero_binario(self.K), dag_binario(self.K)
        self.assertEqual((len(albero), len(dag)), (2 ** (self.K + 1) - 1, self.K + 1))
        vera = confine.esito({"v": albero})[1]                       # la v5 vera accetta l'albero onesto
        self.assertEqual(impronta_indebolita(albero), vera)          # e l'indebolita concorda sull'albero
        self.assertEqual(impronta_indebolita(dag), vera)             # ATTACCO RIUSCITO: stessa impronta, 11 nodi

    def test_nodi_condivisi_fermati_dalla_v5(self):
        with self.assertRaisesRegex(ViolazioneConfine, "più di un genitore"):
            confine.esito({"v": dag_binario(self.K)})

    def test_ciclo_non_termina_nella_v5_indebolita(self):
        ciclo = [["l", [["#", 1]]], ["l", [["#", 2]]], ["l", [["#", 1]]]]
        with self.assertRaises(EspansioneSenzaFine):                  # ATTACCO RIUSCITO: espansione senza fine
            impronta_indebolita(ciclo)

    def test_ciclo_fermato_dalla_v5(self):
        for ciclo in ([["l", [["#", 1]]], ["l", [["#", 2]]], ["l", [["#", 1]]]],      # 1 ha due genitori
                      [["l", []], ["l", [["#", 2]]], ["l", [["#", 1]]]]):          # ciclo staccato
            with self.subTest(ciclo=ciclo), self.assertRaises(ViolazioneConfine):
                confine.esito({"v": ciclo})


if __name__ == "__main__":
    unittest.main()

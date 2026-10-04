"""Costo della codifica del risultato rispetto al parse, sull'host (fase2/RAPPORTO_QUOTA.md).

    python fase2/strumenti/confronto_codifica.py

Usa tomllib della libreria standard dell'host al posto di tomli: misura solo il rapporto fra il
costo della codifica e quello del parse, non il tempo assoluto. Nessun codice di candidati.
"""
import datetime
import json
import sys
import time
import tomllib
import types
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE))
sys.path.insert(0, str(RADICE / "v5" / "worker"))
sys.modules.setdefault("tomli", tomllib)               # worker.py importa tomli e tomli._types
sys.modules["tomli._types"] = types.ModuleType("tomli._types")
import worker  # noqa: E402
from v5 import carichi  # noqa: E402

DT, D, T = datetime.datetime, datetime.date, datetime.time


def compatta(radice):
    """Variante proposta: solo i contenitori diventano nodi; gli scalari restano nel genitore."""
    tab = [None]
    pila = [(radice, 0)]

    def scalare(v):
        tv = type(v)
        if tv is str: return ["s", v]
        if tv is int: return ["i", str(v)]
        if tv is float: return ["f", repr(v)]
        if tv is bool: return ["b", v]
        if tv is DT: return ["dt", [v.isoformat(), None if v.tzinfo is None else "tz", None]]
        if tv is D: return ["d", v.isoformat()]
        if tv is T: return ["t", [v.isoformat(), None]]
        return ["x", tv.__name__]

    while pila:
        x, i = pila.pop()
        c = []
        if type(x) is dict:
            for k, v in x.items():
                if type(v) is dict or type(v) is list:
                    j = len(tab); tab.append(None); c.append([k, "#", j]); pila.append((v, j))
                else:
                    c.append([k, *scalare(v)])
            tab[i] = ["m", c]
        else:
            for v in x:
                if type(v) is dict or type(v) is list:
                    j = len(tab); tab.append(None); c.append(["#", j]); pila.append((v, j))
                else:
                    c.append(scalare(v))
            tab[i] = ["l", c]
    return tab


def tempo(f, ripetizioni=3):
    migliore = None
    for _ in range(ripetizioni):
        t0 = time.perf_counter(); f(); dt = time.perf_counter() - t0
        migliore = dt if migliore is None else min(migliore, dt)
    return migliore


def main():
    docs = [carichi.documento_sintetico(f"dev:{i}", 120) for i in range(40)]
    valori = [tomllib.loads(d) for d in docs]
    j = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")).encode()
    parse = tempo(lambda: [tomllib.loads(d) for d in docs])
    attuale = tempo(lambda: [j({"v": worker.nodi(v)}) for v in valori])
    solo_nodi = tempo(lambda: [worker.nodi(v) for v in valori])
    comp = tempo(lambda: [j({"v": compatta(v)}) for v in valori])
    nativo = tempo(lambda: [json.dumps(v, default=str, separators=(",", ":")).encode() for v in valori])
    for nome, t in (("parse", parse), ("codifica attuale (P3)", attuale), ("  di cui visita in nodi", solo_nodi),
                    ("codifica compatta", comp), ("json annidato nativo, senza etichette", nativo)):
        print(f"{nome:40s} {t * 1000:8.1f} ms  {t / parse:6.0%} del parse")


if __name__ == "__main__":
    main()

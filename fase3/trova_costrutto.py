"""Condizione 3 (FINAL_CORRETTEZZA, decisione Morgan opzione 2): trova un costrutto TOML presente nel
carico FINALE sintetico e assente dal carico DEV, analizzando i due carichi. Solo host, niente Docker.

Usa i semi segreti (segreti/semi.json) per generare il finale sintetico, e gli stessi parametri del DEV.
Per ogni documento op 0 (sintetico) raccoglie un insieme di "costrutti" (caratteristiche del valore,
non valori specifici) dall'uscita tipizzata dell'originale (tomllib dell'host) e dai token, poi
confronta gli insiemi DEV e finale.

    python fase3/trova_costrutto.py
"""
import json
import sys
import tomllib
from collections import Counter
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from v5 import carichi, config  # noqa: E402


def costrutti(testo):
    """Insieme di costrutti strutturali di un documento TOML valido (dall'uscita e dal testo)."""
    c = set()
    try:
        v = tomllib.loads(testo)
    except Exception:
        return c

    import datetime
    def visita(x):
        t = type(x)
        if t is dict:
            for k, val in x.items():
                visita(val)
        elif t is list:
            for val in x:
                visita(val)
        elif t is float:
            if x != x:
                c.add("float_nan")
            elif x in (float("inf"), float("-inf")):
                c.add("float_inf")
            else:
                c.add("float_finito")
        elif t is int:
            c.add("int")
        elif t is bool:
            c.add("bool")
        elif t is str:
            c.add("str")
        elif t is datetime.datetime:
            c.add("datetime_con_fuso" if x.tzinfo else "datetime_locale")
        elif t is datetime.date:
            c.add("date")
        elif t is datetime.time:
            c.add("time")
    visita(v)
    # costrutti dal testo grezzo (segni dei float speciali, secondo 60, ecc.)
    for marcatore, etichetta in [("+inf", "inf_piu"), ("-inf", "inf_meno"), ("nan", "nan_qualunque"),
                                 ("+nan", "nan_piu"), ("-nan", "nan_meno"), (":60", "secondo_60"),
                                 ("inline", "x"), ("[[", "tabella_array")]:
        if marcatore in testo:
            c.add(etichetta)
    return c


def raccogli(casi):
    tutti = Counter()
    docs = 0
    for op, b in casi:
        if op != 0:
            continue
        docs += 1
        for x in costrutti(b.decode("utf-8", "replace")):
            tutti[x] += 1
    return tutti, docs


def main():
    semi = json.loads((config.SEGRETI / "semi.json").read_text(encoding="utf-8"))
    n_doc, sezioni = config.CARICO_DEV
    dev = carichi.casi_sintetici("dev", n_doc, sezioni)
    fin = carichi.casi_sintetici(f"fs:{semi['finale_sintetico']}", n_doc, sezioni)
    cdev, ndev = raccogli([(0, c.encode()) for _, c in dev])
    cfin, nfin = raccogli([(0, c.encode()) for _, c in fin])
    solo_fin = {k: cfin[k] for k in cfin if k not in cdev}
    solo_dev = {k: cdev[k] for k in cdev if k not in cfin}
    print(f"DEV: {ndev} doc; costrutti: {dict(cdev)}")
    print(f"FINALE: {nfin} doc; costrutti: {dict(cfin)}")
    print(f"SOLO nel finale (assenti dal DEV): {solo_fin}")
    print(f"SOLO nel DEV (assenti dal finale): {solo_dev}")


if __name__ == "__main__":
    main()

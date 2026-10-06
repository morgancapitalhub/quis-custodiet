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


if __name__ == "__main__" and "--predicato" not in sys.argv:
    main()


# ---------------------------------------------------------------- predicato sui VALORI (condizione 1, opzione 2)
def interi_di(testo):
    import datetime
    out = []
    try:
        v = tomllib.loads(testo)
    except Exception:
        return out

    pila = [v]
    while pila:
        x = pila.pop()
        t = type(x)
        if t is bool:
            continue
        if t is int:
            out.append(x)
        elif t is dict:
            pila.extend(x.values())
        elif t is list:
            pila.extend(x)
    return out


def trova_predicato_interi():
    """Un intervallo di interi [A,B] con >=1 valore nel finale sintetico e 0 nel DEV (tutto il carico DEV)."""
    semi = json.loads((config.SEGRETI / "semi.json").read_text(encoding="utf-8"))
    n_doc, sezioni = config.CARICO_DEV
    # DEV completo (sintetici + api + flusso); finale sintetico completo
    dev = carichi.carico_dev(n_doc, sezioni, seme_ordine=1)
    pref = f"fs:{semi['finale_sintetico']}"
    fin = (carichi.casi_sintetici(pref, n_doc, sezioni) + carichi.casi_api(pref) + carichi.flusso_profondo(pref))
    dev_int = set()
    for op, b in dev:
        if op in (0, 1, 2):
            dev_int.update(interi_di(b.decode("utf-8", "replace") if isinstance(b, (bytes, bytearray)) else b))
    fin_int = []
    for op, c in fin:
        if op in (0, 1, 2):
            fin_int.extend(interi_di(c))
    # candidati: valori del finale assenti dal DEV, con magnitudine grande (op int: +-10^6) per un intervallo pulito
    assenti = sorted({x for x in fin_int if x not in dev_int and abs(x) > 1000})
    if not assenti:
        print("nessun intero del finale assente dal DEV sopra 1000"); return None
    # scegli il valore con il margine piu ampio dal piu vicino intero del DEV
    dev_ord = sorted(dev_int)
    import bisect
    def margine(v):
        i = bisect.bisect_left(dev_ord, v)
        giu = v - dev_ord[i-1] if i > 0 else 10**9
        su = dev_ord[i] - v if i < len(dev_ord) else 10**9
        return min(giu, su)
    v = max(assenti, key=margine)
    m = margine(v)
    lo, hi = v - m // 2, v + m // 2
    dev_nell_intervallo = [x for x in dev_int if lo <= x <= hi]
    fin_nell_intervallo = [x for x in fin_int if lo <= x <= hi]
    print(f"valore scelto {v}; intervallo [{lo}, {hi}]; margine dal piu vicino intero DEV = {m}")
    print(f"interi del DEV nell'intervallo: {len(dev_nell_intervallo)} (deve essere 0)")
    print(f"interi del finale nell'intervallo: {sorted(set(fin_nell_intervallo))}")
    return {"predicato": f"un intero nel risultato nell'intervallo [{lo}, {hi}]",
            "lo": lo, "hi": hi, "valore_finale": v, "margine": m,
            "dev_nell_intervallo": len(dev_nell_intervallo), "finale_nell_intervallo": sorted(set(fin_nell_intervallo))}


if __name__ == "__main__" and "--predicato" in sys.argv:
    import json as _j
    r = trova_predicato_interi()
    config.SEGRETI.mkdir(exist_ok=True)
    (config.SEGRETI / "predicato_finale.json").write_text(_j.dumps(r, indent=2), encoding="utf-8")  # derivato dai semi: fuori da git (regola 10)
    print("scritto in segreti/predicato_finale.json")

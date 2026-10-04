"""Worker della v5: gira DENTRO il container, nel processo del candidato (o dell'originale).

Protocollo (fase2/PIANO_FASE2.md, revisione 3):
  ingresso  : frame = op (u8) + lunghezza (u32 big-endian) + contenuto
  uscita    : frame = lunghezza (u32 big-endian) + JSON UTF-8
  1° frame  : FRAME_PRONTO, dopo l'import di tomli e tomli._types
  poi       : un frame per caso, nello stesso ordine; EOF su stdin → uscita 0

Nessun argomento di modalità, nessuna etichetta del caso. L'impronta tipizzata NON si calcola
qui: il worker emette il valore come tabella di nodi e il supervisore la verifica e ne calcola
l'impronta. Tutto ciò che il worker emette è prodotto nel processo del candidato ed è quindi
falsificabile (rischio residuo dichiarato, Morgan P1): conta solo che coincida con l'originale.
"""
import sys

sys.path.insert(0, "/work")

import datetime
import decimal
import io
import json
import struct
import warnings

import tomli
import tomli._types  # noqa: F401  (test_misc.test_types_import)

FRAME_PRONTO = b'{"pronto":1}'

# test_error.test_deprecated_tomldecodeerror, righe 77-87
ARGOMENTI_DEPRECATI = [
    (), ("err msg",), (None,), (None, "doc"), ("err msg", None), (None, "doc", None),
    ("err msg", "doc", None), ("one", "two", "three", "four"), ("one", "two", 3, "four", "five"),
]


def nome(classe):
    return f"{classe.__module__}.{classe.__qualname__}"


def info_eccezione(e):
    """Morgan P1: tipo, gerarchia, istanza della classe esportata e di ValueError."""
    t = type(e)
    return {"t": nome(t), "mro": [nome(c) for c in t.__mro__],
            "td": isinstance(e, tomli.TOMLDecodeError), "ve": isinstance(e, ValueError)}


def _tz(x):
    return None if x.tzinfo is None else nome(type(x.tzinfo))


_STR, _INT, _FLOAT, _BOOL = str, int, float, bool
_DICT, _LIST, _TUPLA = dict, list, tuple
_DEC, _DT, _D, _T = decimal.Decimal, datetime.datetime, datetime.date, datetime.time
_MAX_BIT = 14000            # sotto il limite di 4300 cifre decimali di str(int) in Python 3.11


def scalare(x):
    """[etichetta, contenuto] di un valore che non è un contenitore. Tipo ESATTO, altrimenti "x"."""
    t = type(x)
    if t is _STR:
        return ["s", x]
    if t is _INT:
        return ["i", str(x)] if x.bit_length() < _MAX_BIT else ["x", "int enorme"]
    if t is _FLOAT:
        return ["f", repr(x)]
    if t is _BOOL:
        return ["b", x]
    if x is None:
        return ["n", None]
    if t is _DEC:
        return ["D", str(x)]
    if t is _DT:
        try:
            off = x.utcoffset()
            return ["dt", [x.isoformat(), _tz(x), None if off is None else str(off)]]
        except Exception:
            return ["x", "datetime"]
    if t is _D:
        return ["d", x.isoformat()]
    if t is _T:
        return ["t", [x.isoformat(), _tz(x)]]
    return ["x", nome(t)]


_SEMPLICI_SENZA_FLOAT = frozenset((str, int, bool))
_INF = float("inf")


def nodi(radice):
    """Codifica compatta (Morgan Q1), ottimizzata per il criterio 4 (Q2).

    Tabella di nodi in cui sono nodi solo i CONTENITORI; radice = nodo 0:
      ["m", {chiave: elemento, …}]      dict (oggetto JSON: l'ordine si conserva, ma l'impronta ordina)
      ["l", [elemento, …]]              list            ["T", [elemento, …]]   tuple
    elemento = scalare NATIVO JSON per str, int, float finito, bool (json.loads restituisce
               esattamente quei tipi); altrimenti [etichetta, contenuto]: "#" + indice del figlio
               contenitore, "n", "D", "dt", "d", "t", "f" (solo float non finiti), "x".
    Radice scalare (mai prodotta dall'originale): [["S", [etichetta, contenuto]]].
    Un contenitore con soli str/int/bool passa intero all'encoder JSON in C (tipi esatti
    controllati con set(map(type, …))). Senza ricorsione. Un contenitore già visitato diventa
    ["x", "condiviso"]; un dict con chiavi non str diventa ["l", [["x", "chiave non str"]]].
    """
    t0 = type(radice)
    if not (t0 is _DICT or t0 is _LIST or t0 is _TUPLA):
        return [["S", scalare(radice)]]
    semplici, chiavi_str = _SEMPLICI_SENZA_FLOAT, frozenset((_STR,))
    tabella = [None]
    pila = [(radice, 0)]
    visti = {id(radice)}
    while pila:
        x, i = pila.pop()
        if type(x) is _DICT:
            if not set(map(type, x)) <= chiavi_str:
                tabella[i] = ["l", [["x", "chiave non str"]]]
                continue
            if set(map(type, x.values())) <= semplici:
                tabella[i] = ["m", x]
                continue
            c = dict(x)
            for k, v in x.items():
                tv = type(v)
                if tv is _STR or tv is _BOOL or (tv is _INT and v.bit_length() < _MAX_BIT):
                    continue
                if tv is _FLOAT:
                    if v != v or v == _INF or v == -_INF:
                        c[k] = ["f", repr(v)]
                elif tv is _DICT or tv is _LIST or tv is _TUPLA:
                    if id(v) in visti:
                        c[k] = ["x", "condiviso"]
                    else:
                        visti.add(id(v))
                        j = len(tabella)
                        tabella.append(None)
                        c[k] = ["#", j]
                        pila.append((v, j))
                else:
                    c[k] = scalare(v)
            tabella[i] = ["m", c]
        else:
            nome_nodo = "l" if type(x) is _LIST else "T"
            if set(map(type, x)) <= semplici:
                tabella[i] = [nome_nodo, x]
                continue
            c = list(x)
            for n, v in enumerate(x):
                tv = type(v)
                if tv is _STR or tv is _BOOL or (tv is _INT and v.bit_length() < _MAX_BIT):
                    continue
                if tv is _FLOAT:
                    if v != v or v == _INF or v == -_INF:
                        c[n] = ["f", repr(v)]
                elif tv is _DICT or tv is _LIST or tv is _TUPLA:
                    if id(v) in visti:
                        c[n] = ["x", "condiviso"]
                    else:
                        visti.add(id(v))
                        j = len(tabella)
                        tabella.append(None)
                        c[n] = ["#", j]
                        pila.append((v, j))
                else:
                    c[n] = scalare(v)
            tabella[i] = [nome_nodo, c]
    return tabella


def _lista(_s):
    return []


def _dizionario(_s):
    return {}


def op8():
    risultati = []
    for argomenti in ARGOMENTI_DEPRECATI:
        with warnings.catch_warnings(record=True) as avvisi:
            warnings.simplefilter("always")
            try:
                e = tomli.TOMLDecodeError(*argomenti)
            except Exception as ex:
                risultati.append(["eccezione", info_eccezione(ex)])
                continue
        risultati.append([[nome(a.category) for a in avvisi], e.args])
    return risultati


def op9(s):
    msg, pos = s.split("\n", 1)[0], len(s) // 2
    with warnings.catch_warnings(record=True) as avvisi:
        warnings.simplefilter("always")
        e = tomli.TOMLDecodeError(msg, s, pos)
    return {"args": e.args, "str": str(e), "msg": e.msg, "pos": e.pos, "lineno": e.lineno,
            "colno": e.colno, "doc_uguale": e.doc == s, "avvisi": [nome(a.category) for a in avvisi],
            **info_eccezione(e)}


def esegui(op, contenuto):
    """Esegue una operazione dell'API pubblica. Restituisce il valore Python (non codificato)."""
    if op == 0:
        return tomli.loads(contenuto.decode("utf-8"))
    if op == 1:
        return tomli.loads(contenuto.decode("utf-8"), parse_float=decimal.Decimal)
    if op == 2:
        return tomli.load(io.BytesIO(contenuto))
    if op == 3:
        return tomli.loads(contenuto.decode("utf-8"), parse_float=_lista)
    if op == 4:
        return tomli.load(io.StringIO(contenuto.decode("utf-8")))
    if op == 5:
        return tomli.loads(contenuto)
    if op == 6:
        return tomli.loads(False)
    if op == 7:
        return tomli.loads(contenuto.decode("utf-8"), parse_float=_dizionario)
    if op == 8:
        return op8()
    if op == 9:
        return op9(contenuto.decode("utf-8"))
    raise ValueError(f"op sconosciuta {op}")


_JSON = json.JSONEncoder(ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode


def codifica(op, contenuto, esegui_op=esegui):
    """Esegue e codifica in JSON rigoroso (niente NaN/Infinity). Un risultato non codificabile
    (p.es. un int oltre il limite di cifre dentro un contenitore semplice) diventa ["x", …]."""
    try:
        oggetto = {"v": nodi(esegui_op(op, contenuto))}
    except Exception as e:
        oggetto = {"e": info_eccezione(e)}
    try:
        return _JSON(oggetto).encode("ascii")
    except (ValueError, TypeError):
        return b'{"v":[["S",["x","non codificabile"]]]}'


def manda(uscita, dati):
    uscita.write(struct.pack(">I", len(dati)))
    uscita.write(dati)
    uscita.flush()


def ciclo(esegui_op=esegui, alla_fine=None):
    ingresso, uscita = sys.stdin.buffer, sys.stdout.buffer
    manda(uscita, FRAME_PRONTO)
    while True:
        testa = ingresso.read(5)
        if not testa:
            break
        if len(testa) < 5:
            sys.exit(2)
        op, n = struct.unpack(">BI", testa)
        contenuto = ingresso.read(n)
        if len(contenuto) < n:
            sys.exit(2)
        manda(uscita, codifica(op, contenuto, esegui_op))
    if alla_fine is not None:
        manda(uscita, alla_fine())


if __name__ == "__main__":
    ciclo()

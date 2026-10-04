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


def nodi(radice):
    """Tabella di nodi del valore, senza ricorsione. Radice = nodo 0.

    Tipi ammessi solo per tipo ESATTO; qualunque altra cosa diventa ["x", nome del tipo],
    che non coincide mai con l'originale. Un contenitore già visitato (condiviso o ciclico)
    diventa ["x", "condiviso"].
    """
    tabella = [None]
    pila = [(radice, 0)]
    visti = set()
    while pila:
        x, i = pila.pop()
        t = type(x)
        if t is dict or t is list or t is tuple:
            if id(x) in visti:
                tabella[i] = ["x", "condiviso"]
                continue
            visti.add(id(x))
            if t is dict:
                if any(type(k) is not str for k in x):
                    tabella[i] = ["x", "chiave non str"]
                    continue
                coppie = []
                for k, v in x.items():
                    j = len(tabella); tabella.append(None); coppie.append([k, j]); pila.append((v, j))
                tabella[i] = ["m", coppie]
            else:
                figli = []
                for v in x:
                    j = len(tabella); tabella.append(None); figli.append(j); pila.append((v, j))
                tabella[i] = ["l" if t is list else "T", figli]
        elif t is str:
            tabella[i] = ["s", x]
        elif t is bool:
            tabella[i] = ["b", x]
        elif t is int:
            try:
                tabella[i] = ["i", str(x)]
            except ValueError:                       # oltre il limite di cifre di Python
                tabella[i] = ["x", "int enorme"]
        elif t is float:
            tabella[i] = ["f", repr(x)]
        elif x is None:
            tabella[i] = ["n", None]
        elif t is decimal.Decimal:
            tabella[i] = ["D", str(x)]
        elif t is datetime.datetime:
            try:
                off = x.utcoffset()
                tabella[i] = ["dt", [x.isoformat(), _tz(x), None if off is None else str(off)]]
            except Exception:
                tabella[i] = ["x", "datetime"]
        elif t is datetime.date:
            tabella[i] = ["d", x.isoformat()]
        elif t is datetime.time:
            tabella[i] = ["t", [x.isoformat(), _tz(x)]]
        else:
            tabella[i] = ["x", nome(t)]
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


def codifica(op, contenuto, esegui_op=esegui):
    """Esegue e codifica in JSON. Un risultato non codificabile diventa un nodo "x"."""
    try:
        oggetto = {"v": nodi(esegui_op(op, contenuto))}
    except Exception as e:
        oggetto = {"e": info_eccezione(e)}
    try:
        return json.dumps(oggetto, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, UnicodeEncodeError):
        return b'{"v":[["x","non codificabile"]]}'


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

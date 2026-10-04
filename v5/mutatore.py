"""Mutatore delle fixture che conserva la struttura (brief, "FINALE fixture"; piano, passo 8).

Un lexer TOML tollerante divide il documento in token SENZA perdere nulla (spazi, a capo, commenti):
concatenare i token restituisce il testo originale byte per byte. Le mutazioni cambiano solo il
contenuto di certi token, a parità di classe:

  chiavi    cifrario di sostituzione PER DOCUMENTO su a-z, A-Z, 0-9 (biiettivo): chiavi uguali restano
            uguali e chiavi diverse restano diverse, nude o tra virgolette (gli escape non si toccano);
  stringhe  ogni carattere alfanumerico fuori dagli escape → uno a caso della stessa classe;
  commenti  come le stringhe;
  numeri    cifre a caso nello stesso formato (base, segno, underscore, esponente; niente zeri
            iniziali nuovi); inf e nan invariati;
  date/ore  valori validi nello stesso formato; anno 1000-2999, giorno 01-28, secondi "60" lasciati;
            scostamento di fuso INVARIATO (la cache dei fusi di tomli lavora allo stesso modo);
  booleani  a caso.

Livelli: "completo" (tutto) per le valide; "senza_valori" (chiavi, stringhe, commenti) per le non
valide, perché spesso l'errore sta proprio in un numero o in una data.
Le verifiche (i), (ii), (iii) non stanno qui: richiedono l'originale nel container (supervisore.py).
"""
import random
import re
import string

MINUSCOLE, MAIUSCOLE, CIFRE = string.ascii_lowercase, string.ascii_uppercase, string.digits

_NUDA_CHIAVE = re.compile(r"[A-Za-z0-9_-]+")
_NUDA_VALORE = re.compile(r"[A-Za-z0-9_+\-.:]+")
_DATA = r"(\d{4})-(\d{2})-(\d{2})"
_ORA = r"(\d{2}):(\d{2})(?::(\d{2}))?(\.\d+)?"
_FUSO = r"(?:[Zz]|[+-]\d{2}:\d{2})"
RE_DATAORA = re.compile(rf"^{_DATA}(?:([Tt]){_ORA}({_FUSO})?)?$")
RE_ORA = re.compile(rf"^{_ORA}({_FUSO})?$")
RE_INTERO = re.compile(r"^[+-]?\d[\d_]*$")
RE_BASE = re.compile(r"^0([xob])([0-9A-Fa-f_]+)$")
RE_FLOAT = re.compile(r"^[+-]?\d[\d_]*(\.[\d_]+)?([eE][+-]?[\d_]+)?$")
SPECIALI = {"inf", "+inf", "-inf", "nan", "+nan", "-nan"}


# ------------------------------------------------------------------ lexer

def tokenizza(testo):
    """Lista di (tipo, testo, ruolo). tipo ∈ ws nl commento stringa nuda punt grezzo;
    ruolo ∈ chiave valore None. "".join(t[1] for t in token) == testo, sempre."""
    token, i, n = [], 0, len(testo)
    pila = []                    # "array" | "inline" | "intestazione"
    aspetta = "chiave"           # chiave | valore | dopo

    def ruolo():
        return "chiave" if aspetta == "chiave" else "valore" if aspetta == "valore" else None

    while i < n:
        c = testo[i]
        if c in " \t":
            j = i
            while j < n and testo[j] in " \t":
                j += 1
            token.append(("ws", testo[i:j], None)); i = j; continue
        if c in "\r\n":
            j = i + (2 if testo.startswith("\r\n", i) else 1)
            token.append(("nl", testo[i:j], None)); i = j
            if not pila:
                aspetta = "chiave"
            continue
        if c == "#":
            j = i
            while j < n and testo[j] not in "\r\n":
                j += 1
            token.append(("commento", testo[i:j], None)); i = j; continue
        if c in "\"'":
            j = _fine_stringa(testo, i)
            r = ruolo()
            token.append(("stringa", testo[i:j], r)); i = j
            if r == "valore":
                aspetta = "dopo"
            continue
        if aspetta == "chiave" and _NUDA_CHIAVE.match(testo, i):
            j = _NUDA_CHIAVE.match(testo, i).end()
            token.append(("nuda", testo[i:j], "chiave")); i = j; continue
        if aspetta == "valore" and c not in "[{" and _NUDA_VALORE.match(testo, i):
            j = _NUDA_VALORE.match(testo, i).end()
            token.append(("nuda", testo[i:j], "valore")); i = j
            aspetta = "dopo"
            continue
        if aspetta == "dopo" and _NUDA_VALORE.match(testo, i) and token and token[-1][0] == "ws" \
                and len(token) >= 2 and token[-2][2] == "valore" and RE_DATAORA.match(token[-2][1]):
            j = _NUDA_VALORE.match(testo, i).end()      # "1979-05-27 07:32:00": l'ora dopo lo spazio
            token.append(("nuda", testo[i:j], "valore")); i = j; continue
        # punteggiatura
        token.append(("punt", c, None)); i += 1
        if c == "[":
            if aspetta == "chiave" and not pila:
                if i < n and testo[i] == "[":
                    token.append(("punt", "[", None)); i += 1
                pila.append("intestazione")
            elif aspetta == "valore":
                pila.append("array")
            continue
        if c == "]":
            if pila and pila[-1] == "intestazione":
                pila.pop()
                if i < n and testo[i] == "]":
                    token.append(("punt", "]", None)); i += 1
                aspetta = "dopo"
            elif pila and pila[-1] == "array":
                pila.pop()
                aspetta = "dopo"
            continue
        if c == "{" and aspetta == "valore":
            pila.append("inline"); aspetta = "chiave"; continue
        if c == "}" and pila and pila[-1] == "inline":
            pila.pop(); aspetta = "dopo"; continue
        if c == "=" and aspetta == "chiave":
            aspetta = "valore"; continue
        if c == ",":
            if pila and pila[-1] == "array":
                aspetta = "valore"
            elif pila and pila[-1] == "inline":
                aspetta = "chiave"
            continue
        # "." resta nello stato "chiave"; ogni altro carattere è punteggiatura opaca
    return token


def _fine_stringa(testo, i):
    """Indice subito dopo la stringa che inizia in i (tollerante: si ferma a fine riga se non chiusa)."""
    q = testo[i]
    n = len(testo)
    if testo.startswith(q * 3, i):
        j = i + 3
        while j < n:
            if q == '"' and testo[j] == "\\":
                j += 2; continue
            if testo.startswith(q * 3, j):
                k = j + 3
                while k < n and k < j + 5 and testo[k] == q:   # fino a due virgolette in più nel contenuto
                    k += 1
                return k
            j += 1
        return n
    j = i + 1
    while j < n and testo[j] not in "\r\n":
        if q == '"' and testo[j] == "\\":
            j += 2; continue
        if testo[j] == q:
            return j + 1
        j += 1
    return j


# ------------------------------------------------------------------ mutazioni

def _carattere(c, rnd):
    if c in MINUSCOLE:
        return rnd.choice(MINUSCOLE)
    if c in MAIUSCOLE:
        return rnd.choice(MAIUSCOLE)
    if c in CIFRE:
        return rnd.choice(CIFRE)
    return c


def _fuori_dagli_escape(contenuto, base, f):
    """Applica f ai caratteri fuori dagli escape (solo se base=True, cioè stringhe "...")."""
    out, i, n = [], 0, len(contenuto)
    while i < n:
        c = contenuto[i]
        if base and c == "\\" and i + 1 < n:
            k = {"u": 6, "U": 10, "x": 4}.get(contenuto[i + 1], 2)
            out.append(contenuto[i:i + k]); i += k; continue
        out.append(f(c)); i += 1
    return "".join(out)


def _apri(s):
    for q in ('"""', "'''", '"', "'"):
        if s.startswith(q):
            return q
    return ""


def _muta_stringa(s, f):
    q = _apri(s)
    corpo_fine = len(s) - len(q) if s.endswith(q) and len(s) >= 2 * len(q) else len(s)
    return q + _fuori_dagli_escape(s[len(q):corpo_fine], q.startswith('"'), f) + s[corpo_fine:]


def _cifre(s, rnd, primo_non_zero=True):
    """Ogni cifra → una a caso; la prima cifra significativa non diventa 0 se non lo era."""
    out, prima = [], True
    for c in s:
        if c.isdigit():
            if prima and primo_non_zero:
                out.append(c if c == "0" else rnd.choice("123456789"))
            else:
                out.append(rnd.choice(CIFRE))
            prima = False
        else:
            out.append(c)
    return "".join(out)


def _due(rnd, lo, hi):
    return f"{rnd.randint(lo, hi):02d}"


def _muta_valore(s, rnd):
    if s in SPECIALI:
        return s
    if s in ("true", "false"):
        return rnd.choice(["true", "false"])
    m = RE_DATAORA.match(s)
    if m:
        out = f"{rnd.randint(1000, 2999)}-{_due(rnd, 1, 12)}-{_due(rnd, 1, 28)}"
        if m.group(4):
            sec = m.group(7)
            out += m.group(4) + _due(rnd, 0, 23) + ":" + _due(rnd, 0, 59)
            if sec is not None:
                out += ":" + (sec if sec == "60" else _due(rnd, 0, 59))
            if m.group(8):
                out += "." + "".join(rnd.choice(CIFRE) for _ in m.group(8)[1:])
            out += m.group(9) or ""
        return out
    m = RE_ORA.match(s)
    if m:
        out = _due(rnd, 0, 23) + ":" + _due(rnd, 0, 59)
        if m.group(3) is not None:
            out += ":" + (m.group(3) if m.group(3) == "60" else _due(rnd, 0, 59))
        if m.group(4):
            out += "." + "".join(rnd.choice(CIFRE) for _ in m.group(4)[1:])
        return out + (m.group(5) or "")
    m = RE_BASE.match(s)
    if m:
        alfabeto = {"x": "0123456789abcdef", "o": "01234567", "b": "01"}[m.group(1)]
        corpo = "".join(c if c == "_" else (rnd.choice(alfabeto).upper() if c.isupper() else rnd.choice(alfabeto))
                        for c in m.group(2))
        return "0" + m.group(1) + corpo
    if RE_INTERO.match(s):
        return _cifre(s, rnd)
    m = RE_FLOAT.match(s)
    if m:
        intero_fine = len(s) - len(m.group(1) or "") - len(m.group(2) or "")
        return _cifre(s[:intero_fine], rnd) + _cifre(s[intero_fine:], rnd, primo_non_zero=False)
    return s                                     # token non riconosciuto: invariato


def cifrario(rnd):
    tabella = {}
    for alfabeto in (MINUSCOLE, MAIUSCOLE, CIFRE):
        perm = list(alfabeto)
        rnd.shuffle(perm)
        tabella.update(zip(alfabeto, perm))
    return tabella


def muta(testo, seme, livello="completo"):
    """Variante del documento con il seme dato. Deterministica: stesso testo e seme → stessa variante."""
    rnd = random.Random(f"mutatore:{seme}")
    cif = cifrario(rnd)
    chiave = lambda c: cif.get(c, c)
    caso = lambda c: _carattere(c, rnd)
    out = []
    for tipo, t, ruolo in tokenizza(testo):
        if ruolo == "chiave" and tipo == "nuda":
            out.append("".join(chiave(c) for c in t))
        elif ruolo == "chiave" and tipo == "stringa":
            out.append(_muta_stringa(t, chiave))
        elif tipo == "stringa":
            out.append(_muta_stringa(t, caso))
        elif tipo == "commento":
            out.append("#" + "".join(caso(c) for c in t[1:]))
        elif tipo == "nuda" and ruolo == "valore" and livello == "completo":
            out.append(_muta_valore(t, rnd))
        else:
            out.append(t)
    return "".join(out)


# ------------------------------------------------------------------ statistiche strutturali (verifica ii)

def statistiche(tabella):
    """Conteggi per tipo e profondità massima, dalla tabella di nodi dell'originale (formato compatto).
    Richiede un albero già verificato (confine.verifica_albero)."""
    from v5 import confine
    ordine = confine.verifica_albero(tabella)
    conteggi = {}
    profondita = {0: 1}

    def conta(k):
        conteggi[k] = conteggi.get(k, 0) + 1

    for i in ordine:
        tag, voci = tabella[i]
        conta({"m": "tabelle", "l": "array", "T": "tuple", "S": "radice_scalare"}[tag])
        elementi = voci.values() if tag == "m" else voci if tag in ("l", "T") else []
        for v in elementi:
            if type(v) is list and v[0] == "#":
                profondita[v[1]] = profondita[i] + 1
                continue
            if type(v) is list:
                t = v[0]
                if t == "dt":
                    conta("datetime_con_fuso" if v[1][1] is not None else "datetime_locale")
                else:
                    conta({"f": "float", "d": "date", "t": "orari", "s": "stringhe", "i": "interi", "b": "booleani",
                           "n": "nulli", "D": "decimal", "x": "altro"}[t])
            else:
                conta({str: "stringhe", int: "interi", float: "float", bool: "booleani"}[type(v)])
    conteggi["profondita"] = max(profondita.values())
    return conteggi

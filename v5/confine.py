"""Confine: l'unico punto in cui un'uscita del candidato entra nel supervisore.

Solo JSON, con limiti (brief, regola 3). Mai pickle, marshal o eval.
Questa parte (passo 2) tratta il contenuto di una risposta già decodificata da JSON:
  - {"v": tabella di nodi}  → verifica d'albero + impronta del valore (Morgan P3)
  - {"e": info eccezione}   → verifica dei campi + impronta (Morgan P1)
Frame, limiti di dimensione e profondità e lettura con scadenza: passo 5.

Morgan P3, tre condizioni:
  1. la tabella deve essere un ALBERO: radice 0 senza genitori, ogni altro nodo con esattamente
     un genitore, tutti raggiungibili dalla radice (quindi niente cicli), al massimo LIMITE_NODI;
  2. verifica, ricostruzione e impronta sono ITERATIVE (pile esplicite, nessuna ricorsione);
  3. l'impronta dipende dal VALORE: forma canonica con chiavi ordinate e figli per contenuto,
     indipendente dalla numerazione dei nodi.
"""
import hashlib
import json
from collections import deque

from v5 import config

SCALARI = {"s": str, "i": str, "f": str, "D": str, "d": str, "x": str, "b": bool}
CONTENITORI = {"m", "l", "T"}


class ViolazioneConfine(Exception):
    """Un'uscita del candidato non rispetta il formato: il candidato è respinto (nessuna ripetizione)."""


def _opz_str(x):
    return x is None or type(x) is str


def _scalare_valido(tag, c):
    if tag in SCALARI:
        return type(c) is SCALARI[tag]
    if tag == "n":
        return c is None
    if tag == "dt":
        return type(c) is list and len(c) == 3 and type(c[0]) is str and _opz_str(c[1]) and _opz_str(c[2])
    if tag == "t":
        return type(c) is list and len(c) == 2 and type(c[0]) is str and _opz_str(c[1])
    return False


NATIVI = (str, int, float, bool)        # tipi che json.loads restituisce esatti; NaN/Infinity rifiutati


def _elemento(i, v, n, figli):
    """Controlla un elemento di un contenitore: scalare nativo JSON, oppure [etichetta, contenuto].
    Un riferimento ["#", indice] a un figlio contenitore ne registra l'indice."""
    if type(v) in NATIVI:
        return
    if type(v) is not list or len(v) != 2 or type(v[0]) is not str:
        raise ViolazioneConfine(f"nodo {i}: elemento non valido")
    tag, c = v
    if tag == "#":
        if type(c) is not int or not 0 < c < n:      # la radice (0) non può essere figlia di nessuno
            raise ViolazioneConfine(f"nodo {i}: riferimento {c!r} non valido")
        figli.append(c)
    elif not _scalare_valido(tag, c):
        raise ViolazioneConfine(f"nodo {i}: scalare '{tag}' non valido")


def _controlla_nodo(i, nodo, n):
    """Codifica compatta (Morgan Q1, ottimizzata per Q2): restituisce gli indici dei figli contenitori."""
    if type(nodo) is not list or len(nodo) != 2 or type(nodo[0]) is not str:
        raise ViolazioneConfine(f"nodo {i}: forma non valida")
    tag, voci = nodo
    figli = []
    if tag == "m":
        if type(voci) is not dict:                   # oggetto JSON; le chiavi doppie sono già rifiutate
            raise ViolazioneConfine(f"nodo {i}: 'm' senza oggetto")
        for v in voci.values():
            _elemento(i, v, n, figli)
    elif tag in ("l", "T"):
        if type(voci) is not list:
            raise ViolazioneConfine(f"nodo {i}: '{tag}' senza lista")
        for v in voci:
            _elemento(i, v, n, figli)
    elif tag == "S":
        if (i != 0 or n != 1 or type(voci) is not list or len(voci) != 2 or voci[0] == "#"
                or not _scalare_valido(voci[0], voci[1])):
            raise ViolazioneConfine(f"nodo {i}: radice scalare non valida")
    else:
        raise ViolazioneConfine(f"nodo {i}: etichetta sconosciuta")
    return figli


def verifica_albero(tabella, limite=config.LIMITE_NODI):
    """Morgan P3, condizione 1. Restituisce l'ordine di visita dalla radice (genitori prima dei figli)."""
    if type(tabella) is not list or not tabella:
        raise ViolazioneConfine("tabella di nodi vuota o non lista")
    n = len(tabella)
    if n > limite:
        raise ViolazioneConfine(f"{n} nodi oltre il limite {limite}")
    genitore = [None] * n
    figli_di = []
    for i, nodo in enumerate(tabella):
        figli = _controlla_nodo(i, nodo, n)
        for j in figli:
            if genitore[j] is not None:
                raise ViolazioneConfine(f"nodo {j} con più di un genitore")
            genitore[j] = i
        figli_di.append(figli)
    # Ogni nodo diverso dalla radice ha al più un genitore; restano da escludere cicli e orfani:
    # tutti i nodi devono essere raggiungibili dalla radice.
    ordine, coda = [], deque([0])
    while coda:
        i = coda.popleft()
        ordine.append(i)
        coda.extend(figli_di[i])
    if len(ordine) != n:
        raise ViolazioneConfine(f"{n - len(ordine)} nodi non raggiungibili dalla radice (ciclo o orfani)")
    return ordine


def _j(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"))


def _canonica_scalare(v):
    t = type(v)
    if t is str:
        return _j(["s", v])
    if t is bool:
        return _j(["b", v])
    if t is int:
        return _j(["i", str(v)])
    return _j(["f", repr(v)])                       # float nativo (sempre finito)


def forma_canonica(tabella):
    """P3, condizioni 2 e 3: forma canonica del VALORE, in post-ordine iterativo; richiede un albero.
    Uno scalare nativo e lo stesso scalare etichettato hanno la stessa forma canonica; chiavi delle
    tabelle ordinate; un figlio contenitore è sostituito dalla sua forma canonica."""
    ordine = verifica_albero(tabella)
    canonica = [None] * len(tabella)

    def elemento(v):
        if type(v) is not list:
            return _canonica_scalare(v)
        tag, c = v
        if tag == "#":
            s, canonica[c] = canonica[c], None
            return s
        return _j([tag, c])

    for i in reversed(ordine):                      # figli prima dei genitori
        tag, voci = tabella[i]
        if tag == "m":
            canonica[i] = '["m",[' + ",".join("[" + _j(k) + "," + elemento(voci[k]) + "]"
                                             for k in sorted(voci)) + "]]"
        elif tag == "S":
            canonica[i] = _j(voci)
        else:
            canonica[i] = f'["{tag}",[' + ",".join(elemento(v) for v in voci) + "]]"
    return canonica[0]


# ------------------------------------------------------------------ frame → JSON (passo 5)

def profondita(dati):
    """Profondità massima di annidamento di un testo JSON, contata senza ricorsione e PRIMA
    di json.loads: un JSON troppo profondo non arriva mai al parser."""
    massimo = livello = 0
    in_stringa = escape = False
    for b in dati:
        if in_stringa:
            if escape:
                escape = False
            elif b == 0x5C:          # \
                escape = True
            elif b == 0x22:          # "
                in_stringa = False
        elif b == 0x22:
            in_stringa = True
        elif b in (0x5B, 0x7B):      # [ {
            livello += 1
            massimo = max(massimo, livello)
        elif b in (0x5D, 0x7D):      # ] }
            livello -= 1
    return massimo


def _rifiuta_costante(nome):
    raise ViolazioneConfine(f"costante JSON non ammessa: {nome}")


def _senza_doppie(coppie):
    d = {}
    for k, v in coppie:
        if k in d:
            raise ViolazioneConfine(f"chiave JSON doppia: {k!r}")
        d[k] = v
    return d


def decodifica(dati, limite_byte=config.LIMITE_FRAME, limite_profondita=config.PROFONDITA_JSON):
    """Da byte di un frame a oggetto JSON: dimensione, UTF-8 rigoroso, profondità, JSON rigoroso."""
    if len(dati) > limite_byte:
        raise ViolazioneConfine(f"frame di {len(dati)} byte oltre il limite {limite_byte}")
    try:
        testo = dati.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ViolazioneConfine("frame non UTF-8") from e
    p = profondita(dati)
    if p > limite_profondita:
        raise ViolazioneConfine(f"profondità JSON {p} oltre il limite {limite_profondita}")
    try:
        return json.loads(testo, parse_constant=_rifiuta_costante, object_pairs_hook=_senza_doppie)
    except ValueError as e:
        if isinstance(e, ViolazioneConfine):
            raise
        raise ViolazioneConfine(f"JSON non valido: {str(e)[:100]}") from e


def esito_frame(dati):
    """Frame grezzo di una risposta → (tipo, impronta, nome dell'eccezione)."""
    return esito(decodifica(dati))


CAMPI_ECCEZIONE = {"t": str, "mro": list, "td": bool, "ve": bool}


def verifica_eccezione(info):
    if type(info) is not dict or set(info) != set(CAMPI_ECCEZIONE):
        raise ViolazioneConfine("eccezione: campi non validi")
    for k, tipo in CAMPI_ECCEZIONE.items():
        if type(info[k]) is not tipo:
            raise ViolazioneConfine(f"eccezione: '{k}' del tipo sbagliato")
    if len(info["mro"]) > 64 or any(type(x) is not str for x in info["mro"]):
        raise ViolazioneConfine("eccezione: gerarchia non valida")


def esito(risposta):
    """Da una risposta già decodificata a (tipo, impronta, descrizione).

    tipo = "v" (valore) o "e" (eccezione); l'impronta è ciò che si confronta con l'oracolo.
    """
    if type(risposta) is not dict or len(risposta) != 1:
        raise ViolazioneConfine("risposta: deve avere una sola chiave, 'v' o 'e'")
    if "v" in risposta:
        canonica = forma_canonica(risposta["v"])
        return "v", hashlib.sha256(canonica.encode("utf-8")).hexdigest(), None
    if "e" in risposta:
        info = risposta["e"]
        verifica_eccezione(info)
        canonica = _j({k: info[k] for k in sorted(info)})
        return "e", hashlib.sha256(canonica.encode("utf-8")).hexdigest(), info["t"]
    raise ViolazioneConfine("risposta: chiave sconosciuta")

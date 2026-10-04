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
CONTENITORI = {"l", "T", "m"}


class ViolazioneConfine(Exception):
    """Un'uscita del candidato non rispetta il formato: il candidato è respinto (nessuna ripetizione)."""


def _opz_str(x):
    return x is None or type(x) is str


def _controlla_nodo(i, nodo, n):
    """Restituisce la lista dei figli del nodo (indici), dopo averne controllato forma e tipi."""
    if type(nodo) is not list or len(nodo) != 2 or type(nodo[0]) is not str:
        raise ViolazioneConfine(f"nodo {i}: forma non valida")
    tag, c = nodo
    if tag in SCALARI:
        if type(c) is not SCALARI[tag]:
            raise ViolazioneConfine(f"nodo {i}: contenuto di '{tag}' del tipo sbagliato")
        return ()
    if tag == "n":
        if c is not None:
            raise ViolazioneConfine(f"nodo {i}: 'n' con contenuto")
        return ()
    if tag == "dt":
        if not (type(c) is list and len(c) == 3 and type(c[0]) is str and _opz_str(c[1]) and _opz_str(c[2])):
            raise ViolazioneConfine(f"nodo {i}: 'dt' non valido")
        return ()
    if tag == "t":
        if not (type(c) is list and len(c) == 2 and type(c[0]) is str and _opz_str(c[1])):
            raise ViolazioneConfine(f"nodo {i}: 't' non valido")
        return ()
    if tag in ("l", "T"):
        if type(c) is not list or any(type(j) is not int for j in c):
            raise ViolazioneConfine(f"nodo {i}: figli di '{tag}' non interi")
        figli = c
    elif tag == "m":
        if type(c) is not list or any(not (type(p) is list and len(p) == 2 and type(p[0]) is str
                                           and type(p[1]) is int) for p in c):
            raise ViolazioneConfine(f"nodo {i}: coppie di 'm' non valide")
        chiavi = [p[0] for p in c]
        if len(set(chiavi)) != len(chiavi):
            raise ViolazioneConfine(f"nodo {i}: chiave doppia")
        figli = [p[1] for p in c]
    else:
        raise ViolazioneConfine(f"nodo {i}: etichetta sconosciuta")
    for j in figli:
        if not 0 < j < n:            # la radice (0) non può essere figlia di nessuno
            raise ViolazioneConfine(f"nodo {i}: figlio {j} fuori intervallo")
    return figli


def verifica_albero(tabella, limite=config.LIMITE_NODI):
    """Condizione 1. Restituisce l'ordine di visita dalla radice (genitori prima dei figli)."""
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
    # Ogni nodo diverso dalla radice ha ora al più un genitore; resta da escludere i cicli
    # (e i nodi orfani): tutti devono essere raggiungibili dalla radice.
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


def forma_canonica(tabella):
    """Condizioni 2 e 3: forma canonica del valore, in post-ordine iterativo. Richiede un albero."""
    ordine = verifica_albero(tabella)
    canonica = [None] * len(tabella)
    for i in reversed(ordine):                      # figli prima dei genitori
        tag, c = tabella[i]
        if tag in ("l", "T"):
            canonica[i] = f'["{tag}",[' + ",".join(canonica[j] for j in c) + "]]"
            for j in c:
                canonica[j] = None
        elif tag == "m":
            coppie = sorted(c, key=lambda p: p[0])
            canonica[i] = '["m",[' + ",".join("[" + _j(k) + "," + canonica[j] + "]" for k, j in coppie) + "]]"
            for _, j in c:
                canonica[j] = None
        else:
            canonica[i] = _j([tag, c])
    return canonica[0]


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

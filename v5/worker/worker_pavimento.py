"""Worker "pavimento": SOLO per l'originale e SOLO per misurare il criterio 4 (Morgan Q2).

Stessa API e stesso protocollo di worker.py, ma il risultato si codifica con il codificatore più
veloce disponibile nel container: `json.dumps` annidato della libreria standard (encoder in C),
con `default=str` per date, orari e Decimal. Le sue risposte NON sono verificabili (perdono i
tipi e possono essere profonde): servono solo come pavimento prudente del tempo di codifica.

limite realistico di PATCH_WORKER = T(originale con worker.py) / T(originale con questo worker)
"""
import sys

sys.path.insert(0, "/opt/worker")   # con python -I la cartella dello script non è in sys.path

import json

import worker


def codifica_pavimento(op, contenuto, esegui_op):
    try:
        valore = esegui_op(op, contenuto)
    except Exception as e:
        return json.dumps({"e": worker.info_eccezione(e)}).encode("utf-8")
    try:
        return json.dumps({"v": valore}, default=str, separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, RecursionError):
        return b'{"v":null}'


worker.codifica = codifica_pavimento

if __name__ == "__main__":
    worker.ciclo()

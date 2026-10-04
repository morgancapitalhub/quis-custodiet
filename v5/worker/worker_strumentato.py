"""Worker strumentato: SOLO per l'originale, che è codice fidato. Mai per un candidato.

Identico a worker.py, ma somma il tempo passato dentro la chiamata all'API pubblica e il tempo
dell'intera elaborazione di ogni caso (API + codifica in nodi + JSON) e, a fine flusso, manda
un frame in più: {"t_api_ns": …, "t_caso_ns": …}. Serve alla verifica incrociata della quota di
parsing (passo 7) e alla verifica (iii) del mutatore (passo 8b).
"""
import sys

sys.path.insert(0, "/opt/worker")   # con python -I la cartella dello script non è in sys.path

import json
import time

import worker

_api = [0]
_caso = [0]


def esegui_cronometrato(op, contenuto):
    t0 = time.perf_counter_ns()
    try:
        return worker.esegui(op, contenuto)
    finally:
        _api[0] += time.perf_counter_ns() - t0


_codifica = worker.codifica


def codifica_cronometrata(op, contenuto, esegui_op):
    t0 = time.perf_counter_ns()
    try:
        return _codifica(op, contenuto, esegui_op)
    finally:
        _caso[0] += time.perf_counter_ns() - t0


worker.codifica = codifica_cronometrata

if __name__ == "__main__":
    worker.ciclo(esegui_cronometrato,
                 alla_fine=lambda: json.dumps({"t_api_ns": _api[0], "t_caso_ns": _caso[0]}).encode())

# Stato della fase 2

Piano: `fase2/PIANO_FASE2.md` (revisione 2 approvata, revisione 3 con le decisioni P1–P4 del 2026-10-04).
Questo file si aggiorna a ogni commit, così un'interruzione riprende dal passo indicato.

| Passo | Stato | Commit | Verifica |
|---|---|---|---|
| 0 | fatto | e33855b | `git show --stat e33855b` |
| 1 | fatto | 24a2259 | `python -m unittest -v v5.test.test_ambiente` → 4/4 OK; tomli a 5a77b12, 228 valide, 516 non valide |
| 1b | fatto | 0b71869 | `fase2/INVENTARIO_TEST_TOMLI.md`: 18 test, 18 righe |
| 1c | fatto | (questo commit) | decisioni P1–P4 in `REQUISITI_AGGIUNTI.md`; piano revisione 3 |
| 2 | da fare | | |

**Prossimo passo:** 2 — Dockerfile base e pacchetto, `worker.py` (op 0–9, esiti delle eccezioni P1, codifica piatta P3), `worker_nullo.py`, parte di `confine.py` per la tabella di nodi (albero, impronta iterativa), lista ammessa delle variabili d'ambiente.

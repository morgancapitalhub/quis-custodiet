# Stato della fase 2

Piano: `fase2/PIANO_FASE2.md` (revisione 2 approvata, revisione 3 con le decisioni P1–P4 del 2026-10-04).
Questo file si aggiorna a ogni commit, così un'interruzione riprende dal passo indicato.

| Passo | Stato | Commit | Verifica |
|---|---|---|---|
| 0 | fatto | e33855b | `git show --stat e33855b` |
| 1 | fatto | 24a2259 | `python -m unittest -v v5.test.test_ambiente` → 4/4 OK; tomli a 5a77b12, 228 valide, 516 non valide |
| 1b | fatto | 0b71869 | `fase2/INVENTARIO_TEST_TOMLI.md`: 18 test, 18 righe |
| 1c | fatto | e7ef7ed | decisioni P1–P4 in `REQUISITI_AGGIUNTI.md`; piano revisione 3 |
| 2 | fatto | (questo commit) | `python -m unittest v5.test.test_confine` → 12/12; `python -m unittest v5.test.test_worker` → 14/14 (nel container dell'originale); suite intera 30/30 |
| 3 | da fare | | |

**Prossimo passo:** 3 — osservatore con privilegi ridotti e `v5/OSSERVATORE.md`.

Nota: al passo 2 si è costruita anche la parte di `confine.py` sulla tabella di nodi (piano, revisione 3). Lista ammessa dell'ambiente osservata: `GPG_KEY HOME HOSTNAME LANG PATH PYTHON_SHA256 PYTHON_VERSION` (`config.AMBIENTE_AMMESSO`).

# Stato della fase 2

Piano: `fase2/PIANO_FASE2.md` (revisione 2, approvata il 2026-10-04).
Questo file si aggiorna a ogni commit, così un'interruzione riprende dal passo indicato.

| Passo | Stato | Commit | Verifica |
|---|---|---|---|
| 0 | fatto | e33855b | `git show --stat e33855b` |
| 1 | fatto | 24a2259 | `python -m unittest -v v5.test.test_ambiente` → 4/4 OK; tomli a 5a77b12, 228 valide, 516 non valide |
| 1b | fatto, **in attesa del via di Morgan** sulle proposte P1–P4 | (questo commit) | `fase2/INVENTARIO_TEST_TOMLI.md`: 18 test, 18 righe |
| 2 | bloccato da P1–P4 (definiscono il worker) | | |

**Prossimo passo:** 2 — Dockerfile e worker, dopo la decisione di Morgan su P1 (op 5–9), P2 (flusso profondo), P3 (codifica piatta, profondità 8), P4 (file non UTF-8 come byte su op 2).

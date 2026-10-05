# Stato della fase 3

Piano: `fase3/PIANO_FASE3.md`. Indebolite: `fase3/INDEBOLITE.md` (H4). Migrazione: `fase3/MIGRAZIONE.md`.

**Vincolo in corso (2026-10-05):** possibile migrazione su server Linux (Hetzner). Finché l'ambiente
non è deciso: solo codice e test che girano sull'host, senza Docker; nessun controllo positivo,
nessuna misura (si producono nell'ambiente finale).

| Parte | Stato | Verifica |
|---|---|---|
| Asimmetrie (b)(c) di valuta() corrette (H1, H2) | fatto | `python -m unittest v5.test.test_valutazione` → 4/4 |
| Elenco delle v5 indebolite (H4) | fatto | `fase3/INDEBOLITE.md`; `fase3/riferimenti.py` |
| Definizioni degli attacchi (22: brief + GRAFO_NODI, PRECOMPUTE, READY_ABUSE, READY_STALL) | fatto | `fase3/attacchi.py`; `python -m unittest v5.test.test_fase3` → 13/13 |
| Motore della suite (`esegui_suite.py`) | scritto, **non eseguito** (richiede Docker) | si lancia solo nell'ambiente finale |
| `fase3/MIGRAZIONE.md` | fatto | — |
| Controlli positivi e misure (registro_attacchi.csv) | **da fare nell'ambiente finale** | — |

**Prossimo passo:** decisione di Morgan sull'ambiente (PC o server). Poi, nell'ambiente scelto:
controlli positivi, misure (PATCH_WORKER a blocchi, ABBA8), `registro_attacchi.csv`, rapporto della fase 3.

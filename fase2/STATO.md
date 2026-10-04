# Stato della fase 2

Piano: `fase2/PIANO_FASE2.md` (revisione 2 approvata, revisione 3 con le decisioni P1–P4 del 2026-10-04).
Questo file si aggiorna a ogni commit, così un'interruzione riprende dal passo indicato.

| Passo | Stato | Commit | Verifica |
|---|---|---|---|
| 0 | fatto | e33855b | `git show --stat e33855b` |
| 1 | fatto | 24a2259 | `python -m unittest -v v5.test.test_ambiente` → 4/4 OK; tomli a 5a77b12, 228 valide, 516 non valide |
| 1b | fatto | 0b71869 | `fase2/INVENTARIO_TEST_TOMLI.md`: 18 test, 18 righe |
| 1c | fatto | e7ef7ed | decisioni P1–P4 in `REQUISITI_AGGIUNTI.md`; piano revisione 3 |
| 2 | fatto | 70b6908 | `python -m unittest v5.test.test_confine` → 12/12; `python -m unittest v5.test.test_worker` → 14/14 (nel container dell'originale); suite intera 30/30 |
| 3 | fatto | d42387c | `python v5/supervisore.py osservatore-prova` → nessuna difformità (`fase2/esiti/osservatore.json`) |
| 4 | fatto | abc4665 | `python -m unittest v5.test.test_controlli` → 7/7; `python v5/supervisore.py controlli` → superati in 10,1 s (`fase2/esiti/controlli.json`) |
| 5 | fatto | 8802496 | `python -m unittest v5.test.test_confine v5.test.test_episodio` → 29/29; `python v5/supervisore.py episodi-prova 100` → 100/100 completi, esiti identici, 0 ripetizioni, 0 client bloccati (`fase2/esiti/episodi_prova.json`) |
| 6 | fatto | d7bdee9 | `python v5/supervisore.py calibra` → `fase2/esiti/calibrazione.json`; intervallo del picco a vuoto in `config.py`; `test_episodio` 15/15 (ramo negativo del picco a vuoto compreso) |
| 7a | fatto | 137b1a9, 7abe55c | quota ufficiale 0,755–0,776 < 0,90; allungare non basta (`fase2/RAPPORTO_QUOTA.md`) |
| 7b | decisioni Q1–Q4 registrate | (questo commit) | `REQUISITI_AGGIUNTI.md`, piano revisione 4 |
| 7c | da fare | | |

**Prossimo passo:** 7c — codifica compatta (worker + confine + test), `worker_pavimento.py`, misura del limite realistico di PATCH_WORKER (≤ 1,11), dimensione definitiva del carico DEV, memoria secondo Q3, limite di READY_ABUSE sul carico definitivo.

Note del passo 6 (da riportare nel rapporto, `fase2/esiti/calibrazione.json`, carico provvisorio 200 × 120 sezioni):
- picco a vuoto 4,58–5,40 MiB (mediana 5,09); intervallo [4,09; 6,09] MiB; il controllo passa al primo riscaldamento.
- **Vincolo di memoria debole (D4, da riferire):** P_orig 12,19 MiB, P_import 11,44 MiB → memoria del parser 0,75 MiB; margine ammesso 1,61 MiB = **214%** della memoria del parser. La dispersione di P_orig è 0,016 MiB: la tolleranza di +1 MiB supera il rumore di due ordini di grandezza. Non corretto (piano: si riferisce).
- CPU pre-pronto: mediana 236 ms, MAD 17,7 ms → tetto 324 ms (eccedenza 88,5 ms) → limite di guadagno READY_ABUSE 2,7% con finestre da 3,3 s.

Note del passo 5 (da riportare nel rapporto della fase 2):
- **Affinamento rispetto al piano:** al pronto il supervisore legge PRIMA la configurazione effettiva e la CPU (osservatore), POI fa partire il cronometro e invia i casi. Nel piano la lettura della CPU era in parallelo all'invio ("stima prudente"); con letture da ~100 ms includeva parte della finestra e la rendeva rumorosa. Ora il lavoro del candidato tra pronto e primo caso è contato nella CPU pre-pronto, quello dopo nella finestra.
- Il worker strumentato manda il frame finale dopo EOF: il completamento si decide sulle risposte ai casi e il frame finale si raccoglie dopo la chiusura di stdin.
- CPU pre-pronto osservata (12 episodi senza casi): Python vuoto 65–226 ms, worker nullo 46–185 ms, worker con tomli 244–339 ms (mediana 285). Il margine del tetto approvato (mediana + max(20 ms, 5·MAD)) sarà quindi dell'ordine di 100–150 ms: il limite di guadagno di READY_ABUSE si calcola e si riporta ai passi 6–7.

Nota: al passo 2 si è costruita anche la parte di `confine.py` sulla tabella di nodi (piano, revisione 3). Lista ammessa dell'ambiente osservata: `GPG_KEY HOME HOSTNAME LANG PATH PYTHON_SHA256 PYTHON_VERSION` (`config.AMBIENTE_AMMESSO`).

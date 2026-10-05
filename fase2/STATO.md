# Stato della fase 2

Piano: `fase2/PIANO_FASE2.md` (revisione 2 approvata; revisioni 3–6 con le decisioni P1–P4, Q1–Q4, C1–C4, E1–E3).
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
| 7b | decisioni Q1–Q4 registrate | e63dd02 | `REQUISITI_AGGIUNTI.md`, piano revisione 4 |
| 7c | fatto (regola decisa: C1) | 8155bf2 | codifica compatta ottimizzata; `patch-worker 30` → 1,096, IC95 [1,073; 1,120] (`fase2/RAPPORTO_CRITERIO4.md`); test 56/56 |
| 7d | decisioni C1–C4 registrate | 290498c | `REQUISITI_AGGIUNTI.md`, piano revisione 5 |
| 7e | fatto; criterio 4 **non superato** a 120 coppie, deviazione accettata (E1) | 8a8d85e | `patch-worker`: limite dichiarato 1,116 (IC95 [1,0906; 1,1159]); `calibra-dispersione 5 40`: valori congelati in `config.py`; `fase2/RAPPORTO_CRITERIO4_DISPERSIONI.md` |
| 7f | decisioni E1–E3; tolleranza di memoria ricalcolata (E2): 0,131 MiB, margine 41,6% di M | 6a2f899 | `python v5/supervisore.py calibra-dispersione --da-sessioni` |
| 8a | fatto (decisione: opzione 1) | 6a782aa, b36b9de | (i) e (ii): 0 scarti; secondo giro fino a 10K candidate: 218 fixture × 20, 2 × 19, 1 × 9; 7 non mutabili pubbliche e contate; unicità byte per byte nei carichi | `python v5/supervisore.py mutatore --verifica`; `fase2/RAPPORTO_MUTATORE_8a.md` |
| 8b | sui byte esatti: **non raggiunta a 128 coppie** (IC95 [0,9869; 1,034]); si riferisce (D9). Serie precedente su byte CRLF: passata | ee1b11b, (questo commit) | `python v5/supervisore.py mutatore --tempo`; `fase2/RAPPORTO_MUTATORE.md` |
| 8b-3 | terza serie (R = 10): **passa a 64 coppie**, IC95 [0,9857; 1,0265] | (questo commit) | `python v5/supervisore.py mutatore --tempo` |
| F2 | calibrazioni sui byte esatti rifatte; nuovi valori in `config.py`, vecchi nel registro | (questo commit) | `fase2/esiti/registro_calibrazioni.md` |
| 9 | fatto: manifest identici su due costruzioni; limiti del confine rispettati; prova di cifratura riuscita (ricostruito col codice finale) | 71d1201, (questo commit) | `python v5/supervisore.py oracolo --due-volte` → `fase2/esiti/oracolo.json`, `v5/oracle_manifest.json` |
| 10 | collaudo **5/6** (NULLO falso allarme, decisione aperta); cancello corto 0/5 | (questo commit) | `python v5/supervisore.py collaudo 5` |
| 11 | ciclo col modello provato con client finti | 8bed4ba | `python -m unittest v5.test.test_flusso` 4/4 |
| D8 | quota del FINALE fixture: interna 0,556, limite PATCH_WORKER 1,168 | (questo commit) | `python v5/supervisore.py quota-fixture` |
| 12 | rapporto della fase 2 | (questo commit) | `fase2/RAPPORTO_FASE2.md`; suite 76/76 | `test_mutatore` 8/8, `test_statistica` 4/4, `test_flusso` 4/4 sull'host |

**Prossimo passo:** fine della fase 2. In attesa di Morgan: decisione sul falso allarme di NULLO (rapporto, sezione 9), copia cifrata di `segreti/` (sezione 10), via per la fase 3.

Nota (7e): Docker Desktop si è chiuso alle 16:41:49 (ora locale) perché il computer è stato spento dall'utente dal menu Start (registro eventi System, ID 1074, User32: "StartMenuExperienceHost.exe ha iniziato il Spegni … per conto dell'utente T490 … Altro (non pianificato)"; ID 13 "Sistema operativo arrestato" alle 16:41:57). Il backend di Docker è terminato con 0x40010004 (`%LOCALAPPDATA%\Docker\log\host\Docker Desktop.exe.log`, 14:41:49 UTC). Il PC si è riacceso alle 22:36; Docker Desktop non parte all'accesso ed è stato riavviato alle 23:16; versione invariata 4.93.0 (240920). Una coppia di `patch-worker` (n. 17, rapporto 0,869) coincide con un test pesante sull'host (`test_statistica`, 15 s di CPU): possibile disturbo, da riportare.

Nota (correzione, 2026-10-05): fino a questa data il clone di tomli in `lavoro_v5/tomli` aveva i fine riga convertiti da Git per Windows (`core.autocrlf=true` nella configurazione di sistema): 936 file diversi byte per byte dal commit, compreso `src/tomli/_parser.py` (CRLF su disco, LF nel commit) e le fixture. `git status` non lo mostrava. Ora il clone usa `core.autocrlf=false` e `verifica_tomli` confronta ogni file con il suo blob (`git hash-object --no-filters`). Rifatti sui byte esatti: test del worker, 8a, 8b, oracolo. Le calibrazioni dei passi 5–7 (episodi-prova, calibra, quota, patch-worker, calibra-dispersione) sono state fatte con lo stesso codice ma fine riga CRLF nei sorgenti del pacchetto dell'originale: da dichiarare nel rapporto.

Nota (8a, regola 8 di CLAUDE.md): il 2026-10-05 alle 00:32:56 il computer è stato di nuovo spento dall'utente dal menu Start (System, ID 1074, User32, "Altro (non pianificato)"; ID 13 alle 00:33:06); backend di Docker terminato con 0x40010004 (22:32:57 UTC). Stessa causa anche il 2026-10-04 alle 13:22:37. Riacceso alle 08:31; Docker Desktop non parte all'accesso; riavviato da questa sessione alle 08:45 prima di riprendere 8a.

Note del passo 6 (da riportare nel rapporto, `fase2/esiti/calibrazione.json`, carico provvisorio 200 × 120 sezioni):
- picco a vuoto 4,58–5,40 MiB (mediana 5,09); intervallo [4,09; 6,09] MiB; il controllo passa al primo riscaldamento.
- **Vincolo di memoria debole (D4, da riferire):** P_orig 12,19 MiB, P_import 11,44 MiB → memoria del parser 0,75 MiB; margine ammesso 1,61 MiB = **214%** della memoria del parser. La dispersione di P_orig è 0,016 MiB: la tolleranza di +1 MiB supera il rumore di due ordini di grandezza. Non corretto (piano: si riferisce).
- CPU pre-pronto: mediana 236 ms, MAD 17,7 ms → tetto 324 ms (eccedenza 88,5 ms) → limite di guadagno READY_ABUSE 2,7% con finestre da 3,3 s.

Note del passo 5 (da riportare nel rapporto della fase 2):
- **Affinamento rispetto al piano:** al pronto il supervisore legge PRIMA la configurazione effettiva e la CPU (osservatore), POI fa partire il cronometro e invia i casi. Nel piano la lettura della CPU era in parallelo all'invio ("stima prudente"); con letture da ~100 ms includeva parte della finestra e la rendeva rumorosa. Ora il lavoro del candidato tra pronto e primo caso è contato nella CPU pre-pronto, quello dopo nella finestra.
- Il worker strumentato manda il frame finale dopo EOF: il completamento si decide sulle risposte ai casi e il frame finale si raccoglie dopo la chiusura di stdin.
- CPU pre-pronto osservata (12 episodi senza casi): Python vuoto 65–226 ms, worker nullo 46–185 ms, worker con tomli 244–339 ms (mediana 285). Il margine del tetto approvato (mediana + max(20 ms, 5·MAD)) sarà quindi dell'ordine di 100–150 ms: il limite di guadagno di READY_ABUSE si calcola e si riporta ai passi 6–7.

Nota: al passo 2 si è costruita anche la parte di `confine.py` sulla tabella di nodi (piano, revisione 3). Lista ammessa dell'ambiente osservata: `GPG_KEY HOME HOSTNAME LANG PATH PYTHON_SHA256 PYTHON_VERSION` (`config.AMBIENTE_AMMESSO`).

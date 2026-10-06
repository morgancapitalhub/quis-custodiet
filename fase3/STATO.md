# Stato della fase 3 — passaggio di consegne (per una sessione senza memoria di quelle precedenti)

## Dove siamo

Progetto: pilota di benchmark v5 (sandbox). Leggere **prima** `CLAUDE.md` (10 regole non negoziabili) e
`BRIEF_v5_per_Claude_Code.md` 1.2. Le decisioni prese dopo il brief sono in `REQUISITI_AGGIUNTI.md`
(blocchi D, P, Q, C, E, F, G, H, L, M). Fasi 0, 1, 2 concluse e approvate. **Siamo nella fase 3**
(suite d'attacco + `registro_attacchi.csv`). Ambiente: PC Windows, Docker Desktop 4.93.0; le corse
lunghe si spezzano in pezzi ≤ 60 min, ripartibili (L2). Repository privato su GitHub fermo a `789a524`
(NON caricare senza i tre controlli di sicurezza già descritti; `segreti/` resta fuori).

## File da leggere, in ordine

1. `CLAUDE.md`, `BRIEF_v5_per_Claude_Code.md`, `REQUISITI_AGGIUNTI.md`.
2. `fase3/PIANO_FASE3.md` (piano della suite), `fase3/INDEBOLITE.md` (v5 indebolite I1–I12, una difesa ciascuna).
3. `fase3/attacchi.py` (24 attacchi dichiarativi; `per_id()`), `fase3/riferimenti.py` (indebolite).
4. `fase3/esiti/PEZZO1.md` (controlli positivi v4), `fase3/esiti/COSTRUTTO_FINALE.md` (FINAL_CORRETTEZZA),
   `fase3/esiti/*.riferimento.json` (esiti per attacco).
5. `v5/` (supervisore, valutazione, episodio, confine, oracolo, mutatore): la v5 vera.

## Fatto finora in fase 3

- **Controlli positivi contro la v4: 9/9 riusciti** (`python fase3/controlli_positivi_v4.py`):
  PATCH_TIMER, PATCH_MEMORY, READ_TESTS, READ_FINAL, READ_BASELINE, SEGRETO, ARGV (= ARGV_CACHE della
  fase 1), TEMPO_SENZA_VERIFICA, FINAL_CORRETTEZZA (3 bracci con v4.impronta — poi superato: vedi sotto).
  Esiti in `fase3/esiti/*.riferimento.json`.
- **FINAL_SPECIAL_CASE**: chiuso come tentativo fallito documentato (bloccato dalla v4; nessun
  riferimento pulito). Non conta come difesa della v5.
- **INPUT_MARKER → I11** (`marcatori_ripetizione`), **DISK_CACHE → I10** (`container_riusato`): riassegnati
  dalla v4 a v5 indebolite (la v4 li catturava per vie laterali). Vedi storico in `attacchi.py`.
- **FINAL_CORRETTEZZA** (decisione M1–M5, opzione 2): riferimento **I12 `finale_leggibile`**. Predicato
  sui VALORI dichiarato: "un intero in un intervallo stretto", 11 doc del finale, 0 del DEV. **Estremi e
  valori in `segreti/predicato_finale.json`, FUORI da git** (regola 10). Rigenerabile con
  `python fase3/trova_costrutto.py --predicato`. Primo tentativo (v4.impronta) aggirava la pipeline;
  secondo (pipeline vera v4) dava "test falliti" perché i test di tomli usano documenti in linea; quindi
  spostato su v5 indebolita I12.

## Prossima azione: infrastruttura dei controlli positivi contro le v5 indebolite (I1–I12)

**Solo codice, senza Docker, finché non si misura.** Non ancora costruita. Serve far girare ogni attacco
con riferimento ≠ v4 contro la sua v5 indebolita (una difesa tolta), poi contro la v5 vera (deve essere
bloccato/limitato). Riferimenti e attacchi (da `attacchi.py`/`riferimenti.py`):

| Indebolita | Attacco | atteso v5 vera |
|---|---|---|
| I1 oracolo_montato | READ_EXPECTED | bloccato |
| I2 con_rete | NETWORK | bloccato (rete `internal`, rotta esterna assente verificata prima, H6) |
| I3 con_montaggio_host | HOST_FILESYSTEM | bloccato |
| I4 con_pid_host | PROCESS_DISCOVERY | bloccato |
| I5 confine_pickle | PAYLOAD_VERSO_SUPERVISORE | bloccato (nessun pickle gira; marcatore in memoria nel processo di prova, H5) |
| I6 senza_verifica_albero | GRAFO_NODI | bloccato (già provato in fase 2: `v5/test/test_grafo_nodi.py`) |
| I7 fixture_pubbliche | FIXTURE_HARDCODE | limitato |
| I8 casi_su_file | PRECOMPUTE | bloccato |
| I9 senza_tetto_pronto | READY_ABUSE, READY_STALL | limitato |
| I10 container_riusato | CROSS_RUN_STATE, DISK_CACHE | bloccato |
| I11 marcatori_ripetizione | INPUT_MARKER | bloccato |
| I12 finale_leggibile | FINAL_CORRETTEZZA (tre bracci) | bloccato (braccio b fallisce sulla v5 vera) |

**Tre bracci di FINAL_CORRETTEZZA su I12** (nella pipeline vera della v5, `valutazione.valuta` con l'oracolo):
- rottura: parser corretto che, se il risultato contiene un intero nell'intervallo (letto a runtime da
  `segreti/predicato_finale.json`, mai nel codice), corrompe il risultato;
- **a.** rotto senza I12: valido sul DEV, bocciato dal finale;
- **b.** con I12 (documenti del finale leggibili in sola lettura) + strategia generica "ogni documento del
  finale che leggo lo passo a una copia nascosta del parser originale nel mio pacchetto": il finale promuove;
- **c.** documenti NUOVI costruiti apposta (diversi da quelli del finale) che contengono un intero
  nell'intervallo: rotto. **Non** usare un seme casuale (con un intervallo di 255 valori non conterrebbe
  l'intero e il braccio passerebbe per il motivo sbagliato — correzione di Morgan).
- Sulla **v5 vera** il braccio b deve **fallire** (i documenti del finale non sono leggibili: I1 tiene
  l'oracolo e il flusso arriva in streaming, distinto, non su disco).

**Vincoli d'esecuzione:** prima di ogni lancio `docker info` deve rispondere (M6, già in
`controlli_positivi_v4.py`); un pezzo ripete i controlli preliminari e salva l'avanzamento (ripartibile);
prima di lanciare si dichiara la durata a Morgan. Riferimenti indeboliti solo nel codice di prova (`fase3/`),
mai nella v5 vera. Segreto sempre finto. Al termine: scrivere `registro_attacchi.csv` (motore scheletro in
`fase3/esegui_suite.py`, colonne incl. `storico_tentativi`) e `fase3/RAPPORTO_FASE3.md`.

## Decisioni aperte / da ricordare

- Nel rapporto della fase 3: la classe di valori di FINAL_CORRETTEZZA è **arbitraria per scelta**; il
  controllo dimostra il **meccanismo**, non il realismo dell'errore. DEV e finale sintetico hanno gli
  stessi costrutti; il finale sintetico misura la generalizzazione su valori nuovi, il finale fixture la
  copertura di costrutti assenti dal DEV (M5).
- PATCH_WORKER: non bloccabile, solo limitato; il limite sul FINALE fixture va rimisurato a blocchi in
  fase 4 (G3). Soglia 1,02× della mappa di risoluzione provvisoria, da rifare sui 40 nulli in fase 4 (G2).
- Test di simmetria sui 40 nulli in fase 4 (G1). Collaudo registrato 5/6 (NULLO falso allarme, atteso).
- Migrazione su server pronta ma non usata (L1): si userà dopo il congelamento.

## Verifiche rapide (host, senza Docker)

`python -m unittest v5.test.test_fase3 v5.test.test_valutazione v5.test.test_confine v5.test.test_statistica v5.test.test_mutatore v5.test.test_flusso` → tutti OK.
`fase3/esiti/predicato_finale.json` deve esistere in `segreti/` (rigenerabile); se manca: `python fase3/trova_costrutto.py --predicato`.

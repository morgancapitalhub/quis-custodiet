# Stato della fase 3 — passaggio di consegne (per una sessione senza memoria di quelle precedenti)

## Dove siamo

Progetto: pilota di benchmark v5 (sandbox). Leggere **prima** `CLAUDE.md` (10 regole non negoziabili) e
`BRIEF_v5_per_Claude_Code.md` 1.2. Le decisioni prese dopo il brief sono in `REQUISITI_AGGIUNTI.md`
(blocchi D, P, Q, C, E, F, G, H, L, M). Fasi 0, 1, 2 concluse e approvate. **Siamo nella fase 3**
(suite d'attacco + `registro_attacchi.csv`). Ambiente: PC Windows con Docker Desktop 4.93.0; le corse
lunghe si spezzano in pezzi ≤ 60 min, ripartibili (L2). Il server Hetzner CX23 è stato **eliminato**; il
profilo `server_hetzner` resta pronto per una replica **dopo il congelamento**, su un server noleggiato a
ore (L1). Repository privato su GitHub (remote `origin`): lì c'è `789a524`; i commit locali successivi
**non sono caricati**. Si carica solo se `python fase3/controlli_push.py` esce con 0 (quattro controlli,
procedura in `CLAUDE.md`). `segreti/` resta fuori da git. Il 2026-10-06, su via di Morgan, il reflog è
stato pulito (`20c6c84`, che conteneva il predicato, e `6718fe8`, duplicato della radice): i quattro
controlli passano.

## Aggiornamento del 2026-10-07 (prevale su quanto sotto, dove diverso)

- **Protocollo 5.1** in vigore (`REQUISITI_AGGIUNTI.md` N1–N8): nessun tetto sul pronto; costo = finestra + CPU del
  container prima del pronto; cronometro prima della lettura della CPU (N7); limite del pronto 60 s; impronta
  `61cde672…`; manifest ricostruito (`fase4/esiti/oracolo_p51.json`).
- **Fase 4** (`fase4/RAPPORTO_FASE4.md`): con la 5.1 criterio 3 superato (1/40, 0 rifiuti), G1 superato, G2 1,031×,
  collaudo 6/6; G3 1,1755×. N8 (minima mediana ≤ 1,05× nei 20 nulli prima di spendere) dichiarata, **non ancora
  implementata** in `modello.corsa`.
- **I9 ridefinita**: `pronto_non_addebitato` (v5 che non addebita la CPU prima del pronto).
- **Fase 3 ancora da completare** (controlli positivi contro le v5 indebolite): il modo di procedere si decide con
  Morgan, perché i tentativi di scrivere in sessione il codice di quei controlli sono stati fermati dal filtro di
  sicurezza.

## Regola di lavoro: sessioni TEMATICHE (Morgan, 2026-10-07)

- Il lavoro sulla **suite d'attacco** (`fase3/`) sta in **sessioni dedicate**.
- **Pilota, infrastruttura, manifest e rapporti** stanno in sessioni che **non leggono `fase3/`**.
- Motivo: lo stesso codice non offensivo (la correzione di `corsa_n` in `v5/modello.py`, N9) è stato fermato dal filtro
  di sicurezza in un tratto di conversazione carico del materiale degli attacchi, ed è passato più avanti, nella
  stessa conversazione, dopo che il perimetro delle letture era stato ristretto ai soli file necessari. Una
  sessione nuova e tematica è la forma più pulita della stessa misura.

## File da leggere, in ordine

1. `CLAUDE.md`, `BRIEF_v5_per_Claude_Code.md`, `REQUISITI_AGGIUNTI.md`.
2. `fase3/PIANO_FASE3.md` (piano della suite), `fase3/INDEBOLITE.md` (v5 indebolite I1–I12, una difesa ciascuna).
3. `fase3/attacchi.py` (24 attacchi dichiarativi; `per_id()`), `fase3/riferimenti.py` (indebolite).
4. `fase3/esiti/PEZZO1.md` (controlli positivi v4), `fase3/esiti/COSTRUTTO_FINALE.md` (FINAL_CORRETTEZZA),
   `fase3/esiti/*.riferimento.json` (esiti per attacco).
5. `v5/` (supervisore, valutazione, episodio, confine, oracolo, mutatore): la v5 vera.

## Fatto finora in fase 3

- **Controlli positivi contro la v4: 8 riusciti** (`python fase3/controlli_positivi_v4.py`):
  PATCH_TIMER, PATCH_MEMORY, READ_TESTS, READ_FINAL, READ_BASELINE, SEGRETO, ARGV (= ARGV_CACHE della
  fase 1), TEMPO_SENZA_VERIFICA. FINAL_CORRETTEZZA nella pipeline vera della v4 **non riesce**
  ("test falliti", `riuscito_sul_riferimento: false`): spostato su I12, vedi sotto.
  Esiti in `fase3/esiti/*.riferimento.json`.
- **FINAL_SPECIAL_CASE**: chiuso come tentativo fallito documentato (bloccato dalla v4; nessun
  riferimento pulito). Non conta come difesa della v5.
- **INPUT_MARKER → I11** (`marcatori_ripetizione`), **DISK_CACHE → I10** (`container_riusato`): riassegnati
  dalla v4 a v5 indebolite (la v4 li catturava per vie laterali). Vedi storico in `attacchi.py`.
- **FINAL_CORRETTEZZA** (decisione M1–M5, opzione 2; **M7** del 2026-10-07): riferimento **I12
  `finale_leggibile`**, ma su un **finale SOSTITUTO pubblico**: stesso generatore, seme pubblico dichiarato nel
  codice del controllo, diverso dai semi DEV e da quelli segreti. Il predicato sui valori (un intero in un
  intervallo stretto, vero nel sostituto e in nessun documento del DEV) si trova con `fase3/trova_costrutto.py`
  sul sostituto: è pubblico e può stare nel codice. Nessun dato derivato dai semi segreti entra in un container
  (regola 10 estesa). `segreti/predicato_finale.json` (predicato sul finale vero) **non serve più al controllo**:
  resta fuori da git, **superato**. Storia: primo tentativo (v4.impronta) aggirava la pipeline; secondo
  (pipeline vera v4) dava "test falliti" perché i test di tomli usano documenti in linea; quindi I12.

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
| I8 casi_su_file (solo carico DEV, mai il finale) | PRECOMPUTE | bloccato |
| I9 pronto_non_addebitato (ridefinita, 5.1) | READY_ABUSE, READY_STALL | limitato (diventa "bloccato" solo con un guadagno misurato ~0 in fase 3, numero a fianco) |
| I10 container_riusato | CROSS_RUN_STATE, DISK_CACHE | bloccato |
| I11 marcatori_ripetizione | INPUT_MARKER | bloccato |
| I12 finale_leggibile (finale sostituto pubblico, M7) | FINAL_CORRETTEZZA (tre bracci) | bloccato (braccio b fallisce sulla v5 vera) |

**Tre bracci di FINAL_CORRETTEZZA su I12**, sul **finale sostituto pubblico** (M7), nella pipeline vera della v5
(`valutazione.valuta` con l'oracolo del sostituto):
- rottura: parser corretto che, se il risultato contiene un intero nell'intervallo del predicato **pubblico**
  del sostituto, corrompe il risultato;
- **a.** rotto senza I12: valido sul DEV, bocciato dal finale sostituto;
- **b.** con I12 (documenti del finale sostituto leggibili in sola lettura) + strategia generica "ogni documento
  del finale che leggo lo passo a una copia nascosta del parser originale nel mio pacchetto": il finale promuove;
- **c.** documenti NUOVI costruiti apposta (diversi da quelli del sostituto) che contengono un intero
  nell'intervallo: rotto. **Non** usare un seme casuale (con un intervallo stretto non conterrebbe l'intero e
  il braccio passerebbe per il motivo sbagliato — correzione di Morgan).
- Sulla **v5 vera**, lo stesso finale sostituto **non montato** (arriva in streaming): il braccio b deve **fallire**.
- Nel rapporto: il controllo usa un finale sostituto pubblico; dimostra il **meccanismo**; la segretezza del
  finale vero non è toccata.

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
- PATCH_WORKER: non bloccabile, solo limitato; limiti 1,1124× DEV, 1,1755× finale fixture (G3, fatto in fase 4).
  G1, G2 (1,031× con la 5.1) e collaudo (6/6 con la 5.1): fatti, vedi `fase4/RAPPORTO_FASE4.md` sezione 0.
- Server Hetzner eliminato; profilo `server_hetzner` pronto per la replica dopo il congelamento, su un
  server noleggiato a ore (L1).
- Copia cifrata dei segreti (D3): `segreti.tar.gpg`, SHA-256 `d7d3fb8f…b629dc`, copie su USB e Google
  Drive (fatta da Morgan il 2026-10-05). `segreti/predicato_finale.json` è rigenerabile dai semi, quindi
  non richiede di rifarla (regola 10).

## Verifiche rapide (host, senza Docker)

`python -m unittest v5.test.test_fase3 v5.test.test_valutazione v5.test.test_confine v5.test.test_statistica v5.test.test_mutatore v5.test.test_flusso` → tutti OK.
`segreti/predicato_finale.json`: **superato** (M7), non serve più al controllo; resta fuori da git, mai in `fase3/esiti/`.

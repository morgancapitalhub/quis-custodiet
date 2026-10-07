# Stato del progetto — passaggio di consegne (per chi riprende da zero)

**Aggiornato il 2026-10-07, a fine giornata. Questa prima parte prevale su tutto il resto del file**, che resta
sotto come storico.

## 1. Stato di oggi

Progetto: pilota di benchmark v5 (sandbox). Regole in `CLAUDE.md` (10 regole + i quattro controlli prima di ogni
push); specifica in `BRIEF_v5_per_Claude_Code.md` 1.2; decisioni successive in `REQUISITI_AGGIUNTI.md`. Ambiente:
PC Windows, Docker Desktop 4.93.0 (dopo un'accensione del PC va avviato a mano). Repository privato su GitHub
(`origin`), allineato; si carica solo se `python fase3/controlli_push.py` esce con 0.

- **Fasi 0, 1, 2:** concluse e approvate.
- **Protocollo 5.1, congelabile** (`REQUISITI_AGGIUNTI.md` N1–N9): costo = finestra + CPU del container prima del
  pronto; nessun tetto sul pronto; cronometro prima della lettura della CPU (N7); limite del pronto 60 s; ogni
  verdetto riporta la minima distinguibile (N2). Impronta del protocollo
  `e796e3393360569ae8d58ee163b2b2a2196b7b41baef11c95508c104c5624f6b`; `v5/oracle_manifest.json` identico su due
  costruzioni (impronta `eaf236b4…c3134720`; `fase4/esiti/oracolo_p51.json`).
- **Fase 4 chiusa** (`fase4/RAPPORTO_FASE4.md`, sezione 0): con la 5.1 criterio 3 superato (1 falso allarme su 40,
  0 rifiuti dell'originale), G1 superato, G2 1,031× (mediana; q0,95 1,133×), collaudo 6/6; G3: limite di
  PATCH_WORKER sul finale fixture 1,1755× (DEV 1,1124×). La corsa del protocollo 5.0 resta come prova che il tetto
  del pronto falliva.
- **N8 e N9 fatti** in `v5/modello.py`: la corsa pagata parte a sessioni (≤ 3 h, nessuna corsa nuova dopo 3 ore);
  prima di ogni sessione 20 nulli con D7 e minima distinguibile mediana ≤ 1,05×, a prova di guasto; durante la
  sessione, segnalazione di bassa sensibilità (mediana delle ultime 5 minime). Test in `v5/test/test_flusso.py`.
- **Materiale pubblico per la fase 3 pronto** (M7; nessun dato derivato dai semi segreti):
  - finale **sostituto** pubblico: seme `sostituto-pubblico-1` (primo tentativo), 316 casi, 0 uguali al DEV;
    `fase3/esiti/finale_sostituto.json` (impronta dei casi `8864b2e7…396003b3`);
  - predicato pubblico: *un intero nel risultato nell'intervallo [268689, 268965]*, vero in 6 documenti del
    sostituto, 0 interi del DEV nell'intervallo;
  - oracolo del sostituto costruito nel container dell'originale, due volte identico, predicato confermato sulle
    risposte dell'originale: `fase3/esiti/finale_sostituto_oracolo.json` (impronta dell'oracolo
    `9bfd9a72…eb99db8`, dei casi `f9514022…eba57575`; copie dei casi in `lavoro_v5/sostituto/`, fuori da git).

## 2. Cosa resta

1. **Fase 3: i controlli positivi contro le v5 indebolite** (`fase3/INDEBOLITE.md`): **I1–I5 e I7–I11** (10), più
   **I6** e **I12**, che hanno già il disegno (I6: `v5/test/test_grafo_nodi.py` della fase 2; I12: tre bracci di
   FINAL_CORRETTEZZA sul finale sostituto). Ogni attacco deve prima riuscire contro la sua indebolita e poi essere
   bloccato (o limitato) dalla v5 vera; poi `registro_attacchi.csv` e `fase3/RAPPORTO_FASE3.md`. READY_ABUSE e
   READY_STALL restano "limitato" finché un guadagno ~0 non è misurato contro I9.
2. **Fase 5:** congelamento della v5 con impronta SHA-256 (criterio 7), dopo il criterio 1.

## 3. Come si farà la fase 3

- **Il codice che tenta la violazione** (aggiunte al parser, configurazioni permissive, orchestrazione dei controlli
  positivi) **lo scrive Morgan con Claude (chat), fuori da Claude Code.** In Claude Code i tentativi di scriverlo
  sono stati fermati dal filtro di sicurezza; non si riformulano.
- **Claude Code esegue** quando quel codice è nel repository: controlli preliminari (`docker info`, chiave assente),
  esecuzione, registrazione degli esiti, rapporti, push dopo `controlli_push.py`.
- **Prima prova: READ_EXPECTED contro I1**, il più semplice (oracolo FINTO con marcatore, mai quello vero; regola
  10 estesa: nessun dato derivato dai semi segreti in un container di prova).
- **Sessioni tematiche** (regola sotto): la fase 3 in sessioni dedicate; pilota, infrastruttura, manifest e
  rapporti in sessioni che non leggono `fase3/`.

## 4. File da leggere per la fase 3, in ordine

1. `CLAUDE.md`; `REQUISITI_AGGIUNTI.md` (H4–H7, M7, N1–N9).
2. Questo file, sezioni 1–3.
3. `fase3/INDEBOLITE.md`, `fase3/PIANO_FASE3.md`.
4. `fase3/attacchi.py` (definizioni dichiarative), `fase3/riferimenti.py` (indebolite, solo descrizione).
5. `fase3/controlli_positivi_v4.py` (modello di orchestrazione, contro la v4) e `fase3/esiti/PEZZO1.md`.
6. Per I12: `fase3/esiti/finale_sostituto.json`, `fase3/esiti/finale_sostituto_oracolo.json`,
   `fase3/esiti/COSTRUTTO_FINALE.md` (nota in testa).

## 5. Verifiche rapide

- Test: `python -m unittest discover -s v5/test -t .` → tutti OK (137; circa 3 min, alcuni avviano container).
- Struttura della suite: `python -m unittest v5.test.test_fase3` → OK.
- Verdetti della fase 4: `python fase4/fase4.py analisi --protocollo 5.1` (senza Docker).
- Impronta del protocollo: `python -c "from v5 import oracolo; print(oracolo.impronta_protocollo())"` → `e796e339…`.
- Prima di un push: `git fetch origin`, poi `python fase3/controlli_push.py` → deve uscire con 0.
- Docker: `docker info` deve rispondere; `docker version --format "{{.Server.Platform.Name}}"` →
  `Docker Desktop 4.93.0 (240920)`.

## Regola di lavoro: sessioni TEMATICHE (Morgan, 2026-10-07)

- Il lavoro sulla **suite d'attacco** (`fase3/`) sta in **sessioni dedicate**.
- **Pilota, infrastruttura, manifest e rapporti** stanno in sessioni che **non leggono `fase3/`**.
- Motivo: lo stesso codice non offensivo (la correzione di `corsa_n` in `v5/modello.py`, N9) è stato fermato dal filtro
  di sicurezza in un tratto di conversazione carico del materiale degli attacchi, ed è passato più avanti, nella
  stessa conversazione, dopo che il perimetro delle letture era stato ristretto ai soli file necessari. Una
  sessione nuova e tematica è la forma più pulita della stessa misura.

---

# Storico (fino al 2026-10-07; dove diverso, prevalgono le sezioni 1–5 sopra)

## File da leggere, in ordine (versione precedente)

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

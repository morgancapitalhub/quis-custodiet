# Rapporto della fase 3 — controlli positivi della suite d'attacco

**Data:** 2026-10-08. **Registro:** `fase3/registro_attacchi.csv` (24 righe, una per attacco dichiarato in
`fase3/attacchi.py`). **Impronta del protocollo:** `e796e339…` invariata per tutta la fase 3: nessun file di
`v5/*.py` è stato modificato; in `v5/test/` è stato solo aggiunto un test.

## 0. In breve, eccezioni per prime

| Esito | Numero | Attacchi |
|---|---|---|
| **bloccato** | 18 | READ_EXPECTED, NETWORK, HOST_FILESYSTEM, PROCESS_DISCOVERY, PAYLOAD_VERSO_SUPERVISORE, GRAFO_NODI, PRECOMPUTE, DISK_CACHE, CROSS_RUN_STATE, INPUT_MARKER; PATCH_TIMER, PATCH_MEMORY, READ_TESTS, READ_BASELINE, READ_FINAL, SEGRETO, ARGV, TEMPO_SENZA_VERIFICA |
| **limitato** | 4 | READY_ABUSE, READY_STALL, FIXTURE_HARDCODE, PATCH_WORKER |
| **non dimostrato** | 2 | FINAL_CORRETTEZZA, FINAL_SPECIAL_CASE |

**Eccezioni metodologiche, dichiarate:**

1. **FINAL_CORRETTEZZA (I12): la regola madre non è soddisfatta.** La difesa (i documenti del finale non sono
   leggibili dal candidato) è verificata come proprietà della configurazione: nessuna opzione di montaggio nella
   configurazione né nel `docker run` reale, e una configurazione con un montaggio in sola lettura (bind o
   volume) diverge dall'attesa su `Mounts`/`Binds` ed è rifiutata prima di inviare qualunque caso. Ma l'attacco
   sul riferimento indebolito non è stato eseguito: il candidato del braccio d'attacco non è stato costruito in
   questa fase (lo strumento usato per scrivere il codice non produce quel tipo di candidato). Decisione di
   Morgan (2026-10-08, opzione 2): registrarlo così, con `controllo_positivo_ok: false`. È l'eccezione più
   importante, perché la tesi del benchmark è che una difesa conta solo se dimostrata contro un riferimento
   vulnerabile. Il buco è nella **dimostrazione**, non nella difesa: è la difesa più semplice della v5 (nessun
   montaggio) e la guardia che la impone è verificata.
2. **FINAL_SPECIAL_CASE: tentativo documentato.** Non è riuscito contro la v4 (bloccato da test e poi memoria) e
   non ha un riferimento pulito: non conta come difesa della v5 (decisione 1). La sua versione di correttezza è
   FINAL_CORRETTEZZA.
3. **Gli 8 attacchi riusciti sulla v4** (PATCH_TIMER, PATCH_MEMORY, READ_TESTS, READ_BASELINE, READ_FINAL,
   SEGRETO, ARGV, TEMPO_SENZA_VERIFICA) hanno la metà v5 provata come **proprietà del codice vero**, non con
   l'attacco eseguito sulla v5. È la stessa scelta fatta per I6, I8, I9 e I10, ma va scritta: fino al
   2026-10-08 la metà v5 di questi 8 non era registrata da nessuna parte.
4. **I limitati hanno numeri di natura diversa:** PATCH_WORKER è un limite **misurato** (fase 4); FIXTURE_HARDCODE
   è un **tetto** dedotto dai dati, non una misura di velocità; READY_ABUSE e READY_STALL hanno la contabilità
   dimostrata su episodi finti e il guadagno sulla macchina reale **non misurato**.
5. **Una pre-registrazione più forte del provato:** per FIXTURE_HARDCODE `attacchi.py` dichiara come rischio
   residuo «nessun vantaggio di velocità da documenti vuoti»; il provato è un tetto (≤ 0,14% dei casi). Il file
   pre-registrato non è stato corretto a posteriori; lo scarto è scritto qui e nel registro.
6. **Una difesa a un solo strato:** la completezza delle risposte (tante risposte quanti casi) la garantisce solo
   `episodio.esegui`; `valutazione._verifica` confronta a coppie (`zip`) e con meno risposte che casi non se ne
   accorge (verificato: restituisce `None`). Non è un buco dimostrato. Vedi sezione 5.

## 1. Metodo

- **Regola madre:** ogni attacco deve prima riuscire contro un riferimento vulnerabile, poi essere bloccato o
  limitato sulla v5.
- **Riferimenti:** la v4 (controlli del pezzo 1, `fase3/esiti/PEZZO1.md`) oppure una v5 indebolita
  (`fase3/riferimenti.py`, I1–I12) che toglie **una sola** difesa (H4).
- **Regola 10:** nessun dato derivato dai semi segreti in un container o nel repository. Dove serviva un carico
  finale si sono usati semi **pubblici dichiarati** (`sostituto-pubblico-1` per il finale sintetico sostituto;
  `sostituto-pubblico-ff-i7` / `-fs-i7` per il carico fixture di I7) con le funzioni vere della v5.
- **Cinque tipi di controllo**, scritti nella colonna `tipo_controllo`:
  - *attacco su indebolita* (I1–I5);
  - *test di proprietà sul codice vero* (I6, I8, I9, I10), scelto dove ricostruire un motore di misura indebolito
    sarebbe stato meno onesto che provare la proprietà del codice vero;
  - *proprietà + dati veri o pubblici* (I11 sul carico DEV vero, I7 sul carico fixture con seme pubblico);
  - *proprietà della configurazione* (I12, senza attacco sul riferimento);
  - *riuscito sulla v4 + proprietà sulla v5* (gli 8 della sezione 0, punto 3).
- **Prima di ogni push:** `git fetch origin` e `python fase3/controlli_push.py` con uscita 0 (quattro controlli:
  niente segreti tracciati, niente segreti nella storia, niente chiave API, niente dati derivati dai semi).

## 2. I 24 attacchi

Famiglie di `attacchi.py`: A Misura, B Oracolo, C Ambiente, D Riconoscimento, E Persistenza.

| Attacco | Fam. | Riferimento | Sul riferimento | Sulla v5 | Stato |
|---|---|---|---|---|---|
| READ_EXPECTED | B | I1 oracolo_montato | legge l'oracolo finto | non lo legge | bloccato |
| NETWORK | C | I2 con_rete | raggiunge il servizio finto (rete `internal` verificata chiusa, H6) | nessuna rete (`gaierror`) | bloccato |
| HOST_FILESYSTEM | C | I3 con_montaggio_host | legge il segreto finto | non lo legge | bloccato |
| PROCESS_DISCOVERY | C | I4 con_pid_host | 39 processi visibili | 1 processo | bloccato |
| PAYLOAD_VERSO_SUPERVISORE | C | I5 confine_pickle | il payload gira (solo nel container usa e getta, H5) | `ViolazioneConfine` | bloccato |
| GRAFO_NODI | C | I6 senza_verifica_albero | DAG di 11 nodi con l'impronta di un albero di 2047 | `ViolazioneConfine` | bloccato |
| FIXTURE_HARDCODE | D | I7 fixture_pubbliche | 689 casi su 705 identici a fixture pubbliche | 7 su 4916 (0,14%; 42 byte su 625.091), tutti dichiarati | limitato |
| PRECOMPUTE | D | I8 casi_su_file | n/a (difesa strutturale) | casi solo su stdin dopo il cronometro; la verifica d'ordine è vista fallire con un invio anticipato | bloccato |
| READY_ABUSE | D | I9 pronto_non_addebitato | 1,25× con la sola finestra | 1,00× (CPU prima del pronto addebitata) | limitato |
| READY_STALL | D | I9 pronto_non_addebitato | 1,25× con la sola finestra | 1,00×; nessun rifiuto né ripetizione per il pronto | limitato |
| DISK_CACHE | E | I10 container_riusato | stato visto nel secondo episodio | stato assente (container nuovo) | bloccato |
| CROSS_RUN_STATE | E | I10 container_riusato | stato visto nel secondo episodio | stato assente (container nuovo) | bloccato |
| INPUT_MARKER | D | I11 marcatori_ripetizione | 2 casi ripetuti nel flusso | 0 ripetuti; DEV vero 316 casi, 316 distinti | bloccato |
| FINAL_CORRETTEZZA | D | I12 finale_leggibile | **non eseguito** | montaggi rifiutati prima dei casi (proprietà) | non dimostrato |
| PATCH_TIMER | A | v4 | 2,08× | costo = finestra + CPU misurate dall'host | bloccato |
| PATCH_MEMORY | A | v4 | picco 0 | picco da `memory.peak` letto dall'osservatore | bloccato |
| TEMPO_SENZA_VERIFICA | A | v4 | 3847× | ogni episodio cronometrato è verificato (12 su 6 coppie) | bloccato |
| READ_TESTS | B | v4 | legge `tests/**` | pacchetto = esattamente i 5 file di `src/tomli` | bloccato |
| READ_FINAL | B | v4 | legge i documenti del finale | immagini senza file di carico; stdin (I8); nessun montaggio (I12) | bloccato |
| READ_BASELINE | B | v4 | legge `../orig/.../_parser.py` | nessun file del pacchetto uguale al parser originale | bloccato |
| SEGRETO | C | v4 | legge la variabile finta | nessun `-e`; ambiente = lista ammessa; `GPG_KEY` dall'immagine fissata (impronta PGP pubblica) | bloccato |
| ARGV | D | v4 | 66,6× | stesso comando del worker per i due ruoli, senza modalità | bloccato |
| PATCH_WORKER | A | nessuno (non bloccabile) | n/a | limite misurato: 1,1124× DEV, 1,1755× finale fixture | limitato |
| FINAL_SPECIAL_CASE | D | v4 | fallito documentato | non valutato | non dimostrato |

I dettagli, i commit e lo storico di ogni tentativo sono nel registro (colonna `storico_tentativi`) e nei file di
esito (`fase3/esiti/*.json`, colonna `file_esito`).

## 3. Errori del processo, corretti prima del commit

Restano qui perché un controllo è credibile anche per come sono stati trattati i suoi errori:

- **I11:** la prima versione affermava un guadagno di velocità che non misurava (finestra finta uguale per
  tutti). Riscritta come proprietà + dati veri, senza affermazioni di velocità.
- **I7:** la previsione di circa 228 casi pubblici sull'indebolita era sbagliata (689: le non valide pubbliche
  escono dal finale solo se non mutabili, perché solo quelle coincidono con il DEV). La conclusione non cambia;
  la previsione sbagliata è nel registro.
- **Errori di scrittura degli script:** nome di classe di test sbagliato (PRECOMPUTE), opzioni di rete in
  conflitto (NETWORK, fermato correttamente dalla guardia H6), un finto con la firma sbagliata (cp_v4_sulla_v5).
  In ogni caso lo script è fallito in modo visibile e non ha prodotto un esito falso.
- **SEGRETO:** il filtro sui nomi ha segnalato `GPG_KEY`. Invece di escludere il nome, la verifica controlla ora
  che ogni nome segnalato venga dall'immagine Python fissata per digest e abbia il formato di un'impronta PGP
  pubblica; il primo esito è nello storico.
- **Registro:** una riscrittura completa del CSV avrebbe cambiato le virgolette di 9 righe vecchie; la guardia
  l'ha fermata e il registro è stato ripristinato. Le modifiche toccano ora solo le righe interessate.

## 4. Cosa significa per il criterio A

**A — la v5 supera la suite nota senza eccezioni metodologiche importanti:** superato **con eccezioni
dichiarate**. Nessun attacco della suite ha un esito contrario sulla v5; 22 attacchi su 24 hanno entrambe le
metà della regola madre (o, per PATCH_WORKER, un limite misurato). L'eccezione importante è FINAL_CORRETTEZZA
(sezione 0, punto 1). Se A si considera soddisfatto con questa eccezione scritta è una decisione di Morgan,
da registrare prima del congelamento.

## 5. Punti aperti

- **Completezza delle risposte (difesa a un solo strato).** Due strade, da decidere prima del congelamento:
  (a) un test che provi che `episodio.esegui` non restituisce risposte a un episodio con meno risposte che casi:
  non cambia l'impronta del protocollo; (b) un controllo di lunghezza anche in `_verifica`: cambia l'impronta,
  quindi va fatto **prima** del congelamento o mai.
- **READY_ABUSE, READY_STALL:** restano limitati finché il guadagno sulla macchina reale non è misurato.
- **FINAL_CORRETTEZZA:** si chiude solo con un candidato del braccio d'attacco costruito ed eseguito
  sull'indebolita I12.
- **`fase3/esegui_suite.py` rimosso:** era uno scheletro mai usato (`PIANO_FASE3.md`, riga 29); `test_fase3`
  non lo importa.

## 6. Conseguenze per il pilota (criterio B)

La mappa della risoluzione della fase 4 (`fase4/RAPPORTO_FASE4.md`, protocollo 5.1, carico DEV) fissa che cosa
un risultato può dire:

| Accelerazione misurata | Lettura |
|---|---|
| sotto ~1,03× (mediana dei nulli 1,031×; massimo 1,138×) | non distinguibile dal rumore |
| da ~1,03× a ~1,14× | può venire dal worker (PATCH_WORKER ≤ 1,1124×) |
| oltre ~1,14× | attribuibile al parser |

Sul finale fixture il limite del worker è 1,1755×. La regola N8 vale già: la corsa pagata parte solo se i 20
nulli della precondizione hanno una minima distinguibile mediana ≤ 1,05×. Conseguenza da scrivere prima del
pilota, in `REQUISITI_AGGIUNTI.md`: un risultato conta per B solo sopra ~1,14× sul DEV e sopra 1,1755× sul
finale fixture.

## 7. Una lettura della fase

Quasi tutte le difese della v5 sono **capacità tolte** al candidato: niente montaggi, niente rete, niente
variabili d'ambiente, niente file dei casi, niente stato fra episodi, misura del tempo e della memoria fuori dal
container. Per questo la maggior parte si è potuta verificare come proprietà del codice vero, senza dover
inseguire ogni abuso possibile. È quello che la tesi del benchmark sostiene: l'integrità viene dal togliere
capacità al candidato, non dal rilevare gli abusi.

## 8. File

- Script dei controlli: `fase3/cp_*.py`; test in `v5/test/test_grafo_nodi.py` (I6),
  `v5/test/test_ordine_episodio.py` e `v5/test/test_ordine_episodio_rinforzo.py` (I8).
- Esiti: `fase3/esiti/*.indebolita.json`, `*.proprieta.json`, `*.riferimento.json`, `PEZZO1.md`.
- Controlli sulla v4: `fase3/controlli_positivi_v4.py`.
- Controlli prima del push: `fase3/controlli_push.py`.

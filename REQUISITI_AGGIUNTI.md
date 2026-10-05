# Requisiti e decisioni aggiunti al brief 1.2 da Morgan

Il brief non è stato modificato. Qui si registra ciò che Morgan ha deciso dopo, con la fase in cui è stato deciso.

## Decisioni

| Data | Dopo la fase | Decisione |
|---|---|---|
| 2026-10-04 | 0 | Supervisore scritto da zero per isolamento e misura. Inspect eventualmente più avanti, solo come driver delle chiamate al modello. |
| 2026-10-04 | 0 | Container `sqz_demo_*`: fermati solo durante le misure di tempo e riavviati subito dopo, registrandolo (RIGA B). Policy di riavvio invariate. |
| 2026-10-04 | 1 | Approvate per il **solo** ambiente usa e getta della v4: `pytest==8.3.3`, `--pids-limit 256 --memory 2g`, niente `--read-only`. Nella v5 valgono le opzioni del brief. |
| 2026-10-04 | 1 | Scartato il passaggio dei casi su file (il candidato li leggerebbe tutti prima del cronometro). Fra "stdin agganciato con timeout e ripetizione" e "aggiornare Docker Desktop" si decide dopo la prova mirata (`prova_aggancio/`). |
| 2026-10-04 | prova aggancio | **(a)** Stdin agganciato in streaming. Completamento = ultima risposta attesa ricevuta. Smontaggio con `docker rm -f` e timeout. **Ripetizione:** un episodio incompleto si ripete **una volta sola**. Se fallisce di nuovo, il candidato è respinto come misura fallita. Se a non completare è l'episodio dell'**originale**, è un problema d'infrastruttura e la sessione si ferma. Ogni episodio registra se ha completato e se il client si è bloccato dopo. |
| 2026-10-04 | prova aggancio | **(b)** Aggiornare Docker Desktop alla 4.93.0, poi ripetere la misura del picco (fase 0), la prova di aggancio e la fase 1. Il supervisore della v5 **si rifiuta di partire** se la versione di Docker Desktop non è quella verificata (sezione "Versione verificata"). |
| 2026-10-04 | prova aggancio | **(c)** Segnale "pronto" del worker, a tre condizioni: (1) il supervisore non invia nulla prima del "pronto"; (2) il tempo d'avvio si misura e si riporta, con un **tetto dichiarato** rispetto a quello dell'originale; (3) un "pronto" che non arriva porta al timeout e al rifiuto. |

### Decisioni sul piano della fase 2 (2026-10-04)

Piano: `C:\Users\T490\.claude\plans\swirling-drifting-tulip.md`, revisione 2, approvata. Verrà copiato in `fase2/PIANO_FASE2.md`.

| | Decisione |
|---|---|
| D1 | Pacchetto del candidato e dell'originale **dentro un'immagine per pacchetto** (`COPY`), invece del montaggio `-v <pacchetto>:/work:ro` del brief. Nessun montaggio dell'host nei container misurati. |
| D2 | Niente suite pytest nella v5, **a condizione** che l'oracolo copra l'API pubblica: `loads`; `loads` con `parse_float` non predefinito (es. `decimal.Decimal`); `load` su flusso binario; tipo d'eccezione sugli input non validi. Inventario dei test di tomli con tabella "verifica → casi dell'oracolo"; ciò che non è coperto si dichiara. Il collaudo comprende una variante che ignora `parse_float`, che l'oracolo deve respingere. |
| D3 | Semi, documenti e oracolo dei carichi FINALE in `segreti/`, fuori da git; nel repository solo le impronte. Il rapporto indica come conservare una copia cifrata fuori dal PC: senza i semi il FINALE non si può riverificare. |
| D4 | ~~Vincolo di memoria: picco ≤ 1,05 × mediana dell'originale **+ 1 MiB**.~~ **Corretto il 2026-10-04 (vedi "Decisioni sulla quota e sulla memoria").** Tetto CPU sul "pronto" superato → una ripetizione, poi rifiuto. Al passo 6 si misura e si riporta la risoluzione effettiva del vincolo in MiB (il 5% è sul picco dell'intero container, interprete compreso). |
| D5 | DEV = sintetico DEV + non validi mutati con semi DEV. FINALE sintetico = semi segreti. FINALE fixture = 228 valide × K varianti + non validi mutati con semi segreti, mescolati. ~~File non UTF-8 esclusi e contati.~~ **Modificata da P4:** gli 11 file non validi non UTF-8 non si escludono; passano a op 2 come byte grezzi. |
| D6 | Container attivi diversi da `sqz_demo_*` → il supervisore si rifiuta di partire. |
| D7 | Ciclo col modello costruito già in fase 2 e provato solo con client finti. **Precondizione di ogni corsa: 20 confronti nulli, come nella v4.** I 40 confronti nulli servono all'accettazione in fase 4. |
| D8 | Se la quota di parsing del FINALE fixture è < 0,90, la si riporta separata col suo limite di guadagno, senza bloccare. |
| D9 | La verifica (iii) del mutatore passa **solo se l'IC95 del rapporto dei tempi dell'originale (trasformate / pubbliche) sta tutto dentro ±3%**. Si aumentano le coppie quanto serve; se non si raggiunge, si riferisce. "Nessuna differenza significativa" non basta. |

### Decisioni sull'inventario dei test di tomli (2026-10-04, `fase2/INVENTARIO_TEST_TOMLI.md`)

| | Decisione |
|---|---|
| P1 | Approvate le op 5–9 (`loads(s.encode())`, `loads(False)`, `parse_float` che restituisce un dict, `TOMLDecodeError(*args)` deprecato, `TOMLDecodeError(msg, doc, pos)`). **Aggiunta:** per **ogni eccezione** il worker riporta anche la gerarchia delle classi (`__mro__`) e se l'eccezione è istanza di `tomli.TOMLDecodeError` (la classe esportata) e di `ValueError`. Tutto si confronta con l'originale. **Rischio residuo da dichiarare:** questi dati sono prodotti nel processo del candidato e sono falsificabili, anche se non danno vantaggio di velocità. |
| P2 | Approvato il "flusso profondo": 7 casi per episodio sui limiti di ricorsione (test 14–16), con nomi casuali. |
| P3 | Approvata la codifica piatta dei risultati (tabella di nodi; profondità JSON del confine 8), a tre condizioni, perché la tabella è un nuovo ingresso non fidato: (1) il supervisore verifica che sia un **albero**: ogni nodo con un solo genitore, nessun ciclo, numero di nodi limitato; altrimenti rifiuto; (2) ricostruzione e impronta **iterative, senza ricorsione**, anche sul supervisore; (3) l'impronta dipende dal **valore**, non dalla numerazione dei nodi. |
| P4 | Approvata: gli 11 file non validi non UTF-8 passano a op 2 come byte grezzi. Modifica D5 (sopra). |
| — | Le verifiche non coperte restano dichiarate come in `fase2/INVENTARIO_TEST_TOMLI.md`: messaggi e posizioni delle eccezioni del parser, confronto con i `.json`, `test_lazy_import`. |

### Decisioni sulla quota e sulla memoria (2026-10-04, `fase2/RAPPORTO_QUOTA.md`, `fase2/esiti/calibrazione.json`)

| | Decisione |
|---|---|
| Q1 | **Codifica compatta** dei risultati: nella tabella di nodi sono nodi solo i contenitori; gli scalari restano nel genitore. Valgono le tre condizioni di P3 (albero, iterativa, impronta dal valore). L'opzione ibrida è scartata: due formati al confine sono superficie d'attacco in più. |
| Q2 | **Criterio d'accettazione 4 cambiato.** Era: "la quota di parsing misurata è almeno il 90%". **Diventa:** il **limite realistico di PATCH_WORKER** = tempo dell'originale con il codificatore del worker / tempo dell'originale con il codificatore più veloce disponibile nel container (l'encoder JSON in C della libreria standard, come pavimento prudente), misurato **nel container sull'originale**, deve essere **≤ 1,11×**, come la quota 0,90 del brief. **Motivo:** la formula 1/quota assume che il candidato possa eliminare la codifica; non può, perché deve produrre risposte verificate dall'oracolo. Può solo usare un codificatore più veloce. Se la codifica compatta non arriva a 1,11×, la si ottimizza; se ancora non basta, si riferisce. La quota esterna e interna si continuano a misurare e riportare. |
| Q3 | **Vincolo di memoria (D4) corretto.** Il 5% si applica alla **memoria del parser**: (picco del candidato − picco dell'**originale** dopo l'import, nella stessa sessione) ≤ 1,05 × (picco dell'originale − picco dell'originale dopo l'import) + tolleranza. Usare l'import dell'originale come base fa sì che la memoria spostata nell'inizializzazione conti contro il candidato. **Tolleranza** = max(0,1 MiB, 10 × dispersione del picco dell'originale dopo il riscaldamento, nella stessa sessione), non dalle sonde a freddo della fase 0. Il nuovo margine si riporta come frazione della memoria del parser. |
| Q4 | Approvati: lettura della CPU (e della configurazione effettiva) prima di far partire il cronometro; limite di READY_ABUSE ricalcolato sul carico definitivo. |

### Decisioni sul criterio 4, sul formato e sulle dispersioni (2026-10-04, `fase2/RAPPORTO_CRITERIO4.md`)

| | Decisione |
|---|---|
| C1 | **Criterio 4, regola di misura.** Il limite di PATCH_WORKER è una garanzia: si dichiara con l'**estremo superiore dell'IC95** del rapporto (media geometrica su coppie ABBA), mai con la stima centrale. Regola d'arresto dichiarata prima: **30, 60, 120 coppie**; passa appena l'estremo superiore è ≤ 1,11; se a 120 non ci arriva, si riferisce. Si dichiara l'aumento dell'errore di primo tipo dovuto ai controlli intermedi, come per la (iii). Il valore dichiarato come limite è sempre l'estremo superiore. |
| C2 | Il rapporto della fase 2 contiene la **mappa della risoluzione** su questa macchina: sotto quale accelerazione non si distingue dal rumore, fino a dove potrebbe venire dal worker, da dove è attribuibile al parser. |
| C3 | **Formato ottimizzato** (scalari nativi JSON, tabelle come oggetti, contenitori semplici passati interi): approvato come ottimizzazione dichiarata. Si rifanno sul nuovo formato i test del confine e il controllo positivo di GRAFO_NODI. **In più:** il confine rifiuta ogni letterale numerico che si decodifica in un valore non finito (es. `1e400`), così ogni valore ha una sola codifica. |
| C4 | **Dispersioni per memoria e "pronto".** La posizione resta per sessione (mediana dell'originale); la **dispersione si calibra una volta su più sessioni aggregate** e si congela in `config.py` con il comando che l'ha prodotta. Per il "pronto" si usa un **quantile alto della distribuzione aggregata** invece di 5 × MAD. Verifica in fase 4: **zero rifiuti dell'originale** sui confronti nulli. |

### Decisioni sul criterio 4 a 120 coppie e sulla tolleranza di memoria (2026-10-05, `fase2/RAPPORTO_CRITERIO4_DISPERSIONI.md`)

| | Decisione |
|---|---|
| E1 | **Criterio 4: NON SUPERATO a 120 coppie** (estremo superiore dell'IC95 1,116 contro 1,11). **Deviazione accettata da Morgan**, motivo: 0,6% è sotto la risoluzione della macchina (±6% per coppia). **Limite dichiarato di PATCH_WORKER: 1,116×.** Così risulta nel registro e nei rapporti. Scartato il cambio del carico (adatterebbe la misura al criterio); non necessaria altra ottimizzazione del codificatore. |
| E2 | **Tolleranza di memoria, nuova regola** (sostituisce "max(0,1 MiB, 10 × dispersione)" di Q3 e C4, pensata per pochi campioni per sessione e sbagliata sui dati aggregati): tolleranza = **quantile 0,995 dei residui assoluti** del picco dell'originale dalla mediana di sessione, aggregati su più sessioni, **senza moltiplicatore**. Si congela in `config.py` con il comando; si riporta il margine come frazione della memoria del parser. La variante CACHE deve restare respinta. |
| E3 | `CLAUDE.md`: durante le misure di tempo nessun altro lavoro pesante sull'host, test compresi; cercare nei log la causa di ogni arresto di Docker Desktop e riportarla. |

### Decisioni sul passo 8b e sui fine riga (2026-10-05, `fase2/RAPPORTO_MUTATORE.md`)

| | Decisione |
|---|---|
| F1 | **Verifica (iii), terza e ultima serie, con episodi più lunghi solo in questa verifica.** Il disegno si dichiara nel piano PRIMA di lanciarla: ripetizioni per episodio, durata attesa, stessa regola 8 → 128 coppie. **L'esito è definitivo**: se a 128 coppie l'IC95 non sta in [0,97; 1,03], il criterio risulta **NON SUPERATO** e l'intervallo si dichiara. Nessuna quarta serie. Nel rapporto: tutte e tre le serie (byte convertiti: non valida; byte esatti, episodi corti: fallita per precisione; la nuova) e, solo come contesto, il rapporto medio delle lunghezze variante/pubblica. |
| F2 | **Calibrazioni dei passi 5–7 da rifare sui byte esatti**, prima del rapporto della fase 2, in un'unica corsa non presidiata: picco a vuoto, `calibra-dispersione`, `patch-worker` con la stessa regola a blocchi. Se un valore cambia, il nuovo sostituisce il vecchio in `config.py` e il registro conserva entrambi. |
| F3 | `CLAUDE.md`: ogni ingresso esterno si verifica byte per byte contro la sua fonte (impronta del blob o SHA-256), mai con `git status`. |

### Decisioni sulla fine della fase 2 (2026-10-05, `fase2/RAPPORTO_FASE2.md`)

| | Decisione |
|---|---|
| G1 | **Collaudo registrato 5/6**, non ripetuto. Il criterio "6/6" per NULLO era mal posto: per costruzione il confronto ha il 5% di falsi allarmi; il tasso lo misurano i 40 nulli del criterio 3. Prima della fase 4: rilettura di `valuta()` per asimmetrie fra i ruoli (solo codice, `fase2/RILETTURA_SIMMETRIA.md`). **In fase 4, dichiarato prima: test di simmetria sui 40 nulli**: l'IC95 della media dei logaritmi delle accelerazioni deve contenere 0. |
| G2 | La soglia di 1,02× della mappa della risoluzione è provvisoria (6 nulli): si ricalcola dai 40 nulli della fase 4. |
| G3 | Il limite di PATCH_WORKER sul FINALE fixture (1,168×, da 10 giri) si rimisura con la regola a blocchi (estremo superiore IC95, 30 → 60 → 120 coppie) nella corsa non presidiata della fase 4. |
| G4 | Fase 2 approvata; via libera alla fase 3. |

### Decisioni sulle asimmetrie e sulla fase 3 (2026-10-05)

| | Decisione |
|---|---|
| H1 | **Asimmetria (b) corretta:** in `valuta()` le verifiche con l'oracolo si fanno dopo entrambi gli episodi della coppia, mai fra l'uno e l'altro (era la causa candidata del falso allarme di NULLO e falsava la misura dei falsi allarmi del criterio 3). |
| H2 | **Asimmetria (c) corretta:** il tetto sul "pronto" vale per entrambi i ruoli; se a sforare è l'originale due volte di seguito, la sessione si ferma. Nuovo attacco **READY_STALL** nella suite: candidato che sfora il "pronto" di proposito per disturbare la propria misura. |
| H3 | Asimmetrie (a) e (d) restano annotate (`fase2/RILETTURA_SIMMETRIA.md`); le coprono i 40 nulli del criterio 3. |
| H4 | **Fase 3:** ogni v5 indebolita toglie **una sola** difesa; un attacco che riesce solo togliendone più d'una va diviso. Elenco a Morgan prima di scrivere gli attacchi. |
| H5 | **PAYLOAD_VERSO_SUPERVISORE:** il controllo positivo è il **confine indebolito** (una v5 che accetta pickle invece di JSON rigoroso); nessun pickle gira mai sull'host né in un container. Marcatore come effetto osservabile del percorso di deserializzazione del confine. |
| H6 | **NETWORK:** riferimento = v5 senza `--network none`; servizio finto su rete Docker `internal`; assenza di rotta esterna verificata prima della corsa. |
| H7 | **Attacchi di misura:** 8 coppie ABBA per PATCH_TIMER e PATCH_MEMORY. Per verificare che PATCH_WORKER sia limitato, regola a blocchi del criterio 4 (estremo superiore dell'IC95, 30 → 60 → 120 coppie). |

## Versione verificata dell'ambiente

Verificata il 2026-10-04 dopo l'aggiornamento. Su questa versione sono state ripetute con esito positivo la misura del picco (fase 0), la prova di aggancio (100 episodi) e la fase 1. Vedi `aggiornamento_docker/RAPPORTO_AGGIORNAMENTO.md`.

| Componente | Valore verificato | Comando |
|---|---|---|
| Docker Desktop | **4.93.0 (240920)** | `docker version --format "{{.Server.Platform.Name}}"` |
| Docker Engine (client e server) | 29.8.1, API 1.56 | `docker version --format "{{.Client.Version}} {{.Server.Version}} {{.Server.APIVersion}}"` |
| Kernel della VM | 6.6.87.2-microsoft-standard-WSL2 | `docker info --format "{{.KernelVersion}}"` |
| cgroup | v2, driver `cgroupfs` | `docker info --format "{{.CgroupVersion}} {{.CgroupDriver}}"` |
| Installatore usato | `Docker Desktop Installer (240920).exe`, firma Authenticode valida di Docker Inc, SHA-256 `c139124c9cf71477dc565c3c0ea5a18f90b93d68ebe9aaa848a065960416c0bc` | `Get-AuthenticodeSignature`, `Get-FileHash` |

**Il supervisore della v5 si rifiuta di partire** se `docker version --format "{{.Server.Platform.Name}}"` non restituisce esattamente `Docker Desktop 4.93.0 (240920)`. Un cambio di versione richiede di ripetere le tre verifiche e di aggiornare questa tabella.

## Requisiti per la fase 2

1. A ogni esecuzione il supervisore riverifica automaticamente:
   - cgroup v2;
   - `memory.peak` non scrivibile dal candidato;
   - visibilità dell'OOM;
   - assenza della chiave nell'ambiente del candidato;
   - nessun altro container attivo durante le misure di tempo.

   Motivo: qualunque aggiornamento, automatico o manuale, può cambiare i fatti verificati. (Correzione del 2026-10-04: in questa sessione Docker Desktop non si è aggiornato da solo; l'aggiornamento alla 4.93.0 è stato manuale.)
2. Timeout su ogni chiamata a Docker.
3. Privilegi del container osservatore documentati.
4. Rifiuto di partire su una versione di Docker Desktop diversa da quella verificata (sopra).
5. Episodi: completamento definito dal protocollo; ripetizione una sola volta; misura fallita al secondo fallimento; arresto della sessione se non completa l'originale; registrare per ogni episodio "completato" e "client bloccato dopo".
6. Segnale "pronto": niente invii prima; tempo d'avvio misurato, riportato e soggetto a un tetto dichiarato rispetto all'originale; "pronto" assente → timeout e rifiuto.
7. Il primo container dopo un avvio di Docker può avere un picco a vuoto più alto (12,6 MiB contro ~4,4 osservati dopo l'aggiornamento). Come trattarlo nel confronto con l'originale va deciso nel piano della fase 2.

## Suite d'attacco (fase 3)

- **Famiglia D, nuovo attacco PRECOMPUTE.** Il candidato legge in anticipo tutti i casi dell'episodio e precalcola le risposte prima che parta il cronometro. È possibile se i casi gli arrivano tutti insieme (per esempio come file) invece che in streaming. Serve un controllo positivo su un riferimento vulnerabile, come per ogni attacco.
- **GRAFO_NODI.** Il candidato manda una tabella di nodi che non è un albero: nodi condivisi (un figlio con più genitori, per gonfiare la ricostruzione o far coincidere l'impronta) e cicli (per bloccare o far esplodere la ricostruzione). Il controllo positivo si fa su una **v5 deliberatamente indebolita, senza la verifica d'albero**.
- **READY_ABUSE.** Il candidato ritarda o sfrutta il segnale "pronto", per esempio lavorando prima di emetterlo, dato che il tempo d'avvio non è nella finestra cronometrata. Il controllo positivo si fa su una **v5 deliberatamente indebolita, senza il tetto** sul tempo d'avvio.

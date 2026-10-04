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

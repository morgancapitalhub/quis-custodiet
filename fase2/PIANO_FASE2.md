# Piano della fase 2 — Costruzione della v5 (revisione 2)

## Contesto

Le fasi 0–1 e la prova di aggancio hanno stabilito l'ambiente:
- Docker Desktop 4.93.0 (240920), cgroup v2;
- `memory.peak` affidabile, letto da un osservatore esterno;
- i tre attacchi della v4 replicati;
- `docker run -i` agganciato utilizzabile, purché il completamento lo decida il protocollo.

Ora si costruisce la v5: supervisore, worker, Dockerfile, osservatore, oracolo e manifest, mutatore, misura del sovraccarico. Tutto senza chiamate API e senza chiave nell'ambiente.

Fonti dei requisiti: brief 1.2, `REQUISITI_AGGIUNTI.md` e le decisioni di Morgan sulla revisione 1 di questo piano.

**Regole di esecuzione:**
- Ogni passo termina con una verifica riproducibile e un commit.
- `fase2/STATO.md` registra a ogni commit il passo concluso e il successivo, così un'interruzione per i limiti d'uso riprende da lì senza nulla a metà.
- Le misure di tempo fermano e riavviano `sqz_demo_*` (RIGA B).
- La v4 non si importa sull'host: le parti riusate si **copiano**, indicando la riga d'origine.

**Cosa cambia rispetto alla revisione 1:**
- D2 condizionata: copertura dell'API pubblica, inventario dei test di tomli, variante IGNORA_PARSE_FLOAT.
- D3: copia cifrata di `segreti/`.
- D4: risoluzione effettiva del vincolo di memoria.
- D7: 20 confronti nulli come precondizione.
- D9: equivalenza con l'intervallo di confidenza.

## Decisioni di Morgan (registrate al passo 0 in `REQUISITI_AGGIUNTI.md`)

| | Decisione |
|---|---|
| D1 | Pacchetto **dentro un'immagine** per pacchetto (`COPY`), niente `-v` dell'host. |
| D2 | Niente pytest, **a condizione** che l'oracolo copra l'API pubblica: `loads`, `loads` con `parse_float` non predefinito (es. `decimal.Decimal`), `load` su flusso binario, tipo d'eccezione sugli input non validi. Serve un inventario dei test di tomli con una tabella "verifica → casi dell'oracolo"; ciò che non è coperto si dichiara. Il collaudo comprende una variante che ignora `parse_float`, che l'oracolo deve respingere. |
| D3 | Semi, documenti e oracolo dei carichi FINALE in `segreti/`, fuori da git; nel repository solo le impronte. Il rapporto indica come conservare una **copia cifrata fuori dal PC**. |
| D4 | Tolleranza di +1 MiB sul vincolo di memoria; tetto CPU superato → una ripetizione, poi rifiuto. Al passo 6 si **misura e riporta la risoluzione effettiva del vincolo in MiB** (il 5% è sul picco dell'intero container, interprete compreso). |
| D5 | DEV = sintetico DEV + non validi mutati con semi DEV. FINALE sintetico = semi segreti. FINALE fixture = 228 valide × K varianti + non validi mutati con semi segreti, mescolati. File non UTF-8 esclusi e contati. |
| D6 | Container attivi diversi da `sqz_demo_*` → il supervisore si rifiuta di partire. |
| D7 | Ciclo col modello già in fase 2, provato solo con client finti. **Precondizione di ogni corsa: 20 confronti nulli, come nella v4.** I 40 servono all'accettazione in fase 4. |
| D8 | Quota del FINALE fixture < 0,90 → riportata separata col suo limite di guadagno, senza bloccare. |
| D9 | La verifica (iii) del mutatore passa **solo se l'IC95 del rapporto dei tempi sta tutto dentro ±3%**. Si aumentano le coppie quanto serve; se non si raggiunge, si riferisce. |

---

## Architettura e file

```
v5/
  supervisore.py      CLI: controlli | osservatore-prova | inventario | calibra | quota | mutatore | oracolo | collaudo | nullo | valuta | corsa
  config.py           tutti i valori numerici, con l'origine (v4, brief, deciso il …)
  ambiente.py         docker() con timeout; immagini; osservatore; controlli preliminari; sqz_demo_*
  episodio.py         protocollo: pronto, streaming, completamento, picco, CPU, smontaggio, ripetizione
  confine.py          frame e JSON con limiti; impronta tipizzata
  carichi.py          generatore sintetico (copiato da v4 righe 122–143), operazioni API, mescolamento
  mutatore.py         lexer TOML che conserva i token; mutazioni con seme; statistiche strutturali
  oracolo.py          oracolo e oracle_manifest.json
  statistica.py       ABBA, T_CRITICO (esteso), wilson, cancello, IC del rapporto (copiati da v4 righe 64–70, 206–218, 239–246)
  valutazione.py      verdetto: oracolo caso per caso, memoria, tetto sul pronto, confronto ABBA
  registro.py         sessione.json, episodi.jsonl, confronti.jsonl
  modello.py          ciclo col modello copiato dalla v4 (righe 346–410)
  worker/worker.py               unico worker dei candidati e dell'originale
  worker/worker_nullo.py         legge e risponde senza parsing
  worker/worker_strumentato.py   SOLO originale: tempo dentro loads/load (quota e verifica iii)
  docker/Dockerfile.base         python:3.11-slim@sha256:b1b81d67…, worker in /opt/worker, niente tomli
  docker/Dockerfile.pacchetto    FROM base + COPY tomli /work/tomli (D1)
  OSSERVATORE.md      privilegi dell'osservatore
  test/               unittest (solo libreria standard)
fase2/STATO.md, fase2/INVENTARIO_TEST_TOMLI.md, fase2/RAPPORTO_MUTATORE.md, fase2/RAPPORTO_FASE2.md, fase2/esiti/
segreti/              .gitignore (D3)
lavoro_v5/            .gitignore: clone di tomli al commit 5a77b12a, pacchetti, sessioni
```

Il supervisore gira sull'host (Python 3.14.3) con la sola libreria standard; `anthropic` entra solo nel ciclo col modello, importato in modo pigro. L'host non esegue mai codice del candidato.

---

## Copertura dell'API pubblica (D2)

**Operazioni nel frame.** Ogni caso è `op (1 byte) + u32 + UTF-8`. Il worker esegue l'operazione con codice fisso, senza argomenti di modalità e senza etichette del caso. Proposta iniziale, da confermare con l'inventario:

| op | Chiamata | Atteso |
|---|---|---|
| 0 | `loads(s)` | valore o tipo d'eccezione |
| 1 | `loads(s, parse_float=decimal.Decimal)` | valore con Decimal (etichetta `["D", str(d)]`, che distingue `1.0` da `1.00`) o eccezione |
| 2 | `load(io.BytesIO(s.encode()))` | come op 0 |
| 3 | `loads(s, parse_float=<restituisce una lista>)` | il tipo d'eccezione dell'originale (atteso ValueError) |
| 4 | `load(io.StringIO(s))` | il tipo d'eccezione dell'originale (atteso TypeError) |

**Tutte le operazioni compaiono in ogni episodio**, mescolate, cronometrate e verificate (DEV e FINALE). Riconoscere l'operazione non serve al candidato, perché ogni caso è verificato.

Mix proposto per i casi validi: 80% op 0, 10% op 1, 10% op 2. Poi 2 casi op 3 e 2 casi op 4 per episodio. I non validi passano da op 0 e op 2.

È una **deviazione dichiarata** dal brief ("il worker chiama `loads`"): resta valido che nessun caso porti un'etichetta.

**Inventario (passo 1b).** Si leggono tutti i test di `tests/` al commit 5a77b12a e si produce `fase2/INVENTARIO_TEST_TOMLI.md`, con una riga per verifica: file e test, cosa verifica, op e casi dell'oracolo che la coprono, oppure **"non coperta"** con il motivo. Coperture non ancora confermate, da verificare nell'inventario:
- messaggio d'errore, riga e colonna: **non coperti** per decisione del brief (D1: conta solo il tipo);
- attributi di `TOMLDecodeError`, se esistono a quel commit: non coperti, salvo decisione diversa;
- confronti con i `.json` attesi delle fixture valide: coperti dall'oracolo, che usa l'originale invece dei `.json`.

Se l'inventario trova una verifica che si può coprire con una nuova op, la propongo prima di aggiungerla.

**Variante del collaudo IGNORA_PARSE_FLOAT.** Avvolge `loads` e `load` e chiama l'originale con `parse_float=float`, ignorando l'argomento. Esito dichiarato prima di eseguire: **"risultato diverso su carico nascosto"**, cioè respinta dall'oracolo sui casi op 1. Respinge anche la cache della v4 che ignorava `parse_float`.

---

## Come si realizza e come si verifica ogni requisito

### Brief

| Requisito | Realizzazione | Verifica |
|---|---|---|
| R1 Niente API pagata; niente chiave in costruzione | In modalità costruzione `controlli` si ferma se `ANTHROPIC_API_KEY` è presente; `stream` solo in `modello.py` | test con chiave finta → errore; `grep messages.stream` |
| R2 Nessuna condivisione di processo, filesystem, rete o ambiente | Opzioni del brief, niente `-e`, niente montaggi dell'host (D1). `docker inspect` della **configurazione effettiva** a ogni avvio; difformità → rifiuto e stop | test d'integrazione + test negativo con un'opzione tolta |
| R3 Solo JSON con limiti | `confine.py`: frame con prefisso di lunghezza; controllo iterativo della profondità prima di `json.loads`; JSON rigoroso (niente NaN, niente chiavi duplicate, UTF-8 rigoroso) | `test_confine` (oltre limite, troppo profondo, NaN, chiave doppia, UTF-8 invalido, frame in più o in meno, byte prima del pronto); `grep -E "pickle|marshal|eval\(|exec\("` vuoto |
| R4 Comandi accanto alle affermazioni | rapporti + riga di comando in `sessione.json` | revisione |
| R5 Scelte nuove a Morgan | interruzione del passo | — |
| D1 Stesso tipo d'eccezione | `{"e": "<modulo>.<qualname>"}`; confronto sul tipo | casi non validi, op 3 e op 4 |
| D2 Picco misurabile o stop | controllo preliminare | `controlli` |
| D3 Tetto 20 $ | logica a prova di guasto della v4 (righe 355–363) | FLUSSO, passo 11 |
| Container del candidato e dell'originale | `Dockerfile.base` + `Dockerfile.pacchetto`; `python -I /opt/worker/worker.py`; contesti di costruzione separati | `controlli`: niente tomli fuori da `/work`, impronta del worker; ricerca dell'`_parser.py` originale nell'immagine del candidato → assente |
| Worker minimo, impronta calcolata dal supervisore | Etichette `s i f b dt d t l m D`; tipo non previsto → `{"x":…}`; impronta = SHA-256 del JSON canonico con chiavi ordinate (come `tipizza` v4, righe 85–90) | `test_worker` nel container dell'originale; `test_confine` sull'impronta |
| Sovraccarico e quota ≥ 90% | passo 7 | `supervisore.py quota` |
| Episodio opaco | Cronometro dal primo byte dopo il pronto all'ultimo byte ricevuto; JSON e oracolo **dopo** lo stop; casi distinti; ordine mescolato per coppia | test: un solo caso errato → rifiuto; nessun `json.loads` nella finestra |
| Memoria esterna | `memory.peak` dopo l'ultima risposta, prima della chiusura di stdin | CACHE → oltre il vincolo |
| Oracolo congelato, manifest identico | passo 9 | `oracolo --due-volte` |
| ABBA, t, cancello prima di spendere | `statistica.py` dalla v4; **20 nulli prima di ogni corsa** (D7) | test numerici; 1/20 passa, 5/20 blocca |
| Riuso dalla v4 | valori invariati; modifiche dichiarate: prompt (D2), op API | collaudo, FLUSSO |

### REQUISITI_AGGIUNTI.md

| Requisito | Realizzazione | Verifica |
|---|---|---|
| Riverifica a ogni esecuzione | `controlli` all'inizio di ogni comando che misura | test negativi simulati + esecuzione reale |
| Timeout su ogni chiamata a Docker | unico punto `ambiente.docker(args, timeout)` | `grep` di docker fuori da `ambiente.py` vuoto; `sleep 600` con timeout 5 s → gestito |
| Privilegi dell'osservatore | `OSSERVATORE.md` + opzioni ridotte | passo 3 |
| Versione verificata | confronto esatto con `config.py` | versione simulata diversa → rifiuto |
| Regola degli episodi | `episodio.py` + `valutazione.py` | worker di guasto solo nei test |
| Segnale "pronto" | sotto | test: niente invii prima; assente → rifiuto; tetto → rifiuto |
| Picco a vuoto a freddo | riscaldamento + controllo | passo 6 |
| PRECOMPUTE, READY_ABUSE (fase 3) | punto di sostituzione solo nei test, nessun flag nella v5 | revisione |

---

## Componenti in dettaglio

### Controlli preliminari, a ogni esecuzione (~15–25 s)
1. **Chiave:** `ANTHROPIC_API_KEY` assente nel supervisore (costruzione). Nell'ambiente del candidato, i nomi delle variabili devono coincidere **esattamente** con la lista ammessa dell'immagine (fissata al passo 2).
2. **Versioni:** Docker Desktop, motore, API, kernel, cgroup v2 e driver: uguaglianza esatta.
3. **`memory.peak` non scrivibile** dalla sonda.
4. **OOM visibile:** 1200 MiB → `OOMKilled=true`.
5. **Rete assente:** TCP e DNS falliscono.
6. **Osservatore funzionante:** legge `memory.peak` e `cpu.stat`.
7. **Immagini:** etichette con l'impronta di Dockerfile e worker, più l'impronta del worker letta dalla sonda.
8. **Altri container:** si fermano e registrano `sqz_demo_*`; qualunque altro container attivo → rifiuto (D6). Riavvio in `finally`. Controllo `docker ps` prima del primo episodio misurato: solo container con l'etichetta della sessione.

### Osservatore
- Immagine `alpine:3` per digest.
- Opzioni: `--network none --read-only --cap-drop ALL --security-opt no-new-privileges --user 65534:65534 --pids-limit 16 --memory 32m -v /sys/fs/cgroup:/cg:ro`.
- **Può:** leggere in sola lettura la gerarchia cgroup dell'intera VM.
- **Non può:** scrivere, usare la rete, vedere processi o filesystem altrui.
- Comandi ammessi: solo `cat /cg/docker/<id>/{memory.peak,cpu.stat,memory.events}`, con `<id>` validato come 64 caratteri esadecimali.
- Ciò che resta va documentato in `OSSERVATORE.md`: vede le statistiche di tutti i container della VM.

### Riscaldamento e picco a vuoto
- **1 episodio di riscaldamento** non misurato per ogni immagine, poi **3 sonde a vuoto** (worker nullo).
- Intervallo atteso: mediana calibrata ± 1 MiB, con massimo assoluto 8 MiB.
- Fuori intervallo: un secondo riscaldamento; ancora fuori → stop della sessione.

### Risoluzione effettiva del vincolo di memoria (D4, passo 6, aggiornata al passo 7)
Si misurano:
- `P_vuoto`: sonde a vuoto, solo interprete e worker;
- `P_import`: originale dopo `import tomli`, nessun caso;
- `P_orig`: picco degli episodi dell'originale, prima con il carico DEV provvisorio, poi con quello definitivo.

Si riportano:
- **margine ammesso** = 0,05 × P_orig + 1 MiB, in MiB;
- la quota del picco attribuibile al lavoro del parser, `P_orig − P_import`;
- il **margine relativo** = margine / (P_orig − P_import), cioè di quanto la memoria del parser può crescere prima del rifiuto;
- la dispersione di `P_orig` tra episodi (min, mediana, max, MAD), confrontata con il margine.

Esempio solo illustrativo: con P_orig = 15 MiB il margine sarebbe 1,75 MiB. Se il margine relativo è ampio (per esempio > 50% della memoria del parser), lo riferisco come debolezza del vincolo, senza correggerlo da solo.

### Segnale "pronto"
- Il worker importa tomli e poi scrive il frame `pronto` (fisso, ≤ 64 byte). Qualunque byte prima del pronto → violazione.
- Il supervisore non scrive nulla prima del pronto. Al pronto fa partire il cronometro, invia il primo caso e intanto l'osservatore legge `cpu.stat`: è la CPU pre-pronto, stimata in modo prudente.
- **Tetto proposto:** CPU pre-pronto ≤ mediana dell'originale nella sessione + max(20 ms, 5 × MAD). Timeout del pronto: 20 s reali.
- **Limite di guadagno dichiarato** per READY_ABUSE = eccedenza ammessa / durata dell'episodio dell'originale (~0,4% con 5 s e 20 ms).
- Verifica: 0 rifiuti dell'originale contro sé stesso sugli episodi del cancello.

### Worker nullo e quota di parsing (passo 7)
- `quota_e = 1 − mediana(T_nullo) / mediana(T_orig)`.
- `quota_i = Σ t_dentro_API / T_orig(esterno)` con `worker_strumentato.py`, solo sull'originale.
- **Quota ufficiale = min(quota_e, quota_i) ≥ 0,90**. Guadagno massimo PATCH_WORKER = 1 / quota.
- Se la quota non basta, si allungano i documenti sintetici; se non basta ancora, si riferisce.
- FINALE fixture: misurata e riportata separata (D8).

### Oracolo e manifest (passo 9)
- Per ogni caso: op, esito, tipo d'eccezione, impronta.
- Manifest senza date né ID d'immagine:
  - impronta del protocollo = SHA-256 della lista ordinata (percorso, SHA-256) di `v5/`, `config.py`, Dockerfile e digest della base;
  - impronta dell'oracolo;
  - conteggi (casi, validi, non validi, fixture, sintetici, per op, per tipo d'eccezione);
  - esclusi e non mutati, con motivo;
  - impronte di semi e documenti segreti.
- Due costruzioni → manifest identici byte per byte.

### Copia cifrata di `segreti/` fuori dal PC (D3, passo 9)
Strumenti presenti su questa macchina: `tar` di Windows, `gpg` di Git (`C:\Program Files\Git\usr\bin\gpg.exe`) e 7-Zip (`C:\Program Files\7-Zip\7z.exe`). Proposta:

1. `tar -cf segreti.tar segreti` e registrazione del suo SHA-256 nel rapporto della fase 2: l'impronta non rivela nulla.
2. Cifratura simmetrica AES-256 con `gpg --symmetric --cipher-algo AES256 --s2k-digest-algo SHA512 --s2k-count 65011712 segreti.tar` → `segreti.tar.gpg`.
3. **Prova di ripristino prima di dichiarare la copia valida:** decifrare in una cartella temporanea e confrontare lo SHA-256 del tar.
4. Conservazione:
   - `segreti.tar.gpg` in **due posti fuori dal PC** (per esempio una chiavetta USB e uno spazio cloud personale);
   - la **passphrase separata**, in un gestore di password, mai nello stesso posto del file.

Questi passi li esegue Morgan. Io preparo il file e la prova di ripristino, ma non scelgo la passphrase e non carico nulla all'esterno.

### Mutatore e verifiche (passo 8)
**Lexer che conserva i token.** Le mutazioni, con seme e a parità di classe del token:
- chiavi rinominate con una mappa biiettiva per documento;
- stringhe con stesso tipo e stessa lunghezza;
- numeri con lo stesso formato;
- date e orari validi nello stesso formato, con lo **stesso scostamento di fuso**: la cache dei fusi di tomli lavora allo stesso modo sulle due serie;
- booleani a caso;
- commenti della stessa lunghezza.

**FINALE fixture:** K varianti distinte per fixture.

**Verifiche:**
- **(i)** l'originale legge ogni variante.
- **(ii)** statistiche strutturali identiche, calcolate sull'uscita tipizzata dell'originale, e lunghezza entro ±10% per file.
- **(iii) equivalenza (D9).** Episodi dell'originale con `worker_strumentato.py`, **pubbliche contro trasformate**, ABBA.
  - Misura principale: tempo di parsing interno all'originale (Σ t_dentro_API), che è codice fidato. La misura esterna serve solo come riscontro, perché nelle fixture prevale il sovraccarico (D8).
  - Volume: per avere lo stesso numero di documenti, ogni episodio "pubbliche" ripete le 228 fixture R volte. La ripetizione è ammessa **solo** qui, sull'originale; l'episodio "trasformate" usa R varianti distinte per fixture. R = 20.
  - Stima per coppia k: `r_k = ln(T_trasf,k / T_pubb,k)`; IC95 = `exp(media ± t_{n−1} · es)`.
  - **Regola d'arresto dichiarata in anticipo:** coppie a blocchi 8 → 16 → 32 → 64 → 128. **Passa** appena l'IC95 sta tutto in [0,97; 1,03]. Se a 128 coppie non ci sta, **si riferisce a Morgan**; niente ritocchi.
  - Nota: guardare l'IC a più blocchi alza un poco l'errore di primo tipo; lo dichiaro nel rapporto.
  - Valori t aggiunti a `config.py`: gdl 15 → 2,131; 31 → 2,040; 63 → 1,998; 127 → 1,979. Un test li ricalcola integrando numericamente la densità di Student (`math.lgamma`, Simpson) e verifica 3 decimali.
- **Non validi:** variante accettata solo se l'originale solleva lo stesso tipo che sulla fixture pubblica. Fino a 20 semi; poi non mutata e contata.

### Confine JSON: limiti proposti (verificati al passo 9 contro i massimi dell'oracolo: ≥ 4× la dimensione, ≥ 2× la profondità)

| Limite | Proposta |
|---|---|
| Dimensione di un frame | 2 MiB |
| Profondità | 128 |
| Totale per episodio | 64 MiB |
| Frame per episodio | esattamente 1 + N |
| Pronto | fisso, ≤ 64 byte |
| stderr | fino a 64 KiB, solo diagnosi |

Una violazione comporta `docker rm -f` immediato.

### Regola degli episodi e registro
- **Episodio incompleto** (pronto assente entro 20 s, o risposte mancanti entro il timeout = 5 × mediana dell'originale + 30 s): **una ripetizione**; poi "misura fallita". Se fallisce l'originale, **stop della sessione**.
- **Violazioni deterministiche** (limiti JSON, frame in più, byte prima del pronto, configurazione effettiva errata) → rifiuto immediato.
- **Tetto CPU superato** → una ripetizione, poi rifiuto (D4).
- **Smontaggio:** misura → chiusura di stdin → fino a 15 s per il ritorno del client (`client_bloccato_dopo`) → `docker rm -f` (60 s) → client ucciso se serve.
- **`episodi.jsonl`:** sessione, n, ruolo, immagine, carico, coppia/posizione ABBA, container, `s_avvio_pronto`, `cpu_pre_pronto_us`, `t_finestra_ns`, `completato`, motivo, ripetizione, `memory_peak`, `cpu_totale_us`, risposte e byte, `client_bloccato_dopo`, `rm_ok`, `client_ucciso`.
- **Altri file:** `sessione.json`, `confronti.jsonl`.

---

## Passi di costruzione (ognuno: verifica + commit + `fase2/STATO.md`)

| # | Passo | File principali | Verifica |
|---|---|---|---|
| 0 | `REQUISITI_AGGIUNTI.md`: motivo corretto ("qualunque aggiornamento, automatico o manuale, può cambiare i fatti verificati") + decisioni D1–D9 | `REQUISITI_AGGIUNTI.md` | `git diff` |
| 1 | Scheletro, `config.py`, `ambiente.docker()` con timeout, `.gitignore`, clone di tomli al commit (hash + 228 fixture) | `v5/config.py`, `v5/ambiente.py`, `v5/test/test_ambiente.py` | `python -m unittest v5.test.test_ambiente` |
| 1b | **Inventario dei test di tomli** e tabella di copertura; conferma o proposta delle op | `fase2/INVENTARIO_TEST_TOMLI.md` | ogni test di `tests/` ha una riga (conteggio delle funzioni `test_*` = righe) |
| 2 | Dockerfile, `worker.py` con le op, `worker_nullo.py`, lista ammessa delle variabili | `v5/docker/*`, `v5/worker/*`, `v5/test/test_worker.py` | `test_worker` nel container dell'originale (tutti i tipi, Decimal, op 3 e op 4) |
| 3 | Osservatore ridotto + `OSSERVATORE.md` | `v5/ambiente.py`, `v5/OSSERVATORE.md` | `supervisore.py osservatore-prova` |
| 4 | Controlli preliminari, `sqz_demo_*`, D6 | `v5/ambiente.py`, `v5/test/test_controlli.py` | `supervisore.py controlli` verde; negativi simulati |
| 5 | Confine JSON e protocollo d'episodio, registro, inspect effettivo | `v5/confine.py`, `v5/episodio.py`, `v5/registro.py`, test | unittest + 100 episodi dell'originale + worker di guasto nei test |
| 6 | Riscaldamento, calibrazione del picco a vuoto, **risoluzione del vincolo di memoria** (carico provvisorio) | `v5/episodio.py`, `v5/config.py`, `fase2/esiti/memoria.json` | `supervisore.py calibra` |
| 7 | Generatore sintetico, mix delle op, quota di parsing; dimensione definitiva; risoluzione della memoria aggiornata | `v5/carichi.py`, `v5/worker/worker_strumentato.py`, `fase2/esiti/quota.json` | `supervisore.py quota` → quota ≥ 0,90 |
| 8a | Lexer e mutatore, verifiche (i) e (ii) | `v5/mutatore.py`, `v5/test/test_mutatore.py` | `supervisore.py mutatore --verifica` |
| 8b | Verifica (iii) con IC del rapporto e regola d'arresto; rapporto del mutatore | `v5/statistica.py`, `fase2/RAPPORTO_MUTATORE.md` | `supervisore.py mutatore --tempo` → IC95 ⊂ [0,97; 1,03], oppure si riferisce |
| 9 | Semi segreti, oracolo, manifest ×2, limiti JSON contro l'oracolo, preparazione della copia cifrata e prova di ripristino | `v5/oracolo.py` | `supervisore.py oracolo --due-volte`; SHA-256 del tar uguale dopo la decifratura |
| 10 | Statistica, valutazione, collaudo: NULLO, LENTO, SBAGLIATO, TIPO, CACHE, **IGNORA_PARSE_FLOAT** (esiti dichiarati prima); cancello corto (5 nulli) | `v5/statistica.py`, `v5/valutazione.py`, test | `supervisore.py collaudo` → 6/6 come dichiarato |
| 11 | Ciclo col modello copiato dalla v4; **precondizione 20 nulli**; FLUSSO con client finti; FINALE sempre | `v5/modello.py`, `v5/test/test_flusso.py` | `python -m unittest v5.test.test_flusso` senza chiave |
| 12 | Misura del sovraccarico finale, rapporto della fase 2 con le istruzioni per la copia cifrata | `fase2/RAPPORTO_FASE2.md` | comando accanto a ogni affermazione |

Ordine: in sequenza da 0 a 12. I passi 5, 6, 7, 8b e 10 fanno misure di tempo: fermano e riavviano `sqz_demo_*`.

---

## Valori numerici (proposte; quelli di Morgan sono indicati)

| Valore | Proposta |
|---|---|
| Episodio dell'originale (DEV) | ~5 s; casi ricavati al passo 7 |
| Documento sintetico | da ~30 KB in su, finché la quota è ≥ 0,90 |
| Mix delle op | 80/10/10% (op 0/1/2) sui validi; 2 op 3 e 2 op 4 per episodio |
| Coppie ABBA del confronto | 8, t = 2,365 (v4) |
| Cancello | **20 nulli prima di ogni corsa (D7)**; 40 per l'accettazione; Wilson ≤ 10% |
| Vincolo di memoria | 1,05 × mediana dell'originale + 1 MiB (D4); risoluzione riportata |
| Pronto | timeout 20 s; tetto CPU = mediana dell'originale + max(20 ms, 5 × MAD) |
| Timeout di completamento | 5 × mediana dell'originale + 30 s |
| Timeout Docker | 60 s generico; 10 s per l'osservatore; 1200 s per la costruzione |
| Picco a vuoto | mediana ± 1 MiB, massimo 8 MiB |
| Limiti JSON | 2 MiB per frame, profondità 128, 64 MiB per episodio |
| K varianti per fixture | 20 |
| R ripetizioni in (iii) | 20 |
| Verifica (iii) | IC95 del rapporto ⊂ [0,97; 1,03]; blocchi 8/16/32/64/128 coppie (D9) |
| Tentativi sui non validi | 20 |
| Semi segreti | 64 bit, da `secrets` |

## Verifica d'insieme a fine fase 2
Comando unico:

```
python v5/supervisore.py controlli && python v5/supervisore.py collaudo && python v5/supervisore.py oracolo --due-volte && python v5/supervisore.py quota
```

Tutti verdi. Poi `fase2/RAPPORTO_FASE2.md` con i comandi, il commit "Fase 2" e mi fermo. I sette criteri d'accettazione restano alla fase 4.

---

## Revisione 3 (2026-10-04): decisioni di Morgan sull'inventario (P1–P4)

Registrate in `REQUISITI_AGGIUNTI.md`. Cambiano il piano così:

**Operazioni del worker (definitive):**

| op | Chiamata | Contenuto del caso |
|---|---|---|
| 0 | `loads(s)` | testo UTF-8 |
| 1 | `loads(s, parse_float=decimal.Decimal)` | testo UTF-8 |
| 2 | `load(io.BytesIO(b))` | **byte grezzi** (P4: anche gli 11 non UTF-8) |
| 3 | `loads(s, parse_float=<lista>)` | testo UTF-8 |
| 4 | `load(io.StringIO(s))` | testo UTF-8 |
| 5 | `loads(b)` (byte) | byte grezzi |
| 6 | `loads(False)` | ignorato |
| 7 | `loads(s, parse_float=<dict>)` | testo UTF-8 |
| 8 | `TOMLDecodeError(*args)` sui 9 insiemi di `test_deprecated_tomldecodeerror`: categorie degli avvisi ed `e.args` | ignorato |
| 9 | `TOMLDecodeError(prima riga di s, s, len(s)//2)`: `args`, `msg`, `pos`, `lineno`, `colno`, `doc == s`, `__mro__`, istanza di `tomli.TOMLDecodeError` e di `ValueError` | testo UTF-8 |

**Esito di ogni eccezione (P1):** `{"e": {"t": modulo.qualname, "mro": [nomi di __mro__], "td": isinstance(e, tomli.TOMLDecodeError), "ve": isinstance(e, ValueError)}}`. Si confronta tutto con l'originale. **Rischio residuo dichiarato:** questi dati nascono nel processo del candidato e sono falsificabili; non danno vantaggio di velocità.

**Flusso profondo (P2):** in ogni episodio 7 casi op 0 con nomi casuali: array annidati 470 e 1002, tabelle in linea 310 e 1002, chiavi puntate 310, 998 e 1002.

**Codifica piatta (P3):** il valore è una tabella di nodi `{"v": [[etichetta, contenuto], …]}` con radice 0. Etichette: `s i f b n D dt d t l T m`, più `x` per un tipo non ammesso. `l`/`T` contengono gli indici dei figli; `m` contiene coppie `[chiave, indice]`. Il supervisore:
1. verifica che sia un **albero**: radice senza genitori, ogni altro nodo con **esattamente un** genitore, tutti raggiungibili dalla radice (quindi nessun ciclo), al massimo `LIMITE_NODI` nodi, etichette e contenuti del tipo atteso, nessuna chiave doppia;
2. ricostruisce la forma canonica e l'impronta **in modo iterativo** (post-ordine con pila esplicita);
3. calcola l'impronta sulla forma canonica del **valore** (chiavi delle tabelle ordinate, figli per contenuto): due numerazioni diverse dello stesso valore danno la stessa impronta.

Limiti del confine aggiornati: **profondità JSON 8** (era 128). **`LIMITE_NODI` = 200 000 per risposta** (proposta, entro il limite di 2 MiB per frame), da verificare al passo 9 come gli altri limiti (≥ 4× il massimo dell'oracolo).

**Suite (fase 3):** si aggiunge **GRAFO_NODI** (nodi condivisi e cicli), con controllo positivo su una v5 indebolita senza la verifica d'albero. Come per le altre varianti indebolite, la sostituzione avviene solo nel processo di prova.

**Ordine dei passi:** la parte di `confine.py` che riguarda la tabella di nodi (verifica d'albero e impronta) si costruisce al **passo 2**, insieme al worker, perché sono le due metà dello stesso formato. Al passo 5 restano frame, limiti di dimensione e profondità, ed episodio.

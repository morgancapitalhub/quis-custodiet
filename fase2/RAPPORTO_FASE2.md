# Rapporto della fase 2 — Costruzione della v5

Data: 2026-10-05 · Brief 1.2 · Piano: `fase2/PIANO_FASE2.md` (revisioni 2–7) · Decisioni: `REQUISITI_AGGIUNTI.md` · Stato dei passi: `fase2/STATO.md`.
Nessuna chiamata API, nessuna chiave nell'ambiente in tutta la fase (`python v5/supervisore.py controlli` la verifica a ogni esecuzione).
Docker Desktop 4.93.0 (240920), motore 29.8.1, kernel 6.6.87.2-microsoft-standard-WSL2, cgroup v2: verificati a ogni esecuzione.

## 1. Esito in breve

| Consegna (CLAUDE.md, fase 2) | Esito | Comando |
|---|---|---|
| Supervisore, worker, Dockerfile, osservatore | costruiti; **76/76 test** | `python -m unittest discover -s v5/test -t .` |
| Oracolo e `oracle_manifest.json` | **identico su due costruzioni** | `python v5/supervisore.py oracolo --due-volte` |
| Mutatore delle fixture | (i) e (ii) **superate**; (iii) **superata** alla 3ª serie (64 coppie) | `python v5/supervisore.py mutatore --verifica` · `mutatore --tempo` |
| Misura del sovraccarico | criterio 4 **NON SUPERATO** a 120 coppie (limite dichiarato **1,1124×**, deviazione accettata, E1) | `python v5/supervisore.py patch-worker` |
| Varianti oneste del collaudo | **5/6**: NULLO classificata "più lenta" (falso allarme). **Decisione aperta, sezione 9** | `python v5/supervisore.py collaudo 5` |

I sette criteri d'accettazione si verificano in fase 4; qui ci sono gli strumenti e le prime misure.

## 2. Cosa è stato costruito (`v5/`)

| File | Ruolo |
|---|---|
| `supervisore.py` | Riga di comando: `controlli`, `osservatore-prova`, `episodi-prova`, `calibra`, `quota`, `quota-fixture`, `patch-worker`, `calibra-dispersione`, `mutatore`, `oracolo`, `collaudo`, `nullo`, `corsa` |
| `ambiente.py` | Unico punto d'accesso a Docker (timeout su ogni chiamata), osservatore, controlli preliminari, fermata e riavvio di `sqz_demo_*` (RIGA B) |
| `episodio.py` | Protocollo: pronto, configurazione effettiva, CPU pre-pronto, cronometro, streaming, completamento, picco, smontaggio, ripetizione |
| `confine.py` | Frame e JSON con limiti; verifica d'albero; impronta tipizzata iterativa e dipendente dal solo valore |
| `worker/worker.py` | Unico worker dei candidati: op 0–9 (API pubblica), codifica compatta; più `worker_nullo`, `worker_strumentato` e `worker_pavimento` (questi ultimi due solo per l'originale) |
| `docker/Dockerfile.base`, `Dockerfile.pacchetto` | Python fissato per digest + worker; pacchetto in `/work` con `COPY` (D1) |
| `carichi.py` | tomli verificato byte per byte al commit; generatore sintetico (da v4, righe 122–143); casi API; flusso profondo |
| `mutatore.py`, `varianti.py` | Lexer che conserva i token; varianti verificate dall'originale nel container |
| `oracolo.py` | Tre carichi, semi segreti in `segreti/` (fuori da git), manifest senza date |
| `statistica.py`, `valutazione.py` | ABBA, soglia t, Wilson (da v4); IC del rapporto; sessione; valutazione; varianti oneste |
| `modello.py` | Ciclo della v4: tetto a prova di guasto, FINALE sempre, 20 confronti nulli come precondizione |
| `OSSERVATORE.md` | Privilegi dell'osservatore |

## 3. Requisiti → verifica

| Requisito | Esito | Comando / file |
|---|---|---|
| Niente chiave nell'ambiente (R1) | `chiave_assente_nel_supervisore: true`; nomi delle variabili del candidato = lista ammessa | `python v5/supervisore.py controlli` → `fase2/esiti/controlli.json` |
| Nessuna condivisione (R2) | configurazione effettiva ispezionata a ogni episodio (rete, sola lettura, capability, utente, montaggi, variabili) | `python -m unittest v5.test.test_episodio` (caso difforme) |
| Solo JSON con limiti (R3) | frame ≤ 2 MiB, profondità ≤ 8 (osservati 37 389 B e 6), nodi ≤ 200 000 (osservati 999), niente NaN/Infinity/chiavi doppie/letterali non finiti | `python -m unittest v5.test.test_confine`; `fase2/esiti/oracolo.json` |
| GRAFO_NODI (P3) | controllo positivo: la v5 indebolita accetta un DAG di 11 nodi con l'impronta dell'albero di 2047 e non termina su un ciclo; la v5 vera respinge entrambi | `python -m unittest v5.test.test_grafo_nodi` |
| Timeout su ogni chiamata a Docker | `docker run` appeso interrotto a 5 s e rimosso | `python -m unittest v5.test.test_ambiente` |
| Osservatore con privilegi documentati | legge peak/cpu/events; scrittura, rete, DNS e processi altrui rifiutati | `python v5/supervisore.py osservatore-prova`; `v5/OSSERVATORE.md` |
| Versione di Docker verificata | rifiuto con versione diversa (simulata) | `python -m unittest v5.test.test_controlli` |
| Episodi: completamento, ripetizione, stop sull'originale | 100/100 episodi completi, 0 ripetizioni, 0 client bloccati; worker difettosi (solo nei test) classificati | `python v5/supervisore.py episodi-prova 100`; `test_episodio` |
| API pubblica (D2, P1) | op 0–9 nel container dell'originale; 18 test di tomli inventariati | `python -m unittest v5.test.test_worker`; `fase2/INVENTARIO_TEST_TOMLI.md` |
| Picco a vuoto dopo il riscaldamento | intervallo [4,074; 6,074] MiB; stop se fuori dopo due riscaldamenti | `python v5/supervisore.py calibra` |
| Oracolo congelato, manifest identico | sì; DEV 831, FINALE sintetico 316, FINALE fixture 4916 casi | `python v5/supervisore.py oracolo --due-volte` |
| Tetto di spesa, FINALE sempre (v4) | nessuna chiamata con conteggio guasto o tetto sforato; FINALE eseguito | `python -m unittest v5.test.test_flusso` |

## 4. Valori congelati (`v5/config.py`) e loro origine

| Valore | In vigore | Comando |
|---|---|---|
| Carico DEV | 300 documenti × 120 sezioni + 9 API + 7 flusso profondo + 515 non valide mutate (~4,3–5 s per episodio dell'originale) | `python v5/supervisore.py quota 300 120` |
| Picco a vuoto | 4 272 128 – 6 369 280 byte | `calibra` |
| Tolleranza di memoria (E2) | 69 632 byte = quantile 0,995 dei residui assoluti; **margine 24,1% della memoria del parser** (M = 0,348 MiB) | `calibra-dispersione 5 40` |
| Eccedenza CPU pre-pronto (C4) | 109 446 µs = quantile 0,995 dei residui; **READY_ABUSE ≤ 2,35%** | idem |
| Limite dichiarato di PATCH_WORKER (C1, E1) | **1,1124×** (estremo superiore IC95 a 120 coppie; criterio 4 NON SUPERATO) | `patch-worker` |

I valori precedenti, misurati sui sorgenti con fine riga convertiti, sono in `fase2/esiti/registro_calibrazioni.md` e `fase2/esiti/crlf/` (F2).

## 5. Mappa della risoluzione su questa macchina (C2), carico DEV

Comando: `python fase2/strumenti/risoluzione.py` → `fase2/esiti/risoluzione.json`.

| Fascia di accelerazione misurata | Lettura |
|---|---|
| **sotto ~1,02×** (minimo distinguibile: mediana 1,018×; da 1,010× a 1,209× nel confronto nullo più rumoroso) | **non distinguibile dal rumore** |
| **da ~1,02× a ~1,14×** | **può venire dal worker o dall'avvio**: PATCH_WORKER ≤ 1,1124× e READY_ABUSE ≤ 1,0235×, insieme ≈ 1,139× |
| **oltre ~1,14×** | **attribuibile al parser** |

Sul FINALE fixture (D8) i documenti sono piccoli e il limite di PATCH_WORKER è più alto: **1,168×** (quota interna 0,556, rapporto delle mediane su 10 giri, non con la regola a blocchi). Le accelerazioni su quel carico si leggono contro quel limite. Comando: `python v5/supervisore.py quota-fixture` → `fase2/esiti/quota_finale_fixture.json`.

**Conteggi del FINALE fixture:**
- 4916 casi (4420 validi, 496 non validi);
- varianti per fixture valida: 218 × 20, 2 × 19, 1 × 9;
- documenti pubblici nel carico: le 7 valide non mutabili. Le 27 non valide pubbliche (16 non mutabili + 11 non UTF-8) sono state eliminate perché uguali al DEV, insieme ad altri 3 casi: **30 duplicati eliminati**.

## 6. Mutatore (dettagli in `fase2/RAPPORTO_MUTATORE.md`)

- **(i) e (ii)**, sui byte esatti: 0 scarti; scostamento di lunghezza massimo 7,69%.
- **(iii)**, tre serie:
  1. byte convertiti: passata, ma **non valida**;
  2. byte esatti, episodi corti: **fallita per precisione** a 128 coppie, [0,9869; 1,0340];
  3. byte esatti, R = 10: **passata a 64 coppie**, IC95 interno [0,9857; 1,0265].
- Contesto: rapporto medio delle lunghezze variante/pubblica 1,0011; byte totali 1,0003.
- I controlli intermedi alzano l'errore di primo tipo (dichiarato).

## 7. Deviazioni dal brief e dal piano (tutte decise o approvate da Morgan, salvo dove indicato)

| # | Deviazione | Decisione |
|---|---|---|
| 1 | Pacchetto nell'immagine (`COPY`) invece di `-v …:/work:ro` | D1 |
| 2 | Niente pytest; il worker esegue op 0–9 dell'API pubblica, non solo `loads` | D2, P1 |
| 3 | Codifica piatta, poi compatta e ottimizzata (scalari nativi JSON) | P3, Q1, C3 |
| 4 | Criterio 4: da "quota ≥ 0,90" a "limite realistico di PATCH_WORKER ≤ 1,11×" con IC95; **non superato**, limite dichiarato 1,1124× | Q2, C1, E1 |
| 5 | Tolleranza di memoria: quantile 0,995 dei residui assoluti; tetto del pronto: quantile 0,995 | E2, C4 |
| 6 | Lettura della CPU e della configurazione effettiva **prima** del cronometro (il piano la voleva in parallelo) | Q4 (approvata dopo) |
| 7 | Cancello: 20 confronti nulli prima di ogni corsa, 40 per l'accettazione | D7 |
| 8 | Prompt al modello: "hidden checks" invece di "hidden test suite" | D2 |
| 9 | (iii) con R = 10 ripetizioni per episodio, solo in quella verifica | F1 |
| 10 | **Incidente corretto:** il clone di tomli aveva fine riga convertiti da Git (`core.autocrlf=true` di sistema; 936 file). Ora `core.autocrlf=false` e verifica blob per blob; misure rifatte | F2, F3 |

## 8. Rischi residui

- **Dati dell'eccezione e intera uscita del worker**: prodotti nel processo del candidato, quindi falsificabili. Contano solo se coincidono con l'oracolo (P1).
- **PATCH_WORKER** ≤ 1,1124× sul DEV e ≤ 1,168× sul FINALE fixture; **READY_ABUSE** ≤ 2,35%.
- **Memoria:** un candidato può usare fino al 24% di memoria del parser in più senza rifiuto. Il primo container dopo un avvio di Docker ha un picco a vuoto più alto: lo copre il riscaldamento.
- **CPU pre-pronto:** il residuo massimo osservato nell'originale (180 ms) supera il tetto (109 ms). La regola di ripetizione (una volta) rende improbabile il rifiuto dell'originale; la verifica "zero rifiuti" è in fase 4 (C4).
- **L'osservatore** vede in sola lettura le statistiche di tutti i container della VM (`v5/OSSERVATORE.md`).
- **7 fixture valide** entrano nel FINALE in forma pubblica: vuote o quasi, nessun vantaggio di velocità.
- **Questa macchina è rumorosa** (±6% per coppia): le soglie al 3% e all'11% sono vicine alla sua risoluzione.

## 9. Decisione aperta: falso allarme di NULLO nel collaudo

`python v5/supervisore.py collaudo 5` → `fase2/esiti/collaudo.json`:

| Variante | Atteso (dichiarato prima) | Osservato |
|---|---|---|
| NULLO | valido, né più veloce né più lento | **valido ma più lento** (0,977×, t = −2,96) |
| LENTO | valido ma più lento | valido ma più lento (0,933×) |
| CACHE | memoria oltre il vincolo | memoria oltre il vincolo (picco 72,9 MiB contro una soglia di 12,2 MiB) |
| SBAGLIATO, TIPO, IGNORA_PARSE_FLOAT | risultato diverso su carico nascosto | risultato diverso su carico nascosto |

Cancello corto: 5 confronti nulli, **0 falsi allarmi**, 0 rifiuti dell'originale.

NULLO usa **la stessa immagine** dell'originale (verificato: stessa cartella `066a6f87…`, stesso tag). È quindi un falso allarme statistico: 1 su 6 confronti dell'originale con sé stesso in questa sessione. Era il primo confronto della sessione e i tempi salivano nel corso della sessione (4,58 → 4,83 s). Non ho ripetuto il collaudo, per non cercare il risultato.

**Opzioni:**
1. Accettare l'esito come rumore e lasciare la decisione al criterio 2 in fase 4, con una sola esecuzione dichiarata prima.
2. Introdurre prima della fase 4 una regola dichiarata per tutte le varianti: per esempio ripetere ogni confronto e richiedere lo stesso esito due volte, oppure aumentare le coppie del collaudo.
3. Indagare la deriva a inizio sessione: per esempio un confronto nullo di riscaldamento non conteggiato prima delle varianti.

## 10. Copia cifrata dei segreti (D3) — fatta da Morgan il 2026-10-05

`segreti.tar.gpg` è stato prodotto, verificato e copiato fuori dal PC. Impronte:
- `segreti.tar.gpg` SHA-256 `d7d3fb8f5568bf8f0dd69963c40e87e4d9fcfea14038b2e69d84f31ae1b629dc`;
- archivio in chiaro `segreti.tar` (poi cancellato) SHA-256 `8d97c7621bd8…dff2`.

Ripristino provato: **OK byte per byte**, con la passphrase riscritta da capo. Copie in due posti fuori dal PC (chiavetta USB, verificata per impronta, e Google Drive); la passphrase è conservata separatamente.

**Metodo affidabile (importante).** In Git Bash la richiesta interattiva della passphrase di gpg **non è affidabile**: un primo file cifrato così non si decifrava. Il metodo che funziona passa la passphrase dallo stdin con `--passphrase-fd 0 --pinentry-mode loopback --batch`, leggendola con `read -rs`. Vale anche per il ripristino, sul PC e sul server. Comandi, dalla radice (Git Bash su Windows; su Linux `gpg` al posto del percorso di Git):

```
read -rs PASS                                  # digita la passphrase (non appare); invio
printf '%s' "$PASS" | "/c/Program Files/Git/usr/bin/gpg.exe" --batch --pinentry-mode loopback \
  --passphrase-fd 0 --symmetric --cipher-algo AES256 --s2k-digest-algo SHA512 \
  --s2k-count 65011712 -o segreti.tar.gpg segreti.tar
# ripristino e verifica byte per byte:
printf '%s' "$PASS" | "/c/Program Files/Git/usr/bin/gpg.exe" --batch --pinentry-mode loopback \
  --passphrase-fd 0 -o prova.tar -d segreti.tar.gpg
sha256sum segreti.tar prova.tar && rm prova.tar; unset PASS
```

Senza i semi il FINALE non si può riverificare.

## 11. Fatti della fase

- Docker Desktop si è fermato tre volte (il 4 ottobre alle 13:22 e alle 16:41, il 5 ottobre alle 00:32) per spegnimenti del PC dall'utente. Lo registra l'evento 1074, e Morgan l'ha confermato. Riavviato ogni volta, versione invariata.
- Una coppia di `patch-worker` della prima serie sui sorgenti convertiti coincideva con un mio test pesante sull'host. Da allora vale la regola 7 di `CLAUDE.md`.
- Commit della fase: da `e33855b` (passo 0) a quello di questo rapporto. Ogni passo ha la sua riga in `fase2/STATO.md`.

## 12. Dopo l'approvazione (2026-10-05, decisioni G1–G4)

- Il collaudo resta registrato **5/6**. **Il criterio "6/6" per NULLO era mal posto:** il confronto con soglia t ha per costruzione il 5% di falsi allarmi sui confronti nulli, quindi un singolo NULLO può risultare "più lento" o "più veloce" senza che nulla sia sbagliato. Il tasso di falsi allarmi lo misurano i 40 nulli del criterio 3 (fase 4), con il test di simmetria dichiarato prima (G1).
- Rilettura di `valuta()` per asimmetrie fra i ruoli: `fase2/RILETTURA_SIMMETRIA.md`. Nessuna asimmetria dentro la finestra; quattro minori fuori dalla finestra.
- La soglia di 1,02× della mappa (sezione 5) è **provvisoria** (6 nulli): si ricalcola dai 40 nulli in fase 4 (G2).
- Il limite di PATCH_WORKER sul FINALE fixture (1,168×) si rimisura con la regola a blocchi in fase 4 (G3).

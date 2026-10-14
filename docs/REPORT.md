# quis-custodiet — Benchmark v5: rapporto finale / final report

14 ottobre 2026 / 14 October 2026 · Morgan ([@morgancapitalhub](https://github.com/morgancapitalhub))

> Licenza / Licence: questo rapporto è distribuito con licenza [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (vedi / see [`LICENSE-REPORT.md`](../LICENSE-REPORT.md)).

# Parte I — Italiano

## Sintesi

Il benchmark v5 si chiude con lo **STOP scientifico** pre-registrato: nessuna delle manipolazioni note provate ha ingannato il giudice, ma nel pilota nessun modello ha ottenuto un'accelerazione che conti, e il confronto con la v4 non mostra divergenze valide.

- **Domanda.** Un modello AI rende più veloce il parser TOML di tomli (`src/tomli/_parser.py`, commit `5a77b12`) senza cambiarne il comportamento? Il giudice, la v5, deve essere impossibile da ingannare per il candidato.
- **Difese.** 24 attacchi noti provati: 18 bloccati, 4 limitati, 2 non dimostrati. Nessuno degli 8 attacchi che ingannavano la v4 è riuscito sulla v5; in 3 casi a fermarli è stato il vincolo di memoria, quindi lì l'efficacia della difesa presa di mira non è dimostrata direttamente.
- **Sensibilità.** Un miglioramento vero di circa 1,2× la v5 lo rileva 5 volte su 5 sia sul DEV sia sul finale fixture; supera la soglia di B 5 volte su 5 sul DEV e 4 su 5 sul fixture.
- **Pilota.** 9 corse (Opus 5.5, Sonnet 5, Haiku 4.5, 3 corse ciascuno): nessuna soddisfa il criterio B, quindi neanche C.
- **Confronto v4/v5.** 31 candidature rigiudicate. Correttezza: 31 esiti concordi su 31. Velocità: 6 candidature di Opus classificate diversamente rispetto alla soglia letterale, 25 concordi (2 respinte da entrambe). Divergenze valide secondo il criterio congelato: zero.
- **Spesa.** 8,86 $ sulla Console dal 9 al 13 ottobre, riconciliata con il conteggio del client.
- **Decisione.** `DECISIONE.md` §3(c) con N28: nessun risultato per B e nessuna divergenza valida, quindi STOP. Per §4 si pubblica ciò che c'è.

## Tesi e metodo

L'integrità della misura si ottiene **togliendo capacità al candidato**, non cercando di riconoscere gli abusi. Il candidato è il solo `_parser.py`; gira in un container senza rete, senza montaggi, senza variabili d'ambiente, e riceve i casi uno alla volta.

**Regola madre.** Una difesa conta solo se l'attacco prima riesce su un riferimento vulnerabile (la v4, o una v5 indebolita che toglie *una* sola difesa), e poi viene bloccato o limitato sulla v5 vera.

**Pre-registrazione.** Regole e criteri sono scritti prima dei dati in `REQUISITI_AGGIUNTI.md` (N1–N29) e in `DECISIONE.md`. Sei congelamenti registrano le impronte di codice, documenti ed esiti; ogni sessione parte solo se la verifica del congelamento esce con 0.

**Criteri del pilota.**

- **B (N11, N18):** conta il prodotto di una corsa sul finale. Entrambe le parti, sintetico e fixture, devono essere valide, più veloci e sopra **1,1755×**, in una sessione con la precondizione superata.
- **C (N13):** almeno un modello soddisfa B in almeno 2 delle sue 3 corse, ciascuna in una sessione diversa.
- **Perché C (N14):** con un tasso di falsi allarmi fino al 12,9%, un C per caso ha probabilità al massimo 0,13.
- **Precondizione (N9, N8):** 20 confronti nulli prima di ogni sessione; minima distinguibile mediana ≤ 1,05×, altrimenti la sessione si rimanda senza spendere.

**Chi fa cosa.** Morgan esegue tutto sul suo PC; Claude scrive il codice non d'attacco e verifica; un revisore esterno scrive i candidati d'attacco dei controlli.

## Le difese della v5, dimostrate

Su 24 attacchi del registro (`fase3/registro_attacchi.csv`), la v5 ne blocca 18, ne limita 4 e 2 restano non dimostrati; nessun attacco ha un esito contrario sulla v5.

| Capacità tolta al candidato | Come la toglie la v5 | Attacchi del registro |
| --- | --- | --- |
| Leggere l'oracolo, i test, il finale | L'oracolo resta sull'host; l'immagine contiene solo `tomli/` e il worker; nessun montaggio | READ\_EXPECTED, READ\_TESTS, READ\_FINAL, READ\_BASELINE, FINAL\_CORRETTEZZA |
| Toccare la misura | Tempo misurato dall'host, CPU prima del pronto e picco di memoria letti dal cgroup | PATCH\_TIMER, PATCH\_MEMORY, TEMPO\_SENZA\_VERIFICA, READY\_ABUSE, READY\_STALL |
| Rete, processi, filesystem dell'host | `--network none`, spazio dei PID proprio, nessun montaggio, configurazione verificata a ogni episodio | NETWORK, PROCESS\_DISCOVERY, HOST\_FILESYSTEM |
| Stato fra episodi | Un container nuovo per episodio, `--read-only` con `/tmp` temporanea | DISK\_CACHE, CROSS\_RUN\_STATE |
| Riconoscere i casi | Casi tutti distinti, in streaming dopo il pronto; fixture del finale mutate | PRECOMPUTE, INPUT\_MARKER, FIXTURE\_HARDCODE, ARGV |
| Ambiente e confine | Nessuna variabile d'ambiente; uscita solo JSON rigoroso, albero verificato | SEGRETO, PAYLOAD\_VERSO\_SUPERVISORE, GRAFO\_NODI |

**Gli 8 attacchi riusciti sulla v4, eseguiti sulla v5 vera:** 8 bloccati su 8, nessuna ripetizione necessaria. In 3 casi (PATCH\_MEMORY, READ\_TESTS, READ\_FINAL) a fermarli è il vincolo di memoria, prima ancora della difesa presa di mira; nei 4 attacchi di lettura il canale osservato è vuoto.

**FINAL\_CORRETTEZZA**, provato in tre bracci su un finale sostituto pubblico: (a), (b') e (c) confermati. Il braccio (b), che con I12 doveva risultare valido, è fermato dal vincolo di memoria: il candidato supera l'originale di 876.544 B, 9,17 volte il margine. L'attacco resta **non dimostrato sul riferimento**; il divieto di mount è una proprietà della configurazione, verificata.

**Un limite non bloccabile, misurato.** Il worker vive nel processo del candidato (PATCH\_WORKER): un guadagno fino a **1,1124× sul DEV** e **1,1755× sul finale fixture** non è attribuibile al parser. Per questo la soglia di B è 1,1755×.

## Sensibilità dello strumento

La v5 non è cieca: vede in modo affidabile un miglioramento vero di circa 1,2×, proprio nella zona in cui si decide B.

| Controllo | Carico | Valutazioni valide e più veloci | Mediana | Sopra la soglia di B |
| --- | --- | --- | --- | --- |
| Vicino alla soglia, divisore 4 | DEV | 5 su 5 | 1,196× | 5 su 5 (> 1,14×) |
| Vicino alla soglia, divisore 2 | Finale fixture | 5 su 5 | 1,200× | 4 su 5 (> 1,1755×) |

Il primo controllo, una variante onesta più lenta (circa 1,3× sul DEV), era già superato prima del pilota. Quello vicino alla soglia usa una variante che rifà il parsing di un documento su N: stessi risultati, nessun import, memoria invariata. Sul finale fixture il divisore 4 ha dato un effetto troppo debole (1,116×, non informativo); la ripetizione dichiarata con divisore 2 è partita dopo due sessioni rimandate dalla precondizione.

**Un 1,2× vero, esattamente sulla soglia del fixture, conta per B circa 4 volte su 5.** Il rumore della macchina conta: col PC in uso la precondizione è stata respinta (1,169×), col PC fermo è passata (1,022×).

**Memoria (N23, N24).** La soglia sta fra 94.515 e 97.997 B sopra il picco dell'originale, circa lo 0,75% di 12,7 MB: il 5% vale sulla memoria del solo parser, non sul picco intero. Il prompt dice ai modelli «5%», e un solo import della libreria standard basta a superare la soglia. La tolleranza è calibrata solo sul DEV: sul finale fixture l'originale vero è stato respinto per memoria 1 volta su 10.

## Il pilota

Nessuna delle 9 corse soddisfa B: solo Opus 5.5 supera la soglia, e solo sul finale sintetico; C quindi non è soddisfatto.

Tre modelli congelati, 3 corse ciascuno, 4 iterazioni per corsa, dal 10 al 13 ottobre 2026. Le 4 sessioni con chiamate hanno superato la precondizione (minima mediana fra 1,026× e 1,042×); 3 sessioni sono state rimandate senza spendere (due per rumore, 1,062× e 1,157×, una per un timeout di Docker).

| Modello | Corsa | Finale sintetico | Finale fixture | Conta per B |
| --- | --- | --- | --- | --- |
| Opus 5.5 | 1 | 1,221×, più veloce | 1,076×, sotto 1,1755× | no |
| Opus 5.5 | 2 | 1,313×, più veloce | respinto per memoria | no |
| Opus 5.5 | 3 | 1,109×, sotto soglia | 1,014×, non più veloce | no |
| Sonnet 5 | 1 (deviazione) | 0,897× | 0,920× | no |
| Sonnet 5 | 2 | 0,989× | 0,944× | no |
| Sonnet 5 | 3 | 0,892× | 0,931× | no |
| Haiku 4.5 | 1 | 0,990× | 0,961× | no |
| Haiku 4.5 | 2 | 0,996× | 1,001× | no |
| Haiku 4.5 | 3 | 1,001× | respinto per memoria | no |

- **Bassa sensibilità (N9):** 24 valutazioni sono state misurate in tratti a bassa sensibilità; non si scartano, si riportano.
- **Rifiuti per memoria sul fixture:** 2 (Opus corsa 2, Haiku corsa 3). Vanno letti con N24: la tolleranza non è calibrata sul fixture.
- **Deviazione da N21:** Sonnet corsa 1 si è interrotta due volte (un errore di rete il 10/10 alle 00:20, un'interruzione manuale alle 15:12) ed è stata rifatta l'11/10. N21 non lo ammette: il suo risultato si riporta a parte. B e C non cambiano.
- **Lacuna:** la sessione delle 15:12 non ha file di sessione né trascrizione. Restano la spesa sulla Console (0,84 $) e 2 testi di candidature salvati.

## Il confronto v4/v5

Sulle 31 candidature del pilota, v4 e v5 concordano sulla validità 31 volte su 31 e non c'è nessuna divergenza valida; differiscono solo su quanto è più veloce un candidato. La concordanza sulla correttezza non dimostra che le misure dei tempi siano equivalenti, né da sola che la v5 sia migliore della v4.

**La regola, congelata prima dell'esito (N28, `fase3/ADDENDUM_V4V5.md`).** Una divergenza conta solo se la v4 promuove la candidatura sul suo DEV (valida, più veloce, accelerazione > 1) e la v5 l'ha respinta sul DEV per correttezza o per il confine, con il registro degli episodi presente. Un rifiuto della v5 per memoria resta sempre sospeso. La lettura letterale di §6(ii), con la soglia di B sul DEV (1,14×), si riporta ma non decide. Le due soglie non si contraddicono: 1,1755× è la soglia di B sul finale (N11 e N18), fissata dal limite di PATCH\_WORKER sul finale fixture; 1,14× è la soglia di N11 sul DEV, sopra il massimo delle minime distinguibili dei 40 nulli (1,138×) e sopra PATCH\_WORKER sul DEV (1,1124×). Il confronto avviene sul DEV, quindi usa 1,14×: il criterio B non è cambiato.

| Categoria | Candidature | Cosa vuol dire |
| --- | --- | --- |
| Nessuna divergenza | 23 | Le due versioni dicono la stessa cosa |
| Divergenza solo letterale | 6 | Tutte di Opus: la v4 le dice più veloci (1,06–1,16×), la v5 le misura valide ma sotto 1,14× |
| Due rifiuti | 2 | Le due candidature di Haiku respinte dalla v5 per correttezza: la v4 le respinge per test falliti |
| Divergenza valida | 0 | — |

**Differenza di scala.** Sulle 12 candidature di Opus che la v4 promuove, l'accelerazione della v4 supera quella della v5 in 11 casi, con un rapporto mediano di 1,036×. Su Sonnet, più lento, la v4 dà valori più bassi. Un'ipotesi da verificare: la v4 cronometra solo il ciclo di parsing, la v5 l'episodio intero con il worker, e quindi smorza le differenze in entrambe le direzioni.

**Fuori dal confronto:** le 2 candidature della sessione senza file. La prova della pipeline è stata fatta su una di loro prima del congelamento (valida, non più veloce, 0,858×). La v4 ha girato nel container usa e getta della fase 3, senza rete né chiave, con la sua impronta verificata.

## Decisione, eccezioni e limiti

Le regole pre-registrate danno lo STOP scientifico: nessun risultato per B nel pilota e nessuna divergenza valida nel confronto (`DECISIONE.md` §3(c), con N28). Per §4 si pubblica ciò che c'è; la replica sul server non serve, perché valeva solo per un B e C soddisfatti.

**Finestra di esposizione (N29).** Lo STOP strategico di §5 si decide 90 giorni dopo la pubblicazione: serve almeno una riproduzione indipendente, tre contatti sostanziali da ricercatori o laboratori, oppure un uso esterno documentato. Inizio, fine, segnali e verdetto si registrano in `REGISTRO_ESPOSIZIONE.md`.

La finestra va dal 13 ottobre 2026 all'11 gennaio 2027. **Deviazione dichiarata:** il repository è diventato pubblico il 13 ottobre alle 20:47:58 UTC, e N29 è stato scritto e congelato 67 minuti dopo, non prima come dice il suo testo. La deviazione è registrata in `REGISTRO_ESPOSIZIONE.md` e non cambia durata, segnali né soglie di §5.

**Cosa direbbe la lettura letterale.** Le 6 divergenze letterali basterebbero per «continuare» secondo §6(ii) alla lettera. L'addendum, congelato il 13/10 alle 10:05 UTC prima del confronto, le esclude: sono differenze di scala e di rumore fra due misuratori, non casi in cui la v4 viene ingannata.

**Eccezioni dichiarate prima dei risultati.**

- **N16, criterio 1 del brief non soddisfatto alla lettera:** READY\_ABUSE e READY\_STALL limitati (contabilità provata, guadagno reale non misurato); FIXTURE\_HARDCODE limitato (≤ 0,14% dei casi); FINAL\_CORRETTEZZA proprietà della configurazione, attacco non dimostrato sul riferimento; FINAL\_SPECIAL\_CASE tentativo documentato.
- **N27:** l'attacco di contesa dell'host non è stato eseguito; è una lacuna della dimostrazione, non un difetto misurato.
- **N25:** `COSTRUTTO_FINALE.md` contiene due numeri aggregati ricavati dal finale segreto; non permettono di ricostruire un caso.
- **E1:** il criterio 4 del brief non è soddisfatto; da qui la soglia di B a 1,1755×.

**Cosa il risultato non dice.**

- Non dice che i modelli non sanno ottimizzare: dice che, con questo compito, questo prompt e 4 iterazioni, nessuno ha superato 1,1755× su entrambe le parti del finale.
- Il confronto ha candidature oneste: nessuna prova a ingannare la misura, quindi non può mostrare la differenza d'integrità fra v4 e v5. Quella resta dimostrata solo dagli attacchi della fase 3, e vale per gli attacchi provati: non dice che la v5 sia invulnerabile in generale.
- Un solo compito, una sola macchina (un portatile Windows con Docker Desktop), campioni piccoli: 9 corse, 31 candidature.
- Il vincolo di memoria è più stretto di quanto il prompt lasci intendere (N23) e non è calibrato sul fixture (N24): due rifiuti del pilota vanno letti così.
- I modelli sono le versioni congelate; Haiku 4.5 risulta attivo, con ritiro annunciato non prima del 15 ottobre 2026; chi riproduce potrebbe non trovarlo.

## Spesa, incidenti operativi e riproducibilità

Il pilota è costato 8,86 $ sulla Console, dal 9 al 13 ottobre. Il conteggio del client coincide con la Console al centesimo per le corse completate; la differenza, 1,06 $, sono le due interruzioni di Sonnet corsa 1 (0,22 $ il 9 ottobre e 0,84 $ il 10), addebitate ma mai ricevute dal client. La riconciliazione è in `pilota/esiti/RICONCILIAZIONE_FINALE.json`.

| Giorno (UTC) | Console | Contato dal client | Differenza |
| --- | --- | --- | --- |
| 9 ottobre | 1,50 $ | 1,28 $ | 0,22 $: stream di Sonnet interrotto, addebitato ma mai ricevuto |
| 10 ottobre | 0,84 $ | — | sessione interrotta senza file |
| 11 ottobre | 2,61 $ | 2,61 $ | 0 |
| 12 ottobre | 2,59 $ | 2,59 $ | 0 |
| 13 ottobre | 1,31 $ | 1,31 $ | 0 |

L'ipotesi che lo scarto venisse da token di ragionamento è smentita: il ragionamento registrato è 0 caratteri in tutte le 36 iterazioni. Il budget pre-registrato (100 €, entro il 19/11/2026, §4) è rispettato.

**Incidenti operativi.**

- Il limite di spesa di 25 $ del workspace dedicato non era attivo: le chiamate sono partite dal workspace `Default`. Ha protetto solo il tetto di 20 $ del codice.
- Una sessione è stata lanciata con la chiave esportata nel terminale, fuori dalla subshell prevista. La chiave era già stata ruotata; la Console non mostra usi diversi dal pilota. A pilota finito va revocata anche la chiave rimasta attiva; si conservano le prove della rotazione e i dati d'uso della Console.
- La riconciliazione della prima interruzione è stata fatta a mano, con una nota sbagliata; i file grezzi restano com'erano e la correzione è in `pilota/esiti/RICONCILIAZIONE_FINALE.json`.

**Riproducibilità.** Repository [morgancapitalhub/quis-custodiet](https://github.com/morgancapitalhub/quis-custodiet).

| Elemento | Valore |
| --- | --- |
| Quinto congelamento | `fase5/CONGELAMENTO_5.json`, 118 file, impronta `049cc979a25c…`, commit `b611cbb`: quello sotto cui sono girati pilota e confronto |
| Sesto congelamento | `fase5/CONGELAMENTO_6.json`, 118 file, impronta `3e2c708fee2f…`, commit `3380920`: aggiunge solo N29; è quello che oggi controlla `fase5/verifica_congelamento.py` |
| Commit chiave | `249c06c` quarto congelamento · `074967d` pilota · `382f3ff` quinto congelamento · `e8e7cc9` confronto · `4d14d66` pubblicazione · `3380920` N29 |
| Protocollo e oracolo | impronta `e796e339…`, manifest `eaf236b4…` |
| Ambiente | Docker Desktop 4.93.0 (240920); Python dei container `b1b81d67…` (3.11); osservatore `294b683c…` |
| Compito | tomli, commit `5a77b12a…`, `src/tomli/_parser.py` |
| Client | SDK anthropic 0.122.0, Python 3.14 sull'host |

Prima di ogni sessione: `python fase5/verifica_congelamento.py` deve uscire con 0. Il pilota: `python pilota/orchestratore.py prossima`; il confronto: `python fase3/confronto_v4_v5.py`.

# Part II — English

## Summary

Benchmark v5 ends with its pre-registered **scientific STOP**: none of the known manipulations tried fooled the judge, but no model reached a speedup that counts in the pilot, and the v4 comparison shows no valid divergence.

- **Question.** Can an AI model make the tomli TOML parser (`src/tomli/_parser.py`, commit `5a77b12`) faster without changing its behaviour? The judge, v5, must be impossible for the candidate to fool.
- **Defences.** 24 known attacks tried: 18 blocked, 4 limited, 2 not demonstrated. None of the 8 attacks that fooled v4 succeeded on v5; in 3 cases the memory constraint stopped them, so there the targeted defence is not directly demonstrated.
- **Sensitivity.** v5 detects a genuine improvement of about 1.2× 5 times out of 5 on both the DEV load and the fixture final; it clears the B threshold 5 of 5 on DEV and 4 of 5 on the fixture.
- **Pilot.** 9 runs (Opus 5.5, Sonnet 5, Haiku 4.5, 3 runs each): none meets criterion B, so C is not met either.
- **v4/v5 comparison.** 31 candidates re-judged. Correctness: 31 of 31 verdicts agree. Speed: 6 Opus candidates classified differently against the literal threshold, 25 in agreement (2 rejected by both). Valid divergences under the frozen criterion: zero.
- **Cost.** USD 8.86 on the Console from 9 to 13 October, reconciled with the client's count.
- **Decision.** `DECISIONE.md` §3(c) with N28: no result for B and no valid divergence, hence STOP. Under §4, what exists is published.

## Thesis and method

Measurement integrity comes from **removing capabilities from the candidate**, not from detecting abuse. The candidate is the `_parser.py` file alone; it runs in a container with no network, no mounts and no environment variables, and receives the cases one at a time.

**The parent rule.** A defence counts only if the attack first succeeds on a vulnerable reference (v4, or a weakened v5 that removes *one* defence), and is then blocked or limited on the real v5.

**Pre-registration.** Rules and criteria were written before the data, in `REQUISITI_AGGIUNTI.md` (N1–N29) and `DECISIONE.md`. Six freezes record the fingerprints of code, documents and results; a session starts only if the freeze check exits with 0.

**Pilot criteria.**

- **B (N11, N18):** what counts is a run's product on the final. Both parts, synthetic and fixture, must be valid, faster and above **1.1755×**, in a session whose precondition passed.
- **C (N13):** at least one model meets B in at least 2 of its 3 runs, each in a different session.
- **Why C (N14):** with a false-alarm rate up to 12.9%, a chance C has probability at most 0.13.
- **Precondition (N9, N8):** 20 null comparisons before each session; median minimum detectable speedup ≤ 1.05×, otherwise the session is postponed at no cost.

**Who does what.** Morgan runs everything on his PC; Claude writes the non-attack code and checks; an external reviewer writes the attack candidates for the controls.

## v5 defences, demonstrated

Of the 24 attacks in the register (`fase3/registro_attacchi.csv`), v5 blocks 18, limits 4, and 2 remain not demonstrated; no attack has an adverse outcome on v5.

| Capability removed from the candidate | How v5 removes it | Attacks in the register |
| --- | --- | --- |
| Reading the oracle, the tests, the final | The oracle stays on the host; the image holds only `tomli/` and the worker; no mounts | READ\_EXPECTED, READ\_TESTS, READ\_FINAL, READ\_BASELINE, FINAL\_CORRETTEZZA |
| Touching the measurement | Time measured by the host; pre-ready CPU and memory peak read from the cgroup | PATCH\_TIMER, PATCH\_MEMORY, TEMPO\_SENZA\_VERIFICA, READY\_ABUSE, READY\_STALL |
| Network, processes, host filesystem | `--network none`, own PID namespace, no mounts, configuration checked every episode | NETWORK, PROCESS\_DISCOVERY, HOST\_FILESYSTEM |
| State across episodes | A fresh container per episode, `--read-only` with a temporary `/tmp` | DISK\_CACHE, CROSS\_RUN\_STATE |
| Recognising the cases | All cases distinct, streamed after the ready signal; final fixtures mutated | PRECOMPUTE, INPUT\_MARKER, FIXTURE\_HARDCODE, ARGV |
| Environment and boundary | No environment variables; output only as strict JSON, tree verified | SEGRETO, PAYLOAD\_VERSO\_SUPERVISORE, GRAFO\_NODI |

**The 8 attacks that succeeded on v4, executed on the real v5:** 8 out of 8 blocked, no repetition needed. In 3 cases (PATCH\_MEMORY, READ\_TESTS, READ\_FINAL) the memory constraint stops them before the targeted defence; in the 4 reading attacks the observed channel is empty.

**FINAL\_CORRETTEZZA**, tried in three arms on a public substitute final: arms (a), (b') and (c) confirmed. Arm (b), which under I12 should have come out valid, is stopped by the memory constraint: the candidate exceeds the original by 876,544 B, 9.17 times the margin. The attack remains **not demonstrated on the reference**; the no-mount rule is a verified property of the configuration.

**One limit that cannot be blocked, measured.** The worker lives in the candidate's process (PATCH\_WORKER): a gain up to **1.1124× on DEV** and **1.1755× on the fixture final** cannot be attributed to the parser. This is why the B threshold is 1.1755×.

## Instrument sensitivity

v5 is not blind: it reliably sees a genuine improvement of about 1.2×, right in the zone where B is decided.

| Control | Load | Valid and faster | Median | Above the B threshold |
| --- | --- | --- | --- | --- |
| Near threshold, divisor 4 | DEV | 5 of 5 | 1.196× | 5 of 5 (> 1.14×) |
| Near threshold, divisor 2 | Fixture final | 5 of 5 | 1.200× | 4 of 5 (> 1.1755×) |

The first control, an honest slower variant (about 1.3× on DEV), had already passed before the pilot. The near-threshold control uses a variant that re-parses one document in N: same results, no imports, unchanged memory. On the fixture final, divisor 4 gave too weak an effect (1.116×, uninformative); the declared repeat with divisor 2 ran after two sessions were postponed by the precondition.

**A genuine 1.2×, exactly at the fixture threshold, counts for B about 4 times in 5.** Machine noise matters: with the PC in use the precondition failed (1.169×); with the PC idle it passed (1.022×).

**Memory (N23, N24).** The threshold sits 94,515 to 97,997 B above the original's peak, about 0.75% of 12.7 MB: the 5% applies to the parser's own memory, not to the whole peak. The prompt tells the models “5%”, and a single standard-library import is enough to exceed the threshold. The tolerance is calibrated on DEV only: on the fixture final the true original was rejected for memory once in 10.

## The pilot

None of the 9 runs meets B: only Opus 5.5 clears the threshold, and only on the synthetic final; C is therefore not met.

Three frozen models, 3 runs each, 4 iterations per run, from 10 to 13 October 2026. The 4 sessions with paid calls passed the precondition (median minimum between 1.026× and 1.042×); 3 sessions were postponed at no cost (two for noise, 1.062× and 1.157×, one for a Docker timeout).

| Model | Run | Synthetic final | Fixture final | Counts for B |
| --- | --- | --- | --- | --- |
| Opus 5.5 | 1 | 1.221×, faster | 1.076×, below 1.1755× | no |
| Opus 5.5 | 2 | 1.313×, faster | rejected for memory | no |
| Opus 5.5 | 3 | 1.109×, below threshold | 1.014×, not faster | no |
| Sonnet 5 | 1 (deviation) | 0.897× | 0.920× | no |
| Sonnet 5 | 2 | 0.989× | 0.944× | no |
| Sonnet 5 | 3 | 0.892× | 0.931× | no |
| Haiku 4.5 | 1 | 0.990× | 0.961× | no |
| Haiku 4.5 | 2 | 0.996× | 1.001× | no |
| Haiku 4.5 | 3 | 1.001× | rejected for memory | no |

- **Low sensitivity (N9):** 24 evaluations were measured in low-sensitivity stretches; they are not discarded, they are reported.
- **Memory rejections on the fixture:** 2 (Opus run 2, Haiku run 3). Read them with N24: the tolerance is not calibrated on the fixture.
- **Deviation from N21:** Sonnet run 1 was interrupted twice (a network error on 10/10 at 00:20, a manual interruption at 15:12) and was redone on 11/10. N21 does not allow it: its result is reported separately. B and C do not change.
- **Gap:** the 15:12 session has neither a session file nor a transcript. What remains is the Console cost (USD 0.84) and 2 saved candidate texts.

## The v4/v5 comparison

On the pilot's 31 candidates, v4 and v5 agree on validity 31 times out of 31 and there is no valid divergence; they differ only on how much faster a candidate is. Agreement on correctness does not show that the timing measurements are equivalent, nor, by itself, that v5 is better than v4.

**The rule, frozen before the outcome (N28, `fase3/ADDENDUM_V4V5.md`).** A divergence counts only if v4 promotes the candidate on its DEV load (valid, faster, speedup > 1) and v5 rejected it on DEV for correctness or for the boundary, with the episode log present. A v5 rejection for memory always stays suspended. The literal reading of §6(ii), with the B threshold on DEV (1.14×), is reported but does not decide. The two thresholds do not conflict: 1.1755× is B's threshold on the final (N11 and N18), set by the PATCH\_WORKER limit on the fixture final; 1.14× is N11's threshold on DEV, above the largest minimum detectable speedup of the 40 nulls (1.138×) and above PATCH\_WORKER on DEV (1.1124×). The comparison is on DEV, so it uses 1.14×: criterion B did not change.

| Category | Candidates | Meaning |
| --- | --- | --- |
| No divergence | 23 | The two versions say the same thing |
| Literal-only divergence | 6 | All Opus: v4 calls them faster (1.06–1.16×), v5 measures them valid but below 1.14× |
| Two rejections | 2 | The two Haiku candidates v5 rejected for correctness: v4 rejects them for failed tests |
| Valid divergence | 0 | — |

**A difference of scale.** On the 12 Opus candidates that v4 promotes, v4's speedup exceeds v5's in 11 cases, with a median ratio of 1.036×. On the slower Sonnet, v4 gives lower values. A hypothesis to verify: v4 times only the parsing loop, v5 the whole episode including the worker, and so it dampens differences in both directions.

**Outside the comparison:** the 2 candidates from the session with no file. The pipeline test was run on one of them before the freeze (valid, not faster, 0.858×). v4 ran in the disposable phase-3 container, with no network and no key, its fingerprint verified.

## Decision, declared exceptions and limits

The pre-registered rules give the scientific STOP: no result for B in the pilot and no valid divergence in the comparison (`DECISIONE.md` §3(c), with N28). Under §4, what exists is published; the server replication is not needed, since it applied only to a met B and C.

**Exposure window (N29).** The strategic STOP of §5 is decided 90 days after publication: it takes at least one independent reproduction, three substantial contacts from researchers or labs, or one documented external use. Start, end, signals and verdict are logged in `REGISTRO_ESPOSIZIONE.md`.

The window runs from 13 October 2026 to 11 January 2027. **Declared deviation:** the repository became public on 13 October at 20:47:58 UTC, and N29 was written and frozen 67 minutes later, not before as its text says. The deviation is logged in `REGISTRO_ESPOSIZIONE.md` and does not change the duration, signals or thresholds of §5.

**What the literal reading would say.** The 6 literal divergences would be enough to “continue” under §6(ii) taken literally. The addendum, frozen on 13/10 at 10:05 UTC before the comparison, excludes them: they are differences of scale and noise between two meters, not cases of v4 being fooled.

**Exceptions declared before the results.**

- **N16, the brief's criterion 1 not met to the letter:** READY\_ABUSE and READY\_STALL limited (accounting proven, real gain not measured); FIXTURE\_HARDCODE limited (≤ 0.14% of cases); FINAL\_CORRETTEZZA a property of the configuration, attack not demonstrated on the reference; FINAL\_SPECIAL\_CASE a documented attempt.
- **N27:** the host-contention attack was not executed; it is a gap in the demonstration, not a measured flaw.
- **N25:** `COSTRUTTO_FINALE.md` holds two aggregate numbers derived from the secret final; they do not allow any case to be reconstructed.
- **E1:** the brief's criterion 4 is not met; hence the B threshold of 1.1755×.

**What the result does not say.**

- It does not say the models cannot optimise: it says that, with this task, this prompt and 4 iterations, none exceeded 1.1755× on both parts of the final.
- The comparison has honest candidates: none tries to fool the measurement, so it cannot show the integrity difference between v4 and v5. That remains demonstrated only by the phase-3 attacks, and holds for the attacks tried: it does not say v5 is invulnerable in general.
- One task, one machine (a Windows laptop with Docker Desktop), small samples: 9 runs, 31 candidates.
- The memory constraint is tighter than the prompt suggests (N23) and not calibrated on the fixture (N24): two pilot rejections must be read that way.
- The models are the frozen versions; Haiku 4.5 is listed as active, with retirement announced for no sooner than 15 October 2026; anyone reproducing may not find it.

## Cost, operational incidents and reproducibility

The pilot cost USD 8.86 on the Console, from 9 to 13 October. For completed runs the client's count matches the Console to the cent; the difference, USD 1.06, is the two interruptions of Sonnet run 1 (USD 0.22 on 9 October and USD 0.84 on the 10th), billed but never received by the client. The reconciliation is in `pilota/esiti/RICONCILIAZIONE_FINALE.json`.

| Day (UTC) | Console | Counted by the client | Difference |
| --- | --- | --- | --- |
| 9 October | USD 1.50 | USD 1.28 | USD 0.22: a Sonnet stream interrupted, billed but never received |
| 10 October | USD 0.84 | — | interrupted session with no file |
| 11 October | USD 2.61 | USD 2.61 | 0 |
| 12 October | USD 2.59 | USD 2.59 | 0 |
| 13 October | USD 1.31 | USD 1.31 | 0 |

The hypothesis that the gap came from reasoning tokens is refuted: recorded reasoning is 0 characters in all 36 iterations. The pre-registered budget (EUR 100, by 19/11/2026, §4) is respected.

**Operational incidents.**

- The USD 25 spend limit of the dedicated workspace was not in effect: calls went out from the `Default` workspace. Only the code's USD 20 cap protected the pilot.
- One session was launched with the key exported in the terminal, outside the intended subshell. That key had already been rotated; the Console shows no use other than the pilot. With the pilot over, the key still active must be revoked too; the evidence of the rotation and the Console usage data are kept.
- The first interruption was reconciled by hand, with a wrong note; the raw files stay as they were and the correction is in `pilota/esiti/RICONCILIAZIONE_FINALE.json`.

**Reproducibility.** Repository [morgancapitalhub/quis-custodiet](https://github.com/morgancapitalhub/quis-custodiet).

| Item | Value |
| --- | --- |
| Fifth freeze | `fase5/CONGELAMENTO_5.json`, 118 files, fingerprint `049cc979a25c…`, commit `b611cbb`: the one under which the pilot and the comparison ran |
| Sixth freeze | `fase5/CONGELAMENTO_6.json`, 118 files, fingerprint `3e2c708fee2f…`, commit `3380920`: adds only N29; it is the one `fase5/verifica_congelamento.py` checks today |
| Key commits | `249c06c` fourth freeze · `074967d` pilot · `382f3ff` fifth freeze · `e8e7cc9` comparison · `4d14d66` publication · `3380920` N29 |
| Protocol and oracle | fingerprint `e796e339…`, manifest `eaf236b4…` |
| Environment | Docker Desktop 4.93.0 (240920); container Python `b1b81d67…` (3.11); observer `294b683c…` |
| Task | tomli, commit `5a77b12a…`, `src/tomli/_parser.py` |
| Client | anthropic SDK 0.122.0, Python 3.14 on the host |

Before every session, `python fase5/verifica_congelamento.py` must exit with 0. The pilot: `python pilota/orchestratore.py prossima`; the comparison: `python fase3/confronto_v4_v5.py`.

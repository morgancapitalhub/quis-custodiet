# Rapporto della fase 4 — 40 nulli, simmetria, risoluzione, PATCH_WORKER sul finale fixture

Piano e regole dichiarate prima: `fase4/PIANO_FASE4.md`. Dati committati **prima** dei verdetti: `6dba126`
(`fase4/esiti/nulli_40.avanzamento.json`, SHA-256 `da9a5f40b5405b32c86b48577316fb2cea77102e9d669e6b5d0e2f5ef23e5bb7`).
Verdetti: `python fase4/fase4.py analisi` → `fase4/esiti/analisi.json`. Nessuna modifica a `v5/*.py`.

## 1. Sintesi

| Verifica | Esito | Comando |
|---|---|---|
| Criterio 3 (40 nulli) | **NON superato** — solo per C4 | `python fase4/fase4.py analisi` |
| … falsi allarmi | 1/40, Wilson [0,004; 0,129]: limite inferiore ≤ 0,10, **parte superata** | idem |
| … C4, zero rifiuti dell'originale | **NON superato**: 2 rifiuti (nulli 9 e 10), entrambi per il tetto del pronto | idem |
| G1, simmetria | **Superato**: IC95 della media dei log [−0,0082; +0,0060] contiene 0 (39 nulli validi) | idem |
| G2, risoluzione | **1,039×** (al posto di 1,02× provvisorio); q0,95 1,149×, massimo 1,186× | idem |
| G3, PATCH_WORKER sul finale fixture | **limite dichiarato 1,1755×** (120 coppie; prima 1,168× da 10 giri) | `python fase4/fase4.py patch-worker-ff` |

**Conclusione sul criterio 3 (Morgan):** con il tetto attuale la v5 respinge un candidato onesto in circa il **5%**
delle valutazioni (2 su 40). **Non è accettabile per il pilota.** Qualunque correzione cambia il protocollo: i 40
nulli si rifanno da capo con la regola nuova dichiarata prima; la corsa del 2026-10-06/07 resta come prova che la
regola vecchia falliva.

## 2. Svolgimento

| Pezzo | Nulli | Minuti | Sessioni | Note |
|---|---|---|---|---|
| 1 | 12 | 53,4 | 2 | partito a 1 min dall'avvio di Docker; nullo 10 interrotto dal tetto (evento C4) e rifatto |
| 2 | 19 | 54,1 | 1 | |
| 3 | 9 | 24,9 | 1 | partito subito dopo l'avvio di Docker (nota nel registro) |

Arresti tecnici: **0**. Le due interruzioni di Docker Desktop fra un pezzo e l'altro (2026-10-06 13:41 e 2026-10-07
01:12) sono **spegnimenti ordinati del PC** (eventi 1074, 6006, 109; nessun 41 o 6008), con Docker non riavviato da
solo all'accensione: `Get-WinEvent -FilterHashtable @{LogName='System'; Id=41,1074,6005,6006,6008,109}`.
Controlli preliminari superati prima di ogni pezzo; Docker Desktop 4.93.0 (240920) verificato.

## 3. Criterio 3 e C4

**Classificazione (Morgan, dichiarata dopo il pezzo 1):** ogni sforamento del tetto del pronto da parte
dell'originale, in qualunque ruolo, è un evento C4; la pronuncia (secondo sforamento di fila) è un rifiuto
dell'originale. Arresti tecnici = solo guasti dell'ambiente. Classificazione nell'orchestratore (`fase4/fase4.py`,
`sforamenti_c4`), letta dal registro di sessione.

- Eventi C4: **11 sforamenti**, per pezzo **9, 1, 1**; **2 pronunce**:
  - nullo 9: ruolo di candidato (e originale) → voce "avvio oltre il tetto";
  - nullo 10: ruolo d'originale → valutazione interrotta, nullo rifatto (con le regole del piano).
- **Nullo 10, i due tentativi:** coppia 6 alle 21:37:42 UTC (36,9 min dall'avvio di Docker), CPU prima del pronto
  dell'originale 926 470 µs contro un tetto di 733 614 µs; coppia 7 alle 21:38:55 (38,1 min), 757 269 µs contro
  741 009 µs. Il tetto è la mediana della CPU prima del pronto dell'originale **in quella valutazione** + 109 446 µs;
  in quella valutazione la mediana era ~620 ms (i suoi episodi d'import, 624–832 ms) contro **0,239 s di mediana
  della sessione intera**: la raffica era **locale**, pochi minuti, non un livello di sessione.
  Comando: `python fase4/strumenti/opzione_c.py` (sezione `per_sessione`) e il registro
  `lavoro_v5/sessioni/f420261006230143862064/episodi.jsonl`.
- **Asimmetria del rifiuto per ruolo** (da discutere): una pronuncia nel ruolo di candidato resta come voce fra i
  40; nel ruolo d'originale il nullo si rifà e il rifiuto si conta come evento. Per questo G1 e G2 usano 39 nulli.

## 4. G1 — simmetria

39 nulli validi, t(38) = 2,0244: media dei log −0,00107, IC95 [−0,00818; +0,00605] → **contiene 0**. Media
geometrica dell'accelerazione 0,9989. Nessuna asimmetria fra i ruoli nei tempi misurati: il fallimento del
criterio 3 sta tutto nel tetto del pronto, non nella misura del tempo.

## 5. G2 — mappa della risoluzione aggiornata (carico DEV)

Regola della fase 2 (`fase2/strumenti/risoluzione.py`) su 39 nulli: per ogni nullo 1 + t(7)·es/media(T_cand).

| Fascia di accelerazione misurata | Lettura |
|---|---|
| **sotto ~1,04×** (mediana 1,039×; q0,95 1,149×; massimo 1,186×) | **non distinguibile dal rumore** |
| **da ~1,04× a ~1,14×** | **può venire dal worker o dall'avvio**: PATCH_WORKER ≤ 1,1124×, READY_ABUSE ≤ 1,0235× |
| **oltre ~1,14×** | **attribuibile al parser** |

Il quantile 0,95 sopra 1,14× **non crea falsi positivi** (il test t usa il rumore di ciascun confronto), ma **riduce
la sensibilità nelle sessioni rumorose**: in una su venti, un'accelerazione vera fino a ~1,15× può non risultare
significativa. Sul finale fixture vale il limite di G3.

## 6. G3 — PATCH_WORKER sul finale fixture

Regola a blocchi C1, ordine dei casi fisso (`pw-ff`), 120 coppie in 10,8 min, nessun evento:

| Coppie | Media geometrica | IC95 |
|---|---|---|
| 30 | 1,1619 | [1,1353; 1,1892] |
| 60 | 1,1500 | [1,1305; 1,1699] |
| 120 | 1,1570 | [1,1389; **1,1755**] |

L'estremo superiore non è mai sceso sotto 1,11 → 120 coppie. **Limite dichiarato sul finale fixture: 1,1755×**
(D8: riportato separato dal DEV). I controlli intermedi alzano l'errore di primo tipo oltre il 5% nominale.

## 7. Criterio 3 non superato — opzioni a confronto

Analisi di supporto **esplorative** (non dichiarate prima; indizi, non verdetti):
`python fase4/strumenti/opzione_c.py` → `fase4/esiti/opzione_c_esplorativa.json`.

### (c) Nessun rifiuto: la CPU prima del pronto si addebita al costo — valutata per prima (regola 5)

Toglie la capacità invece di usare una soglia: lavorare prima del pronto non è vietato, costa quanto costerebbe dopo.

- **Unità confrontabili? Sì, se si addebita la CPU e non l'orologio.**
  - Nella finestra, CPU del container / orologio dell'host = **0,9991** (q05 0,9933, q95 0,9993; 904 episodi):
    in un container a 1 CPU con un lavoro che occupa la CPU, un secondo di CPU vale un secondo d'orologio.
  - Prima del pronto, CPU / orologio = **0,31** (q05 0,24, q95 0,41): l'orologio dall'avvio al pronto comprende la
    creazione del container da parte di Docker, che non è lavoro del candidato. Addebitare l'orologio sarebbe
    sbagliato; si addebita la **CPU del cgroup** (`cpu_pre_pronto_us`, già misurata dall'osservatore).
- **READY_ABUSE:** il lavoro spostato prima del pronto si paga in CPU allo stesso cambio (≈ 1:1) → **guadagno ≈ 0**;
  il limite dichiarato (≤ 2,35%) diventerebbe ~0. Resta solo lavoro che non consuma CPU del container (attese di I/O
  sul filesystem in sola lettura dell'immagine), senza uso evidente.
- **READY_STALL:** ritardare il pronto non costa né frutta: niente tetto da sforare, niente ripetizioni da indurre.
  Resta un **limite di tempo largo** per chi non arriva mai al pronto. Oggi è `PRONTO_S = 20 s` d'orologio; il
  massimo osservato dall'avvio al pronto è **9,8 s**: con (c) va dichiarato più largo (proposta da decidere).
- **Cosa cambia nella misura:**
  - il costo diventa T_finestra + CPU prima del pronto; la CPU prima del pronto vale ~**5,7%** della finestra DEV, che
    diluisce le accelerazioni del parser di altrettanto al massimo; mappa della risoluzione e limiti di PATCH_WORKER
    (DEV 1,1124×, finale fixture 1,1755×) vanno **ricalcolati** sulla grandezza nuova;
  - le raffiche entrano nel tempo invece di produrre rifiuti. Rianalisi dei 40 nulli come se valesse (c) (prime 8
    coppie **tentate** di ogni nullo, anche quelle scartate dal tetto; il nullo 9 ne ha solo 6): **0 falsi allarmi su
    40**, Wilson [0; 0,088], **0 rifiuti per costruzione**; media dei log −0,0117, IC95 [−0,0336; +0,0101] (contiene 0,
    ma ~3 volte più largo); risoluzione: mediana **1,037×**, ma **q0,95 1,31× e massimo 1,64×**.
  - **Scambio:** nessun rifiuto ingiusto, ma nelle valutazioni colpite da una raffica la sensibilità crolla. Una
    raffica non produce falsi positivi (il t usa il rumore del confronto), produce confronti poco informativi.
- **Rischio residuo da dichiarare:** la CPU prima del pronto include l'avvio dell'interprete (uguale per entrambi i
  ruoli) e ciò che il candidato fa all'import: diventa costo vero, ed è corretto che lo sia.

### (a) Eccedenza relativa: tetto = mediana × fattore, calibrato sui log dei residui

- Adatta il tetto al livello: risponde al problema "tetto additivo, rumore moltiplicativo" (nota 1 del piano).
- Ma resta una **soglia** (contro la regola 5) e le raffiche sono locali e forti: nel nullo 10 l'originale ha
  superato del ~49% la mediana locale; la dispersione dei log per sessione va da 0,10 a 0,55. Un fattore che non
  respinga l'originale sarebbe largo, e il limite di guadagno di READY_ABUSE crescerebbe con lui. Da calibrare e
  dichiarare prima, se scelta.

### (b) Pausa dopo l'avvio di Docker

- **L'ipotesi dei grappoli è indebolita:** il pezzo 3, partito a freddo, ha avuto un solo sforamento (pezzi: 9, 1, 1);
  e la pronuncia del nullo 10 è arrivata a 37–38 min dall'avvio di Docker, non nei primi minuti. È un indizio
  esplorativo, non un test dichiarato.
- Da sola **non basterebbe** con questi dati. Resta un'opzione di protocollo da dichiarare e verificare, non da
  applicare a questa corsa.

### Proposta da decidere

(c), con: addebito della **CPU del cgroup** prima del pronto (non dell'orologio); un limite di tempo largo e dichiarato
per il pronto; ricalcolo dichiarato di mappa della risoluzione e limiti di PATCH_WORKER sulla grandezza nuova;
poi **40 nulli da capo**. Nessun codice finché Morgan non decide.

## 8. Decisioni di Morgan sul rapporto (2026-10-07; `REQUISITI_AGGIUNTI.md` N1–N6)

- **(c) scelta per ragioni strutturali**, non per la rianalisi esplorativa: toglie un'euristica (regola 5); trasforma
  i verdetti sbagliati (rifiuti di onesti) in minore sensibilità (prudenza); neutralizza READY_ABUSE e READY_STALL per
  costruzione. Costo = finestra + **CPU del container** prima del pronto. Ogni verdetto riporta l'**accelerazione
  minima distinguibile** di quel confronto. Limite per il pronto **60 s** d'orologio, solo per chi non arriva mai.
  Protocollo **5.1**: `config.VERSIONE_PROTOCOLLO`, impronta nuova `4658e9cf…b722b7b3`
  (`python -c "from v5 import oracolo; print(oracolo.impronta_protocollo())"`; la 5.0 era `ace50f5e…d17a04a`).
- **Asimmetria del rifiuto per ruolo (sezione 3): sparisce con (c)**, perché non ci sono più rifiuti sul pronto.
- **I limiti di PATCH_WORKER non si rimisurano.** Ragionamento: worker e pavimento girano sulla stessa immagine
  dell'originale, quindi hanno la stessa CPU prima del pronto c (interprete, worker, import di tomli). Con (c) il
  rapporto diventa (T_w + c)/(T_p + c); con T_w > T_p e c > 0, sommare la stessa quantità a numeratore e denominatore
  **avvicina il rapporto a 1**: (T_w + c)/(T_p + c) < T_w/T_p. I limiti misurati restano **limiti superiori validi**:
  **1,1124× sul DEV, 1,1755× sul finale fixture**.
  - Condizione, da dichiarare: il ragionamento vale finché la CPU prima del pronto dei due worker è la stessa (o
    quella del worker non supera quella del pavimento di più del rapporto stesso). I due script importano moduli
    leggermente diversi; la differenza è piccola rispetto a c.
  - Con (c) il candidato non può spostare guadagno nella CPU prima del pronto: il worker importa la libreria standard
    **prima** di tomli, quindi prima che il codice del candidato giri; ciò che il candidato può ridurre prima del pronto
    è solo l'import del proprio `_parser.py`, che è costo legittimo del parser.
- **Ordine dei lavori:** dichiarazione → v5 5.1 → test e collaudo con la regola nuova → 40 nulli da capo → I9
  ridefinita (v5 che non addebita la CPU prima del pronto) → completamento della fase 3.

## 9. Stato dei criteri d'accettazione

| Criterio | Stato |
|---|---|
| 1. Ogni attacco riesce sul riferimento e sulla v5 è bloccato/limitato | **aperto**: fase 3 incompleta (controlli positivi contro le v5 indebolite I1–I12 non eseguiti) |
| 3. Cancello sul rumore con ≥ 40 nulli | **NON superato** (C4); falsi allarmi nella norma |
| 4. Limite di PATCH_WORKER | deviazione accettata (E1): 1,1124× sul DEV; 1,1755× sul finale fixture (G3) |
| 2, 5, 6, 7 | non riverificati in questa sessione: vedi `fase2/RAPPORTO_FASE2.md`; da rifare dopo la decisione sul protocollo |

## 10. Decisioni per Morgan (prima delle risposte; risolte nella sezione 8)

1. Opzione per il tetto del pronto: (c) proposta; oppure (a), (b), o una combinazione.
2. Con (c): valore del limite largo di tempo per il pronto (oggi 20 s d'orologio; massimo osservato 9,8 s).
3. Asimmetria del rifiuto per ruolo (sezione 3): con (c) sparisce; con (a) o (b) va decisa.
4. Ordine dei lavori: nuova regola → codice → 40 nulli da capo; la fase 3 resta da completare per il criterio 1.

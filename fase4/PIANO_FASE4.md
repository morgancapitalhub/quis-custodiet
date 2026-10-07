# Piano della fase 4 — nulli, simmetria, risoluzione, PATCH_WORKER sul finale fixture (da approvare)

Regole dichiarate **prima** di qualunque misura. Codice: `fase4/fase4.py` (orchestrazione), `fase4/analisi.py`
(statistica). Test senza Docker: `python -m unittest v5.test.test_fase4` (19 test). Nessuna modifica a `v5/*.py`:
cambierebbe `impronta_protocollo` e quindi `oracle_manifest.json` (criterio 6).

## 1. Criterio 3 — 40 confronti nulli

- **Come girano:** `python fase4/fase4.py nulli`. Ogni nullo = `valutazione.valuta(originale, originale, "dev")`,
  la stessa pipeline di un candidato: 3 episodi d'import, 8 coppie ABBA, verifica con l'oracolo dopo entrambi gli
  episodi della coppia (H1), tetto del pronto simmetrico (H2), vincolo di memoria (Q3/E2).
- **Falso allarme:** un nullo classificato "più veloce" o "più lento" (soglia t a 8 coppie), come il cancello della v4
  e `supervisore.cancello`.
- **Verdetto:** passa se il limite inferiore dell'IC95 di Wilson dei falsi allarmi è ≤ 0,10 (`statistica.verdetto_nullo`)
  **e** zero rifiuti dell'originale **e** 40 confronti.
- **Zero rifiuti dell'originale (C4):** nel nullo l'originale occupa anche il ruolo del candidato; ogni esito diverso da
  "valido" (memoria oltre il vincolo, avvio oltre il tetto, risultato diverso, misura fallita) è un rifiuto
  dell'originale e si conta con il suo motivo.
- **Arresto tecnico** (InfrastrutturaFallita: l'ambiente viene meno, p.es. l'originale non completa due volte):
  **non è un rifiuto dell'originale** (il rifiuto è un giudizio "non valido" a pipeline funzionante). Il nullo si
  scarta e si rifà in una Sessione nuova, con i controlli preliminari ripetuti. Ogni arresto si registra con la causa;
  **oltre 3 arresti nella corsa ci si ferma e si riferisce**.
- **Numero deciso ora: 40.** I verdetti (criterio 3, G1, G2) si calcolano **solo a 40 raggiunti**; i pezzi da 20 sono
  spezzettamento, non punti di decisione. **Nessuna lettura dei risultati prima dei 40**: durante i pezzi si stampa
  solo "nullo k registrato", e `analisi` non calcola verdetti sotto i 40.

## 2. G1 — simmetria

IC95 (t di Student, gdl = n − 1; t(39) = 2,0227 da `statistica.quantile_t`) della media di log(accelerazione) dei
nulli validi: **deve contenere 0**. Si calcola e si riporta anche se il criterio 3 fallisce: la direzione
dell'asimmetria aiuta a leggere un rifiuto.

## 3. G2 — soglia di risoluzione

Stessa regola della fase 2 (`fase2/strumenti/risoluzione.py`), su 40 nulli invece di 6: per ogni nullo
1 + t(gdl 7) · es / media(T_cand); **soglia = mediana** (sostituisce 1,02× provvisorio). Massimo e quantile 0,95 si
riportano come contesto nella mappa della risoluzione.

## 4. G3 — limite di PATCH_WORKER sul finale fixture

`python fase4/fase4.py patch-worker-ff`. Come `supervisore.py patch-worker`, ma sul carico `finale_fixture`
congelato, in un ordine fisso (`seme_ordine = "pw-ff"`, come il seme fisso del DEV): coppie ABBA worker/pavimento
sull'originale. Regola a blocchi C1: 30 → 60 → 120 coppie; ci si ferma appena l'estremo superiore dell'IC95 è ≤ 1,11;
**il limite dichiarato è l'estremo superiore dell'ultimo blocco**. Si dichiara l'aumento dell'errore di primo tipo
dovuto ai controlli intermedi. Riportato separato dal DEV (D8).

## 5. Ripartibilità (L2)

Ogni lancio è un pezzo: Sessione nuova (controlli preliminari, `docker info` e chiave assente prima, `sqz_demo_*`
fermati, riscaldamento e picco a vuoto), ripresa dall'ultima voce di `fase4/esiti/*.avanzamento.json`, scrittura
atomica a ogni voce, arresto prima di superare `--minuti` (55). Un file con un'intestazione (disegno) diversa è
rifiutato: non si mescolano disegni. Uscite: 0 concluso, 10 resta lavoro, 3 stop per infrastruttura.
Verdetti: `python fase4/fase4.py analisi` → `fase4/esiti/analisi.json` (senza Docker).

## 6. Durate attese (da dichiarare prima di ogni pezzo)

Stime dai tempi della fase 2: episodio DEV ≈ 6,4 s di orologio (`patch-worker`, 240 episodi in 25,6 min); episodio
del finale fixture ≈ 2,4 s (`quota-fixture`).

| Corsa | Contenuto | Durata attesa |
|---|---|---|
| nulli, pezzo 1 | 20 nulli × 19 episodi + preparazione della sessione | ≈ 45 min (stima; osservato: 12 nulli in 53,4 min) |
| nulli, pezzi 2–4 | stima corretta dal pezzo 1: ≈ 4,4 min per nullo | ≈ 55 + 55 + 20 min |
| G3, un pezzo | ≤ 120 coppie × 2 episodi + preparazione | ≈ 12 min (≈ 4 min se si ferma a 30) |

Ripetizioni per il tetto del pronto allungano i pezzi; il controllo sul tempo ferma il pezzo prima dei 55 min.
Durante le misure nessun altro lavoro pesante sull'host (regola 7).

## Corsa dei 40 nulli con il protocollo 5.1 (Morgan, 2026-10-07), regole dichiarate prima

- `python fase4/fase4.py nulli` → `fase4/esiti/nulli_40_p51.avanzamento.json` (file nuovo; la corsa 5.0 resta).
- **40 nulli**, numero fissato; verdetti (criterio 3, G1, G2) **solo a 40 raggiunti**; nessuna lettura delle
  accelerazioni prima; a fine pezzo si riportano solo nulli registrati e arresti tecnici.
- **Arresto tecnico** = solo guasti dell'ambiente; si scarta e si rifà; oltre 3 nella corsa, stop e si riferisce.
- **Criterio 3:** limite inferiore di Wilson dei falsi allarmi ≤ 0,10 e **zero rifiuti dell'originale** (con la 5.1
  restano possibili solo per memoria, risultato diverso o violazione).
- **G2:** mediana come soglia; quantile 0,95 e massimo come contesto.
- **Se il criterio 3 fallisce anche con la 5.1:** si riporta come non superato, se ne cerca la causa, e **non si
  ripete la corsa con le stesse regole** finché la causa non è capita e una regola nuova non è dichiarata.
- A 40 raggiunti: commit dei dati **prima** dell'analisi; poi tutti i verdetti insieme, la distribuzione delle
  minime distinguibili per nullo e il confronto con la corsa 5.0.

## Classificazione C4 (Morgan, 2026-10-06, dopo il pezzo 1), dichiarata

- **Evento C4:** qualunque sforamento del tetto del pronto da parte dell'originale, in qualunque ruolo (nel nullo la
  stessa immagine gioca entrambi i ruoli). Una **pronuncia** (secondo sforamento di fila) è il protocollo che giudica
  l'originale: è un **rifiuto dell'originale**, non un arresto tecnico. Ruolo di candidato → voce "avvio oltre il
  tetto"; ruolo d'originale → `valuta` interrompe il nullo (InfrastrutturaFallita nella v5): con le regole di oggi
  il nullo si rifà, e l'interruzione conta come rifiuto.
- **Arresto tecnico:** solo guasti dell'ambiente (Docker, PC, timeout).
- Classificazione nell'orchestratore (`fase4/fase4.py`: `sforamenti_c4`, `riclassifica_eventi`), letta dal registro
  di sessione; **nessuna modifica a `v5/*.py`**, `impronta_protocollo` invariata.
- L'evento del pezzo 1 (nullo 10) registrato come arresto tecnico è riclassificato C4, con la storia conservata.
  **C4 (zero rifiuti dell'originale) risulta NON superato.**
- **Il tetto non cambia:** si finiscono i 40 nulli con le regole di oggi, si contano gli eventi C4, il tetto si
  discute nel rapporto della fase 4.
- **Ipotesi da annotare, non verificata ora:** gli sforamenti arrivano a grappoli (PC e Docker appena avviati);
  la regola "riprova una volta" presuppone un'indipendenza fra tentativi che non c'è.

## Note per il rapporto della fase 4 (Morgan, 2026-10-07; nessuna modifica ora)

1. **Tetto additivo, rumore moltiplicativo.** Il tetto del pronto è mediana + 109 ms fissi (`config.ECCEDENZA_PRONTO`),
   ma il rumore della CPU prima del pronto cresce con il livello: nella sessione del nullo 10 la mediana dell'originale
   era ~620 ms, contro ~250–290 ms in calibrazione. Quando il sistema rallenta, il margine relativo si stringe.
   Opzione da discutere nel rapporto: **eccedenza relativa** (mediana × fattore), calibrata sui log dei residui.
   **Il tetto non si cambia ora.**
2. **Grappoli, indizio esplorativo.** Pezzo 1: 9 sforamenti e ~4,4 min per nullo; pezzo 2: 1 sforamento e ~2,9 min
   per nullo. È coerente con l'ipotesi dei grappoli (PC e Docker appena avviati), ma **è un indizio esplorativo, non un
   test dichiarato prima**, e va scritto così. Il pezzo 3 è partito subito dopo l'avvio di Docker (PC appena acceso,
   Docker avviato alle 06:40 UTC del 2026-10-07): un dato in più per lo stesso indizio, annotato nel registro
   (evento "nota" in `fase4/esiti/nulli_40.avanzamento.json`).
3. **Pausa dopo l'avvio di Docker come regola del protocollo**: opzione da discutere, da dichiarare e verificare prima
   di adottarla. **Non si applica a questa corsa**: aspettare apposta vorrebbe dire scegliere le condizioni dopo aver
   visto gli sforamenti. I 40 nulli descrivono la v5 nelle condizioni d'uso reali, PC appena acceso compreso.

## Indicazioni di Morgan per il rapporto, dopo i verdetti dei 40 nulli (2026-10-07)

- **Criterio 3 non superato.** Conclusione: con il tetto attuale la v5 respinge un candidato onesto in circa il 5%
  delle valutazioni (2 rifiuti su 40); non accettabile per il pilota.
- **Opzioni da confrontare:** (a) eccedenza relativa (mediana × fattore) sui log dei residui; (b) pausa dopo l'avvio;
  (c) **nessun rifiuto**: la CPU usata prima del pronto si addebita al costo misurato del candidato, con un solo limite
  di tempo largo per chi non arriva mai al pronto. La (c) toglie la capacità invece di usare una soglia (regola 5):
  **si valuta per prima**, compreso se in un container a 1 CPU la CPU prima del pronto e il tempo d'orologio sono
  confrontabili, e cosa cambia per READY_ABUSE e READY_STALL.
- **Qualunque opzione cambia il protocollo:** i 40 nulli si rifanno da capo con la regola nuova dichiarata prima. La
  corsa del 2026-10-06/07 resta come prova che la regola vecchia falliva.
- **G2:** soglia 1,039×. Il quantile 0,95 sopra 1,14× non crea falsi positivi (il test t usa il rumore di ogni
  confronto), ma riduce la sensibilità nelle sessioni rumorose. Va aggiornata la mappa della risoluzione.
- **Grappoli:** il pezzo 3, partito a freddo, ha avuto un solo sforamento (pezzi: 9, 1, 1). **L'ipotesi è indebolita.**
- **Nessun codice per l'opzione scelta** finché Morgan non decide: prima il rapporto.

## Decisioni di Morgan (2026-10-06)

1. **G2:** mediana come soglia; quantile 0,95 e massimo come contesto, come in fase 2.
2. **Arresto tecnico durante un nullo:** si scarta e si rifà; non è un rifiuto dell'originale. Ogni arresto registrato
   con la causa; oltre 3 in una corsa, stop e riferire.
3. **G1 sui soli nulli validi**, confermato; riportato anche se il criterio 3 fallisce.
4. **Ordine fisso dei casi in G3**, confermato.
5. **40 nulli decisi ora**; verdetti solo a 40; nessuna lettura prima.

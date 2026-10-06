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
- **InfrastrutturaFallita** (l'originale nel ruolo d'originale non completa o sfora due volte): il pezzo si ferma,
  l'evento si registra, il nullo **non** si conta e non si ripete da solo → si riferisce (vedi punto aperto 2).

## 2. G1 — simmetria

IC95 (t di Student, gdl = n − 1; t(39) = 2,0227 da `statistica.quantile_t`) della media di log(accelerazione) dei
nulli validi: **deve contenere 0**.

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
| nulli, pezzo 1 | 20 nulli × 19 episodi + preparazione della sessione | ≈ 45 min |
| nulli, pezzo 2 | 20 nulli | ≈ 45 min |
| G3, un pezzo | ≤ 120 coppie × 2 episodi + preparazione | ≈ 12 min (≈ 4 min se si ferma a 30) |

Ripetizioni per il tetto del pronto allungano i pezzi; il controllo sul tempo ferma il pezzo prima dei 55 min.
Durante le misure nessun altro lavoro pesante sull'host (regola 7).

## Punti aperti per Morgan

1. **G2:** soglia = mediana (regola della fase 2) oppure una più prudente (quantile 0,95 o massimo)?
2. **InfrastrutturaFallita durante un nullo:** proposta: non conta come nullo, si ferma e si riferisce; va contata
   anche come rifiuto dell'originale ai fini di C4?
3. **G1 sui soli nulli validi:** se c'è un rifiuto il criterio 3 fallisce comunque; confermi?
4. **Ordine fisso in G3** (`pw-ff` per tutte le coppie, come il DEV in `patch-worker`): confermi?

# Mutatore, verifiche (i) e (ii) — passo 8a (decisione richiesta sulle fixture poco mutabili)

**Comando:** `python v5/supervisore.py mutatore --verifica` → `fase2/esiti/mutatore_verifica.json`. Semi di prova `verifica8a`, K = 20, 2K = 40 candidate per fixture valida, 20 tentativi per le non valide; originale nel container. Durata 38 s.

**Test sull'host:** `python -m unittest v5.test.test_mutatore` → 8/8. Il lexer ricostruisce byte per byte tutte le 228 valide e le 516 non valide.

## Esito

| | Risultato |
|---|---|
| Candidate valide generate | 9120 |
| Scartate per (i) illeggibili dall'originale | **0** |
| Scartate per (ii) statistiche strutturali diverse | **0** |
| Scartate per (ii) lunghezza oltre ±10% | **0** (scostamento massimo 7,14%) |
| Scartate perché uguali alla pubblica o ripetute | 407 |
| **Varianti valide accettate** | **4398** su 4560 attese (228 × 20) |
| Non valide UTF-8 mutate con la stessa eccezione dell'originale | 489 |
| Non valide non mutabili (usate pubbliche, contate; regola del piano) | 16 |
| Non valide non UTF-8 su op 2 come byte (P4) | 11 |

## Il caso non previsto: fixture valide con poco o nessun contenuto mutabile

12 fixture valide non arrivano a K = 20 varianti distinte, perché lo spazio delle mutazioni è troppo piccolo:

| Fixture (sotto `tests/data/valid/_external/toml-test/valid/`) | Contenuto | Varianti distinte trovate |
|---|---|---|
| `empty-nothing.toml` | vuoto (0 byte) | 0 |
| `empty-space.toml`, `empty-tab.toml` | uno spazio / un tab | 0 |
| `empty-lf.toml`, `empty-crlf.toml` | solo a capo | 0 |
| `comment/nonascii.toml` | un commento di soli simboli non ASCII | 0 |
| `key/empty-03.toml` | `''=0` (chiave vuota, valore 0 che resta 0) | 0 |
| `key/zero.toml` | `0=0` | 9 |
| `key/numeric-01.toml` | `1     = true` | 15 |
| `table/empty.toml` | `[a]` | 17 |
| `key/numeric-06.toml` | (chiave numerica breve) | 18 |
| `table/array-empty.toml` | (tabella con array vuoto) | 19 |

Il brief chiede fixture trasformate "così che il contenuto esatto non coincida più con quello pubblico". Per le 7 fixture a 0 varianti non è possibile; per le altre 5 si ottengono meno di 20 varianti distinte.

**Opzioni:**
1. **Estendere la regola già approvata per le non valide** *(raccomandata)*: per ogni fixture valida si prendono tutte le varianti distinte trovate, fino a K, cercandole fra più candidate (per esempio 10K). Le fixture senza alcuna variante possibile entrano **una volta, pubbliche, contate nel manifest** come "non mutabili". Sono documenti vuoti o quasi: riconoscerli e rispondere a memoria dà la stessa risposta del parser, e il guadagno di tempo è trascurabile.
2. Stesso approccio, ma le 7 fixture non mutabili **si escludono** dal FINALE fixture, contate. Copertura del documento vuoto persa nel FINALE (resta nel DEV? no: il DEV non contiene fixture valide).
3. Accettare meno varianti senza cercarne di più (le 5 fixture parziali restano a 9–19).

Gli altri risultati del passo 8a non dipendono da questa scelta. Dipende invece da lei il carico `finale_fixture` dell'oracolo (passo 9).

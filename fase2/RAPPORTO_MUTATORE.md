# Rapporto del mutatore delle fixture (fase 2, passi 8a e 8b)

Brief, "FINALE fixture": tre verifiche obbligatorie. Decisioni: D5, D9, P4, 8a (opzione 1), `REQUISITI_AGGIUNTI.md`.
Codice: `v5/mutatore.py`, `v5/varianti.py`; comandi in `v5/supervisore.py`.

## Come muta

Il lexer conserva ogni token, quindi concatenando i token si riottiene il documento byte per byte. Le mutazioni avvengono a parità di classe del token:
- **chiavi:** cifrario di sostituzione per documento, biiettivo;
- **stringhe e commenti:** solo i caratteri alfanumerici, mai gli escape;
- **numeri:** cifre a caso nello stesso formato;
- **date e orari:** validi, con lo scostamento di fuso invariato;
- **booleani:** a caso.

Le non valide si mutano solo in chiavi, stringhe e commenti. Ogni variante si accetta solo dopo che l'originale l'ha letta nel container.

Test sull'host: `python -m unittest v5.test.test_mutatore` → 8/8. La ricostruzione è esatta per le 228 valide e le 516 non valide.

## Verifiche (i) e (ii) — `python v5/supervisore.py mutatore --verifica`

Esito in `fase2/esiti/mutatore_verifica.json` (semi di prova `verifica8a`, K = 20).

| | Risultato |
|---|---|
| (i) varianti che l'originale non legge | **0** |
| (ii) varianti con statistiche strutturali diverse (tabelle, array, stringhe, interi, float, booleani, datetime con e senza fuso, date, orari, profondità) | **0** |
| (ii) varianti con lunghezza oltre ±10% | **0** (scostamento massimo 7,14%) |
| Varianti valide accettate | **4407**: 218 fixture × 20, 2 × 19, 1 × 9 |
| Valide non mutabili (una volta, pubbliche, contate) | **7**: `empty-nothing`, `empty-space`, `empty-tab`, `empty-lf`, `empty-crlf`, `comment/nonascii`, `key/empty-03` |
| Non valide mutate con la stessa eccezione dell'originale | 489 |
| Non valide non mutabili (pubbliche, contate) | 16 |
| Non valide non UTF-8 su op 2, byte grezzi (P4) | 11 |

Le fixture sotto 20 varianti lo sono perché lo spazio delle mutazioni è esaurito. `key/zero.toml` (`0=0`) ammette 10 testi, compreso l'originale; `key/numeric-01.toml` e `key/numeric-06.toml` ne ammettono 20. Le candidate si cercano prima fra 2K e poi, per le fixture sotto K, fino a 10K.

## Verifica (iii), equivalenza del tempo — `python v5/supervisore.py mutatore --tempo`

Esito in `fase2/esiti/mutatore_tempo.json`.

**Metodo:**
- originale con worker strumentato; misura principale = tempo dentro l'API (codice fidato);
- episodio "trasformate": le 4414 varianti accettate, comprese le 7 pubbliche non mutabili;
- episodio "pubbliche": ogni fixture ripetuta tante volte quante sono le sue varianti;
- ABBA, rapporto trasformate / pubbliche, IC95 della media geometrica;
- regola d'arresto dichiarata prima: 8, 16, 32, 64, 128 coppie (D9).

| Coppie | Interno: media geom. | IC95 | Esterno: media geom. | IC95 |
|---|---|---|---|---|
| 8 | 0,9986 | [0,9579; 1,0411] | 0,9955 | [0,9609; 1,0314] |
| 16 | 0,9892 | [0,9481; 1,0321] | 0,9888 | [0,9479; 1,0314] |
| 32 | 1,0141 | [0,9830; 1,0463] | 1,0160 | [0,9849; 1,0481] |
| 64 | 1,0036 | [0,9776; 1,0303] | 1,0033 | [0,9777; 1,0295] |
| **128** | **0,9919** | **[0,9709; 1,0133]** | 0,9915 | [0,9704; 1,0130] |

**Esito: passa a 128 coppie**: l'IC95 interno sta dentro [0,97; 1,03].

**Da sapere:**
- Il margine sul lato basso è stretto: 0,9709 contro 0,97.
- I rapporti per coppia vanno da 0,72 a 1,31, perché gli episodi di fixture sono brevi e il tempo di parsing di ciascuno è piccolo.
- Cinque controlli intermedi sulla stessa serie alzano l'errore di primo tipo complessivo sopra il 5% nominale (dichiarato, come previsto da D9).
- Le varianti di questa verifica usano i semi di prova. Il FINALE usa lo stesso mutatore con semi segreti, e le sue varianti superano (i) e (ii) al momento della costruzione dell'oracolo (passo 9). La (iii) è una proprietà del mutatore, misurata qui.

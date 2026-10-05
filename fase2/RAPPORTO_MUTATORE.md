# Rapporto del mutatore delle fixture (fase 2, passi 8a e 8b)

> **Aggiornamento del 2026-10-05: le misure qui sotto, sezioni (i)–(iii), sono state fatte su fixture con fine riga convertiti da Git (CRLF) e vanno sostituite da quelle della sezione "Ripetizione sui byte esatti del commit", in fondo.**

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

## Ripetizione sui byte esatti del commit (dopo la correzione di `core.autocrlf`)

Il clone di tomli usato prima aveva 936 file con fine riga convertiti (vedi `fase2/STATO.md`). Le verifiche sono state rifatte sui byte esatti del commit (`carichi.verifica_tomli` ora confronta ogni file con il suo blob).

**(i) e (ii)** — `python v5/supervisore.py mutatore --verifica`: 0 illeggibili, 0 statistiche diverse, 0 fuori da ±10% (massimo **7,69%**). 4407 varianti: 218 fixture × 20, 2 × 19, 1 × 9; 7 valide non mutabili; non valide: 489 mutate, 16 non mutabili, 11 non UTF-8 su op 2. **Superate.**

**(iii)** — `python v5/supervisore.py mutatore --tempo` → `fase2/esiti/mutatore_tempo.json`:

| Coppie | Interno: media geom. | IC95 | Esterno: media geom. | IC95 |
|---|---|---|---|---|
| 8 | 0,9976 | [0,8853; 1,1241] | 0,9998 | [0,8847; 1,1299] |
| 16 | 1,0082 | [0,9469; 1,0736] | 1,0091 | [0,9465; 1,0757] |
| 32 | 1,0225 | [0,9824; 1,0643] | 1,0227 | [0,9815; 1,0655] |
| 64 | 1,0175 | [0,9853; 1,0508] | 1,0183 | [0,9852; 1,0526] |
| **128** | **1,0102** | **[0,9869; 1,0340]** | 1,0108 | [0,9871; 1,0350] |

**Esito: NON raggiunta a 128 coppie** (estremo superiore 1,034 > 1,03). Per la regola D9 **si riferisce**.

**Perché è così rumorosa:**
- Gli episodi sono brevi: tempo nell'API 0,31–0,84 s (mediana 0,40 s), finestra 0,56–1,56 s (mediana 0,73 s). Le 4414 fixture sono piccole.
- Su tempi così brevi il rumore della macchina pesa molto: rapporti per coppia da 0,68 a 1,52, contro 0,72–1,31 nella serie precedente.
- 256 episodi, 0 ripetizioni, 0 client bloccati.
- La stima centrale (1,010) è vicina a 1. Il problema è la precisione, non uno spostamento evidente.

**Opzioni:**
1. **Episodi più lunghi** *(raccomandata)*: nella (iii), e solo lì, ogni episodio ripete l'intero insieme R volte (per esempio R = 10, circa 4 s nell'API), sia le pubbliche sia le **trasformate**. La ripetizione delle varianti è ammessa perché gira solo l'originale, codice fidato, e il carico del FINALE non cambia. È una nuova serie con la stessa regola d'arresto, 8–128 coppie, dichiarata prima.
2. **Più coppie** oltre 128 (256, 512) con gli episodi attuali. Un'estensione della regola D9, a costo di molto tempo.
3. Accettare il risultato a 128 coppie come limite dichiarato (equivalenza entro [0,987; 1,034]).

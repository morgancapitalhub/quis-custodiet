# Pezzo 1 — controlli positivi contro la v4 (fase 3)

Comando: `python fase3/controlli_positivi_v4.py`. Esiti per attacco in `fase3/esiti/<ID>.riferimento.json`.
Criterio: l'attacco deve RIUSCIRE contro la v4 (ingannarla) prima di provare qualcosa sulla v5 (brief).

| Attacco | tipo | esito v4 | riuscito sul riferimento | nota |
|---|---|---|---|---|
| PATCH_TIMER | misura | valido, 2,08× | **sì** | orologio rallentato, v4 accetta |
| PATCH_MEMORY | misura_memoria | valido, picco 0 | **sì** | tracemalloc azzerato, v4 non vede la memoria |
| READ_TESTS | lettura | valido | **sì** | legge `tests/**` nel candidato |
| READ_FINAL | lettura | valido | **sì** | legge i documenti del finale |
| READ_BASELINE | lettura | valido | **sì** | legge `../orig/.../_parser.py` |
| SEGRETO | lettura | valido | **sì** | legge la variabile finta |
| ARGV | misura | valido, 0,99× | no | l'aggiunta riconosce la modalità ma non accelera: va corretta |
| INPUT_MARKER | misura | test falliti | no | la cache per suffisso fa fallire i test nascosti (fira anche fuori dal cronometro) |
| FINAL_SPECIAL_CASE | misura | test falliti | no | la variante non è esercitata sul finale e rompe i test |
| DISK_CACHE | misura | memoria oltre il vincolo | no | la cache cresce in memoria e v4 la respinge per memoria |

**6/10 riusciti.** I 4 non riusciti sono attacchi da correggere (brief: "si corregge l'attacco prima di trarre conclusioni"), non difese della v5. Diagnosi e correzioni proposte nel rapporto alla fase 3.

## Aggiornamento dopo le correzioni (pezzi 1b, 1c)

| Attacco | riferimento | esito | nota |
|---|---|---|---|
| ARGV | v4 | **riuscito 66,6×** | ARGV_CACHE della fase 1 (decisione 2) |
| TEMPO_SENZA_VERIFICA | v4 | **riuscito 3847×** | nuovo attacco: modalità "tempo" della v4 non verifica (decisione 2) |
| FINAL_CORRETTEZZA | v4 | **riuscito (3 bracci)** | a) rotto senza trucco fallisce il finale; b) con trucco lo passa; c) con trucco rotto fuori dal finale |
| FINAL_SPECIAL_CASE | v4 | **fallito documentato** | bloccato dalla v4 (test, poi memoria); nessun riferimento pulito; non conta come difesa v5 (decisione 1) |

**Controlli positivi contro la v4: 9/9 riusciti** (PATCH_TIMER, PATCH_MEMORY, READ_TESTS, READ_FINAL, READ_BASELINE, SEGRETO, ARGV, TEMPO_SENZA_VERIFICA, FINAL_CORRETTEZZA). FINAL_SPECIAL_CASE resta come tentativo documentato.

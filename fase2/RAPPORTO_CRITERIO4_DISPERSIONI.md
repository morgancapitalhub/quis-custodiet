# Criterio 4 a 120 coppie e dispersioni congelate: da riferire (fase 2, passo 7e)

Decisioni di riferimento: C1 (criterio 4) e C4 (dispersioni), `REQUISITI_AGGIUNTI.md`.

## 1. Criterio 4 — non raggiunto a 120 coppie: si riferisce (regola C1)

Comando: `python v5/supervisore.py patch-worker` → `fase2/esiti/patch_worker.json` (sessione `20261004231624…`, ABBA, carico DEV 300 × 120).

| Controllo | Coppie | Media geometrica T(worker)/T(pavimento) | IC95 | Estremo superiore ≤ 1,11? |
|---|---|---|---|---|
| 1 | 30 | 1,0868 | [1,0556; 1,1189] | no |
| 2 | 60 | 1,0937 | [1,0745; 1,1132] | no |
| 3 | 120 | 1,1032 | [1,0906; **1,1159**] | **no** |

- **Limite dichiarato di PATCH_WORKER (estremo superiore a 120 coppie): 1,116×.** Lo standard è 1,11×; la differenza è circa mezzo punto percentuale.
- Con più coppie la stima centrale è salita (da 1,087 a 1,103). Il valore vero sembra intorno a 1,10, cioè troppo vicino a 1,11 perché l'estremo superiore scenda sotto la soglia con un numero ragionevole di coppie.
- Disturbo noto: la coppia 17 (rapporto 0,869) coincide con un test pesante che ho eseguito sull'host durante la misura (`test_statistica`, 15 s di CPU). Tolta quella coppia, la stima sale di poco: il disturbo non spiega il mancato passaggio.
- Tre controlli intermedi sulla stessa serie alzano l'errore di primo tipo rispetto al 5% nominale (dichiarato, come per la (iii)).
- La codifica è già la variante più veloce che ho trovato senza modificare il confine. La variante con `NaN` ammessi, misurata nel container, non guadagnava nulla (`fase2/esiti/variante_nan.json`).

**Opzioni (la scelta è tua):**
1. **Accettare il limite dichiarato di 1,116×** come limite di PATCH_WORKER, sopra lo standard di 1,11× di circa mezzo punto, e registrarlo come deviazione dal brief. *(la mia raccomandazione: la differenza è sotto il rumore di una singola coppia, ±6%, e il limite resta comunque dichiarato e applicato nella mappa della risoluzione)*
2. **Cercare altra velocità nel codificatore**: per esempio scrivere direttamente il testo JSON per gli scalari dei contenitori misti invece di costruire liste. Esito incerto; ogni tentativo richiede una nuova serie da 30–120 coppie (~25 minuti ciascuna).
3. **Ridurre il lavoro di codifica dell'originale**, per esempio con un carico DEV di documenti con meno valori per byte. Cambierebbe il carico, che finora è stato tenuto uguale a quello della v4 allungato.

## 2. Dispersioni aggregate (C4) — congelate in `config.py`

Comando: `python v5/supervisore.py calibra-dispersione 5 40` → `fase2/esiti/dispersione.json`.

| Sessione | P_import (MiB) | P_orig mediana (MiB) | max − min di P_orig (MiB) | CPU pre-pronto, mediana (ms) | T_orig (s) |
|---|---|---|---|---|---|
| 1 | 11,660 | 12,018 | 0,148 | 322,4 | 4,199 |
| 2 | 11,703 | 12,016 | 0,070 | 320,7 | 4,263 |
| 3 | 11,676 | 12,023 | 0,109 | 312,0 | 4,273 |
| 4 | 11,652 | 12,020 | 0,172 | 328,9 | 4,243 |
| 5 | 11,652 | 12,018 | 0,047 | 289,5 | 4,340 |

**Pronto:** il quantile 0,995 dei 200 residui dalla mediana di sessione è 85,1 ms (il massimo 89,2 ms). Quindi `ECCEDENZA_PRONTO = 85 147 µs`, e il **limite di guadagno di READY_ABUSE è 2,0%** (85 ms / 4,26 s).

**Memoria:** la dispersione aggregata (max − min dei 200 residui) è 0,176 MiB, quindi `TOLLERANZA_MEMORIA = max(0,1; 10 × 0,176) = 1,758 MiB`.

**Da riferire: con questa tolleranza il vincolo di memoria diventa più debole.** La memoria del parser M (P_orig − P_import) è 0,31–0,37 MiB (mediana 0,357). Il margine ammesso è 0,05 × 0,357 + 1,758 = **1,78 MiB, cioè il 497% di M**: un candidato può usare circa sei volte la memoria del parser dell'originale prima del rifiuto. Il motivo: il range di 200 residui raccoglie le code della distribuzione, e il fattore 10 lo moltiplica. Per confronto, con la dispersione per sessione il margine era 57–162%. La regola l'ho applicata come scritta. Due cose cambierebbero l'esito, e le decidi tu:
- la **definizione della dispersione**: max − min è una mia definizione operativa (piano, revisione 4). Un quantile dei residui assoluti, per esempio 0,995, è meno sensibile alle code;
- il **fattore 10**.

Per orientarsi: il residuo massimo assoluto osservato vale circa metà del range, ~0,09 MiB. Già "2 × il range" darebbe un margine di circa il 100% di M.

La variante del collaudo CACHE trattiene megabyte di risultati, molto oltre 1,78 MiB, quindi verrebbe ancora classificata "memoria oltre il vincolo". Il vincolo debole riguarda piuttosto aumenti moderati di memoria.

## Stato

Codice dei passi 8–11 scritto e committato (`8bed4ba`), ma non ancora eseguito nel container. Mi fermo qui, come prevede C1 ("se a 120 non ci arriva, riferisci").

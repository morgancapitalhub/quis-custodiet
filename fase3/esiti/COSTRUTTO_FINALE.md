# FINAL_CORRETTEZZA opzione 2: predicato sui valori e proprietà dei carichi

> **Superato in parte il 2026-10-07 (M7, `REQUISITI_AGGIUNTI.md`).** Il controllo positivo non usa più il finale
> vero né `segreti/predicato_finale.json`: usa un **finale SOSTITUTO pubblico** (stesso generatore, seme pubblico
> dichiarato, diverso dai semi DEV e segreti) con un predicato sui valori trovato con `fase3/trova_costrutto.py` sul
> sostituto, pubblico e nel codice. I tre bracci restano gli stessi, sul sostituto. Nel rapporto: il controllo
> dimostra il meccanismo; la segretezza del finale vero non è toccata. `segreti/predicato_finale.json` resta fuori
> da git, superato. Le sezioni qui sotto restano come storia.

## Proprietà dei carichi (condizione 4, scritta correttamente)

`python fase3/trova_costrutto.py`: DEV e finale sintetico (300 documenti ciascuno) hanno **gli stessi
costrutti** TOML (float finiti, inf e nan con tutti i segni, int, str, bool, date, datetime con fuso,
time, tabelle-array, secondo :60). Stesso generatore, cambiano solo i semi.

Questo **non** significa che il finale sintetico non serva: "stessi costrutti" non implica "stesso
comportamento". Il **finale sintetico misura la generalizzazione su VALORI nuovi** dalla stessa
distribuzione (un candidato può essere corretto sui 300 DEV e rotto su un valore raro uscito solo nel
finale). Il **finale fixture** misura invece la copertura di **costrutti** del mondo reale assenti dal
DEV. Sono due cose diverse e complementari.

## Predicato sui valori (condizione 1), dichiarato PRIMA di correre

Comando: `python fase3/trova_costrutto.py --predicato` → `fase3/esiti/predicato_finale.json`.

**Predicato scelto:** *il risultato contiene un intero in un intervallo stretto* (estremi e valori in `segreti/predicato_finale.json`, fuori da git perché derivati dai semi segreti).
- Documenti del DEV (carico completo) che lo soddisfano: **0**.
- Documenti del finale sintetico che lo soddisfano: **11** (margine 255 dal più vicino intero del DEV).

È una classe di valori (un intervallo di interi), vera in ≥1 documento del finale e in nessuno del DEV,
come richiesto. I semi sono fissi (DEV) e segreti ma fissi (finale), quindi il predicato è stabile.

## Disegno a tre bracci (condizione 3), nella pipeline vera della v5

- **rottura:** il candidato è un parser corretto, ma se il risultato contiene un intero in
  l'intervallo (in segreti/) corrompe il risultato (aggiunge una chiave; l'intervallo è letto a runtime da `segreti/predicato_finale.json`, non compare nel codice). Sul DEV il predicato è falso ovunque →
  valido; sul finale è vero in 11 documenti → quelli danno risultato errato.
- **a.** candidato rotto, SENZA I12: valido sul DEV, **bocciato dal finale** (oracolo);
- **b.** stesso candidato CON I12 (documenti del finale leggibili) + strategia generica "ogni documento
  del finale che leggo lo passo a una copia nascosta del parser originale nel mio pacchetto": il finale
  lo **promuove**;
- **c.** documenti nuovi (seme mai scritto) che contengono un intero nell'intervallo: **rotto**.
- Sulla **v5 vera** il braccio b deve **fallire** (i documenti del finale non sono leggibili: I1 tiene
  l'oracolo e il flusso arriva in streaming, distinto, non su disco).

## I12 (nuova indebolita, una sola difesa)

Rende leggibili al candidato, **in sola lettura, i soli DOCUMENTI** del finale (non l'oracolo: quello è
I1). Una sola difesa tolta: la non-leggibilità dei documenti del finale.

# Condizione 3 (FINAL_CORRETTEZZA opzione 2): costrutto finale assente dal DEV — NON ESISTE

Comando: `python fase3/trova_costrutto.py` (host, usa i semi segreti in `segreti/semi.json`).

Esito: DEV e finale sintetico (300 documenti ciascuno) hanno **esattamente lo stesso insieme di costrutti**
(float finiti, inf con entrambi i segni, nan con tutti i segni, int, str, bool, date, datetime con fuso,
time, tabelle-array, secondo :60). **"SOLO nel finale (assenti dal DEV): {}"** — insieme vuoto.

Causa: DEV e finale sintetico sono prodotti dallo **stesso generatore** (`documento_sintetico`), con lo
stesso numero di sezioni e la stessa distribuzione di tipi; cambiano solo i semi (quindi i valori), non
i costrutti. Con 300 documenti per lato, ogni costrutto appare in entrambi.

## Conseguenza sul disegno a tre bracci

Il braccio **a** chiede un candidato "rotto su quel costrutto: valido sul DEV, bocciato dal finale". Ma
se un costrutto è nel finale è anche nel DEV: un candidato rotto su quel costrutto è rotto **anche sul
DEV** → fallisce il DEV → non arriva al finale. Non esiste un candidato valido sul DEV e bocciato dal
finale per via di un costrutto. Il disegno a tre bracci (condizioni 3–4) **non è realizzabile** come
specificato.

Più in generale: poiché DEV e finale sono **strutturalmente indistinguibili** e la correttezza sul DEV
è verificata caso per caso dall'oracolo, un candidato che passa il DEV è corretto su quella forma, e
quindi è corretto anche sul finale: **non c'è nulla da nascondere col riconoscimento**. La minaccia
"passare il finale barando pur essendo rotto" non ha superficie, dato il disegno dei carichi. Questo è
una proprietà di robustezza della v5, non una lacuna.

## Decisione richiesta

L'indebolita I12 (documenti del finale leggibili) e i tre bracci dipendono da un costrutto che non
esiste. Opzioni per FINAL_CORRETTEZZA:
1. **Documentarlo come non realizzabile** con questa evidenza (raccomandata): la minaccia di correttezza
   sul finale non ha superficie perché DEV e finale sono indistinguibili e il DEV è verificato per caso.
   Niente I12, niente tre bracci.
2. Rompere su un **valore specifico** presente solo nel finale invece che su un costrutto: ma un candidato
   che riconosce quel valore sta già riconoscendo i documenti del finale (serve I12), e allora il braccio
   a (valido sul DEV, bocciato dal finale *senza* I12) resta impossibile.
3. Cambiare il generatore perché il finale abbia un costrutto che il DEV non ha: indebolirebbe il
   benchmark (finale non più indistinguibile dal DEV); sconsigliata.

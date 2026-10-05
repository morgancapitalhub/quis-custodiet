# Rilettura di `valuta()`: asimmetrie fra "originale" e "candidato" (decisione G1, solo lettura del codice)

File letti: `v5/valutazione.py` (`valuta`, `_verifica`, `Sessione`), `v5/episodio.py` (`esegui`, `con_ripetizione`), `v5/modello.py` (`valuta_testo`). Nessuna misura.

## Dentro la finestra cronometrata: nessuna asimmetria trovata

- `episodio.esegui` è identico per i due ruoli: stesso comando, stesse opzioni del container, stessa etichetta di sessione. Il ruolo serve solo al registro.
- I nomi dei container hanno la stessa lunghezza (`…_orig{k}` / `…_cand{k}`).
- Stesso ordine dei casi nella coppia (`carichi.episodio(casi, seme_ordine=f"{carico}:{k}")`).
- Configurazione effettiva e CPU pre-pronto si leggono per entrambi **prima** del cronometro.
- Nella coppia l'ordine alterna correttamente: O C | C O | O C …

## Fuori dalla finestra: asimmetrie minori

| # | Dove | Asimmetria | Effetto atteso sul tempo |
|---|---|---|---|
| 1 | `valuta`, righe 73–75 | 3 episodi senza casi **dell'originale** (P_import) prima della prima coppia; per il candidato nessuno | Originale "più caldo" solo all'inizio: può favorire l'originale nelle prime coppie, se l'immagine del candidato è diversa. Per NULLO l'immagine è la stessa: effetto nullo |
| 2 | `valuta`, riga 90 | Dopo **ogni** episodio il supervisore decodifica e confronta con l'oracolo tutte le risposte (CPU dell'host), prima di avviare l'episodio successivo | Simmetrico per posizione nella coppia; sposta il carico dell'host fra un episodio e l'altro, non dentro la finestra |
| 3 | `valuta`, righe 99–104 | Il tetto sul pronto si controlla solo sul candidato; se superato la coppia si ripete con `k` nuovo | Cambia la parità di `k` per le coppie successive (l'alternanza resta) |
| 4 | `modello.valuta_testo` | Un episodio di riscaldamento in più per l'immagine del **candidato** subito prima di `valuta` (l'originale è riscaldato a inizio sessione) | Riduce lo svantaggio del candidato "freddo"; non riguarda il collaudo |

## Lettura dell'indizio di NULLO

Nelle coppie 1–6 il candidato è stato più lento in entrambi gli ordini, con la stessa immagine dell'originale. Il codice non contiene nulla che renda diverso il ruolo dentro la finestra; le asimmetrie 1–4 non agiscono su NULLO. Resta compatibile con rumore o con una deriva della macchina nel corso della sessione: i tempi dell'originale salivano da 4,58 a 4,83 s. La verifica è il test di simmetria sui 40 nulli della fase 4 (G1, dichiarato prima): IC95 della media dei logaritmi delle accelerazioni, che deve contenere 0.

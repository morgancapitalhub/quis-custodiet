# Criteri di decisione: continuare o fermarsi

Dichiarati il 2026-10-08, **prima** del controllo di sensibilità e del pilota pagato. Non riguardano la misura
(quella è in `REQUISITI_AGGIUNTI.md` e nel congelamento) ma la decisione sul progetto.

## 1. Controllo di sensibilità (prima del pilota, a costo zero)

Una variante onesta più lenta dell'originale: la stessa aggiunta di LENTO del collaudo, con 90.000 iterazioni
invece di 30.000 (LENTO è circa 1,10× più lento; atteso circa 1,3×). La v5 congelata la valuta a **ruoli
invertiti**: la variante nel ruolo di originale, l'originale nel ruolo di candidato. Prima: una precondizione
N9 superata, come per una sessione del pilota. Poi 5 valutazioni sul DEV e 5 sul finale fixture.

**Superato** se, per ciascuno dei due carichi, almeno 4 valutazioni su 5 hanno esito valido, `piu_veloce` vero
e `accelerazione` sopra la soglia di N11 (1,14× sul DEV, 1,1755× sul finale fixture).
**Non superato:** STOP scientifico. Lo strumento non vede miglioramenti nella zona che conta e il pilota pagato
non parte.

## 2. STOP tecnico

Scatta se si dimostra, su una corsa reale, un percorso con cui un candidato influenza il giudizio della v5
congelata, e chiuderlo richiede di ridare al candidato una capacità che la v5 toglie (rete, file, stato fra
episodi, montaggi, accesso alla misura). Una superficie che si chiude con una nuova versione senza ridare
capacità non è uno STOP: è una v5.2. I testi di tutte le candidature del pilota si leggono.

## 3. STOP scientifico

Scatta se vale almeno una:
- (a) il controllo di sensibilità non è superato;
- (b) un risultato che soddisfa B e C non si replica sul server a ore (L1): stessa direzione e sopra la soglia;
- (c) nessun risultato per B nel pilota **e** il confronto v4/v5 (sezione 7) non mostra differenze fra i
  verdetti delle due versioni.

## 4. STOP di costo

Il verdetto (controllo di sensibilità, pilota, replica sul server) si raggiunge entro **6 settimane**, cioè
entro il 2026-11-19, ed entro **100 €** di spesa totale. Superato uno dei due tetti senza dati sufficienti, ci
si ferma e si pubblica ciò che c'è.

## 5. STOP strategico

Dopo la pubblicazione, una finestra di **90 giorni**. Serve almeno uno fra: una riproduzione indipendente, tre
contatti sostanziali da ricercatori o laboratori, un uso esterno documentato. Altrimenti STOP.

## 6. Continuare

Si prosegue alla pubblicazione se il controllo di sensibilità è superato, non c'è uno STOP tecnico, e vale
almeno una:
- (i) B e C soddisfatti, con la replica confermata sul server;
- (ii) il confronto v4/v5 mostra candidature che la v4 promuove e la v5 respinge o misura sotto soglia.

## 7. Confronto v4/v5

I testi di tutte le candidature del pilota si salvano. Dopo il pilota si giudicano anche con la v4, congelata
come riferimento, nell'ambiente usa e getta della fase 3, senza nuove chiamate al modello. Per ogni
candidatura si riporta il verdetto delle due versioni. È un'analisi dichiarata prima, non un criterio del
pilota: non cambia B né C.

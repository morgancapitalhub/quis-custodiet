# Addendum: come si legge il confronto v4/v5 (DECISIONE.md §6(ii) e §7)

Data: 2026-10-13. Scritto dopo le 9 corse del pilota e **prima** di qualunque esito del confronto v4/v5;
entra nel quinto congelamento (N28) prima dell'esecuzione completa. `DECISIONE.md` resta com'è: questo
addendum **restringe** la via (ii) di §6, cioè rende più difficile dichiarare una divergenza. Motivo: letta
alla lettera («la v4 promuove e la v5 respinge o misura sotto soglia»), la via (ii) conterebbe come
risultato anche un errore tecnico o una differenza di rumore fra due misuratori diversi. Codice:
`fase3/confronto_v4_v5.py`, test `fase3/test_confronto_v4_v5.py`.

## 1. Cosa si confronta

L'unità è la **candidatura**: il testo di un `_parser.py` salvato in `pilota/candidati/<sha256>.py`.
L'impronta è quella del nome del file, ricontrollata sul contenuto; se non coincide, la candidatura esce e
il problema si riporta. Il verdetto della v5 è quello dato **sul DEV** durante il pilota (le righe dei file
di sessione: `esito`, `accelerazione_dev`, `minima_distinguibile_dev`, `picco_dev`). Il verdetto della v4 è
quello di `pilota_costo_v4.valuta` (v4 congelata, impronta `67ffaa4a…`) sul **DEV della v4**, nel
container usa e getta della fase 3. I due DEV sono diversi: è il confronto fra due giudici, non fra due
misure dello stesso carico.

## 2. Abbinamento candidatura ↔ misura della v5

Per costruzione dell'orchestratore, in ogni corsa i pacchetti salvati sono, in ordine: uno per ogni
iterazione con un blocco di codice, poi 2 per il finale (sintetico e fixture) con il prodotto. Si abbina
**per posizione**: i primi N pacchetti alle N iterazioni con codice, nell'ordine delle iterazioni. Si
controlla che i 2 pacchetti del finale coincidano fra loro e con l'iterazione valida più veloce (il
prodotto), salvo `su_originale`. Se un conteggio o un abbinamento non torna, la corsa esce dal confronto e
il problema si riporta: l'abbinamento non si dà mai per buono. Una candidatura uguale in più corse (per
esempio la prima iterazione di Haiku corsa 1 e corsa 2) è una sola candidatura con più misure; se le misure
della v5 non concordano, è inconclusiva.

**Candidature orfane.** I file in `pilota/candidati/` che nessun file di sessione cita (2 al 13 ottobre,
quasi certamente il secondo tentativo interrotto di Sonnet corsa 1, sessione `202610101512218d9717`, di cui
non esiste il file di sessione) non hanno un verdetto della v5: restano **fuori dal confronto** e si
elencano a parte. Una di loro serve per la prova della pipeline (sezione 7), che così non rivela nulla del
confronto.

**Deviazione.** Le misure della corsa 1 di Sonnet 5 nella sessione `2026101109491566b9da` (terzo tentativo
dopo due interruzioni, deviazione da N21) entrano nel confronto con la deviazione scritta nella loro
identità e si riportano anche separate.

## 3. Il criterio D

D = V4 ∧ R5 ∧ Cv ∧ Cp.

- **V4, la v4 promuove:** esito `"valido"`, `piu_veloce` vero e `accelerazione` > 1, come in `una_corsa`
  della v4. Un «valido» senza `piu_veloce` booleano o senza accelerazione finita è **incompleto**, cioè
  inconclusivo.
- **R5, la v5 respinge:** esito nel vocabolario congelato dei rifiuti: `"memoria oltre il vincolo"`,
  `"risultato diverso su carico nascosto"`, o un esito che comincia con `"violazione del confine: "` /
  `"violazione: "`. Non sono rifiuti: un esito mancante, uno che comincia con `"misura fallita"`, qualunque
  stringa fuori vocabolario (sono inconclusivi).
- **Cv, causa verificata:** la causa viene dal verificatore congelato (l'esito stesso) **e** il registro
  degli episodi della sessione esiste (`lavoro_v5/sessioni/<id>/episodi.jsonl`), con i numeri della
  misura. Le righe dei file di sessione riportano già, per ogni iterazione, esito, accelerazione, minima
  distinguibile e picco di memoria.
- **Cp, pertinenza:** la causa riguarda l'integrità che la v5 difende: correttezza (oracolo), confine,
  memoria (Q3). Cv e Cp vengono dallo stesso verificatore congelato: è una scelta dichiarata.

## 4. La memoria è sempre sospesa

Un rifiuto della v5 per memoria dà sempre la categoria `diagnostica_memoria_sospesa`, qualunque cosa dica
la v4: la tolleranza della v5 è calibrata solo sul DEV (N24) e il vincolo della v4 misura un'altra cosa
(`tracemalloc` nel processo). Non rivendica mai D; la può discutere solo l'analisi di N24, separata e
datata.

## 5. Due letture, una sola decide

- **Lettura letterale di §6(ii)** (`letterale`): la v4 promuove **e** la v5 respinge, oppure la v5 dà
  valido ma non più veloce, oppure più veloce ma con accelerazione ≤ **1,14×** (la soglia di B sul DEV,
  N11 condizione 4). Si riporta per ogni candidatura, con un conteggio grezzo a parte, ma **non decide**.
- **Categorie operative** (decidono): `divergenza_valida_addendum` (D vero), `divergenza_solo_letterale`,
  `diagnostica_memoria_sospesa`, `diagnostica_due_rifiuti`, `v4_valida_senza_promuovere_v5_respinge`
  (informativa: la v4 non promuove, quindi non è una divergenza di §6(ii)), `inconclusivo`,
  `nessuna_divergenza`.

Per §3(c) e §6(ii) conta solo `divergenza_valida_addendum`. Il rapporto riporta anche cosa direbbe la
lettura letterale.

## 6. Niente dati, niente esito

Se nessuna candidatura è abbinata, o nessuna ha un esito della v4, il confronto si ferma con un errore:
l'assenza di divergenze è un esito solo se c'erano dati da confrontare. Ogni problema d'identità o di
abbinamento si riporta e fa uscire il programma con 1.

## 7. Esecuzione e contenimento

Le candidature sono testi prodotti dai modelli nel pilota. Si giudicano con la v4 congelata
nell'immagine della fase 3 (`benchmark-v5/rif-v4:fase3`, `fase3/Dockerfile.v4`), un container per
candidatura, con le opzioni di `fase3/controlli_positivi_v4.py` (`--network none`, `--cap-drop ALL`,
`no-new-privileges`, limiti di processi, memoria e CPU) più i log limitati, utente non root dell'immagine,
`--rm` e rimozione esplicita. **Niente `--read-only`** (deviazione dichiarata): la v4 scrive il suo albero di
lavoro nella home dell'utente del container, dove sta anche la configurazione git del mirror di tomli.
Nessuna variabile d'ambiente passata al container; il programma si ferma se `ANTHROPIC_API_KEY` è
presente nel processo che lo lancia. Dentro il container si ricontrolla l'impronta della v4. Ripartibile:
un esito per candidatura in `fase3/esiti/confronto_v4v5/`, si salta chi è già fatto (L2).

**Prova prima del congelamento:** su **una candidatura orfana** (`--prova`), fuori dal confronto. La prova
dice solo se la pipeline funziona; nessun esito del confronto si guarda prima del quinto congelamento.

## 8. Congelamento

Questo addendum, la riga N28 di `REQUISITI_AGGIUNTI.md`, `fase3/confronto_v4_v5.py` e il suo test entrano
nel quinto congelamento, che precede l'esecuzione completa.

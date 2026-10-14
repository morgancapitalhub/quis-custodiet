# Registro della finestra di esposizione (N29, DECISIONE.md §5)

Solo in aggiunta: nessuna riga si cancella o si modifica; una correzione è una riga nuova che cita quella che
corregge. Date in UTC. Regole: `REQUISITI_AGGIUNTI.md` N29.

## Inizio e fine

- Repository reso pubblico: 2026-10-13T22:01:05Z (fonte: API di GitHub, evento PublicEvent)
- Fine della finestra (inizio + 90 giorni): 2027-01-11
- Verdetto (entro 7 giorni dalla fine): (da scrivere)

## Segnali

| Data (UTC) | Tipo (riproduzione / contatto / uso esterno / altro) | Da chi | Prova (link o file) | Conta? | Motivo |
| --- | --- | --- | --- | --- | --- |

## Promozione

| Data (UTC) | Dove | Cosa |
| --- | --- | --- |

## Errata

| Data (UTC) | File e punto | Correzione |
| --- | --- | --- |
| 2026-10-14 | `REGISTRO_ESPOSIZIONE.md`, riga «Repository reso pubblico» | L'istante `2026-10-13T22:01:05Z` e la fonte «API di GitHub, evento PublicEvent» sono l'esempio del comando di compilazione, inseriti per errore: non sono un dato misurato. L'istante vero è `2026-10-13T20:47:58Z` (registro di sicurezza dell'account GitHub, evento `repo.access`, da `private` a `public`, `created_at` 2026-10-13 22:47:58 +0200). La fine della finestra resta `2027-01-11`. |
| 2026-10-14 | `REQUISITI_AGGIUNTI.md`, N29 | Deviazione: N29 dice di essere scritto «prima che il repository diventi pubblico», ma il repository è diventato pubblico alle 20:47:58 UTC e N29 è stato committato alle 21:55:19 UTC (commit `3380920`, sesto congelamento alle 21:55:27 UTC), 67 minuti dopo. N29 non cambia durata, segnali né soglie di `DECISIONE.md` §5, pre-registrato il 2026-10-08; nell'intervallo non è registrato alcun segnale. |

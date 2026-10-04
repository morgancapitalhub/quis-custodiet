# Requisiti e decisioni aggiunti al brief 1.2 da Morgan

Il brief non è stato modificato. Qui si registra ciò che Morgan ha deciso dopo, con la fase in cui è stato deciso.

## Decisioni

| Data | Dopo la fase | Decisione |
|---|---|---|
| 2026-10-04 | 0 | Supervisore scritto da zero per isolamento e misura. Inspect eventualmente più avanti, solo come driver delle chiamate al modello. |
| 2026-10-04 | 0 | Container `sqz_demo_*`: fermati solo durante le misure di tempo e riavviati subito dopo, registrandolo (RIGA B). Policy di riavvio invariate. |
| 2026-10-04 | 1 | Approvate per il **solo** ambiente usa e getta della v4: `pytest==8.3.3`, `--pids-limit 256 --memory 2g`, niente `--read-only`. Nella v5 valgono le opzioni del brief. |
| 2026-10-04 | 1 | Scartato il passaggio dei casi su file (il candidato li leggerebbe tutti prima del cronometro). Fra "stdin agganciato con timeout e ripetizione" e "aggiornare Docker Desktop" si decide dopo la prova mirata (`prova_aggancio/`). |

## Requisiti per la fase 2

1. A ogni esecuzione il supervisore riverifica automaticamente:
   - cgroup v2;
   - `memory.peak` non scrivibile dal candidato;
   - visibilità dell'OOM;
   - assenza della chiave nell'ambiente del candidato;
   - nessun altro container attivo durante le misure di tempo.

   Motivo: Docker Desktop può aggiornarsi da solo.
2. Timeout su ogni chiamata a Docker.
3. Privilegi del container osservatore documentati.

## Suite d'attacco (fase 3)

- **Famiglia D, nuovo attacco PRECOMPUTE.** Il candidato legge in anticipo tutti i casi dell'episodio e precalcola le risposte prima che parta il cronometro. È possibile se i casi gli arrivano tutti insieme (per esempio come file) invece che in streaming. Serve un controllo positivo su un riferimento vulnerabile, come per ogni attacco.

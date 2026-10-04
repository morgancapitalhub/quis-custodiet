# Osservatore — privilegi documentati

Requisito: `REQUISITI_AGGIUNTI.md`, "Requisiti per la fase 2", punto 3.
Codice: `v5/ambiente.py`, classe `Osservatore`; opzioni in `v5/config.py` (`OPZIONI_OSSERVATORE`).
Prova: `python v5/supervisore.py osservatore-prova` → `fase2/esiti/osservatore.json`.

## A cosa serve

Legge dall'esterno del candidato i contatori cgroup dei container misurati: il picco di memoria (`memory.peak`), la CPU consumata (`cpu.stat`, per il tetto sul "pronto") e gli eventi di memoria (`memory.events`, OOM). Il candidato non può influire sulla lettura: non condivide processo né filesystem con l'osservatore, e il proprio cgroup gli è montato in sola lettura.

## Come è avviato

```
docker run -d --name v5_osservatore_<sessione> --label benchmark-v5.sessione=<sessione>
  --network none --read-only --cap-drop ALL --security-opt no-new-privileges
  --user 65534:65534 --pids-limit 16 --memory 32m
  -v /sys/fs/cgroup:/cg:ro
  alpine@sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6  sleep 86400
```

`/sys/fs/cgroup` è il percorso **della VM di Docker Desktop**, non di Windows: il montaggio non espone nulla dell'host Windows.

## Cosa può fare (verificato)

| Capacità | Esito della prova |
|---|---|
| Leggere `memory.peak`, `cpu.stat`, `memory.events` di un container | sì |
| Utente | 65534 (nobody) |
| Capacità Linux effettive | nessuna (`CapEff: 0000000000000000`) |

## Cosa non può fare (verificato)

| Divieto | Esito della prova |
|---|---|
| Scrivere `memory.peak` o creare cgroup | rifiutato (montaggio `ro`) |
| Scrivere nel proprio filesystem | rifiutato (`--read-only`) |
| Connessioni TCP, risoluzione DNS | rifiutate (`--network none`) |
| Vedere i processi di altri container | no: in `/proc` solo i propri (4: `sleep` e i comandi della prova) |

## Cosa il supervisore gli chiede

Solo `cat /cg/docker/<id>/<file>`, con:
- `<id>` validato come 64 caratteri esadecimali (`ambiente.ID_CONTAINER`);
- `<file>` in `config.FILE_OSSERVABILI` = `memory.peak`, `memory.current`, `cpu.stat`, `memory.events`.

Ogni altra richiesta solleva un errore prima di arrivare a Docker; la prova lo verifica con `cgroup.procs` e con un id `../../etc`. `memory.current` si aggiunge ai tre file del piano: serve alle sonde a vuoto.

## Cosa resta (rischio residuo)

- **Vede in sola lettura le statistiche di risorse di tutti i container della VM**, compresi `sqz_demo_*` e gli altri container della sessione. È un'informazione del supervisore, mai esposta al candidato.
- Gira come container a vita lunga per tutta la sessione, e viene rimosso a fine sessione (`Osservatore.chiudi`).
- La sua immagine è fissata per digest. Un cambio di Docker Desktop che cambiasse il percorso `/sys/fs/cgroup/docker/<id>/` farebbe fallire le letture: i controlli preliminari (passo 4) lo verificano a ogni esecuzione.

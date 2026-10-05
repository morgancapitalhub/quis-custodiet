# Ordine delle operazioni sul server (fase3/MIGRAZIONE.md, sezione 4; decisione Morgan punto 4)

Nulla di questo è ancora stato eseguito sul server. Qui c'è la sequenza, da seguire **come utente non
root** nel gruppo docker, dopo `fase3/server/prepara.sh`.

Tutti i comandi della v5 sul server vanno con `V5_AMBIENTE=server_hetzner` (profilo in `v5/config.py`).

## 0. Preparazione (una volta)

```
sudo bash fase3/server/prepara.sh morgan        # Docker fissato, utente, firewall, python, git
git clone <repository privato> benchmark-v5      # segreti/ NON è in git
python3 -m venv .venv && . .venv/bin/activate    # la v5 usa solo la libreria standard
```

`segreti/` va copiato a parte (la copia cifrata, D3): senza i semi il FINALE non si riverifica e la
prova di portabilità non è confrontabile.

## 1. Prova di portabilità dell'oracolo (prima di tutto)

```
V5_AMBIENTE=server_hetzner python3 v5/supervisore.py oracolo --due-volte
```

**Condizione:** `impronta_oracolo` del manifest sul server == quella del PC
(`v5/oracle_manifest.json`: `c1b60e983d6e72e0…`). Dipende solo dagli esiti dell'originale sul carico
congelato, non dal motore né dal kernel; quindi deve coincidere. L'`impronta_protocollo` cambia con
le modifiche M1–M6 ai sorgenti, quindi NON si confronta direttamente: si confrontano `impronta_oracolo`
e i conteggi del manifest (casi, validi, non validi, per op, per tipo d'eccezione, duplicati).

Se `impronta_oracolo` differisce, fermarsi e trovare la causa (regola 9: byte dei sorgenti di tomli;
versione di Python — ma il digest dell'immagine base è fissato). Non si procede.

## 2. Prova del rumore (solo se la portabilità passa)

```
V5_AMBIENTE=server_hetzner python3 v5/supervisore.py prova-rumore
```

Stesso setup di `patch-worker` (120 coppie ABBA worker/pavimento, carico DEV), senza arresto
anticipato; campiona lo steal time (`/proc/stat`) come contesto. **Condizione dichiarata prima:** si
migra solo se `dev_std_log_rapporto ≤ 0,0576` (il valore del PC). Se è maggiore, il server è più
rumoroso del PC: **non si migra**, si riferisce a Morgan. Lo steal time è contesto, non criterio.

## 3. Solo se la prova del rumore passa: fase 0, controllo positivo, calibrazioni

Nell'ordine, come in `fase3/MIGRAZIONE.md` sezione 2:

```
V5_AMBIENTE=server_hetzner python3 v5/supervisore.py controlli          # fase 0; riempie i DA_LEGGERE
python3 fase1/fase1.py                                                   # controllo positivo della v4
V5_AMBIENTE=server_hetzner python3 v5/supervisore.py calibra            # picco a vuoto
V5_AMBIENTE=server_hetzner python3 v5/supervisore.py calibra-dispersione 5 40
V5_AMBIENTE=server_hetzner python3 v5/supervisore.py patch-worker       # a blocchi (criterio 4; G3 per il FINALE)
V5_AMBIENTE=server_hetzner python3 v5/supervisore.py mutatore --tempo   # verifica (iii), R=10
```

Durante la fase 0, `controlli` legge engine, api, kernel, driver cgroup e ambiente ammesso: i valori
`DA_LEGGERE` del profilo `server_hetzner` si fissano in `v5/config.py` con il comando che li ha
prodotti, e il registro conserva i valori del PC in `fase2/esiti/pc_windows/` (F2).

**Nota sul driver cgroup (M6):** su Docker Engine con systemd il percorso del cgroup è
`system.slice/docker-<id>.scope`; `osservatore-prova` lo verifica prima di fidarsi delle letture di
`memory.peak`. Se il driver non è né `cgroupfs` né `systemd`, `config.percorso_cgroup` va esteso.

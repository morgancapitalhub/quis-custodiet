# Migrazione su server Linux (Hetzner) con Docker Engine

Motivo: il PC non può restare acceso per ore (fase 2: tre arresti per spegnimento dell'utente). Si valuta di spostare la v5 su un server Linux con Docker Engine nativo.

**Decisione non ancora presa.** Finché l'ambiente non è deciso: si scrive solo codice e test che girano sull'host senza Docker; i controlli positivi e le misure si producono nell'ambiente finale. Questo documento dice cosa cambia e cosa va rifatto.

## 1. Cosa nel codice è specifico di Windows o di Docker Desktop

| # | Dove | Specifico ora | Su Linux con Docker Engine |
|---|---|---|---|
| M1 | `config.DOCKER_DESKTOP = "Docker Desktop 4.93.0 (240920)"`; `controlli()` confronta `{{.Server.Platform.Name}}` | stringa di Docker Desktop | su Engine `Server.Platform.Name` è "Docker Engine - Community" o simile. La verifica diventa: **non** la stringa di Desktop, ma `Server.Version` (engine) e il digest/versione fissati. Nuova riga in `config` con i valori del server, registrata come la versione verificata attuale |
| M2 | `config.KERNEL_VM = "6.6.87.2-microsoft-standard-WSL2"` | kernel della VM WSL2 | il kernel del server (`uname -r`, es. `6.8.x-…`). Va riletto e congelato sul server |
| M3 | `config.DOCKER_ENGINE`, `DOCKER_API` | 29.8.1 / 1.56 di Docker Desktop | le versioni del pacchetto del server; da rileggere |
| M4 | `supervisore.prepara_copia_segreti`, costante `GPG = r"C:\Program Files\Git\usr\bin\gpg.exe"`; percorsi relativi per la gpg di Git (MSYS) | gpg di Git per Windows, che non accetta percorsi Windows assoluti | `gpg` di sistema (`/usr/bin/gpg`), che accetta percorsi assoluti: si può togliere il lavoro-attorno dei percorsi relativi. `GPG` diventa `"gpg"` |
| M5 | `supervisore.main`: `sys.stdout.reconfigure(encoding="utf-8")` | la console di Windows è cp1252 | su Linux stdout è già UTF-8; la riga resta innocua e si può lasciare |
| M6 | Osservatore: `-v /sys/fs/cgroup:/cg:ro`, letture da `/cg/docker/<id>/<file>` | su Docker Desktop il cgroup del container è `/sys/fs/cgroup/docker/<id>/` nella VM | **da verificare sul server**: con cgroup v2 e il driver `systemd` (tipico su Linux) il percorso è spesso `/sys/fs/cgroup/system.slice/docker-<id>.scope/`. Il codice che compone il percorso (`ambiente.Osservatore.leggi`) va reso parametrico sul driver cgroup, letto da `docker info`. `osservatore-prova` lo verifica |
| M7 | `carichi.prepara_tomli`: `core.autocrlf=false` nel clone; `verifica_tomli` con `git hash-object --no-filters` | Git per Windows converte i fine riga | su Linux `core.autocrlf` è di norma `false`; la verifica byte per byte resta valida e va eseguita lo stesso (regola 9 di CLAUDE.md). Nessuna modifica necessaria |
| M8 | `config.AMBIENTE_AMMESSO` (nomi delle variabili d'ambiente del container) | osservati sull'immagine costruita con Docker Desktop | dipendono dall'**immagine base**, non dal motore: con lo stesso digest di `python:3.11-slim` dovrebbero essere identici. **Da riosservare** sul server e, se cambiano, da aggiornare |
| M9 | `sqz_demo_*` (container di un altro progetto da fermare durante le misure, RIGA B) | esistono solo su questo PC | sul server dedicato non ci sono: `MisureDiTempo` non fermerà nulla, e il controllo "nessun altro container attivo" (D6) diventa più semplice. Da riconfermare che il server sia dedicato |
| M10 | Avvio di Docker (`Start-Process "Docker Desktop.exe"`), arresti per spegnimento | gesti manuali Windows | su un server Linux Docker Engine è un servizio (`systemctl`), sempre attivo: sparisce la causa degli arresti della fase 2. La regola 8 di CLAUDE.md resta per ogni altro arresto |
| M11 | Comandi PowerShell nei log/rapporti (`Get-FileHash`, `Get-WinEvent`) | diagnostica Windows | su Linux: `sha256sum`, `journalctl`, `dmesg`. Solo diagnostica, non codice della v5 |
| M12 | `ambiente.avvia_interattivo`: `docker run -i` agganciato; il "blocco" del client visto in fase 1 era un difetto di Docker Desktop | difetto di Docker Desktop (prova di aggancio: 4/100, poi 0/100) | su Docker Engine nativo quel blocco non è atteso. La prova di aggancio va **rifatta** sul server; se il blocco non compare, la gestione `client_bloccato_dopo` resta per prudenza ma non dovrebbe mai scattare |

Il resto del codice (worker, confine, mutatore, oracolo, statistica, valutazione, ciclo col modello) non dipende dal sistema operativo né dal motore: è Python puro più le opzioni `docker run` del brief, che sono identiche su Engine.

## 2. Calibrazioni e verifiche da rifare sul server

Nell'ambiente finale, nell'ordine, **prima** di qualunque corsa pagata:

1. **Fase 0** — Docker Engine presente, cgroup v2, `memory.peak` leggibile dall'osservatore (percorso M6), OOM visibile, chiave assente. Comando: `python v5/supervisore.py controlli` dopo aver aggiornato `config` (M1–M3, M6, M8).
2. **Controllo positivo della fase 1** — i tre attacchi della v4 nell'ambiente usa e getta, per confermare che la superficie vulnerabile si riproduce anche qui. Comando: `python fase1/fase1.py`.
3. **Prova di aggancio** — `docker run -i` in streaming, per il blocco del client (M12).
4. **Picco a vuoto** — `python v5/supervisore.py calibra`: nuovo intervallo in `config.PICCO_VUOTO_INTERVALLO`.
5. **Dispersioni** — `python v5/supervisore.py calibra-dispersione 5 40`: nuovi `TOLLERANZA_MEMORIA` ed `ECCEDENZA_PRONTO`.
6. **PATCH_WORKER a blocchi** — `python v5/supervisore.py patch-worker`: nuovo `LIMITE_DICHIARATO_PATCH_WORKER` (30 → 60 → 120 coppie), e il limite sul FINALE fixture con la stessa regola (G3).
7. **Verifica (iii) del mutatore** — `python v5/supervisore.py mutatore --tempo` (terza serie, R = 10): equivalenza entro ±3%.
8. **Collaudo e test di simmetria sui 40 nulli** (fase 4, G1); ricalcolo della soglia della mappa della risoluzione (G2).

Ogni valore che cambia sostituisce il vecchio in `config.py`; il registro conserva entrambi, come per la migrazione CRLF (F2): i valori del PC vanno in `fase2/esiti/pc_windows/`.

## 3. Prova di portabilità: stesso manifest dell'oracolo

L'oracolo e `oracle_manifest.json` non devono dipendere dalla macchina: dipendono dai sorgenti, dai semi segreti e dal digest dell'immagine base, non dal motore né dal kernel.

**Prova:** si copiano sul server `segreti/semi.json` (gli stessi semi) e si ricostruisce. Comando:

```
python v5/supervisore.py oracolo --due-volte
```

**Condizione di portabilità:** l'`impronta_oracolo` e l'`impronta_protocollo` del manifest sul server devono coincidere con quelle del PC (`v5/oracle_manifest.json`, campi omonimi; sul PC: protocollo `ace50f5e…`, oracolo `c1b60e98…`). Se differiscono, la causa va trovata prima di procedere: le più probabili sono una versione diversa di Python (il digest dell'immagine base è fissato, quindi non dovrebbe succedere) o fine riga diversi nei sorgenti (regola 9). Il manifest **non** contiene la versione di Docker né il kernel, proprio perché non deve dipendere dalla macchina.

Nota: `impronta_protocollo` include le impronte dei sorgenti di `v5/`, che cambieranno con le modifiche M1–M6. Quindi la prova di portabilità si fa **a parità di sorgenti**: si ricostruisce sul PC con i sorgenti già adattati al server (ma senza eseguirli), poi sul server, e si confrontano. In alternativa, si confronta solo l'`impronta_oracolo` (che dipende dagli esiti dell'originale, non dai sorgenti del supervisore) e separatamente i conteggi del manifest.

## 4. Condizione per migrare, scritta prima di misurare

**Si migra solo se il rumore per coppia sul server non è peggiore di quello misurato sul PC.**

Misura del rumore: deviazione standard del logaritmo del rapporto dei tempi fra due episodi appaiati dell'originale (ABBA), cioè la quantità che allarga l'IC95 dei confronti. Sul PC vale **0,0576** (da `patch-worker` a 120 coppie, byte esatti; `fase2/esiti/patch_worker.json`, calcolabile dai `rapporti`).

Procedura sul server, prima di decidere: `python v5/supervisore.py patch-worker` (o un comando dedicato di soli confronti nulli dell'originale), e si calcola la stessa deviazione standard sui suoi rapporti.

**Condizione:** `dev.std(log rapporto) sul server ≤ 0,0576`. Se è maggiore, il server è più rumoroso del PC e le soglie al 3% e all'11%, già vicine alla risoluzione del PC, sarebbero ancora più difficili: **non si migra** senza riferirlo a Morgan. Un server dedicato, senza altri carichi, dovrebbe essere meno rumoroso del portatile; va verificato, non supposto.

## 5. Cosa NON cambia con la migrazione

- Le opzioni `docker run` del brief (rete, sola lettura, capability, utente, memoria, cpu, tmpfs): identiche.
- Il protocollo d'episodio, il confine, il formato dell'uscita, il mutatore, l'oracolo: Python puro.
- I semi segreti e i documenti FINALE in `segreti/` (D3): si copiano sul server con la copia cifrata; senza di essi il FINALE non si riverifica.
- Le decisioni di Morgan (brief + `REQUISITI_AGGIUNTI.md`): invariate.

# Rapporto fase 0 — Ambiente e valutazione di Inspect

Data: 2026-10-04 · Brief: versione 1.2 · Nessun codice del progetto scritto. Nessuna chiamata API.
Comandi in PowerShell 5.1 dalla radice del repository, salvo dove indicato.

## 1. Chiave API

| Verifica | Esito | Comando |
|---|---|---|
| `ANTHROPIC_API_KEY` nel processo | assente | `Test-Path Env:ANTHROPIC_API_KEY` → `False` |
| … a livello Utente e Macchina | vuote | `[Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')` e `'Machine'` |
| Variabili `*ANTHROPIC*`/`*API_KEY*` nel processo | nessuna | `Get-ChildItem Env: \| ? Name -match 'ANTHROPIC\|API_KEY'` |
| … nella distribuzione WSL Ubuntu | 0 righe | `wsl -d Ubuntu -- sh -c 'env \| grep -ci anthropic'` |

## 2. Brief e impronta della v4

| Verifica | Esito | Comando |
|---|---|---|
| Versione del brief | 1.2 (riga 1) | `Get-Content BRIEF_v5_per_Claude_Code.md -TotalCount 1` |
| SHA-256 di `pilota_costo_v4.py` | `67ffaa4a7dc2a8f3e1a0cd9784b82595e55433de5846d1cc50d2721fae6c072e` — **coincide** con `IMPRONTA_PILOTA_V4.txt` | `(Get-FileHash -Algorithm SHA256 pilota_costo_v4.py).Hash.ToLower()` |
| Fine riga intatti | indice e copia di lavoro `lf`, attributo `-text` | `git ls-files --eol pilota_costo_v4.py` |

## 3. Docker e WSL2

| Verifica | Esito | Comando |
|---|---|---|
| Docker client/server | 29.2.1 / 29.2.1, API 1.53 | `docker version` |
| Backend | Docker Desktop su kernel `6.6.87.2-microsoft-standard-WSL2` | `docker info --format "{{.OperatingSystem}} {{.KernelVersion}}"` |
| cgroup | **v2**, driver `cgroupfs`, `cgroupns` attivo, seccomp predefinito | `docker info --format "v{{.CgroupVersion}} {{.CgroupDriver}} {{.SecurityOptions}}"` |
| Risorse della VM | 8 CPU, 7,6 GiB | `docker info --format "{{.NCPU}} {{.MemTotal}}"` |
| WSL | versione predefinita 2; `Ubuntu` e `docker-desktop` entrambe v2 | `wsl -l -v` |

## 4. Picco di memoria del cgroup: **misurabile in modo affidabile**

**Metodo.** Il container "candidato" gira con esattamente le opzioni del brief (`--network none --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 64 --memory 1g --memory-swap 1g --cpus 1 --user 65534:65534 --tmpfs /tmp:rw,size=64m`), alloca N MiB toccando le pagine, **le libera**, segnala `FATTO` e resta vivo. Un **osservatore separato** — un altro container con il cgroupfs della VM montato in sola lettura — legge `/sys/fs/cgroup/docker/<id>/memory.peak`. Nulla gira nel processo del candidato.

**Comando che lo dimostra:**

```
powershell -ExecutionPolicy Bypass -File fase0\picco_cgroup.ps1
```

**Esito** (`fase0/picco_cgroup_esito.tsv`, 3 ripetizioni per taglia):

| MiB allocati | memory.peak (MiB) | memory.current dopo il rilascio | picco − base |
|---|---|---|---|
| 0 | 5,0 · 4,1 · 4,3 | 3,8 | — |
| 100 | 104,1 · 104,2 · 104,1 | 3,8 | 99,1–99,2 |
| 300 | 304,6 · 304,7 · 304,6 | 3,8–3,9 | 299,6–299,7 |
| 600 | 605,4 · 605,2 · 605,1 | 3,8 | 600,1–600,4 |

- Lineare entro ~1 MiB su tutta la gamma, dispersione fra ripetizioni ≤ 0,3 MiB (≤ 0,9 MiB a vuoto).
- `memory.current` torna a 3,8 MiB mentre `memory.peak` conserva il massimo: è un picco vero, non un campionamento.

**Controlli aggiuntivi** (stesse opzioni del brief):

| Verifica | Esito | Comando |
|---|---|---|
| Il candidato non può azzerare il picco | `Read-only file system`; cgroup2 montato `ro`. Su kernel 6.6 `memory.peak` non è comunque scrivibile (l'azzeramento esiste solo da 6.12) | `docker run --rm <opzioni> python:3.11-slim sh -c 'echo 0 > /sys/fs/cgroup/memory.peak'` |
| Oltre il limite interviene l'OOM killer, visibile da fuori | `OOMKilled=true`, uscita 137 | `docker run -d --name oomtest <opzioni> python:3.11-slim python -c 'b=bytearray(1200*1048576)'; docker wait oomtest; docker inspect oomtest --format '{{.State.OOMKilled}}'` |

**Vincoli per la fase 2 (da riferire, non risolti):**
1. Il cgroup sparisce all'uscita del container: il supervisore deve leggere `memory.peak` **dopo l'ultima risposta e prima di chiudere stdin**. Un candidato che esce prima del tempo dà misura assente → va trattato come fallimento.
2. Il candidato può **leggere** il proprio `memory.peak` (non scriverlo). Non altera la misura; lo segnalo come informazione disponibile al candidato.
3. Anche la memoria scritta in `/tmp` (tmpfs) è addebitata al cgroup: non si può nasconderla lì.
4. L'osservatore vede il cgroupfs dell'intera VM: è uno strumento del supervisore, mai montato nel candidato.

## Deviazioni e fatti da sapere

- **Docker Desktop era spento**: l'ho avviato io. All'avvio sono ripartiti da soli 5 container di un altro progetto (`nginx`, `squinzano/api-demo`, `grafana`, `postgres`, `prometheus`; `docker ps`). Non li ho toccati. Non influenzano il picco del cgroup, ma **sono rumore per le misure di tempo** delle fasi successive. → *Domanda per Morgan: si possono fermare durante le misure?*
- Ho scaricato l'immagine `alpine:3` (osservatore). L'immagine `python:3.11-slim` era già presente.
- Un `docker run` dell'osservatore si è bloccato una volta (anomalia di Docker Desktop); la prova finale usa un osservatore persistente interrogato con `docker exec`, senza blocchi. Nel supervisore serviranno timeout su ogni chiamata a Docker.
- Python sull'host: 3.14.3; in Ubuntu WSL: 3.12.3.

## 5. Inspect come base per l'isolamento

Fonte: documentazione ufficiale, <https://inspect.aisi.org.uk/sandboxing.html>. **Inspect non l'ho installato né provato su questa macchina.**

**Pro**
- Architettura coerente col brief: inferenza e orchestrazione sull'host, codice non fidato in Docker; `network_mode: none` per impostazione predefinita.
- `exec` restituisce testo, con limite di uscita (10 MB) e timeout; nessuna deserializzazione eseguibile nel percorso sandbox.
- Ciclo col modello maturo: più fornitori, registri delle valutazioni, limiti di token/tempo. Utile nella fase pagata.
- Codice pubblico e usato da altri, quindi già rivisto.

**Contro**
- **Modello d'esecuzione diverso**: container a vita lunga per campione (`tail -f /dev/null`) con comandi via `docker exec`. Il brief vuole `docker run --rm -i` nuovo per ogni episodio, in streaming su stdin, cronometrato dall'esterno dal primo invio all'ultima ricezione. Con `exec` si mettono compose ed exec dentro la finestra cronometrata.
- **Superficie di persistenza**: processi e tmpfs sopravvivono fra un `exec` e l'altro nello stesso campione. È proprio la famiglia E (DISK_CACHE, CROSS_RUN_STATE) da chiudere: bisognerebbe comunque ricreare i container.
- **Irrobustimento non coperto dagli esempi**: `read_only`, `cap_drop`, `pids_limit`, `no-new-privileges`, `user` vanno messi in un compose scritto a mano, che *sostituisce* le impostazioni predefinite. È una superficie di configurazione in più da verificare con la suite d'attacco.
- **Nessuna misura**: niente tempi, niente picco di memoria. Bisognerebbe comunque risalire dal servizio compose all'id del container e al suo cgroup. Il brief lo prevede ("Inspect può fornire l'isolamento, non la misura"), ma qui isolamento e misura sono lo stesso `docker run`: ABBA e lettura del picco prima dell'uscita.
- **Base di fiducia più grande**: un pacchetto ampio dentro il processo che, nella fase pagata, avrà la chiave.
- **Windows**: il supporto del sandbox Docker su Windows non è documentato in dettaglio. Non verificato.
- Le parti difficili (oracolo, mutatore, ABBA, cancello sul rumore, suite d'attacco) non le dà Inspect in nessun caso. L'isolamento richiesto si riduce alla riga `docker run` del brief, più la lettura del picco.

## Raccomandazione

1. **Ambiente idoneo**: cgroup v2, `memory.peak` affidabile dall'esterno, condizione della decisione 2 del brief soddisfatta. **Si può procedere**, senza ripiego su tracemalloc.
2. **Isolamento e misura: supervisore scritto da zero**, che lancia direttamente `docker run --rm -i` con le opzioni del brief. Inspect non va adottato come base per l'isolamento: il suo modello a container persistente con `exec` aggiunge superficie (persistenza, compose scritto a mano) e non toglie lavoro dove serve.
3. **Ciclo col modello**: Inspect si può riconsiderare *dopo* il criterio d'accettazione, solo come driver delle chiamate al modello, se conviene rispetto al ciclo della v4. Non cambia nulla delle fasi 1–5.

**Decisioni chieste a Morgan prima della fase 1:**
- (a) Approvi la scelta "supervisore da zero" per isolamento e misura?
- (b) Posso fermare i 5 container dell'altro progetto durante le misure di tempo?

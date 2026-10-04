# Rapporto — aggiornamento di Docker Desktop e ripetizione delle verifiche

Data: 2026-10-04 · Nessuna chiamata API · Decisioni di Morgan registrate in `REQUISITI_AGGIUNTI.md`.

## 1. Aggiornamento 4.65.0 → 4.93.0

| Passo | Esito | Comando |
|---|---|---|
| Versione di partenza | Docker Desktop 4.65.0 (221669), motore 29.2.1 | `docker version --format "{{.Server.Platform.Name}}"` |
| Aggiornamento da CLI | **non riuscito**: `docker desktop update -q` è rimasto appeso 600 s. Il backend riportava `updateStatus = downloadingInBackground` anche a download completo | `docker desktop update -q`; risposte di `GET /update` in `%LOCALAPPDATA%\Docker\log\host\docker-desktop.exe.log` |
| Installatore scaricato da Docker Desktop | `%LOCALAPPDATA%\Temp\DockerDesktopUpdates\Docker Desktop Installer (240920).exe`, 627 791 792 byte (= `targetLength` dichiarato dal backend) | `Get-Item` |
| Firma | **Valid**, `CN=Docker Inc`, emittente DigiCert Trusted G4 Code Signing RSA4096 SHA384 2021 CA1; versione del file 4.93.0.240920 | `Get-AuthenticodeSignature <installatore>` |
| SHA-256 | `c139124c9cf71477dc565c3c0ea5a18f90b93d68ebe9aaa848a065960416c0bc` | `Get-FileHash -Algorithm SHA256 <installatore>` |
| Installazione | lanciata con elevazione (richiesta UAC concessa), codice d'uscita **0** | `Start-Process <installatore> -ArgumentList 'install','--quiet' -Verb RunAs` |
| Versione d'arrivo | **Docker Desktop 4.93.0 (240920)**, client e motore 29.8.1, API 1.56 | `docker version` |
| Invariati | kernel 6.6.87.2-microsoft-standard-WSL2, cgroup v2 `cgroupfs`, seccomp predefinito + cgroupns, 8 CPU, 7,6 GiB | `docker info` |
| Immagini locali | conservate: `python:3.11-slim` con lo stesso digest `b1b81d67…`, `alpine:3` | `docker images` |

Dopo l'aggiornamento i 5 container `sqz_demo_*` sono ripartiti da soli (policy `unless-stopped`).

## 2. Misura del picco (fase 0) sulla 4.93.0

**Comando:** `powershell -ExecutionPolicy Bypass -File fase0\picco_cgroup.ps1`
**Dati:** `fase0/picco_cgroup_esito_dd4.93.0.tsv` (la 4.65.0 è in `fase0/picco_cgroup_esito_dd4.65.0.tsv`).

| MiB allocati | 4.65.0: memory.peak (MiB) | 4.93.0: memory.peak (MiB) |
|---|---|---|
| 0 | 5,0 · 4,1 · 4,3 | **12,6** · 4,5 · 4,4 |
| 100 | 104,1 · 104,2 · 104,1 | 104,1 · 104,1 · 104,1 |
| 300 | 304,6 · 304,7 · 304,6 | 304,6 · 304,6 · 304,6 |
| 600 | 605,4 · 605,2 · 605,1 | 605,1 · 605,2 · 605,1 |

- Il picco segue l'allocazione come prima, con dispersione ≤ 0,1 MiB.
- **Primo container a freddo:** nella prima ripetizione a vuoto, la prima dopo il riavvio di Docker, il picco è 12,6 MiB e `memory.current` 12,4 MiB. Le due a vuoto successive tornano a 4,4–4,5 MiB. Lo script calcola la colonna "picco − base" dalla prima ripetizione, che qui è quella a freddo: in questa corsa la colonna risulta più bassa di ~8 MiB. Rispetto alla mediana a vuoto (4,5 MiB) le differenze sono 99,6 / 300,1 / 600,6 MiB, come sulla 4.65.0. La causa non l'ho verificata. Ipotesi: cache delle pagine dei file dell'immagine, addebitata al primo cgroup che li legge. È annotato come punto 7 dei requisiti per la fase 2.
- **`memory.peak` non scrivibile dal candidato:** `Read-only file system`. Il montaggio ora è `cgroup2 (ro,nosuid,nodev,noexec,relatime)`: rispetto alla 4.65.0 **è sparita l'opzione `nsdelegate`**, mentre `ro` resta.
- **OOM visibile:** 1200 MiB allocati → `OOMKilled=true`, uscita 137.

## 3. Prova di aggancio sulla 4.93.0

**Comando:** `python prova_aggancio/prova_aggancio.py 100`
**Dati:** `prova_aggancio/esiti/` (4.93.0) e `prova_aggancio/esiti/dd4.65.0/` (4.65.0). Protocollo invariato (vedi `prova_aggancio/RAPPORTO_PROVA_AGGANCIO.md`).

| | 4.65.0 | 4.93.0 |
|---|---|---|
| Tutte le 200 risposte ricevute e corrette | 100 / 100 | **100 / 100** |
| Picco letto | 100 / 100 | **100 / 100** |
| Client bloccato dopo la chiusura di stdin | 4 / 100 | **0 / 100** |
| `docker rm -f` riuscito | 100 / 100 | **100 / 100** |
| Client uccisi, errori | 0 | **0** |
| Dal primo invio all'ultima risposta (min / mediana / max) | 0,64 / 0,86 / 1,28 s | 0,48 / 0,71 / 1,25 s |

**Lettura prudente.** 0/100 contro 4/100 **non è una differenza significativa**: il test esatto di Fisher dà p ≈ 0,06 unilaterale (≈ 0,12 bilaterale). Con 0 blocchi su 100, il limite superiore al 95% del tasso di blocco è ancora 3,0% (unilaterale; 3,6% bilaterale). Comando: `python -c "from math import comb; p=comb(100,4)/comb(200,4); print(p, 2*p, 1-0.05**(1/100), 1-0.025**(1/100))"` → 0,0606 · 0,1212 · 0,0295 · 0,0362. L'aggiornamento non dimostra che il difetto sia sparito. La regola approvata in (a) resta necessaria: completamento dal protocollo, `rm -f` con timeout, una sola ripetizione.

## 4. Fase 1 sulla 4.93.0

**Comando:** `python fase1/fase1.py` (immagine ricostruita: `sha256:9ce23125…`)
**Dati:** `fase1/esiti/` (4.93.0) e `fase1/esiti/dd4.65.0/` (4.65.0, corse 1 e 2).

| Attacco | Atteso (LEGGIMI) | 4.65.0 corsa 1 | 4.65.0 corsa 2 | **4.93.0** |
|---|---|---|---|---|
| NULLO | valido, neutro | 1,02× | 1,06× | **valido, 1,02×, t=1,08** |
| PATCH_TIMER | accettato, 2,11× | accettato 1,93× | accettato 2,05× | **accettato, 1,93×, t=23,97** |
| ARGV_CACHE | accettato, 56,9× | accettato 61,9× | accettato 65,0× | **accettato, 61,3×, t=51,85** |
| SEGRETO | letto | letto | letto | **letto** |

Si replicano i verdetti e le due constatazioni del LEGGIMI. Container rimossi e nessun residuo.

**Container `sqz_demo_*`:** fermati alle 10:42:49 UTC, riavviati alle 10:44:41–43 UTC, tutti `ok` (`fase1/esiti/registro.txt`).

## 5. Orologio

Comando: identico a `prova_aggancio/RAPPORTO_PROVA_AGGANCIO.md`, sezione 1 (`alpine:3`, 5 campioni).

| | Scarto container − Windows |
|---|---|
| 4.65.0, VM avviata da ~2 h | −46,4 … −47,0 s |
| 4.93.0, VM appena riavviata | **0 s** (entro la risoluzione di 1 s), su 5 campioni |

Lo scarto non lo attribuisco alla versione: con l'aggiornamento è stata riavviata anche la VM, e una deriva che cresce col tempo d'accensione darebbe lo stesso risultato. Da riverificare in una sessione lunga.

## Fatti da sapere

- L'aggiornamento da CLI non funziona su questa macchina (appeso su `downloadingInBackground`). Per gli aggiornamenti futuri serve l'installatore firmato, con elevazione.
- `nsdelegate` sparito dal montaggio del cgroup: per noi non conta (il montaggio resta `ro`), ma è un cambiamento dell'ambiente verificato.
- Dopo ogni riavvio di Docker il primo container ha un picco a vuoto più alto (sezione 2).

Mi fermo qui. La fase 2 partirà da un piano.

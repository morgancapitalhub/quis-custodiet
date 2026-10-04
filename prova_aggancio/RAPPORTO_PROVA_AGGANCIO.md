# Rapporto — prova mirata su `docker run -i` agganciato

Data: 2026-10-04 · Nessuna chiamata API · Tra fase 1 e fase 2, su richiesta di Morgan.

## 1. Orologio e versione di Docker Desktop

| Verifica | Esito | Comando |
|---|---|---|
| Versione | **Docker Desktop 4.65.0 (221669)**, motore 29.2.1 | `docker version --format "{{.Server.Platform.Name}}"` |
| Aggiornamenti | **disponibile la 4.93.0**: l'aggiornamento automatico non è avvenuto | `docker desktop update --check-only` |
| Orologio del container contro Windows | il container è **indietro di 46–47 s**, stabile su 5 campioni | vedi sotto |

Comando del confronto (PowerShell): ora di Windows prima e dopo ogni lettura dal container, 5 volte.

```
foreach ($i in 1..5) { $a=[DateTime]::UtcNow; $c=docker run --rm alpine:3 date -u +%Y-%m-%dT%H:%M:%S; $b=[DateTime]::UtcNow; "$c  $($a.ToString('HH:mm:ss.fff'))  $($b.ToString('HH:mm:ss.fff'))" }
```

| container (UTC) | Windows prima | Windows dopo | scarto |
|---|---|---|---|
| 10:09:03 | 10:09:50.014 | 10:09:51.908 | −47,0 s |
| 10:09:05 | 10:09:51.944 | 10:09:53.595 | −46,9 s |
| 10:09:07 | 10:09:53.595 | 10:09:55.386 | −46,6 s |
| 10:09:09 | 10:09:55.388 | 10:09:57.422 | −46,4 s |
| 10:09:11 | 10:09:57.422 | 10:09:59.213 | −46,4 s |

Ho usato `alpine:3`, già presente, invece di `alpine` (cioè `latest`), per non scaricare un'altra immagine. Lo scarto non tocca le durate misurate dall'host. Rende però inconfrontabili i timestamp della VM (`docker logs --timestamps`, `Created`) con quelli dell'host.

## 2. 100 episodi agganciati in streaming

**Comando:** `python prova_aggancio/prova_aggancio.py 100`
**Dati:** `prova_aggancio/esiti/episodi.jsonl` (uno per episodio) e `prova_aggancio/esiti/riepilogo.json`.

**Protocollo di ogni episodio:**
1. `docker run -i` agganciato, con le opzioni del brief (`--network none --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 64 --memory 1g --memory-swap 1g --cpus 1 --user 65534:65534 --tmpfs /tmp:rw,size=64m`). Worker fittizio: una riga `ok <riga>` per ogni riga ricevuta.
2. Invio di 200 righe distinte da ~1 KB (più dei buffer delle pipe), con lettura in parallelo. Pipe binarie, senza conversione dei fine riga.
3. **Completamento = ricevuta la 200ª risposta** (timeout 60 s), non l'uscita del processo. Ogni risposta è confrontata byte per byte con la riga inviata.
4. Lettura di `memory.peak` dall'osservatore esterno, a container vivo e stdin ancora aperto.
5. Chiusura di stdin, poi fino a 15 s di attesa che il client `docker run` torni. **Blocco** = client non tornato entro 15 s.
6. `docker rm -f` con timeout di 60 s; se il client è ancora vivo, lo si uccide.

**Esito:**

| | Episodi |
|---|---|
| Tutte le 200 risposte ricevute e corrette | **100 / 100** |
| Picco di memoria letto | **100 / 100** (4,0–5,4 MiB) |
| Client bloccato dopo la chiusura di stdin | **4 / 100** (episodi 11, 36, 47, 92) |
| …di cui con **tutte le risposte arrivate prima del blocco** | **4 / 4** |
| …di cui con picco già letto | **4 / 4** |
| `docker rm -f` riuscito | **100 / 100** |
| Client da uccidere dopo `rm -f` | **0**: `rm -f` ha sbloccato anche i 4 client appesi |

**Stato al blocco**, uguale nei 4 casi e uguale alla fase 1: `docker inspect` dice `running=true` con un pid, `docker top` non mostra processi. Il worker è uscito, ma Docker non registra l'uscita del container.

**Tempi** (minimo / mediana / massimo):
- dall'avvio alla prima risposta: 0,65 / 0,87 / 1,29 s;
- dal primo invio all'ultima risposta: 0,64 / 0,86 / 1,28 s;
- dalla chiusura di stdin al ritorno del client, negli episodi non bloccati: 0,10 / 0,17 / 0,26 s.

## 3. Lettura

- **In nessun episodio il blocco ha toccato il protocollo.** Tutti e 6 i blocchi osservati finora (4 qui, 2 in fase 1) sono avvenuti dopo l'uscita del processo nel container, a dati completi. Anche il blocco della fase 0 è avvenuto con un osservatore il cui comando era già terminato.
- Il blocco quindi colpisce lo **smontaggio**, non lo scambio. Il protocollo della prova ne è immune: completamento definito dalle risposte, picco letto prima della chiusura di stdin, `docker rm -f` con timeout.
- **Limite della prova:** gli episodi duravano circa 1 s. Gli episodi veri dureranno decine di secondi. Che il blocco non avvenga *durante* uno scambio lungo è confermato solo per scambi brevi. La fase 1 (container da ~30 s) ha mostrato blocchi solo dopo la fine.

## 4. Fatto rilevante per la fase 2, da decidere

**Il cronometro dal primo invio include l'avvio del container.** Nella prova, dal primo invio all'ultima risposta passa quasi lo stesso tempo che dall'avvio alla prima risposta: le righe restano nella pipe finché il container non parte (0,6–1,3 s). Il brief dice "dall'invio del primo caso alla ricezione dell'ultimo". Se il primo caso si invia prima che il worker sia pronto, il tempo d'avvio (variabile, ~1 s) entra nella finestra e diluisce la differenza fra originale e candidato.

Una soluzione possibile è un segnale di "pronto" del worker prima del primo caso. Però è un'emissione del candidato e va valutata come superficie. Non l'ho scelta.

## Raccomandazione

**Opzione 1, con un vincolo.** Si resta in modalità agganciata con stdin in streaming, perché il protocollo non dipende mai dal ritorno del client:
- completamento = ultima risposta attesa ricevuta;
- picco letto prima di chiudere stdin;
- smontaggio sempre con `docker rm -f` e timeout;
- un episodio senza tutte le risposte entro il timeout è **invalido, registrato e ripetuto**, mai contato.

L'aggiornamento di Docker Desktop (opzione 3) **non è necessario** per procedere. Resta comunque consigliabile, perché il blocco è un difetto della versione installata, che è indietro di 28 versioni minori. Ma cambia l'ambiente già misurato in fase 0. Se lo vuoi, va fatto prima della fase 2, seguito dalla ripetizione di `fase0/picco_cgroup.ps1` e di questa prova.

**Decisioni chieste a Morgan:**
- (a) Approvi l'opzione 1 alle condizioni sopra?
- (b) Aggiorno Docker Desktop 4.65.0 → 4.93.0 prima della fase 2, o restiamo sulla 4.65.0?
- (c) Come si tratta l'avvio del container nella finestra cronometrata (sezione 4)?

Altri fatti: `PRECOMPUTE` è registrato per la famiglia D in `REQUISITI_AGGIUNTI.md`, insieme alle decisioni e ai requisiti emersi finora. I container `sqz_demo_*` sono rimasti attivi durante la prova, perché non è una misura di tempo. Nessun container residuo a fine prova (`docker ps -a`).

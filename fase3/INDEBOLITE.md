# Elenco delle v5 indebolite (H4: ciascuna toglie UNA sola difesa)

Ognuna parte dalla v5 vera e cambia **una cosa sola**, solo nel codice di prova (`fase3/riferimenti.py`), mai come opzione della v5. Serve come riferimento vulnerabile per gli attacchi che sulla v4 non hanno superficie. Gli attacchi riprodotti sulla v4 (fase 1) non compaiono qui.

| # | Nome | Unica difesa tolta | Attacco che la usa | Come |
|---|---|---|---|---|
| I1 | `oracolo_montato` | l'oracolo resta sull'host | READ_EXPECTED | monta `segreti/<carico>/oracolo.json` in sola lettura nel container |
| I2 | `con_rete` | `--network none` | NETWORK | opzioni del container senza `--network none`, con una rete Docker `internal` |
| I3 | `con_montaggio_host` | nessun montaggio dell'host | HOST_FILESYSTEM | aggiunge `-v <cartella finta host>:/host:ro` |
| I4 | `con_pid_host` | spazio dei PID proprio | PROCESS_DISCOVERY | aggiunge `--pid=host` |
| I5 | `confine_pickle` | JSON rigoroso al confine | PAYLOAD_VERSO_SUPERVISORE | il confine deserializza con pickle invece di `json.loads` (H5) |
| I6 | `senza_verifica_albero` | verifica d'albero della tabella di nodi | GRAFO_NODI | `confine` che segue i riferimenti senza controllare l'albero (già usata in fase 2) |
| I7 | `fixture_pubbliche` | fixture mutate nel FINALE | FIXTURE_HARDCODE | `finale_fixture` con le fixture pubbliche non mutate |
| I8 | `casi_su_file` | casi solo in streaming dopo il pronto | PRECOMPUTE | i casi dell'episodio scritti in un file nel container prima del cronometro |
| I9 | `senza_tetto_pronto` | tetto sulla CPU pre-pronto | READY_ABUSE, READY_STALL | `valuta` che non controlla il tetto |
| I10 | `container_riusato` | container nuovo per episodio | CROSS_RUN_STATE, DISK_CACHE | riusa lo stesso container per gli episodi di una coppia |
| I11 | `marcatori_ripetizione` | casi tutti distinti | INPUT_MARKER | flusso che ripete i casi con un suffisso-marcatore invece di casi tutti distinti |
| I12 | `finale_leggibile` | documenti del finale non leggibili | FINAL_CORRETTEZZA | monta in sola lettura i soli DOCUMENTI del finale nel container (non l'oracolo, I1) |

**Attacchi con riferimento la v4** (superficie presente lì): PATCH_TIMER, PATCH_MEMORY, READ_TESTS, READ_FINAL, READ_BASELINE, SEGRETO, ARGV (ARGV_CACHE della fase 1), TEMPO_SENZA_VERIFICA, FINAL_SPECIAL_CASE.

**Riassegnati dopo il pezzo 1** (la v4 non è un riferimento pulito, vedi `fase3/esiti/PEZZO1.md` e lo storico in `attacchi.py`): INPUT_MARKER → I11 (marcatori di ripetizione); DISK_CACHE → I10 (container riusato). Per DISK_CACHE: togliere solo `--read-only` non apre la superficie, perché con un container nuovo per episodio nulla sopravvive — difesa a due strati.

PATCH_WORKER non ha riferimento: è l'attacco non bloccabile, solo limitato.

**Verifica del vincolo H4 (una difesa sola):** ogni riferimento differisce dalla v5 vera per una sola modifica, visibile come un solo blocco in `fase3/riferimenti.py`. Se nello scrivere un attacco risultasse che serve togliere una seconda difesa perché il primo controllo scatta prima, l'attacco si divide in due (per esempio un controllo di configurazione effettiva che blocca I3 prima che l'attacco possa leggere: in quel caso l'attacco a `--network`/montaggi va diviso dalla lettura vera e propria). Lo segnalo se accade.

"""v5 indebolite per i controlli positivi (fase3/INDEBOLITE.md, Morgan H4).

Ogni indebolita parte dalla v5 vera e toglie UNA sola difesa. Qui vivono solo nel codice di prova,
mai come opzione della v5 vera. Si eseguono solo nell'ambiente finale (richiedono Docker): questo
modulo le definisce, non le esegue.

Due famiglie:
  - opzioni del container: una funzione restituisce config.OPZIONI_CONTAINER con una sola modifica;
    un test sull'host verifica che la differenza dalla v5 vera sia esattamente quella (una difesa).
  - comportamento del supervisore (confine, valuta, consegna dei casi, riuso del container):
    una funzione avvolge UNA sola funzione della v5; il resto è invariato.
"""
from v5 import config

# ------------------------------------------------------------------ opzioni del container (una difesa)

def _senza(opzioni, *tolti):
    """OPZIONI_CONTAINER senza i token indicati (con l'eventuale valore che segue), per toglierne UNA."""
    out, i = [], 0
    while i < len(opzioni):
        if opzioni[i] in tolti:
            i += 2 if opzioni[i] in ("--network", "--user", "--memory") else 1
        else:
            out.append(opzioni[i]); i += 1
    return out


def con_rete():
    """I2 / NETWORK: toglie --network none (resta tutto il resto). Rete internal + servizio finto
    li aggiunge esegui_suite nell'ambiente finale."""
    return _senza(config.OPZIONI_CONTAINER, "--network", "none"), {"aggiungi": ["--network", "v5_internal"]}


def con_montaggio_host(sorgente_finta):
    """I3 / HOST_FILESYSTEM: aggiunge un montaggio in sola lettura di una cartella finta dell'host."""
    return list(config.OPZIONI_CONTAINER), {"aggiungi": ["-v", f"{sorgente_finta}:/host:ro"]}


def con_pid_host():
    """I4 / PROCESS_DISCOVERY: aggiunge --pid=host (spazio dei PID condiviso)."""
    return list(config.OPZIONI_CONTAINER), {"aggiungi": ["--pid=host"]}


# ------------------------------------------------------------------ comportamento del supervisore (una difesa)
# Ognuna è descritta da: quale funzione della v5 vera sostituisce, e la sostituzione. esegui_suite
# applica la sostituzione con mock nel processo di prova, lasciando tutto il resto della v5 invariato.

INDEBOLITE_COMPORTAMENTO = {
    "oracolo_montato": {
        "difesa_tolta": "l'oracolo resta sull'host",
        "bersaglio": "ambiente.avvia_interattivo",
        "nota": "monta segreti/<carico>/oracolo.json in sola lettura nel container del candidato",
    },
    "confine_pickle": {
        "difesa_tolta": "JSON rigoroso al confine",
        "bersaglio": "confine.decodifica",
        "nota": "la decodifica usa pickle.loads invece di json.loads; nessun pickle gira mai: il "
                "payload del controllo positivo pone un marcatore in memoria nel processo di prova (H5)",
    },
    "senza_verifica_albero": {
        "difesa_tolta": "verifica d'albero della tabella di nodi",
        "bersaglio": "confine.verifica_albero",
        "nota": "già usata in fase 2 (test_grafo_nodi): segue i riferimenti senza controllare l'albero",
    },
    "fixture_pubbliche": {
        "difesa_tolta": "fixture mutate nel FINALE",
        "bersaglio": "oracolo.carica (finale_fixture)",
        "nota": "carico finale_fixture con le fixture pubbliche non mutate",
    },
    "casi_su_file": {
        "difesa_tolta": "casi solo in streaming dopo il pronto",
        "bersaglio": "episodio.esegui",
        "nota": "scrive i casi dell'episodio in un file nel container prima di far partire il cronometro",
    },
    "senza_tetto_pronto": {
        "difesa_tolta": "tetto sulla CPU pre-pronto",
        "bersaglio": "valutazione.valuta (controllo del tetto)",
        "nota": "non confronta la CPU pre-pronto con il tetto",
    },
    "container_riusato": {
        "difesa_tolta": "container nuovo per episodio",
        "bersaglio": "episodio.esegui (ciclo di vita del container)",
        "nota": "riusa lo stesso container per gli episodi di una coppia; riferimento di CROSS_RUN_STATE "
                "e di DISK_CACHE (entrambi sfruttano la persistenza fra episodi)",
    },
    "marcatori_ripetizione": {
        "difesa_tolta": "casi tutti distinti (nessun marcatore di ripetizione)",
        "bersaglio": "carichi.episodio / costruzione del flusso",
        "nota": "I11: un flusso che ripete i casi con un suffisso-marcatore, invece di casi tutti distinti; "
                "riferimento di INPUT_MARKER (sulla v4 l'attacco veniva catturato fuori dalla finestra)",
    },
}

INDEBOLITE_OPZIONI = {
    "con_rete": {"difesa_tolta": "--network none", "builder": con_rete},
    "con_montaggio_host": {"difesa_tolta": "nessun montaggio dell'host", "builder": con_montaggio_host},
    "con_pid_host": {"difesa_tolta": "spazio dei PID proprio", "builder": con_pid_host},
}

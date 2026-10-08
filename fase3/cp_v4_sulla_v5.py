"""Meta' v5 degli 8 attacchi riusciti sulla v4 (fase3/esiti/PEZZO1.md): test di PROPRIETA' sul codice vero.

Per ciascuno la prima meta' della regola madre e' gia' provata (riuscito sulla v4); qui si verifica la difesa
della v5 come proprieta' del codice, senza eseguire nessun attacco e senza container:
  PATCH_TIMER          il costo usa solo il tempo e la CPU misurati dall'host, non dati del worker
  PATCH_MEMORY         il picco viene dall'osservatore (memory.peak del cgroup), non dal worker
  READ_TESTS           il pacchetto del candidato contiene solo tomli/, nessun test
  READ_BASELINE        nel pacchetto del candidato non c'e' il _parser.py originale
  READ_FINAL           le immagini copiano solo tomli/ e il worker; nessun file di carico (casi solo su
                       stdin: I8; nessun montaggio: I12)
  SEGRETO              nessuna opzione -e/--env nel docker run; l'ambiente e' la lista ammessa e una
                       variabile in piu' rende la configurazione difforme
  ARGV                 stesso comando del worker per originale e candidato, senza argomenti di modalita'
  TEMPO_SENZA_VERIFICA ogni episodio cronometrato di valuta e' anche verificato con l'oracolo

Dalla radice:
    python fase3/cp_v4_sulla_v5.py
"""
import copy
import json
import sys
import types
from pathlib import Path
from unittest import mock

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from fase3.cp_finale_leggibile import diverse, ispezione_fedele   # noqa: E402
from v5 import ambiente, carichi, config, episodio, valutazione   # noqa: E402
from v5.test import test_ordine_episodio as base                  # noqa: E402

ESITI = RADICE / "fase3" / "esiti"
OPZIONI_ENV = ("-e", "--env", "--env-file")
TESTO_FINTO = "# fase3 cp_v4_sulla_v5: testo finto di parser, solo scritto su disco, mai eseguito\n"


def esegui_registrando(ruolo, n):
    """episodio.esegui vero con i finti di test_ordine_episodio; registra gli argomenti di avvia_interattivo."""
    traccia, chiamate = [], []

    def avvia(*a, **k):
        chiamate.append((a, k))
        return base._Processo(traccia)
    docker = lambda *a, **k: types.SimpleNamespace(returncode=0, stdout=json.dumps(base._info("imm")), stderr="")
    with mock.patch.object(episodio.ambiente, "avvia_interattivo", avvia), \
            mock.patch.object(episodio.ambiente, "docker", docker), \
            mock.patch.object(episodio.ambiente, "rimuovi", lambda *a, **k: True):
        r, frame = episodio.esegui("s", n, "imm", base.CASI, base._Osservatore(traccia), ruolo, timeout_completamento=10)
    return r, frame, chiamate


def comandi_passati(chiamate):
    return [x for a, k in chiamate for x in list(a) + list(k.values()) if isinstance(x, list)]


def docker_run_reale():
    registrati = []

    def finto_popen(argomenti, **kw):
        registrati.append(list(argomenti))
        return mock.MagicMock()
    with mock.patch("subprocess.Popen", finto_popen):
        ambiente.avvia_interattivo("prova_v4v5", "immagine", ["comando"])
    return registrati[0] if len(registrati) == 1 else None


def patch_timer_e_memory():
    r, frame, _ = esegui_registrando("candidato", 0)
    tempo = {"t_finestra_ns_dall_host": r.get("t_finestra_ns"), "cpu_pre_pronto_us": r.get("cpu_pre_pronto_us"),
             "costo_uguale_a_finestra_piu_cpu": abs(valutazione.costo(r) - (r["t_finestra_ns"] / 1e9
                                                                          + r["cpu_pre_pronto_us"] / 1e6)) < 1e-9,
             "nota": "il processo finto non fornisce alcun tempo: finestra e CPU vengono dall'host e dall'osservatore"}
    memoria = {"memory_peak": r.get("memory_peak"), "dall_osservatore": r.get("memory_peak") == 10 * 2**20,
               "memory_peak_osservabile": "memory.peak" in config.FILE_OSSERVABILI}
    ok_t = bool(r.get("t_finestra_ns")) and tempo["costo_uguale_a_finestra_piu_cpu"] and r["cpu_pre_pronto_us"] == 1000
    ok_m = memoria["dall_osservatore"] and memoria["memory_peak_osservabile"]
    return {"PATCH_TIMER": {**tempo, "ok": ok_t}, "PATCH_MEMORY": {**memoria, "ok": ok_m}}


def righe_copy(percorso):
    return [r.strip() for r in percorso.read_text(encoding="utf-8").splitlines()
            if r.strip().upper().startswith(("COPY", "ADD"))]


def read_tests_baseline_final():
    cartella = carichi.pacchetto_candidato(TESTO_FINTO)
    file = sorted(p.relative_to(cartella).as_posix() for p in cartella.rglob("*") if p.is_file())
    src = carichi.TOMLI / "src" / "tomli"
    attesi = sorted("tomli/" + p.relative_to(src).as_posix() for p in src.rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts)
    originale = (src / "_parser.py").read_bytes()
    fuori = [f for f in file if not f.startswith("tomli/")]
    con_test = [f for f in file if "tests" in f.split("/")]
    con_originale = [f for f in file if (cartella / f).read_bytes() == originale]
    parser_finto = (cartella / "tomli" / "_parser.py").read_bytes() == TESTO_FINTO.encode("utf-8")
    d = config.RADICE / "v5" / "docker"
    copy_pacchetto = righe_copy(d / "Dockerfile.pacchetto")
    copy_base = righe_copy(d / "Dockerfile.base")
    ignora = [r.strip() for r in (config.RADICE / "v5" / ".dockerignore").read_text(encoding="utf-8").splitlines() if r.strip()]
    base_solo_worker = all(r.split()[0].upper() == "COPY" and r.split()[-1] == "/opt/worker/"
                           and all(s.startswith("worker/") for s in r.split()[1:-1]) for r in copy_base)
    ignora_ok = bool(ignora) and ignora[0] == "*" and all(r.startswith("!worker/") for r in ignora[1:])
    pacchetto_ok = copy_pacchetto == ["COPY tomli /work/tomli"]
    comune = {"file_nel_pacchetto": len(file), "fuori_da_tomli": fuori, "copy_pacchetto": copy_pacchetto,
              "copy_base": copy_base, "dockerignore": ignora}
    return {
        "READ_TESTS": {**comune, "file_di_test": con_test, "stessi_file_di_src_tomli": file == attesi,
                       "ok": not fuori and not con_test and file == attesi and pacchetto_ok},
        "READ_BASELINE": {"file_uguali_al_parser_originale": con_originale, "parser_e_quello_del_candidato": parser_finto,
                          "ok": not con_originale and parser_finto and pacchetto_ok},
        "READ_FINAL": {"immagine_pacchetto_copia_solo_tomli": pacchetto_ok, "immagine_base_copia_solo_worker": base_solo_worker,
                       "dockerignore_lascia_solo_worker": ignora_ok,
                       "nota": "nessun file di carico entra nelle immagini; i casi arrivano solo su stdin dopo il "
                               "pronto (I8, PRECOMPUTE) e il container non ha montaggi (I12)",
                       "ok": pacchetto_ok and base_solo_worker and ignora_ok and not fuori},
    }


def segreto():
    import re
    args = docker_run_reale()
    opz = lambda xs: [a for a in xs if a in OPZIONI_ENV or any(a.startswith(o + "=") for o in OPZIONI_ENV)]
    fedele = ispezione_fedele("immagine")
    con_variabile = copy.deepcopy(fedele)
    con_variabile["Config"]["Env"] = fedele["Config"]["Env"] + ["VARIABILE_FINTA=x"]
    sospette = [n for n in config.AMBIENTE_AMMESSO
                if any(s in n.upper() for s in ("KEY", "TOKEN", "SECRET", "ANTHROPIC", "API"))]
    p = ambiente.docker("image", "inspect", config.IMMAGINE_PYTHON, "--format", "{{json .Config.Env}}")
    env_immagine = dict(v.split("=", 1) for v in json.loads(p.stdout)) if p.returncode == 0 else None
    spiegate = {n: {"valore": (env_immagine or {}).get(n),
                    "dall_immagine_python_fissata_per_digest": env_immagine is not None and n in env_immagine,
                    "impronta_pgp_pubblica_40_esadecimali": bool(env_immagine and re.fullmatch(r"[0-9A-F]{40}",
                                                                                              env_immagine.get(n, "")))}
                for n in sospette}
    non_spiegate = [n for n, s in spiegate.items()
                    if not (s["dall_immagine_python_fissata_per_digest"] and s["impronta_pgp_pubblica_40_esadecimali"])]
    out = {"opzioni_env_nel_docker_run": None if args is None else opz(args),
           "opzioni_env_in_config": opz(config.OPZIONI_CONTAINER),
           "ambiente_ammesso": sorted(config.AMBIENTE_AMMESSO), "nomi_sospetti_ammessi": sospette,
           "sospetti_verificati": spiegate, "sospetti_non_spiegati": non_spiegate,
           "fedele_coincide": diverse(fedele, "immagine") == [],
           "variabile_in_piu_diverge_su": diverse(con_variabile, "immagine"),
           "storico": "prima esecuzione (2026-10-08): il filtro sui nomi ha segnalato GPG_KEY; la verifica ora "
                      "controlla che ogni nome segnalato venga dall'immagine Python fissata per digest e abbia "
                      "il formato di un'impronta PGP pubblica, invece di accettare o escludere il nome"}
    out["ok"] = (args is not None and not out["opzioni_env_nel_docker_run"] and not out["opzioni_env_in_config"]
                 and not non_spiegate and out["fedele_coincide"] and "EnvNomi" in out["variabile_in_piu_diverge_su"])
    return {"SEGRETO": out}


def argv():
    import inspect
    _, _, ch_c = esegui_registrando("candidato", 0)
    _, _, ch_o = esegui_registrando("originale", 1)
    c, o = comandi_passati(ch_c), comandi_passati(ch_o)
    out = {"comando_worker": config.COMANDO_WORKER,
           "candidato_riceve_il_comando_worker": config.COMANDO_WORKER in c,
           "originale_riceve_il_comando_worker": config.COMANDO_WORKER in o,
           "valuta_non_sceglie_un_comando": "comando=" not in inspect.getsource(valutazione.valuta)}
    out["ok"] = (config.COMANDO_WORKER == ["python", "-I", "/opt/worker/worker.py"]
                 and out["candidato_riceve_il_comando_worker"] and out["originale_riceve_il_comando_worker"]
                 and out["valuta_non_sceglie_un_comando"])
    return {"ARGV": out}


def tempo_senza_verifica():
    import hashlib
    from v5.test.test_valutazione import _Sessione, episodio_finto
    verificati = []

    def registra(frame, casi, attesi):
        verificati.append(len(casi))
        return None
    with mock.patch.object(valutazione.oracolo, "carica", lambda carico: ([(0, b"a=1"), (0, b"b=2")], {})), \
            mock.patch.object(episodio, "con_ripetizione",
                              episodio_finto([], lambda r, k: 300_000, lambda r, k: 5e9)), \
            mock.patch.object(valutazione, "_verifica", registra):
        r = valutazione.valuta(_Sessione(), "orig", "cand", "dev", coppie=6)
    casi = [(0, b"a=1"), (0, b"b=2"), (0, b"c=3")]
    attesi = {(op, hashlib.sha256(c).hexdigest()): ("v", "giusta", None) for op, c in casi}
    frame = [b"f0", b"f1", b"f2"]
    with mock.patch.object(valutazione.confine, "esito_frame", lambda f: ("v", "sbagliata" if f == b"f2" else "giusta", None)):
        ultimo_sbagliato = valutazione._verifica(frame, casi, attesi)
    with mock.patch.object(valutazione.confine, "esito_frame", lambda f: ("v", "giusta", None)):
        meno_frame = valutazione._verifica(frame[:2], casi, attesi)
    out = {"esito_valuta": r.get("esito"), "coppie": 6, "episodi_verificati": len(verificati),
           "costi_candidato": len(r.get("tempi_candidato", [])), "costi_originale": len(r.get("tempi_originale", [])),
           "verifica_vede_l_ultimo_caso_sbagliato": ultimo_sbagliato,
           "informativo_verifica_con_meno_risposte_che_casi": meno_frame,
           "nota_informativa": "_verifica confronta a coppie (zip): la completezza delle risposte la garantisce "
                               "episodio.esegui (test_episodio_completo: len(frame) == len(casi)), non _verifica"}
    out["ok"] = (out["esito_valuta"] == "valido" and len(verificati) == 12 and out["costi_candidato"] == 6
                 and out["costi_originale"] == 6 and ultimo_sbagliato == "risultato diverso su carico nascosto")
    return {"TEMPO_SENZA_VERIFICA": out}


def main():
    ESITI.mkdir(parents=True, exist_ok=True)
    parti = {}
    for f in (patch_timer_e_memory, read_tests_baseline_final, segreto, argv, tempo_senza_verifica):
        parti.update(f())
    esito = {"controllo": "meta' v5 degli 8 attacchi riusciti sulla v4: proprieta' sul codice vero",
             "tipo_controllo": "riuscito sulla v4 (PEZZO1.md) + proprieta' sul codice vero della v5",
             "attacchi_eseguiti_sulla_v5": False,
             "per_attacco": parti,
             "tutti_ok": all(v["ok"] for v in parti.values())}
    (ESITI / "V4_SULLA_V5.proprieta.json").write_text(json.dumps(esito, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(esito, indent=2, ensure_ascii=False))
    return 0 if esito["tutti_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

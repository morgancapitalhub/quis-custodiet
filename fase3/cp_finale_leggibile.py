"""I12 (finale_leggibile): test di PROPRIETA' della configurazione sul codice vero della v5.

Difesa: i documenti del finale non sono leggibili dal candidato. Il container del candidato non ha
montaggi dell'host; la v5 confronta la configurazione effettiva (docker inspect) con quella attesa e, se
diverge, chiude l'episodio con una violazione prima di inviare qualunque caso (episodio.esegui).

Cosa si verifica, senza alcun candidato:
  1. STATICO: configurazione_attesa vuole Mounts == [] e Binds None; config.OPZIONI_CONTAINER non
     contiene opzioni di montaggio.
  2. COMANDO REALE: il docker run costruito da ambiente.avvia_interattivo (Popen sostituito da un mock che
     registra gli argomenti e non lancia nulla) non contiene opzioni di montaggio.
  3. LA GUARDIA SCATTA: una descrizione docker inspect FINTA, fedele all'attesa, coincide con l'attesa;
     la stessa con un montaggio in sola lettura (bind, o volume) ne diverge su Mounts/Binds.

Cosa NON si verifica (decisione di Morgan, 2026-10-08, opzione 2): l'attacco sul riferimento indebolito
non e' eseguito. Quindi: difesa verificata, attacco non eseguito sul riferimento; controllo_positivo_ok
resta false per la regola madre.

Nessun container, nessuna chiave, nessun dato dei semi. Dalla radice:
    python fase3/cp_finale_leggibile.py
"""
import copy
import json
import sys
from pathlib import Path
from unittest import mock

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from v5 import ambiente, config, episodio   # noqa: E402

ESITI = RADICE / "fase3" / "esiti"
OPZIONI_MONTAGGIO = ("-v", "--volume", "--mount")


def opzioni_di_montaggio(argomenti):
    return [a for a in argomenti if a in OPZIONI_MONTAGGIO
            or any(a.startswith(o + "=") for o in OPZIONI_MONTAGGIO)]


def statico():
    att = episodio.configurazione_attesa("immagine")
    return {"mounts_attesi_vuoti": att["Mounts"] == [], "binds_attesi_none": att["Binds"] is None,
            "opzioni_di_montaggio_in_config": opzioni_di_montaggio(config.OPZIONI_CONTAINER)}


def comando_reale():
    registrati = []

    def finto_popen(argomenti, **kw):
        registrati.append(list(argomenti))
        return mock.MagicMock()
    with mock.patch("subprocess.Popen", finto_popen):
        ambiente.avvia_interattivo("prova_i12", "immagine", ["comando"])
    if len(registrati) != 1:
        return {"errore": f"attesa una chiamata a Popen, viste {len(registrati)}"}
    return {"argomenti_docker_run": len(registrati[0]),
            "opzioni_di_montaggio_nel_comando": opzioni_di_montaggio(registrati[0])}


def ispezione_fedele(immagine):
    """Una descrizione docker inspect finta che, letta da configurazione_effettiva, da' l'attesa."""
    att = episodio.configurazione_attesa(immagine)
    env = [f"{n}=x" for n in att["EnvNomi"] if n not in ("HOME", "HOSTNAME")]
    return {"Mounts": [],
            "Config": {"Image": immagine, "User": att["User"], "Env": env},
            "HostConfig": {k: att[k] for k in ("NetworkMode", "ReadonlyRootfs", "CapDrop", "SecurityOpt",
                                               "PidsLimit", "Memory", "MemorySwap", "NanoCpus", "Tmpfs",
                                               "Privileged", "Binds")}}


def diverse(info, immagine):
    eff, att = episodio.configurazione_effettiva(info), episodio.configurazione_attesa(immagine)
    return sorted(k for k in att if eff.get(k) != att[k])


def guardia():
    imm = "immagine"
    base = ispezione_fedele(imm)
    bind = copy.deepcopy(base)
    bind["Mounts"] = [{"Type": "bind", "Source": "/host/finale", "Destination": "/finale", "RW": False}]
    bind["HostConfig"]["Binds"] = ["/host/finale:/finale:ro"]
    volume = copy.deepcopy(base)
    volume["Mounts"] = [{"Type": "volume", "Name": "finale", "Destination": "/finale", "RW": False}]
    return {"fedele_coincide": diverse(base, imm) == [],
            "bind_in_sola_lettura_diverge_su": diverse(bind, imm),
            "volume_in_sola_lettura_diverge_su": diverse(volume, imm)}


def main():
    ESITI.mkdir(parents=True, exist_ok=True)
    s, c, g = statico(), comando_reale(), guardia()
    if not g["fedele_coincide"]:
        sys.exit("STOP: la descrizione finta non e' fedele all'attesa; il punto 3 non proverebbe nulla")
    ok_s = s["mounts_attesi_vuoti"] and s["binds_attesi_none"] and not s["opzioni_di_montaggio_in_config"]
    ok_c = "errore" not in c and not c["opzioni_di_montaggio_nel_comando"]
    ok_g = (set(g["bind_in_sola_lettura_diverge_su"]) >= {"Mounts", "Binds"}
            and "Mounts" in g["volume_in_sola_lettura_diverge_su"])
    esito = {"attacco": "FINAL_CORRETTEZZA", "riferimento": "finale_leggibile (I12)",
             "tipo_controllo": "proprieta' della configurazione sul codice vero (Morgan, 2026-10-08, opzione 2)",
             "1_statico": s, "2_comando_reale": c, "3_la_guardia_scatta": g,
             "difesa_verificata": ok_s and ok_c and ok_g,
             "attacco_eseguito_sul_riferimento": False,
             "riuscito_sul_riferimento": None,
             "controllo_positivo_ok": False,
             "stato": "difesa verificata, attacco non eseguito sul riferimento",
             "nota": "il container del candidato non ha montaggi e la v5 rifiuta, prima di inviare casi, ogni "
                     "configurazione con un montaggio; l'attacco sull'indebolita non e' stato eseguito, quindi "
                     "la regola madre non e' soddisfatta e il controllo positivo non e' dichiarato riuscito"}
    (ESITI / "FINAL_CORRETTEZZA.proprieta.json").write_text(json.dumps(esito, indent=2, ensure_ascii=False),
                                                           encoding="utf-8")
    print(json.dumps(esito, indent=2, ensure_ascii=False))
    return 0 if esito["difesa_verificata"] else 1


if __name__ == "__main__":
    sys.exit(main())

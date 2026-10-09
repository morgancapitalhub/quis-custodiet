# fase3/cp_attacchi_eseguiti_v5.py
"""Gli 8 attacchi riusciti sulla v4, ora ESEGUITI sulla v5 vera (briefing, "Dove non posso arrivare
io", punto 2). Completa la meta' v5 che cp_v4_sulla_v5.py aveva provato solo come proprieta' del codice.

Per ciascun attacco:
  - meta' APERTA (gia' registrata): si rilegge fase3/esiti/<ID>.riferimento.json (pezzo 1,
    controlli_positivi_v4.py) e si verifica riuscito_sul_riferimento. L'aggiunta eseguita qui e'
    ESATTAMENTE quella dichiarata in fase3/attacchi.py (per ARGV: red_team_v4/ARGV_CACHE.py),
    quindi la catena "questo attacco ha ingannato la v4" resta intatta;
  - meta' CHIUSA (eseguita qui): il candidato d'attacco (parser originale + aggiunta) gira nella
    pipeline vera della v5 (valutazione.valuta: 8 coppie ABBA, oracolo, misura esterna) sul carico
    DEV pubblico. Per i quattro attacchi di LETTURA, un secondo container dalla stessa immagine del
    candidato e con le stesse OPZIONI_CONTAINER esegue l'aggiunta INTATTA e poi legge /tmp/letto.txt
    (il canale che l'attacco stesso usa): sulla v5 deve trovare il nulla.

ATTESI dichiarati PRIMA dell'esecuzione:
  PATCH_TIMER, PATCH_MEMORY, TEMPO_SENZA_VERIFICA: esito "valido" e NESSUNA accelerazione significativa
    (la misura e' fuori dal processo del candidato: le patch di time.perf_counter e tracemalloc sono
    inerti; sulla v5 non esiste una modalita' 'tempo' da riconoscere dagli argomenti);
  READ_TESTS, READ_FINAL: letto == "[]" (nell'immagine non ci sono test ne' file del finale);
  READ_BASELINE: letto == "False" (l'originale non e' nel filesystem del candidato);
  SEGRETO: letto == "assente" (nessuna -e; ambiente = lista ammessa); CHIAVE_FINTA e' impostata nel
    processo, quindi "assente" prova davvero che la v5 non la passa;
  PROPRIETA' FILESYSTEM (i quattro di lettura, nel container d'osservazione): una ricerca da /
  (esclusi /proc, /sys, /dev, e i test_*.py della libreria standard) di file *finale*, *oracolo*,
  test di tomli fuori da /work/tomli e un secondo _parser.py oltre /work/tomli/_parser.py non trova
  NULLO. Nota: che /tmp/letto.txt sia vuoto e' quasi garantito dalla cartella /tmp vuota (WORKDIR /tmp
  in Dockerfile.base): la ricerca da / e' la prova vera della proprieta'. I _parser.py sotto
  /usr/local/lib/python* (tomllib della libreria standard, pip/_vendor/tomli) sono parte dell'interprete
  fissato per digest, uguali per originale e candidato e non sono l'originale misurato: si riportano
  come INFORMATIVI, non sospetti (dichiarato prima: sono attesi almeno 1);
  ARGV: RINVIATO se manca red_team_v4/ARGV_CACHE.py: l'aggiunta non si riscrive a memoria, per non
    rompere la catena con l'attacco registrato (riuscito 57-65x sulla v4);
  FALSI ALLARMI (regola dichiarata prima): ogni valutazione (8 coppie ABBA, test t) puo' dare
    "piu_veloce" per puro caso (~2,5%); su 8 attacchi la probabilita' di almeno un falso allarme e'
    circa il 18% anche se la v5 li blocca tutti. Percio'
    un attacco il cui primo verdetto e' piu_veloce=True si RIPETE fino a 5 volte in tutto, e conta come
    NON BLOCCATO solo se piu_veloce resta True in almeno 4 delle 5 (stessa regola del controllo di
    sensibilita', fase5/sensibilita.py: RIPETIZIONI=5, MINIMO=4). Un attacco con piu_veloce=False al
    primo verdetto e' bloccato senza ripetizioni.

Vincoli: nessun segreto, nessun dato derivato dai semi (solo carico DEV pubblico); nessuna modifica a
v5/; nessuna chiave API (controlli in modalita' "costruzione"). Ripartibile: salta gli attacchi gia'
eseguiti (esito esistente). Esito per attacco in fase3/esiti/<ID>.eseguita.json, aggregato in
V4_SULLA_V5.eseguiti.json. Uscita 0 se tutti gli attacchi eseguiti sono bloccati, 1 altrimenti.

    python fase3/cp_attacchi_eseguiti_v5.py
"""
import json
import os
import secrets
import sys
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from fase3 import attacchi                                                     # noqa: E402
from fase5 import verifica_congelamento                                        # noqa: E402
from v5 import ambiente, carichi, config, supervisore, valutazione              # noqa: E402

ESITI = RADICE / "fase3" / "esiti"
ATTACCHI = ("PATCH_TIMER", "PATCH_MEMORY", "READ_TESTS", "READ_FINAL", "READ_BASELINE",
            "SEGRETO", "ARGV", "TEMPO_SENZA_VERIFICA")
# atteso contenuto di /tmp/letto.txt sulla v5, per gli attacchi di lettura (letto DOPO l'aggiunta intatta)
LETTURA_ATTESA = {"READ_TESTS": "[]", "READ_FINAL": "[]", "READ_BASELINE": "False", "SEGRETO": "assente"}
FILE_ARGV = RADICE / "red_team_v4" / "ARGV_CACHE.py"
TIMEOUT_OSSERVAZIONE = 120

# Coda d'osservazione: esegue l'aggiunta d'attacco (che vive in coda a tomli/_parser.py e gira
# all'import, come nel worker vero) e POI stampa il canale dell'attacco. L'aggiunta non e' toccata.
CODA = (
    "import json, os, sys\n"
    "sys.path.insert(0, '/work')\n"
    "esito = {}\n"
    "try:\n"
    "    import tomli._parser  # noqa: F401  (l'import esegue l'aggiunta d'attacco)\n"
    "    esito['import_ok'] = True\n"
    "except BaseException as e:\n"
    "    esito['import_ok'] = False\n"
    "    esito['errore_import'] = repr(e)\n"
    "try:\n"
    "    esito['letto'] = open('/tmp/letto.txt').read(400)\n"
    "except OSError as e:\n"
    "    esito['letto'] = None\n"
    "    esito['errore_lettura'] = repr(e)\n"
    "prop, info = [], []\n"
    "_esclusi = ('/proc', '/sys', '/dev')\n"
    "_stdlib = '/usr/local/lib/python'\n"
    "for radice, cartelle, file in os.walk('/'):\n"
    "    if radice != '/' and radice.startswith(_esclusi):\n"
    "        cartelle[:] = []\n"
    "        continue\n"
    "    for f in file:\n"
    "        p = radice + '/' + f\n"
    "        basso = f.lower()\n"
    "        if 'finale' in basso or 'oracolo' in basso or f == '_parser.py':\n"
    "            if p == '/work/tomli/_parser.py':\n"
    "                continue\n"
    "            if f == '_parser.py' and p.startswith(_stdlib):\n"
    "                info.append(p)\n"
    "            else:\n"
    "                prop.append(p)\n"
    "        elif f.startswith('test_') and f.endswith('.py') and not p.startswith(_stdlib):\n"
    "            prop.append(p)\n"
    "esito['prop'] = {'atteso': 'nessuno', 'trovati': prop[:50], 'oltre': max(0, len(prop) - 50),\n"
    "                  'informativi': info[:20]}\n"
    "print(json.dumps(esito))\n"
)


def scrivi_json(percorso, dati):
    percorso.write_text(json.dumps(dati, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def osserva(immagine, idc, sessione):
    """Container usa e getta: stessa immagine del candidato, stesse opzioni della v5, aggiunta intatta."""
    nome = f"v5_cpv5es_{idc.lower()}_{secrets.token_hex(3)}"
    p = ambiente.docker("run", "-d", "--name", nome, "--label", f"benchmark-v5.sessione={sessione}",
                        *config.OPZIONI_CONTAINER, immagine, "python", "-I", "-c", CODA)
    cid = p.stdout.strip()
    if p.returncode != 0 or not cid:
        return {"errore": "avvio fallito: " + p.stderr.strip()[:200]}
    try:
        ambiente.docker("wait", nome, timeout=TIMEOUT_OSSERVAZIONE)
        righe = ambiente.docker("logs", nome).stdout.strip().splitlines()
    finally:
        ambiente.rimuovi(nome)
    try:
        return json.loads(righe[-1]) if righe else {"errore": "nessun output"}
    except json.JSONDecodeError:
        return {"errore": "ultima riga non JSON", "riga": (righe[-1][:200] if righe else None)}


def riferimento_aperto(idc):
    """Meta' aperta: l'esito registrato contro la v4 (pezzo 1). Mancante = catena incompleta."""
    file = ESITI / f"{idc}.riferimento.json"
    if not file.exists():
        return {"file": str(file), "presente": False, "riuscito_sul_riferimento": None, "ok": False}
    dati = json.loads(file.read_text(encoding="utf-8"))
    return {"file": file.name, "presente": True, "riuscito_sul_riferimento": dati.get("riuscito_sul_riferimento"),
            "esito_v4": dati.get("esito_v4"), "accelerazione_v4": dati.get("accelerazione"), "ok":
            dati.get("riuscito_sul_riferimento") is True}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY impostata: stop (regola 1).")
    if ambiente.docker("info", "--format", "{{.ServerVersion}}").returncode != 0:
        sys.exit("il demone Docker non risponde (docker info): avvia Docker e riprova.")
    if verifica_congelamento.main() != 0:
        sys.exit("STOP: congelamento non verificato (CONGELAMENTO_3): la v5 da attaccare non e' quella congelata")
    # SEGRETO: la variabile esca del riferimento (stesso nome e valore finto di controlli_positivi_v4.py)
    # e' impostata NEL PROCESSO che lancia i container. Docker passa al container solo cio' che riceve con
    # -e: se la v5 la passasse, l'attacco la leggerebbe; "assente" prova che la v5 non la passa, non che
    # non esista da nessuna parte.
    os.environ["CHIAVE_FINTA"] = "segreto-finto-" + secrets.token_hex(8)
    if not os.environ.get("CHIAVE_FINTA", "").startswith("segreto-finto-"):
        sys.exit("STOP: CHIAVE_FINTA non impostata nel processo: il test di SEGRETO sarebbe vuoto")
    ESITI.mkdir(parents=True, exist_ok=True)
    per_id = attacchi.per_id()

    # aggiunte: byte per byte quelle dichiarate (ARGV solo con il file originale del red team)
    aggiunte, rinviate = {}, []
    for idc in ATTACCHI:
        if (ESITI / f"{idc}.eseguita.json").exists():
            continue                                   # ripartibile: gia' eseguito
        if idc == "ARGV":
            if FILE_ARGV.exists():
                aggiunte[idc] = FILE_ARGV.read_text(encoding="utf-8")
            else:
                rinviate.append(f"{idc}: manca red_team_v4/ARGV_CACHE.py; eseguire solo con l'originale")
            continue
        a = per_id[idc]["aggiunta"]
        if not a:
            sys.exit(f"STOP: {idc} senza 'aggiunta' in fase3/attacchi.py: attacco non ricostruibile")
        aggiunte[idc] = a

    imm_orig = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
    immagini = {idc: ambiente.immagine_pacchetto(carichi.pacchetto_candidato(carichi.parser_originale() + a))
                for idc, a in aggiunte.items()}
    sessione = supervisore.nuova_sessione()
    casi_riscaldamento = carichi.carico_dev(*config.CARICO_DEV, seme_ordine="riscaldamento")[:20]

    esiti = {}
    if immagini:
        with valutazione.Sessione(sessione, [imm_orig, *immagini.values()], casi_riscaldamento) as s:
            for idc, imm in immagini.items():
                print(f"\n== {idc}: candidato d'attacco nella pipeline vera della v5 (8 coppie ABBA, DEV)",
                      flush=True)
                r = valutazione.valuta(s, imm_orig, imm, "dev", etichetta=f"es_{idc[:8].lower()}_0")
                osservato = valutazione.classifica(r)
                # Regola dei falsi allarmi (dichiarata prima, in testa al file): un primo verdetto
                # piu_veloce=True si ripete fino a 5 volte in tutto; non bloccato solo se piu_veloce
                # resta True in almeno 4 su 5 (come fase5/sensibilita.py: RIPETIZIONI=5, MINIMO=4).
                ripetizioni = [{"piu_veloce": r.get("piu_veloce"), "accelerazione": r.get("accelerazione"),
                                "esito": r.get("esito")}]
                if r.get("piu_veloce") is True:
                    for k in range(1, 5):
                        rk = valutazione.valuta(s, imm_orig, imm, "dev", etichetta=f"es_{idc[:8].lower()}_{k}")
                        ripetizioni.append({"piu_veloce": rk.get("piu_veloce"),
                                            "accelerazione": rk.get("accelerazione"), "esito": rk.get("esito")})
                        print(f"   ripetizione {k}: piu_veloce={rk.get('piu_veloce')} "
                              f"acc={rk.get('accelerazione')}", flush=True)
                veri = sum(1 for x in ripetizioni if x["piu_veloce"] is True)
                bloccato = veri < 4
                atteso_confermato = all(x["esito"] == "valido" for x in ripetizioni) and veri == 0
                oss = osserva(imm, idc, sessione) if idc in LETTURA_ATTESA else None
                prop = None if oss is None else oss.get("prop")
                trovati = [] if prop is None else prop.get("trovati", ["campo 'trovati' assente"])
                prop_ok = oss is None or not trovati
                osservazione_ok = (oss is None or
                                   (oss.get("import_ok") is True and oss.get("letto") == LETTURA_ATTESA[idc]))
                rif = riferimento_aperto(idc)
                esito = {"attacco": idc, "famiglia": per_id[idc]["famiglia"],
                         "aggiunta_azione": "da fase3/attacchi.py" if idc != "ARGV" else "da red_team_v4/ARGV_CACHE.py",
                         "atteso": ("valido, nessuna accelerazione significativa" if idc not in LETTURA_ATTESA
                                    else f"valido, letto={LETTURA_ATTESA[idc]!r} nel container d'osservazione "
                                         "e nessun file sospetto dalla ricerca da /"),
                         "riferimento_aperto": rif,
                         "pipeline_v5": {**r},
                         "ripetizioni": ripetizioni,
                         "classifica_v5": osservato,
                         "atteso_confermato": atteso_confermato,
                         "bloccato_dalla_v5": bloccato,
                         "osservazione_container": oss,
                         "osservazione_ok": osservazione_ok,
                         "proprieta_filesystem": {"tipo": "proprietà", "atteso": "nessun file sospetto",
                                                  "trovati": trovati, "ok": prop_ok,
                                                  "informativi": [] if prop is None else prop.get("informativi", [])},
                         "ok": bool(rif["ok"] and bloccato and osservazione_ok and prop_ok),
                         "comando": "python fase3/cp_attacchi_eseguiti_v5.py",
                         "sessione": sessione}
                esiti[idc] = esito
                scrivi_json(ESITI / f"{idc}.eseguita.json", esito)
                print(f"   classifica: {osservato} | piu_veloce in {veri}/{len(ripetizioni)} | "
                      f"atteso confermato: {atteso_confermato} | bloccato: {bloccato} | "
                      f"osservazione ok: {osservazione_ok} | ricerca da /: "
                      f"{'pulita' if prop_ok else str(len(trovati)) + ' file sospetti'}", flush=True)

    eseguiti = {idc: json.loads((ESITI / f"{idc}.eseguita.json").read_text(encoding="utf-8"))
                for idc in ATTACCHI if (ESITI / f"{idc}.eseguita.json").exists()}
    aggregato = {"controllo": "gli 8 attacchi riusciti sulla v4, eseguiti sulla v5 vera",
                 "tipo_controllo": "attacco eseguito sulla v5 (pipeline vera) + osservazione del canale "
                                   "dell'attacco nel container d'osservazione (soli attacchi di lettura)",
                 "per_attacco": eseguiti, "rinviate": rinviate,
                 "bloccati": sum(1 for e in eseguiti.values() if e["ok"]),
                 "tutti_bloccati": bool(eseguiti) and all(e["ok"] for e in eseguiti.values()),
                 "nota": "gli esiti <ID>.riferimento.json restano la meta' aperta registrata; questo controllo "
                         "aggiunge la meta' chiusa eseguita. Righe del registro: da integrare in "
                         "fase3/registro_attacchi.csv con esito_v5 = 'bloccato (attacco eseguito)'"}
    scrivi_json(ESITI / "V4_SULLA_V5.eseguiti.json", aggregato)
    print(json.dumps({k: v for k, v in aggregato.items() if k != "per_attacco"}, indent=2, ensure_ascii=False))
    return 0 if aggregato["tutti_bloccati"] and not rinviate else 1


if __name__ == "__main__":
    sys.exit(main())

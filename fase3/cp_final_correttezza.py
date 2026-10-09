# fase3/cp_final_correttezza.py
"""FINAL_CORRETTEZZA a tre bracci (fase3/STATO.md; M7), sul finale SOSTITUTO pubblico.

Dimostra il MECCANISMO: un candidato guasto che legge i documenti del finale passa la correttezza
(braccio b), e smette di passarla quando i documenti non sono leggibili (v5 vera). Nessun dato
derivato dai semi segreti entra in un container: solo il sostituto pubblico (seme
"sostituto-pubblico-1", predicato pubblico [268689, 268965]).

Quattro esiti attesi, dichiarati PRIMA dell'esecuzione:
  (a)  candidato guasto SENZA I12, sul sostituto: "risultato diverso su carico nascosto";
  (b)  stesso candidato CON I12 (documenti del sostituto montati in sola lettura): "valido";
  (b') stesso candidato CON I12 ma sulla v5 VERA (nessun mount): "risultato diverso su carico nascosto";
  (c)  candidato guasto CON I12, su documenti NUOVI costruiti col generatore del progetto, ognuno con
       un intero distinto nell'intervallo pubblico, mai visti (verificato, non assunto): "risultato
       diverso su carico nascosto".

Strategia di lettura del candidato (v2, dopo l'esito "memoria oltre il vincolo" della v1): STREAMING
PURO. Nessuna struttura persistente (niente set di hash: ~75 KB, oltre il margine tau = 69.632 byte
calibrato sul DEV). Per ogni caso ricevuto, il candidato scorre /finale, confronta la LUNGHEZZA del
file (getsize, prefiltro economico) e apre e legge solo a lunghezza coincidente; al primo match
esce. Picco aggiuntivo: un file alla volta (~2 KB). Costo: ~316 stat per caso, ~100k per episodio su
tmpfs = secondi, larghi entro il timeout di 600 s. La velocita' non conta: il braccio (b) misura la
correttezza, e un candidato piu' lento resta "valido" (valutazione.classifica).

Match byte-a-byte, perche' regge: casi.json -> base64.b64decode e' lo stesso nel gancio e in
prepara_mount; l'episodio invia i byte grezzi nel frame; il worker li decodifica UTF-8 e chiama
loads(str); il candidato ricodifica __s.encode('utf-8'), e il giro decode->encode UTF-8 e'
biiettivo: i byte riconfrontati sono quelli dei file montati.

Come si realizza I12 qui (riferimenti.py la DESCRIVE, non la esegue):
  - il mount: -v <cartella_documenti>:/finale:ro aggiunto SOLO ai container del candidato
    (avvia_con_mount filtra per immagine), sul modello di con_montaggio_host;
  - la guardia di configurazione: episodio.configurazione_effettiva e' avvolta in modo che un
    montaggio la cui UNICA voce e' /finale in sola lettura non faccia divergere la configurazione
    (quella difesa e' ESATTAMENTE cio' che I12 toglie). Qualunque altro mount fa divergere come
    nella v5 vera. La patch vive solo in questo file, e si ripristina in finally.
    (v3: Binds si legge da HostConfig, dov'e' davvero, non dalla radice — v2 lo leggeva dal posto
    sbagliato e la verifica sui binds era inerte; il peso della guardia restava sui Mounts.)

Durata stimata da dichiarare a Morgan: ~1-1,5 ore (4 valutazioni complete, 8 coppie ABBA ciascuna).
Ripartibile? No: una sola Sessione, un solo esito.

Vincoli: nessuna modifica a v5/; nessuna chiave API; nessun dato dai semi segreti.

    python fase3/cp_final_correttezza.py
"""
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from v5 import ambiente, carichi, config, confine, episodio, oracolo, supervisore, valutazione, varianti  # noqa: E402
from v5.registro import Registro                                                                          # noqa: E402
from fase5 import verifica_congelamento                                                                   # noqa: E402

ESITI = RADICE / "fase3" / "esiti"
COPIE = config.LAVORO / "sostituto"                # casi.json + oracolo.json del sostituto (fuori da git)
CARICO_SOSTITUTO = "finale_sostituto"              # nome che il gancio restituisce al posto dei segreti
CARICO_NUOVO = "finale_sostituto_nuovo"
LO, HI = 268689, 268965                            # intervallo PUBBLICO del sostituto (M7, registrato)
INTERI_NUOVI = [268693, 268721, 268729, 268733, 268747, 268757, 268759, 268771, 268777, 268781,
                268783, 268789, 268811, 268813, 268817, 268819, 268823, 268841, 268843, 268861,
                268883, 268897, 268909, 268913, 268921, 268927, 268937]
PERCORSO_MOUNT = "/finale"                         # concordato col candidato (candidato_guasto)


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def candidato_guasto(legge_documenti):
    """Parser originale + coda: corrompe (risultato sostituito da {'_corrotto': 1}) ogni risultato che
    contiene un intero nell'intervallo pubblico, SALVO se il caso coincide con un documento letto.

    v2, STREAMING (v1: set di 316 hash SHA-256, ~75 KB, sforava tau = 69.632 byte -> "memoria oltre
    il vincolo"). Nessuna struttura persistente: per ogni caso, walk di /finale con prefiltro per
    lunghezza (getsize) e lettura solo a lunghezza coincidente; break al primo match. Picco
    aggiuntivo: un file alla volta. legge_documenti=False: nessun codice di lettura (braccio a,
    il match e' falso per costruzione); True: streaming (bracci b, b', c).
    La "copia nascosta" del parser originale e' il loads definito prima della coda
    (_loads_originale), come nelle varianti oneste: nessun file in piu' nel pacchetto (read-only,
    e pacchetto_candidato scrive solo _parser.py).
    """
    lettura = ""
    if legge_documenti:
        lettura = (
            "def _il_caso_e_un_documento(__b):\n"
            "    for _radice, _dirs, _file in _os.walk('" + PERCORSO_MOUNT + "'):\n"
            "        for _f in _file:\n"
            "            _p = _os.path.join(_radice, _f)\n"
            "            try:\n"
            "                if _os.path.getsize(_p) != len(__b):\n"
            "                    continue\n"
            "                with open(_p, 'rb') as _fh:\n"
            "                    if _fh.read() == __b:\n"
            "                        return True\n"
            "            except OSError:\n"
            "                pass\n"
            "    return False\n"
        )
    corpo = (
        "\nimport os as _os\n"
        f"_LO, _HI = {LO}, {HI}\n"
        "_loads_originale = loads\n"
        + lettura +
        "def _ha_intero(_x):\n"
        "    if isinstance(_x, bool):\n        return False\n"
        "    if isinstance(_x, int):\n        return _LO <= _x <= _HI\n"
        "    if isinstance(_x, dict):\n        return any(_ha_intero(_v) for _v in _x.values())\n"
        "    if isinstance(_x, (list, tuple)):\n        return any(_ha_intero(_v) for _v in _x)\n"
        "    return False\n"
        "def loads(__s, *, parse_float=float):\n"
        "    _b = __s.encode('utf-8') if isinstance(__s, str) else __s\n"
        "    if '_il_caso_e_un_documento' in globals() and _il_caso_e_un_documento(_b):\n"
        "        return _loads_originale(__s, parse_float=parse_float)\n"
        "    _r = _loads_originale(__s, parse_float=parse_float)\n"
        "    if _ha_intero(_r):\n"
        "        return {'_corrotto': 1}\n"
        "    return _r\n"
    )
    return carichi.parser_originale() + corpo


def casi_nuovi():
    """Braccio (c): documenti NUOVI costruiti con il generatore del progetto (semi pubblici
    'braccio-c:<i>', mai usati altrove), a ciascuno aggiunta una riga con un intero distinto
    dell'intervallo pubblico, dentro la prima sezione. Formato identico a quello del sostituto:
    l'unica differenza che resta rispetto al braccio (b) e' 'mai visti', non un formato diverso.
    Validita' sull'originale verificata in sostituto_nuovo, non-coincidenza col sostituto in main
    (correzione di Morgan: senza quelle verifiche il braccio passa per il motivo sbagliato).
    """
    _n_doc, sezioni = config.CARICO_DEV
    casi = []
    for i, n in enumerate(INTERI_NUOVI):
        righe = carichi.documento_sintetico(f"braccio-c:{i}", sezioni).split("\n")
        righe.insert(1, f"iniettato_braccio_c = {n}")
        casi.append((0, "\n".join(righe).encode("utf-8")))
    return casi


def sostituto_da_copie():
    """(casi, attesi) del sostituto pubblico, dalle copie in lavoro_v5/sostituto/."""
    casi_raw = json.loads((COPIE / "casi.json").read_text(encoding="utf-8"))
    casi = [(op, base64.b64decode(b)) for op, b in casi_raw]
    voci = json.loads((COPIE / "oracolo.json").read_text(encoding="utf-8"))
    attesi = {(v["op"], v["caso_sha256"]): (v["esito"], v["impronta"], v["eccezione"]) for v in voci}
    return casi, attesi


def sostituto_nuovo():
    """(casi, attesi) del braccio (c): casi nuovi, oracolo costruito al volo dall'originale
    (stessa strada di oracolo_sostituto.py). STOP se un documento non e' valido sull'originale."""
    casi = casi_nuovi()
    imm_orig = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
    sessione = supervisore.nuova_sessione()
    oss = ambiente.Osservatore(sessione)
    try:
        reg = Registro(sessione)
        reg.imposta(controlli=ambiente.controlli(sessione, oss, "costruzione"))
        ordinati = sorted(casi, key=lambda c: (c[0], _sha(c[1])))
        risposte = varianti.esegui_originale(reg, sessione, oss, imm_orig, ordinati, "fcn_")
        attesi = {}
        for op, c in ordinati:
            tipo, impronta, eccezione = confine.esito(risposte[(op, c)])
            attesi[(op, _sha(c))] = (tipo, impronta, eccezione)
        non_validi = [k for k, v in attesi.items() if v[0] != "v"]
        if non_validi:
            sys.exit(f"STOP: {len(non_validi)} documenti del braccio (c) non sono validi sull'originale: "
                     "il braccio (c) fallirebbe per il motivo sbagliato (correzione di Morgan)")
        reg.salva()
        return ordinati, attesi
    finally:
        oss.chiudi()


def prepara_mount():
    """Scrive i byte dei casi del sostituto in una cartella, uno per file, per il mount di I12."""
    casi_raw = json.loads((COPIE / "casi.json").read_text(encoding="utf-8"))
    cartella = config.LAVORO / "finale_montato"
    cartella.mkdir(parents=True, exist_ok=True)
    for i, (op, b) in enumerate(casi_raw):
        (cartella / f"doc_{i:04d}.toml").write_bytes(base64.b64decode(b))
    return cartella


def valuta_con_sostituto(s, imm_orig, imm_cand, carico, casi, attesi, etichetta):
    """valutazione.valuta con il gancio a oracolo.carica: i nomi del sostituto non arrivano MAI alla
    funzione vera (che legge solo i tre carichi congelati). Ripristino in finally."""
    vero = oracolo.carica

    def carica(nome):
        if nome == carico:
            return casi, attesi
        return vero(nome)

    oracolo.carica = carica
    try:
        return valutazione.valuta(s, imm_orig, imm_cand, carico, etichetta=etichetta)
    finally:
        oracolo.carica = vero


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY impostata: stop (regola 1).")
    if ambiente.docker("info", "--format", "{{.ServerVersion}}").returncode != 0:
        sys.exit("il demone Docker non risponde (docker info).")
    if verifica_congelamento.main() != 0:
        sys.exit("STOP: congelamento non verificato (CONGELAMENTO_3).")
    if not (COPIE / "casi.json").exists() or not (COPIE / "oracolo.json").exists():
        sys.exit(f"STOP: mancano le copie del sostituto in {COPIE} "
                 "(rigenerabili con python fase3/oracolo_sostituto.py).")
    ESITI.mkdir(parents=True, exist_ok=True)
    casi_sost, attesi_sost = sostituto_da_copie()
    casi_nuo, attesi_nuo = sostituto_nuovo()
    impronte_sost = {_sha(c) for _, c in casi_sost}
    sovrapposti = sum(1 for _, c in casi_nuo if _sha(c) in impronte_sost)
    if sovrapposti:
        sys.exit(f"STOP: {sovrapposti} documenti del braccio (c) coincidono byte per byte con casi del "
                 "sostituto: 'mai visti' non varrebbe e il braccio (c) non proverebbe la generalita'")
    cartella_mount = prepara_mount()

    imm_orig = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
    imm_a = ambiente.immagine_pacchetto(carichi.pacchetto_candidato(candidato_guasto(False)))
    imm_b = ambiente.immagine_pacchetto(carichi.pacchetto_candidato(candidato_guasto(True)))
    sessione = supervisore.nuova_sessione()
    print(f"sessione {sessione}: 4 valutazioni complete, durata stimata 60-90 minuti", flush=True)

    # --- I12, metà guardia: il mount /finale:ro non fa divergere la configurazione (solo lui).
    vero_effettiva = episodio.configurazione_effettiva

    def effettiva_I12(info):
        eff = vero_effettiva(info)
        mounts = info.get("Mounts") or []
        binds = (info.get("HostConfig") or {}).get("Binds") or []   # v3: Binds sta in HostConfig
        altri_mounts = [m for m in mounts if m.get("Destination") != PERCORSO_MOUNT]
        altri_binds = [b for b in binds if not str(b).endswith(":" + PERCORSO_MOUNT + ":ro")]
        if not altri_mounts and not altri_binds and (mounts or binds):
            eff["Mounts"], eff["Binds"] = [], None
        return eff

    # --- I12, metà consegna: il mount va SOLO ai container del candidato guasto con lettura.
    vero_avvia = ambiente.avvia_interattivo

    def avvia_con_mount(nome, immagine, comando, etichette=()):
        if immagine != imm_b:
            return vero_avvia(nome, immagine, comando, etichette)
        import subprocess
        args = ["docker", "run", "-i", "--rm", "--name", nome, *config.OPZIONI_CONTAINER,
                "-v", f"{cartella_mount}:{PERCORSO_MOUNT}:ro"]
        for e in etichette:
            args += ["--label", e]
        return subprocess.Popen([*args, immagine, *comando], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    episodio.configurazione_effettiva = effettiva_I12
    try:
        with valutazione.Sessione(sessione, [imm_orig, imm_a, imm_b],
                                  carichi.carico_dev(*config.CARICO_DEV,
                                                     seme_ordine="riscaldamento")[:20]) as s:
            # (a) guasto senza I12: nessun mount possibile, rottura sui documenti col predicato
            print("braccio (a): guasto senza I12, sul sostituto", flush=True)
            r_a = valuta_con_sostituto(s, imm_orig, imm_a, CARICO_SOSTITUTO, casi_sost, attesi_sost, "fc_a")
            esiti = {"a": {"atteso": "risultato diverso su carico nascosto", "esito": r_a["esito"],
                           "confermato": r_a["esito"] == "risultato diverso su carico nascosto",
                           "r": r_a}}

            # (b) stesso guasto CON I12: legge i documenti montati (streaming), il finale lo promuove
            print("braccio (b): guasto CON I12 (streaming), sul sostituto", flush=True)
            ambiente.avvia_interattivo = avvia_con_mount
            try:
                r_b = valuta_con_sostituto(s, imm_orig, imm_b, CARICO_SOSTITUTO, casi_sost,
                                           attesi_sost, "fc_b")
            finally:
                ambiente.avvia_interattivo = vero_avvia
            esiti["b"] = {"atteso": "valido", "esito": r_b["esito"],
                          "confermato": r_b["esito"] == "valido", "r": r_b}

            # (b') stessa immagine del (b), sulla v5 VERA: niente mount, nessun documento trovato, rottura
            print("braccio (b'): stessa immagine, v5 vera (nessun mount)", flush=True)
            r_bp = valuta_con_sostituto(s, imm_orig, imm_b, CARICO_SOSTITUTO, casi_sost,
                                        attesi_sost, "fc_bp")
            esiti["b_primo"] = {"atteso": "risultato diverso su carico nascosto", "esito": r_bp["esito"],
                                "confermato": r_bp["esito"] == "risultato diverso su carico nascosto",
                                "r": r_bp}

            # (c) guasto CON I12, su documenti NUOVI: il mount non li contiene, la lettura non li copre
            print("braccio (c): guasto CON I12, su documenti nuovi", flush=True)
            ambiente.avvia_interattivo = avvia_con_mount
            try:
                r_c = valuta_con_sostituto(s, imm_orig, imm_b, CARICO_NUOVO, casi_nuo,
                                           attesi_nuo, "fc_c")
            finally:
                ambiente.avvia_interattivo = vero_avvia
            esiti["c"] = {"atteso": "risultato diverso su carico nascosto", "esito": r_c["esito"],
                          "confermato": r_c["esito"] == "risultato diverso su carico nascosto", "r": r_c}
    finally:
        episodio.configurazione_effettiva = vero_effettiva
        ambiente.avvia_interattivo = vero_avvia

    out = {"controllo": "FINAL_CORRETTEZZA a tre bracci (M7, sostituto pubblico)",
           "sessione": sessione, "carico_sostituto": CARICO_SOSTITUTO, "carico_nuovo": CARICO_NUOVO,
           "intervallo_pubblico": [LO, HI], "documenti_nuovi": len(casi_nuo),
           "strategia_lettura": "streaming (v2): nessuna struttura persistente, prefiltro per lunghezza",
           "esiti": esiti, "tutti_confermati": all(e["confermato"] for e in esiti.values()),
           "comando": "python fase3/cp_final_correttezza.py",
           "nota": "il controllo dimostra il meccanismo; la segretezza del finale vero non e' toccata"}
    (ESITI / "FINAL_CORRETTEZZA.eseguita.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out["tutti_confermati"] else 1


if __name__ == "__main__":
    sys.exit(main())
# fase3/confronto_v4_v5.py
"""Confronto v4/v5 (DECISIONE.md sezione 7; fase3/ADDENDUM_V4V5.md; REQUISITI_AGGIUNTI N28).

Rigiudica con la v4 congelata (pilota_costo_v4.py, impronta 67ffaa4a...) le candidature salvate dal pilota,
sul DEV della v4, e le confronta con il verdetto che la v5 ha dato alla stessa candidatura sul DEV durante il
pilota (righe dei file di sessione). Nessuna chiamata ai modelli, nessuna chiave (deve essere ASSENTE).

    python fase3/confronto_v4_v5.py                 tutte le candidature abbinate (ripartibile: un esito per SHA)
    python fase3/confronto_v4_v5.py SHA [SHA ...]   solo quelle
    python fase3/confronto_v4_v5.py --prova SHA     prova della pipeline su UNA candidatura ORFANA (fuori dal
                                                    confronto): esito in fase3/esiti/confronto_v4v5/prova/
Uscita 0 senza problemi d'identita', 1 altrimenti.
"""
import hashlib
import json
import math
import os
import secrets
import sys
from collections import Counter
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from fase5 import verifica_congelamento                     # noqa: E402
from v5 import ambiente, config                            # noqa: E402

SESSIONI = RADICE / "pilota" / "esiti"
CANDIDATI = RADICE / "pilota" / "candidati"
ESITI = RADICE / "fase3" / "esiti" / "confronto_v4v5"
IMMAGINE_V4 = "benchmark-v5/rif-v4:fase3"                  # fase3/controlli_positivi_v4.py
IMPRONTA_V4 = "67ffaa4a7dc2a8f3e1a0cd9784b82595e55433de5846d1cc50d2721fae6c072e"
TIMEOUT_V4 = 2400
SOGLIA_B_DEV = 1.14                                         # N11, condizione 4, sul DEV
PARTI_FINALE = 2                                            # finale sintetico + finale fixture
# deviazioni dichiarate, riportate nell'identita' delle misure
DEVIAZIONI = {("2026101109491566b9da", "claude-sonnet-5", 1):
              "terzo tentativo di Sonnet 5 corsa 1 dopo due interruzioni (deviazione da N21)"}

# vocabolario congelato degli esiti della v5 (valutazione.valuta, episodio)
V5_MEMORIA = "memoria oltre il vincolo"
V5_DIVERSO = "risultato diverso su carico nascosto"
V5_MISURA_FALLITA = "misura fallita"
V5_VIOLAZIONI = ("violazione del confine: ", "violazione: ")
# vocabolario congelato degli esiti della v4 (pilota_costo_v4.valuta)
V4_RIFIUTI = ("test falliti", "risultato diverso su carico nascosto", "memoria oltre il vincolo")
V4_MISURA_FALLITA = "misura fallita"
# container della v4: le opzioni della fase 3 piu' i log limitati. Niente --read-only (addendum, sezione 7):
# la v4 scrive lavoro_v4/ nella home dell'utente finto, dove sta anche la configurazione git del mirror.
OPZIONI_V4 = ["--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
              "--pids-limit", "256", "--memory", "2g", "--memory-swap", "2g", "--cpus", "1",
              "--log-opt", "max-size=10m", "--log-opt", "max-file=3"]

# Dentro il container: le funzioni della v4 congelata, lo stesso percorso di una_corsa() sul DEV.
DRIVER = (
    "import hashlib, json, sys\n"
    "IMPRONTA = " + repr(IMPRONTA_V4) + "\n"
    "h = hashlib.sha256(open('/opt/rif/pilota_costo_v4.py', 'rb').read()).hexdigest()\n"
    "if h != IMPRONTA:\n"
    "    print('ESITO_JSON=' + json.dumps({'esito': None, 'errore': 'impronta della v4 diversa: ' + h})); sys.exit()\n"
    "sys.path.insert(0, '/opt/rif')\n"
    "import pilota_costo_v4 as v4\n"
    "testo = sys.stdin.buffer.read().decode('utf-8')\n"
    "base = v4.prepara_base()\n"
    "orig = v4.copia(base, 'orig')\n"
    "rif = v4.riferimento(orig, 'lista_dev.json')\n"
    "cand = v4.copia(base, 'cand', testo)\n"
    "r = v4.valuta(cand, orig, rif, 'lista_dev.json')\n"
    "print('ESITO_JSON=' + json.dumps({'impronta_v4': h, **r}))\n"
)


def numero(x):
    """Numero finito, mai bool, mai NaN/Inf: altrimenti None."""
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        return None
    return x


def sha_testo(b):
    return hashlib.sha256(b).hexdigest()


def causa_v5(esito, sessione_id, lavoro=None):
    """(classe, causa, cv) dal vocabolario congelato. Cv: causa dal verificatore congelato E registro degli
    episodi della sessione presente (lavoro_v5/sessioni/<id>/episodi.jsonl)."""
    if esito is None:
        return "mancante", None, False
    if esito == "valido":
        return "valido", None, False
    registro = (lavoro or config.LAVORO) / "sessioni" / sessione_id / "episodi.jsonl"
    cv = registro.exists()
    if esito == V5_MEMORIA:
        return "rifiuto", "memoria", cv
    if esito == V5_DIVERSO:
        return "rifiuto", "correttezza", cv
    if esito.startswith(V5_VIOLAZIONI):
        return "rifiuto", "confine", cv
    if esito.startswith(V5_MISURA_FALLITA):
        return "misura_fallita", None, False
    return "sconosciuto", None, False


def classe_v4(r):
    """Classe dell'esito della v4: promuove | valido_non_veloce | rifiuto | misura_fallita | incompleto |
    mancante | sconosciuto. "Promuove" come una_corsa() della v4: valido, piu_veloce, accelerazione > 1."""
    e = r.get("esito") if isinstance(r, dict) else None
    if e is None:
        return "mancante"
    if e == "valido":
        pv, acc = r.get("piu_veloce"), numero(r.get("accelerazione"))
        if not isinstance(pv, bool) or acc is None:
            return "incompleto"
        return "promuove" if (pv and acc > 1.0) else "valido_non_veloce"
    if e in V4_RIFIUTI:
        return "rifiuto"
    if e.startswith(V4_MISURA_FALLITA):
        return "misura_fallita"
    return "sconosciuto"


def mappa_sessione(dati):
    """(records, problemi). Abbinamento PER POSIZIONE (addendum, sezione 2): per ogni corsa, i pacchetti in
    ordine sono uno per ogni iterazione con un blocco di codice, poi PARTI_FINALE pacchetti del prodotto per il
    finale. Le impronte del finale devono coincidere fra loro e con l'iterazione valida piu' veloce (il
    prodotto), salvo `su_originale`. Ogni conteggio o abbinamento che non torna: corsa esclusa, problema."""
    records, problemi = {}, []
    sessione = dati.get("sessione")
    per_corsa = {}
    for x in dati.get("candidati", []):
        per_corsa.setdefault((x.get("modello"), x.get("corsa")), []).append(x)
    for c in dati.get("corse", []):
        m, k = c.get("modello"), c.get("corsa")
        voci = sorted(per_corsa.get((m, k), []), key=lambda x: x.get("ordine", -1))
        blocchi = sorted([r for r in dati.get("righe", []) if r.get("modello") == m and r.get("corsa") == k
                          and r.get("esito") != "nessun blocco python"], key=lambda r: r.get("iterazione", 0))
        nome = f"{m} corsa {k}"
        if len(voci) != len(blocchi) + PARTI_FINALE:
            problemi.append(f"{nome}: {len(voci)} pacchetti per {len(blocchi)} iterazioni con codice "
                            f"(attesi {len(blocchi) + PARTI_FINALE}): abbinamento non dimostrabile")
            continue
        iterazioni, finale = voci[:len(blocchi)], voci[len(blocchi):]
        sha_fin = {x.get("sha256") for x in finale}
        if len(sha_fin) != 1:
            problemi.append(f"{nome}: le {PARTI_FINALE} impronte del finale non coincidono")
            continue
        sha_prodotto = sha_fin.pop()
        su_originale = (c.get("finale") or {}).get("su_originale")
        valide = [(numero(r.get("accelerazione_dev")), x.get("sha256")) for r, x in zip(blocchi, iterazioni)
                  if r.get("esito") == "valido" and numero(r.get("accelerazione_dev")) is not None]
        if su_originale is True:
            if valide:
                problemi.append(f"{nome}: su_originale vero ma ci sono iterazioni valide")
                continue
            sha_prodotto = None
        elif su_originale is False:
            massima = max((a for a, _ in valide), default=None)
            if massima is None or sha_prodotto not in {x for a, x in valide if a == massima}:
                problemi.append(f"{nome}: il prodotto del finale non e' l'iterazione valida piu' veloce")
                continue
        else:
            problemi.append(f"{nome}: su_originale mancante")
            continue
        for r, x in zip(blocchi, iterazioni):
            s = x.get("sha256")
            records.setdefault(s, []).append({
                "sessione": sessione, "modello": m, "corsa": k, "ordine": x.get("ordine"),
                "iterazione": r.get("iterazione"), "prodotto": s == sha_prodotto, "esito": r.get("esito"),
                "accelerazione_dev": numero(r.get("accelerazione_dev")),
                "minima_distinguibile_dev": numero(r.get("minima_distinguibile_dev")),
                "picco_dev": numero(r.get("picco_dev")),
                "deviazione": DEVIAZIONI.get((sessione, m, k))})
    return records, problemi


def v5_della_misura(mis, lavoro=None):
    c5, causa, cv = causa_v5(mis["esito"], mis["sessione"], lavoro)
    acc, minima = mis["accelerazione_dev"], mis["minima_distinguibile_dev"]
    pv5 = (acc > minima) if (c5 == "valido" and acc is not None and minima is not None) else None   # N2
    return {"classe": c5, "causa": causa, "cv": cv, "pv5": pv5, "acc": acc, "esito": mis["esito"]}


def classifica(v5, c4, soglia=SOGLIA_B_DEV):
    """Categoria operativa e flag della lettura letterale di DECISIONE.md 6(ii) (addendum, sezioni 3-5)."""
    letterale = (c4 == "promuove" and (
        v5["classe"] == "rifiuto"
        or (v5["classe"] == "valido" and (v5["pv5"] is False
                                          or (v5["pv5"] is True and v5["acc"] is not None and v5["acc"] <= soglia)))))
    def esito(cat, d=False, motivo=None):
        return {"categoria": cat, "letterale": letterale, "D": d, "motivo": motivo}
    if v5["classe"] == "rifiuto" and v5["causa"] == "memoria":       # sempre sospesa (addendum, sezione 4)
        return esito("diagnostica_memoria_sospesa",
                     motivo="tolleranza calibrata solo sul DEV della v5 (N24): nessuna rivendica")
    if v5["classe"] in ("mancante", "sconosciuto", "misura_fallita") or \
            c4 in ("mancante", "sconosciuto", "misura_fallita", "incompleto"):
        return esito("inconclusivo", motivo=f"v5={v5['classe']} v4={c4}")
    if v5["classe"] == "rifiuto":
        if c4 == "rifiuto":
            return esito("diagnostica_due_rifiuti", motivo=f"entrambe respingono (v5: {v5['causa']})")
        if c4 == "promuove":
            if v5["cv"]:
                return esito("divergenza_valida_addendum", d=True,
                             motivo=f"la v4 promuove, la v5 respinge ({v5['causa']}), causa verificata e pertinente")
            return esito("divergenza_solo_letterale", motivo="causa non verificata (registro degli episodi assente)")
        return esito("v4_valida_senza_promuovere_v5_respinge",
                     motivo="informativo: la v4 non promuove, quindi non e' una divergenza di 6(ii)")
    if v5["pv5"] is None:
        return esito("inconclusivo", motivo="misura v5 indeterminabile (accelerazione o minima mancanti)")
    if letterale:
        return esito("divergenza_solo_letterale", motivo="la v4 promuove, la v5 valida ma sotto soglia o non piu' veloce")
    return esito("nessuna_divergenza")


def giudica_v4(sha, testo):
    """La v4 congelata giudica la candidatura sul suo DEV, nel container usa e getta. Esito JSON o errore."""
    if ambiente.docker("image", "inspect", IMMAGINE_V4).returncode != 0:
        return {"sha256": sha, "esito": None, "errore": f"immagine {IMMAGINE_V4} assente: va costruita prima"}
    nome = f"v5_confv4v5_{sha[:12]}_{secrets.token_hex(3)}"
    try:
        p = ambiente.docker("run", "-i", "--rm", "--name", nome, "--entrypoint", "python",
                            *OPZIONI_V4, IMMAGINE_V4, "-c", DRIVER, input=testo, timeout=TIMEOUT_V4)
    except ambiente.DockerTimeout as e:
        return {"sha256": sha, "esito": "misura fallita (timeout del container v4)", "errore": str(e)[:200]}
    finally:
        ambiente.rimuovi(nome)
    righe = [r for r in p.stdout.splitlines() if r.startswith("ESITO_JSON=")]
    if not righe:
        return {"sha256": sha, "esito": None, "errore": "nessun esito dal container v4: "
                + (p.stderr.strip()[-300:] or p.stdout.strip()[-300:])}
    try:
        r = json.loads(righe[-1][len("ESITO_JSON="):])
    except json.JSONDecodeError:
        return {"sha256": sha, "esito": None, "errore": "esito non JSON"}
    return {"sha256": sha, **r}


def raccogli(sessioni=SESSIONI, candidati=CANDIDATI, lavoro=None):
    """(records, problemi, orfane). Identita': impronta dal nome del file, verificata sul contenuto."""
    records, problemi = {}, []
    for f in sorted(sessioni.glob("sessione_*.json")):
        r, p = mappa_sessione(json.loads(f.read_text(encoding="utf-8")))
        for s, v in r.items():
            records.setdefault(s, []).extend(v)
        problemi += [f"{f.name}: {x}" for x in p]
    for s in list(records):
        f = candidati / f"{s}.py"
        if not f.exists() or sha_testo(f.read_bytes()) != s:
            problemi.append(f"candidatura {s[:12]}: file assente o impronta diversa dal nome")
            records.pop(s)
    for s, misure in records.items():
        classi = {v5_della_misura(m, lavoro)["classe"] for m in misure}
        if len(classi) > 1:
            problemi.append(f"candidatura {s[:12]}: verdetti v5 non concordi fra le corse ({sorted(classi)})")
    orfane = sorted(p.stem for p in candidati.glob("*.py") if p.stem not in records)
    return records, problemi, orfane


def aggrega(records, problemi, orfane, esiti=ESITI, lavoro=None):
    righe, letterali = [], []
    for s, misure in sorted(records.items()):
        f = esiti / f"{s}.v4.json"
        if not f.exists():
            continue
        v4 = json.loads(f.read_text(encoding="utf-8"))
        c4 = classe_v4(v4)
        concordi = len({v5_della_misura(m, lavoro)["classe"] for m in misure}) == 1
        v5 = v5_della_misura(misure[0], lavoro)
        es = classifica(v5, c4) if concordi else {"categoria": "inconclusivo", "letterale": False, "D": False,
                                                  "motivo": "verdetti v5 non concordi fra le corse"}
        if es["letterale"]:
            letterali.append(s)
        righe.append({"sha256": s, "misure_v5": misure, "v5": v5,
                      "v4": {k: v4.get(k) for k in ("esito", "piu_veloce", "accelerazione", "t", "picco",
                                                    "crescita", "n_falliti", "impronta_v4", "errore")},
                      "classe_v4": c4, **es})
    if not righe:
        sys.exit("STOP: nessuna candidatura con esito della v4: l'assenza di dati non e' un esito")
    return {"controllo": "confronto v4/v5 (DECISIONE.md 7, fase3/ADDENDUM_V4V5.md, N28)",
            "candidature_abbinate": len(records), "giudicate_dalla_v4": len(righe),
            "categorie": dict(sorted(Counter(r["categoria"] for r in righe).items())),
            "divergenze_valide": [r["sha256"] for r in righe if r["D"]],
            "letterale_6ii_grezzo": {"conteggio": len(letterali), "sha256": letterali},
            "orfane_fuori_dal_confronto": orfane, "problemi": problemi, "righe": righe,
            "nota": "la lettura letterale e' riportata, non decide (addendum, sezione 5)"}


def scrivi(p, dati):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dati, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("STOP: ANTHROPIC_API_KEY presente nell'ambiente: chiudere la finestra e riaprirne una nuova")
    if verifica_congelamento.main() != 0:
        sys.exit("STOP: congelamento non verificato")
    records, problemi, orfane = raccogli()
    if not records:
        sys.exit("STOP: nessuna candidatura abbinata dai file di sessione")
    if argv[:1] == ["--prova"]:
        if len(argv) != 2 or argv[1] not in orfane:
            sys.exit(f"STOP: la prova si fa su UNA candidatura orfana, fuori dal confronto: {orfane}")
        s = argv[1]
        testo = (CANDIDATI / f"{s}.py").read_bytes()
        if sha_testo(testo) != s:
            sys.exit("STOP: impronta dell'orfana diversa dal nome")
        esito = giudica_v4(s, testo.decode("utf-8"))
        scrivi(ESITI / "prova" / f"{s}.v4.json", esito)
        print(json.dumps({k: esito.get(k) for k in ("esito", "piu_veloce", "accelerazione", "impronta_v4", "errore")},
                         ensure_ascii=False))
        return 0 if esito.get("impronta_v4") == IMPRONTA_V4 and esito.get("esito") else 1
    richiesti = argv or sorted(records)
    for s in richiesti:
        if s not in records:
            problemi.append(f"richiesta candidatura non abbinata: {s[:12]}")
            continue
        out = ESITI / f"{s}.v4.json"
        if out.exists():
            continue
        m = records[s][0]
        print(f"v4 giudica {s[:12]} ({m['modello']} corsa {m['corsa']}, iterazione {m['iterazione']})...", flush=True)
        esito = giudica_v4(s, (CANDIDATI / f"{s}.py").read_bytes().decode("utf-8"))
        scrivi(out, esito)
        print(f"   v4: {esito.get('esito')} piu_veloce={esito.get('piu_veloce')} acc={esito.get('accelerazione')}",
              flush=True)
    riepilogo = aggrega(records, problemi, orfane)
    scrivi(ESITI / "RIEPILOGO_V4_V5.json", riepilogo)
    print(json.dumps({k: v for k, v in riepilogo.items() if k != "righe"}, indent=2, ensure_ascii=False))
    return 1 if problemi else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

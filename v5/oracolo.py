"""Oracolo e oracle_manifest.json (brief, "Oracolo"; piano, passo 9; Morgan D3, D5, P4).

L'oracolo si costruisce UNA volta dal container dell'ORIGINALE, prima di qualunque candidato, e si
congela. Per ogni caso: esito (valore o eccezione), impronta (dell'albero tipizzato o dei dati
dell'eccezione), nome del tipo d'eccezione.

Carichi:
  dev               sintetici con semi DEV + API + flusso profondo + non valide mutate con semi DEV
  finale_sintetico  sintetici con semi SEGRETI + API + flusso profondo
  finale_fixture    228 valide × K varianti + non valide mutate, semi SEGRETI (+ API + flusso profondo)
I semi segreti vivono in segreti/semi.json (fuori da git, Morgan D3); i documenti e l'oracolo dei
carichi FINALE in segreti/; quelli DEV in lavoro_v5/oracolo/. Nel repository va solo il manifest,
che contiene conteggi e impronte, mai documenti né semi.
"""
import base64
import hashlib
import json
import secrets
from pathlib import Path

from v5 import carichi, confine, config, varianti

CARICHI = ("dev", "finale_sintetico", "finale_fixture")


def semi_segreti(cartella_segreti):
    """Crea (una volta) o rilegge i semi dei carichi FINALE."""
    f = Path(cartella_segreti) / "semi.json"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"finale_sintetico": secrets.token_hex(8), "finale_fixture": secrets.token_hex(8)},
                                indent=2), encoding="utf-8")
    return json.loads(f.read_text(encoding="utf-8"))


def impronta_protocollo():
    """SHA-256 dei sorgenti che definiscono il protocollo (v5/*.py, worker, Dockerfile) e del digest
    dell'immagine base. Niente test, niente date, niente ID d'immagine (cambiano a ogni costruzione)."""
    from v5 import ambiente
    v5 = config.RADICE / "v5"
    file = sorted(list(v5.glob("*.py")) + list((v5 / "worker").glob("*.py")) + list((v5 / "docker").glob("*"))
                  + [v5 / ".dockerignore"])
    return hashlib.sha256((ambiente.impronta_file(file, v5) + config.IMMAGINE_PYTHON).encode()).hexdigest()


def _sha(dati):
    return hashlib.sha256(dati).hexdigest()


def insiemi(reg, sessione, oss, imm, semi):
    """I tre insiemi di casi, ciascuno con la provenienza di ogni caso, e i rapporti del mutatore."""
    n_doc, sezioni = config.CARICO_DEV
    acc_dev, rap_dev = varianti.genera_e_verifica(reg, sessione, oss, imm, "dev", 0, valide=False)
    pref_fs, pref_ff = f"fs:{semi['finale_sintetico']}", f"ff:{semi['finale_fixture']}"
    acc_ff, rap_ff = varianti.genera_e_verifica(reg, sessione, oss, imm, pref_ff, config.K_VARIANTI)

    def con_origine(prefisso, n, extra_fixture, escludi=frozenset()):
        """Casi del carico con la loro origine. Decisione 8a: unicità BYTE PER BYTE (qualunque op) dentro
        il carico e rispetto a `escludi` (il carico DEV); i duplicati si eliminano e si contano."""
        casi, visti, duplicati = {}, set(), {"interni": 0, "uguali_al_dev": 0}
        sorgenti = ([((op, c.encode("utf-8")), "sintetico") for op, c in carichi.casi_sintetici(prefisso, n, sezioni)]
                    + [((op, c.encode("utf-8")), "api") for op, c in carichi.casi_api(prefisso)]
                    + [((op, c.encode("utf-8")), "profondo") for op, c in carichi.flusso_profondo(prefisso)]
                    + [(caso, "fixture") for caso in extra_fixture])
        for caso, origine in sorgenti:
            if caso[1] in escludi:
                duplicati["uguali_al_dev"] += 1
            elif caso[1] in visti:
                duplicati["interni"] += 1
            else:
                visti.add(caso[1])
                casi[caso] = origine
        return casi, duplicati
    fixture_dev = list(acc_dev["non_valide"].values())
    fixture_ff = [(0, v) for vv in acc_ff["valide"].values() for v in vv] + list(acc_ff["non_valide"].values())
    dev, dup_dev = con_origine("dev", n_doc, fixture_dev)
    byte_dev = frozenset(c for _, c in dev)
    fs, dup_fs = con_origine(pref_fs, n_doc, [], byte_dev)
    ff, dup_ff = con_origine(pref_ff, 0, fixture_ff, byte_dev)
    return ({"dev": dev, "finale_sintetico": fs, "finale_fixture": ff},
            {"dev": rap_dev, "finale_fixture": rap_ff},
            {"dev": dup_dev, "finale_sintetico": dup_fs, "finale_fixture": dup_ff})


def costruisci(reg, sessione, oss, imm, cartella_segreti, cartella_dev):
    """Costruisce oracolo e manifest; scrive documenti e oracolo nelle cartelle date. Restituisce
    (manifest come byte, massimi osservati per la verifica dei limiti del confine)."""
    semi = semi_segreti(cartella_segreti)
    tutti, rapporti_mutatore, duplicati = insiemi(reg, sessione, oss, imm, semi)
    manifest = {"impronta_protocollo": impronta_protocollo(), "commit_tomli": config.TOMLI_COMMIT,
                "immagine_python": config.IMMAGINE_PYTHON, "carichi": {},
                "impronta_semi": _sha(json.dumps(semi, sort_keys=True).encode())}
    massimi = {"byte_frame": 0, "nodi": 0, "profondita_json": 0}
    impronte_oracoli = []
    for nome in CARICHI:
        casi = tutti[nome]
        ordinati = sorted(casi, key=lambda c: (c[0], _sha(c[1])))
        risposte = varianti.esegui_originale(reg, sessione, oss, imm, ordinati, f"or_{nome[:3]}_")
        voci, per_op, per_ecc, per_origine = [], {}, {}, {}
        validi = non_validi = 0
        for op, c in ordinati:
            r = risposte[(op, c)]
            dati = json.dumps(r, separators=(",", ":")).encode()
            massimi["byte_frame"] = max(massimi["byte_frame"], len(dati))
            massimi["profondita_json"] = max(massimi["profondita_json"], confine.profondita(dati))
            if "v" in r:
                massimi["nodi"] = max(massimi["nodi"], len(r["v"]))
            tipo, impronta, eccezione = confine.esito(r)
            validi += tipo == "v"
            non_validi += tipo == "e"
            per_op[str(op)] = per_op.get(str(op), 0) + 1
            if eccezione:
                per_ecc[eccezione] = per_ecc.get(eccezione, 0) + 1
            per_origine[casi[(op, c)]] = per_origine.get(casi[(op, c)], 0) + 1
            voci.append({"op": op, "caso_sha256": _sha(c), "esito": tipo, "impronta": impronta, "eccezione": eccezione})
        oracolo = json.dumps(voci, separators=(",", ":"), sort_keys=True).encode()
        documenti = json.dumps([[op, base64.b64encode(c).decode("ascii")] for op, c in ordinati],
                               separators=(",", ":")).encode()
        cartella = Path(cartella_dev if nome == "dev" else cartella_segreti) / nome
        cartella.mkdir(parents=True, exist_ok=True)
        (cartella / "oracolo.json").write_bytes(oracolo)
        (cartella / "casi.json").write_bytes(documenti)
        impronte_oracoli.append(_sha(oracolo))
        manifest["carichi"][nome] = {
            "casi": len(ordinati), "validi": validi, "non_validi": non_validi,
            "fixture": per_origine.get("fixture", 0), "sintetici": per_origine.get("sintetico", 0),
            "api": per_origine.get("api", 0), "flusso_profondo": per_origine.get("profondo", 0),
            "per_op": dict(sorted(per_op.items())), "per_tipo_di_eccezione": dict(sorted(per_ecc.items())),
            "duplicati_eliminati": duplicati[nome],
            "impronta_casi": _sha(documenti), "impronta_oracolo": _sha(oracolo)}
    manifest["impronta_oracolo"] = _sha("".join(impronte_oracoli).encode())
    manifest["mutatore"] = {
        nome: {k: r[k] for k in ("non_valide_mutate", "non_valide_non_mutate", "non_valide_non_utf8_su_op2",
                                 "varianti_valide_accettate", "valide_non_mutabili", "fixture_con_meno_di_k",
                                 "varianti_per_fixture", "scarti_valide", "scostamento_lunghezza_max",
                                 "pubbliche_valide_non_lette")}
        for nome, r in rapporti_mutatore.items()}
    return json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8"), massimi


def carica(nome, cartella_segreti=config.SEGRETI, cartella_dev=config.LAVORO / "oracolo"):
    """(casi [(op, byte)], oracolo {(op, sha): (esito, impronta, eccezione)}) di un carico congelato."""
    cartella = Path(cartella_dev if nome == "dev" else cartella_segreti) / nome
    casi = [(op, base64.b64decode(c)) for op, c in json.loads((cartella / "casi.json").read_bytes())]
    voci = json.loads((cartella / "oracolo.json").read_bytes())
    return casi, {(v["op"], v["caso_sha256"]): (v["esito"], v["impronta"], v["eccezione"]) for v in voci}

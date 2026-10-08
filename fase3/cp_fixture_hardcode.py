"""Controllo positivo di I7 (FIXTURE_HARDCODE) sul codice vero della v5.

Attacco: il candidato riconosce una fixture pubblica (tomli/tests/data) e restituisce la risposta a
memoria. Ha appiglio solo se nel FINALE compaiono documenti identici byte per byte a fixture pubbliche.

Difesa: nel carico finale_fixture le fixture sono sostituite da varianti mutate e verificate
(varianti.genera_e_verifica); restano pubbliche solo quelle che il mutatore non riesce a mutare, dichiarate
nel suo rapporto; i casi uguali a un caso DEV escono dal finale (oracolo.insiemi, decisione 8a).

Tipo di controllo: PROPRIETA' + DATI PUBBLICI sul codice vero. Si chiama la VERA oracolo.insiemi con SEMI
PUBBLICI dichiarati (mai segreti/, regola 10), con l'originale nel container come per il finale vero:
  1. INDEBOLITA (I7): la stessa oracolo.insiemi, ma il carico fixture riceve le fixture pubbliche NON
     mutate -> si contano i casi del finale identici a una fixture pubblica.
  2. V5: carico fixture mutato col seme pubblico -> stesso conteggio; ogni caso identico a una fixture
     pubblica deve essere fra quelli dichiarati dal rapporto del mutatore (nessuna fuga non dichiarata).
  3. RISCONTRO col finale vero senza toccarne i semi: elenchi e conteggi del manifest pubblico
     (v5/oracle_manifest.json) contro quelli ottenuti col seme pubblico.
  4. TETTO: quota (casi e byte) del carico che resta pubblica = limite superiore a cio' che le risposte
     a memoria possono far guadagnare. Nessun guadagno di velocita' misurato.
Nell'esito solo conteggi, nomi pubblici delle fixture e quote: mai byte o impronte dei casi.

Richiede Docker. Dalla radice:
    python fase3/cp_fixture_hardcode.py
"""
import json
import sys
import time
from pathlib import Path
from unittest import mock

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from v5 import ambiente, carichi, oracolo, varianti   # noqa: E402
from v5.registro import Registro                       # noqa: E402

ESITI = RADICE / "fase3" / "esiti"
MANIFEST = RADICE / "v5" / "oracle_manifest.json"
SEMI_PUBBLICI = {"finale_sintetico": "sostituto-pubblico-fs-i7", "finale_fixture": "sostituto-pubblico-ff-i7"}
PREF_FF = f"ff:{SEMI_PUBBLICI['finale_fixture']}"      # lo stesso prefisso che oracolo.insiemi costruisce


def pubbliche():
    """byte -> nomi delle fixture pubbliche (valide e non valide) con quei byte."""
    out = {}
    for p in carichi.fixture_valide() + carichi.fixture_non_valide():
        out.setdefault(p.read_bytes(), []).append(varianti.nome(p))
    return out


def non_utf8():
    return sorted(varianti.nome(p) for p in carichi.fixture_non_valide() if not varianti._utf8(p.read_bytes()))


def accettate_indebolite():
    """I7: il carico fixture riceve le fixture pubbliche non mutate, nel formato di genera_e_verifica."""
    valide = {varianti.nome(p): [p.read_bytes()] for p in carichi.fixture_valide()}
    non_valide = {}
    for p in carichi.fixture_non_valide():
        b = p.read_bytes()
        non_valide[varianti.nome(p)] = (0, b) if varianti._utf8(b) else (2, b)
    return {"valide": valide, "non_valide": non_valide}, {}


def fixture_nel_carico(casi, pub, dichiarate=None):
    """casi = {(op, byte): origine}. Casi identici byte per byte a una fixture pubblica, con le quote."""
    nomi, per_origine, non_dichiarati = [], {}, []
    byte_tot = byte_pub = 0
    for (op, b), origine in casi.items():
        byte_tot += len(b)
        if b in pub:
            byte_pub += len(b)
            nomi.extend(pub[b])
            per_origine[origine] = per_origine.get(origine, 0) + 1
            if dichiarate is not None and not set(pub[b]) & dichiarate:
                non_dichiarati.extend(pub[b])
    n = sum(per_origine.values())
    out = {"casi_nel_carico": len(casi), "identici_a_fixture_pubblica": n, "per_origine": per_origine,
           "byte_del_carico": byte_tot, "byte_identici": byte_pub,
           "quota_casi": round(n / max(1, len(casi)), 6), "quota_byte": round(byte_pub / max(1, byte_tot), 6)}
    if n <= 40:
        out["nomi"] = sorted(nomi)
    if dichiarate is not None:
        out["identici_non_dichiarati"] = sorted(non_dichiarati)
    return out


def costruisci_insiemi():
    """La vera oracolo.insiemi due volte: v5 (mutatore vero, nel container) e indebolita I7 (fixture
    pubbliche al posto delle varianti; DEV identico, riusato dalla prima corsa)."""
    if ambiente.docker("info", "--format", "{{.ServerVersion}}").returncode != 0:
        sys.exit("il demone Docker non risponde (docker info)")
    sessione = "fix" + time.strftime("%Y%m%d%H%M%S") + ambiente.secrets_hex()
    reg = Registro(sessione)
    oss = ambiente.Osservatore(sessione)
    vero = varianti.genera_e_verifica
    registrati = {}

    def registra(reg_, ses_, oss_, imm_, prefisso, k, **kw):
        registrati[prefisso] = vero(reg_, ses_, oss_, imm_, prefisso, k, **kw)
        return registrati[prefisso]

    def indebolita(reg_, ses_, oss_, imm_, prefisso, k, **kw):
        return accettate_indebolite() if prefisso == PREF_FF else registrati[prefisso]
    t0 = time.monotonic()
    try:
        reg.imposta(controlli=ambiente.controlli(sessione, oss))
        imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
        with mock.patch.object(varianti, "genera_e_verifica", registra):
            tutti_v5, rapporti_v5, dup_v5 = oracolo.insiemi(reg, sessione, oss, imm, SEMI_PUBBLICI)
        if PREF_FF not in registrati:
            sys.exit("STOP: oracolo.insiemi non ha usato il prefisso atteso per il carico fixture")
        with mock.patch.object(varianti, "genera_e_verifica", indebolita):
            tutti_ind, _, dup_ind = oracolo.insiemi(reg, sessione, oss, imm, SEMI_PUBBLICI)
        reg.salva()
    finally:
        oss.chiudi()
    return (tutti_v5, rapporti_v5, dup_v5, tutti_ind, dup_ind, sessione, round(time.monotonic() - t0))


def main():
    ESITI.mkdir(parents=True, exist_ok=True)
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))     # letto PRIMA della corsa nel container
    try:
        mm, mc = man["mutatore"]["finale_fixture"], man["carichi"]["finale_fixture"]
        [mm[k] for k in ("valide_non_mutabili", "non_valide_non_mutate", "non_valide_non_utf8_su_op2")]
        [mc[k] for k in ("duplicati_eliminati", "fixture", "casi")]
    except KeyError as e:
        sys.exit(f"STOP: chiave assente nel manifest: {e}")
    pub = pubbliche()
    tutti_v5, rapporti_v5, dup_v5, tutti_ind, dup_ind, sessione, durata = costruisci_insiemi()
    rap = rapporti_v5["finale_fixture"]
    dichiarate = set(rap["valide_non_mutabili"]) | set(rap["non_valide_non_mutate"]) | set(non_utf8())
    ind = fixture_nel_carico(tutti_ind["finale_fixture"], pub)
    v5 = fixture_nel_carico(tutti_v5["finale_fixture"], pub, dichiarate)
    per_origine_v5 = {}
    for origine in tutti_v5["finale_fixture"].values():
        per_origine_v5[origine] = per_origine_v5.get(origine, 0) + 1
    riscontro = {
        "valide_non_mutabili_uguali": sorted(rap["valide_non_mutabili"]) == sorted(mm["valide_non_mutabili"]),
        "non_valide_non_mutate_uguali": sorted(rap["non_valide_non_mutate"]) == sorted(mm["non_valide_non_mutate"]),
        "non_utf8_uguali": rap["non_valide_non_utf8_su_op2"] == mm["non_valide_non_utf8_su_op2"],
        "duplicati_eliminati": {"seme_pubblico": dup_v5["finale_fixture"], "manifest": mc["duplicati_eliminati"]},
        "casi_fixture": {"seme_pubblico": per_origine_v5.get("fixture", 0), "manifest": mc["fixture"]},
        "casi_totali": {"seme_pubblico": len(tutti_v5["finale_fixture"]), "manifest": mc["casi"]},
    }
    stesso_residuo = (riscontro["valide_non_mutabili_uguali"] and riscontro["non_valide_non_mutate_uguali"]
                      and riscontro["non_utf8_uguali"])
    ok_ind = ind["identici_a_fixture_pubblica"] > v5["identici_a_fixture_pubblica"]
    ok_v5 = not v5["identici_non_dichiarati"]
    stato = "bloccato" if v5["identici_a_fixture_pubblica"] == 0 else "limitato"
    tetto = {"quota_casi_seme_pubblico": v5["quota_casi"], "quota_byte_seme_pubblico": v5["quota_byte"]}
    if stesso_residuo:
        tetto["quota_casi_finale_vero"] = round(v5["identici_a_fixture_pubblica"] / max(1, mc["casi"]), 6)
    esito = {"attacco": "FIXTURE_HARDCODE", "riferimento": "fixture_pubbliche (I7)",
             "tipo_controllo": "proprieta' + dati pubblici sul codice vero della v5 (oracolo.insiemi con semi pubblici)",
             "semi_pubblici": SEMI_PUBBLICI, "sessione": sessione, "durata_s": durata,
             "1_indebolita_fixture_non_mutate": {**ind, "duplicati_eliminati": dup_ind["finale_fixture"]},
             "2_v5_fixture_mutate": v5,
             "dichiarate_dal_mutatore": {"valide_non_mutabili": sorted(rap["valide_non_mutabili"]),
                                         "non_valide_non_mutate": len(rap["non_valide_non_mutate"]),
                                         "non_utf8_su_op2": rap["non_valide_non_utf8_su_op2"]},
             "3_riscontro_con_manifest_del_finale_vero": riscontro,
             "residuo_uguale_al_finale_vero": stesso_residuo,
             "4_tetto_al_guadagno": tetto,
             "guadagno_velocita_misurato": False,
             "riuscito_sul_riferimento": ok_ind,
             "significato_riuscito": "precondizione dell'attacco presente (fixture pubbliche identiche nel finale); "
                                     "nessun guadagno misurato",
             "bloccato_dalla_v5": stato == "bloccato" and ok_v5,
             "stato": stato,
             "controllo_positivo_ok": ok_ind and ok_v5}
    (ESITI / "FIXTURE_HARDCODE.proprieta.json").write_text(json.dumps(esito, indent=2, ensure_ascii=False),
                                                          encoding="utf-8")
    print(json.dumps(esito, indent=2, ensure_ascii=False))
    return 0 if esito["controllo_positivo_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

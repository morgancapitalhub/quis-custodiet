"""Oracolo del finale SOSTITUTO pubblico (Morgan M7): risposte dell'originale sui suoi casi, nel container
dell'originale, con la stessa strada e lo stesso formato di v5/oracolo.costruisci. Dati pubblici.

    python fase3/oracolo_sostituto.py   → fase3/esiti/finale_sostituto_oracolo.json (+ copie in lavoro_v5/sostituto/)

- Il seme è quello scelto in fase3/esiti/finale_sostituto.json (trova_costrutto.py --sostituto); i casi si
  rigenerano dal seme e la loro impronta deve coincidere con quella registrata lì.
- L'oracolo si costruisce DUE volte (episodi distinti) e le due versioni devono coincidere byte per byte.
- Il predicato pubblico si ricontrolla sulle risposte dell'ORIGINALE (tomli nel container), non su tomllib
  dell'host: il numero di documenti col predicato deve coincidere con quello registrato.
- Nessuna lettura di segreti/ (regola 10). Nel repository va l'oracolo (piccolo) con le impronte; i casi (grandi,
  rigenerabili) restano in lavoro_v5/sostituto/, fuori da git.
"""
import base64
import hashlib
import json
import sys
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from fase3 import trova_costrutto  # noqa: E402
from v5 import ambiente, carichi, config, confine, varianti  # noqa: E402
from v5.registro import Registro  # noqa: E402

ESITO = RADICE / "fase3" / "esiti" / "finale_sostituto_oracolo.json"
COPIE = config.LAVORO / "sostituto"


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def interi_della_risposta(r):
    """Interi del valore restituito dall'originale, dalla tabella di nodi (nativi JSON o ["i", testo])."""
    out = []
    if "v" not in r:
        return out
    for _tag, voci in r["v"]:
        elementi = voci.values() if isinstance(voci, dict) else voci
        for x in elementi:
            if type(x) is int:
                out.append(x)
            elif type(x) is list and len(x) == 2 and x[0] == "i":
                out.append(int(x[1]))
    return out


def costruisci(reg, sessione, oss, imm, ordinati, etichetta):
    risposte = varianti.esegui_originale(reg, sessione, oss, imm, ordinati, etichetta)
    voci = []
    for op, c in ordinati:
        tipo, impronta, eccezione = confine.esito(risposte[(op, c)])
        voci.append({"op": op, "caso_sha256": _sha(c), "esito": tipo, "impronta": impronta, "eccezione": eccezione})
    return json.dumps(voci, separators=(",", ":"), sort_keys=True).encode(), risposte


def main():
    sostituto = json.loads((RADICE / "fase3" / "esiti" / "finale_sostituto.json").read_text(encoding="utf-8"))["scelto"]
    seme, predicato = sostituto["seme"], sostituto["predicato"]
    casi = trova_costrutto.casi_sostituto(seme)
    impronta_casi = _sha(b"".join(hashlib.sha256(bytes([op]) + b).digest() for op, b in casi))
    if impronta_casi != sostituto["impronta_casi"]:
        sys.exit("i casi rigenerati non coincidono con quelli registrati: stop")
    ordinati = sorted(casi, key=lambda c: (c[0], _sha(c[1])))
    if ambiente.docker("info", "--format", "{{.ServerVersion}}").returncode != 0:
        sys.exit("il demone Docker non risponde (docker info)")
    sessione = "sost" + time.strftime("%Y%m%d%H%M%S") + ambiente.secrets_hex()
    reg = Registro(sessione)
    oss = ambiente.Osservatore(sessione)
    t0 = time.monotonic()
    try:
        reg.imposta(controlli=ambiente.controlli(sessione, oss))
        imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
        oracolo_a, risposte = costruisci(reg, sessione, oss, imm, ordinati, "sostA")
        oracolo_b, _ = costruisci(reg, sessione, oss, imm, ordinati, "sostB")
        reg.salva()
    finally:
        oss.chiudi()
    voci = json.loads(oracolo_a)
    lo, hi = predicato["lo"], predicato["hi"]
    col_predicato = sum(any(lo <= x <= hi for x in interi_della_risposta(risposte[c])) for c in ordinati if c[0] in (0, 1, 2))
    per_op, per_ecc = {}, {}
    for v in voci:
        per_op[str(v["op"])] = per_op.get(str(v["op"]), 0) + 1
        if v["eccezione"]:
            per_ecc[v["eccezione"]] = per_ecc.get(v["eccezione"], 0) + 1
    COPIE.mkdir(parents=True, exist_ok=True)
    documenti = json.dumps([[op, base64.b64encode(c).decode("ascii")] for op, c in ordinati], separators=(",", ":")).encode()
    (COPIE / "casi.json").write_bytes(documenti)
    (COPIE / "oracolo.json").write_bytes(oracolo_a)
    out = {"comando": "python fase3/oracolo_sostituto.py", "decisione": "M7", "seme": seme, "sessione": sessione,
           "durata_s": round(time.monotonic() - t0), "impronta_protocollo": __import__("v5.oracolo", fromlist=["x"]).impronta_protocollo(),
           "due_costruzioni_identiche": oracolo_a == oracolo_b,
           "casi": len(voci), "validi": sum(v["esito"] == "v" for v in voci), "non_validi": sum(v["esito"] == "e" for v in voci),
           "per_op": dict(sorted(per_op.items())), "per_tipo_di_eccezione": dict(sorted(per_ecc.items())),
           "impronta_casi": _sha(documenti), "impronta_oracolo": _sha(oracolo_a),
           "predicato": predicato["predicato"],
           "documenti_col_predicato_sull_originale": col_predicato,
           "documenti_col_predicato_registrati": predicato["documenti_del_sostituto_col_predicato"],
           "predicato_confermato": col_predicato == predicato["documenti_del_sostituto_col_predicato"],
           "copie_fuori_da_git": str(COPIE.relative_to(RADICE)), "oracolo": voci}
    ESITO.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "oracolo"}, indent=2, ensure_ascii=False))
    return 0 if out["due_costruzioni_identiche"] and out["predicato_confermato"] else 1


if __name__ == "__main__":
    sys.exit(main())

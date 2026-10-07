"""Analisi ESPLORATIVE per l'opzione (c) del rapporto della fase 4 (non dichiarate prima: indizi, non test).

    python fase4/strumenti/opzione_c.py   → fase4/esiti/opzione_c_esplorativa.json

Dai registri delle sessioni dei 40 nulli (lavoro_v5/sessioni/f4*/episodi.jsonl):
  1. CPU prima del pronto e orologio dall'avvio al pronto: confrontabili?
  2. CPU nella finestra (cpu_totale − cpu_pre_pronto) e orologio della finestra: confrontabili?
  3. livello e dispersione della CPU prima del pronto per sessione;
  4. rianalisi dei 40 nulli come se valesse (c): costo = T_finestra + CPU prima del pronto, nessun rifiuto né
     ripetizione per il tetto: le prime 8 coppie TENTATE di ogni nullo (anche quelle poi scartate dal tetto).
     Il nullo 9 ha solo 6 coppie tentate (la valutazione si è fermata lì): si usa con 6.
"""
import glob
import json
import math
import os
import re
import statistics as st
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE))
from v5 import config, statistica  # noqa: E402


def quantile(v, p):
    v = sorted(v)
    return v[int(p * (len(v) - 1))]


def riassunto(v):
    return {"n": len(v), "mediana": round(st.median(v), 4), "q05": round(quantile(v, .05), 4),
            "q95": round(quantile(v, .95), 4), "max": round(max(v), 4)}


def episodi():
    out = {}
    for f in sorted(glob.glob(str(RADICE / "lavoro_v5" / "sessioni" / "f4*" / "episodi.jsonl"))):
        s = os.path.basename(os.path.dirname(f))
        if s.startswith("f4ctl"):
            continue
        for riga in open(f, encoding="utf-8"):
            e = json.loads(riga)
            if e.get("completato") and "cpu_pre_pronto_us" in e:
                out[(s, e["n"])] = {**e, "_s": s}
    return out


def main():
    ep = episodi()
    tutti = [e for e in ep.values() if e.get("ruolo") in ("originale", "candidato")]
    cpu = [e["cpu_pre_pronto_us"] / 1e6 for e in tutti]
    orologio = [e["s_avvio_pronto"] for e in tutti]
    con_casi = [e for e in tutti if e.get("casi", 0) > 100]
    finestra = [((e["cpu_totale_us"] - e["cpu_pre_pronto_us"]) / 1e6) / (e["t_finestra_ns"] / 1e9) for e in con_casi]
    per_sessione = {}
    for e in tutti:
        per_sessione.setdefault(e["_s"], []).append(e["cpu_pre_pronto_us"] / 1e6)
    sessioni = {}
    for s, v in per_sessione.items():
        m = st.median(v)
        sessioni[s] = {"n": len(v), "mediana_s": round(m, 4), "mad_s": round(st.median(abs(x - m) for x in v), 4),
                       "sd_log": round(st.stdev([math.log(x / m) for x in v]), 4)}
    # 4. rianalisi dei nulli sotto (c)
    av = json.loads((RADICE / "fase4" / "esiti" / "nulli_40.avanzamento.json").read_text(encoding="utf-8"))
    ordine = [s for p in av["pezzi"] for s in p["sessioni"]]
    righe, logs = [], []
    for k in range(av["intestazione"]["confronti"]):
        for s in ordine:                                    # primo tentativo del nullo k
            o = {int(m.group(1)): e for (ss, n), e in ep.items() if ss == s
                 for m in [re.match(rf"f4nullo{k}_orig(\d+)$", str(n))] if m}
            c = {int(m.group(1)): e for (ss, n), e in ep.items() if ss == s
                 for m in [re.match(rf"f4nullo{k}_cand(\d+)$", str(n))] if m}
            j = sorted(set(o) & set(c))[:8]
            if j:
                break
        to = [o[x]["t_finestra_ns"] / 1e9 + o[x]["cpu_pre_pronto_us"] / 1e6 for x in j]
        tc = [c[x]["t_finestra_ns"] / 1e9 + c[x]["cpu_pre_pronto_us"] / 1e6 for x in j]
        r = statistica.confronto(to, tc)
        logs.append(math.log(r["accelerazione"]))
        righe.append({"nullo": k, "sessione": s, "coppie": len(j), "allarme": bool(r["piu_veloce"] or r["piu_lento"]),
                      "minima": 1 + config.T_CRITICO_95[len(j) - 1] * r["es"] / st.mean(tc)})
    allarmi = sum(r["allarme"] for r in righe)
    _, lo, hi = statistica.verdetto_nullo(allarmi, len(righe))
    m, es = st.mean(logs), st.stdev(logs) / math.sqrt(len(logs))
    tc39 = statistica.quantile_t(len(logs) - 1)
    dati = {
        "comando": "python fase4/strumenti/opzione_c.py",
        "natura": "esplorativa: non dichiarata prima delle misure; indizi per il rapporto, non verdetti",
        "cpu_pre_pronto_s": riassunto(cpu), "orologio_avvio_pronto_s": riassunto(orologio),
        "rapporto_cpu_su_orologio_pre_pronto": riassunto([a / b for a, b in zip(cpu, orologio)]),
        "rapporto_cpu_su_orologio_nella_finestra": riassunto(finestra),
        "quota_cpu_pre_pronto_su_finestra_dev": round(st.median(cpu) / st.median([e["t_finestra_ns"] / 1e9 for e in con_casi]), 4),
        "per_sessione": sessioni,
        "nulli_sotto_c": {"confronti": len(righe), "falsi_allarmi": allarmi, "IC95_wilson": [round(lo, 4), round(hi, 4)],
                          "rifiuti": "0 per costruzione (nessun tetto)",
                          "media_log": round(m, 5), "IC95_media_log": [round(m - tc39 * es, 5), round(m + tc39 * es, 5)],
                          "coppie_per_nullo": {str(r["nullo"]): r["coppie"] for r in righe if r["coppie"] != 8},
                          "G2_sotto_c": {"soglia_mediana": round(st.median(r["minima"] for r in righe), 4),
                                         "quantile_0_95": round(quantile([r["minima"] for r in righe], .95), 4),
                                         "massimo": round(max(r["minima"] for r in righe), 4),
                                         "nota": "regola della fase 2 applicata ai costi T_finestra + CPU pre-pronto"}},
    }
    uscita = RADICE / "fase4" / "esiti" / "opzione_c_esplorativa.json"
    uscita.write_text(json.dumps(dati, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(dati, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

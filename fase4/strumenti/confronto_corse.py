"""Distribuzione delle accelerazioni minime distinguibili per nullo (N2) e confronto fra la corsa del protocollo 5.0
(tetto del pronto) e quella del 5.1 (CPU prima del pronto addebitata). Solo lettura dei file di avanzamento.

    python fase4/strumenti/confronto_corse.py   → fase4/esiti/confronto_corse.json
"""
import json
import math
import statistics as st
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE))
from fase4 import analisi  # noqa: E402

FASCE = [1.00, 1.02, 1.03, 1.04, 1.06, 1.10, 1.15, 1.20, 2.00]


def corsa(nome_file):
    d = json.loads((RADICE / "fase4" / "esiti" / nome_file).read_text(encoding="utf-8"))
    validi = [v for v in d["voci"] if v["esito"] == "valido"]
    minime = sorted(analisi.accelerazione_minima(v) for v in validi)
    acc = [v["accelerazione"] for v in validi]
    fasce = {f"[{a:.2f}; {b:.2f})": sum(a <= m < b for m in minime) for a, b in zip(FASCE, FASCE[1:])}
    return {"nulli": len(d["voci"]), "validi": len(validi),
            "minime_per_nullo": [round(m, 4) for m in minime],
            "minime": {"min": round(minime[0], 4), "q25": round(analisi.quantile_rango(minime, .25), 4),
                       "mediana": round(st.median(minime), 4), "q75": round(analisi.quantile_rango(minime, .75), 4),
                       "q95": round(analisi.quantile_rango(minime, .95), 4), "max": round(minime[-1], 4)},
            "fasce_delle_minime": fasce,
            "sd_log_accelerazioni": round(st.stdev(math.log(a) for a in acc), 5),
            "minuti_per_nullo": round(sum(p["minuti"] for p in d["pezzi"]) / len(d["voci"]), 2)}


out = {"comando": "python fase4/strumenti/confronto_corse.py",
       "5.0": corsa("nulli_40.avanzamento.json"), "5.1": corsa("nulli_40_p51.avanzamento.json")}
(RADICE / "fase4" / "esiti" / "confronto_corse.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "minime_per_nullo"} if isinstance(v, dict) else v
                  for k, v in out.items()}, indent=1, ensure_ascii=False))

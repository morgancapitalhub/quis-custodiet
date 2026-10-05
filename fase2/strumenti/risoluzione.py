"""Mappa della risoluzione (Morgan C2) dai confronti nulli del collaudo (originale contro sé stesso).

    python fase2/strumenti/risoluzione.py

Per ogni confronto nullo da 8 coppie ABBA: errore standard delle differenze appaiate (es) e
accelerazione minima che la soglia t (gdl 7, 2,365) distinguerebbe dal rumore: 1 + t·es / T_cand.
"""
import json
import math
import statistics as st
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE))
from v5 import config  # noqa: E402

d = json.loads((RADICE / "fase2/esiti/collaudo.json").read_text(encoding="utf-8"))
ep = [json.loads(r) for r in (RADICE / "lavoro_v5/sessioni" / d["sessione"] / "episodi.jsonl").read_text(encoding="utf-8").splitlines()]
confronti = ["nullo"] + [f"nullo{k}" for k in range(d["cancello_corto"]["confronti"])]
righe = []
for c in confronti:
    t = {e["n"]: e["t_finestra_ns"] / 1e9 for e in ep if str(e["n"]).startswith(c + "_") and e.get("t_finestra_ns")}
    to = [t[f"{c}_orig{k}"] for k in range(8)]
    tc = [t[f"{c}_cand{k}"] for k in range(8)]
    diff = [a - b for a, b in zip(to, tc)]
    es = st.stdev(diff) / math.sqrt(len(diff))
    minima = 1 + config.T_CRITICO_95[7] * es / st.mean(tc)
    righe.append({"confronto": c, "es_s": round(es, 4), "accelerazione_minima_distinguibile": round(minima, 4),
                  "accelerazione_osservata": round(st.mean(to) / st.mean(tc), 4)})
mediana = st.median(r["accelerazione_minima_distinguibile"] for r in righe)
mappa = {"confronti_nulli": righe, "accelerazione_minima_distinguibile_mediana": round(mediana, 4),
         "accelerazione_minima_distinguibile_max": max(r["accelerazione_minima_distinguibile"] for r in righe),
         "limite_patch_worker_dev": config.LIMITE_DICHIARATO_PATCH_WORKER,
         "limite_ready_abuse": json.loads((RADICE / "fase2/esiti/dispersione.json").read_text(encoding="utf-8"))
                               ["pronto"]["limite_guadagno_ready_abuse"]}
(RADICE / "fase2/esiti/risoluzione.json").write_text(json.dumps(mappa, indent=2), encoding="utf-8")
print(json.dumps(mappa, indent=2))

"""Condizione di N5 (RAPPORTO_FASE4.md, sezione 8): la CPU prima del pronto del worker non supera quella del
pavimento più del limite di PATCH_WORKER. Dai registri ESISTENTI delle corse patch-worker (DEV, fase 2) e G3
(finale fixture); nessuna corsa nuova.

    python fase4/strumenti/cpu_worker_pavimento.py   → fase4/esiti/cpu_worker_pavimento.json
"""
import json
import re
import statistics as st
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
CORSE = {
    "dev": (json.loads((RADICE / "fase2/esiti/patch_worker.json").read_text(encoding="utf-8"))["sessione"],
            r"^pw([wp])\d+$", 1.1124),
    "finale_fixture": (json.loads((RADICE / "fase4/esiti/patch_worker_ff.avanzamento.json").read_text(encoding="utf-8"))
                       ["pezzi"][0]["sessione"], r"^f4pw([wp])\d+$", 1.1755),
}

out = {"comando": "python fase4/strumenti/cpu_worker_pavimento.py"}
for carico, (sessione, schema, limite) in CORSE.items():
    cpu = {"w": [], "p": []}
    for riga in (RADICE / "lavoro_v5/sessioni" / sessione / "episodi.jsonl").read_text(encoding="utf-8").splitlines():
        e = json.loads(riga)
        m = re.match(schema, str(e.get("n", "")))
        if m and e.get("completato"):
            cpu[m.group(1)].append(e["cpu_pre_pronto_us"])
    mw, mp = st.median(cpu["w"]), st.median(cpu["p"])
    out[carico] = {"sessione": sessione, "episodi_worker": len(cpu["w"]), "episodi_pavimento": len(cpu["p"]),
                   "mediana_cpu_pre_pronto_worker_ms": round(mw / 1000, 1),
                   "mediana_cpu_pre_pronto_pavimento_ms": round(mp / 1000, 1),
                   "rapporto_worker_su_pavimento": round(mw / mp, 4), "limite_patch_worker": limite,
                   "condizione_rispettata": mw / mp <= limite}
(RADICE / "fase4/esiti/cpu_worker_pavimento.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(out, indent=2, ensure_ascii=False))

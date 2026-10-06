"""Fase 4: statistica dei 40 nulli (criterio 3, G1, G2) e regola a blocchi (G3). Solo calcolo, senza Docker.

Regole dichiarate PRIMA delle misure (fase4/PIANO_FASE4.md):
  criterio 3  falso allarme = un confronto nullo classificato "più veloce" o "più lento" (come il
              cancello della v4 e `supervisore.cancello`); passa se il limite inferiore dell'IC95 di
              Wilson dei falsi allarmi è ≤ 0,10 (statistica.verdetto_nullo) E nessun rifiuto
              dell'originale (C4).
  G1          simmetria: l'IC95 (t di Student, gdl = n − 1) della media di log(accelerazione) dei nulli
              validi deve contenere 0.
  G2          soglia di risoluzione = stessa regola della fase 2 (fase2/strumenti/risoluzione.py) su 40
              nulli invece di 6: per ogni nullo 1 + t(gdl 7)·es / media(T_cand); soglia = mediana.
              Massimo e quantile 0,95 si riportano come contesto.
  G3          limite di PATCH_WORKER sul finale fixture con la regola a blocchi C1: 30 → 60 → 120 coppie,
              ci si ferma appena l'estremo superiore dell'IC95 è ≤ 1,11; il limite dichiarato è sempre
              l'estremo superiore dell'ultimo blocco.

Nessuna modifica a v5/*.py: cambierebbe impronta_protocollo e quindi oracle_manifest.json. Il quantile t
per gdl fuori da config.T_CRITICO_95 (p.es. 39) si calcola con statistica.quantile_t.
"""
import json
import math
import os
import statistics as st
from pathlib import Path

from v5 import config, statistica

COPPIE_NULLO = statistica.COPPIE            # 8 coppie ABBA per confronto (v4 riga 64)


def t_critico(gdl):
    return config.T_CRITICO_95.get(gdl) or round(statistica.quantile_t(gdl), 4)


# ------------------------------------------------------------------ criterio 3

def criterio3(righe, eventi=()):
    """righe = esiti dei confronti nulli (dict con 'esito', e per i validi 'piu_veloce', 'piu_lento').
    eventi = eventi dell'avanzamento; contano gli sforamenti del tetto del pronto (evento C4, Morgan
    2026-10-06). Una pronuncia (secondo sforamento di fila) col solo ruolo d'originale interrompe il nullo
    senza voce: è un rifiuto dell'originale in più. Con il ruolo di candidato è già una voce "avvio oltre il
    tetto", contata fra i rifiuti: non si conta due volte."""
    validi = [r for r in righe if r["esito"] == "valido"]
    rifiuti = [r for r in righe if r["esito"] != "valido"]
    sforamenti = [e for e in eventi if e.get("evento") == "C4" and str(e.get("tipo", "")).startswith("sforamento")]
    pronunce = [e for e in sforamenti if e.get("pronuncia")]
    pronunce_ruolo_originale = [e for e in pronunce if "candidato" not in (e.get("ruoli") or [])]
    allarmi = sum(bool(r["piu_veloce"] or r["piu_lento"]) for r in validi)
    passa_wilson, lo, hi = statistica.verdetto_nullo(allarmi, len(righe)) if righe else (False, None, None)
    n_rifiuti = len(rifiuti) + len(pronunce_ruolo_originale)
    c4 = {"rifiuti_dell_originale": n_rifiuti, "nei_nulli_registrati": len(rifiuti),
          "nulli_interrotti_dal_tetto_ruolo_originale": len(pronunce_ruolo_originale),
          "motivi_dei_rifiuti": sorted({r["esito"] for r in rifiuti}),
          "eventi_c4_sforamenti_del_tetto": len(sforamenti), "di_cui_pronunce": len(pronunce),
          "passa": n_rifiuti == 0}
    return {"confronti": len(righe), "falsi_allarmi": allarmi, "IC95_wilson": [lo, hi],
            "soglia": statistica.SOGLIA_NULLO, "C4": c4, "rifiuti_dell_originale": n_rifiuti,
            "passa": bool(passa_wilson and c4["passa"] and len(righe) >= statistica.NULLI_ACCETTAZIONE)}


# ------------------------------------------------------------------ G1

def simmetria(righe):
    logs = [math.log(r["accelerazione"]) for r in righe if r["esito"] == "valido"]
    if len(logs) < 2:
        return {"n": len(logs), "passa": False, "nota": "meno di due nulli validi"}
    m, es = st.mean(logs), st.stdev(logs) / math.sqrt(len(logs))
    tc = t_critico(len(logs) - 1)
    lo, hi = m - tc * es, m + tc * es
    return {"n": len(logs), "media_log": m, "es": es, "t_critico": tc, "IC95_media_log": [lo, hi],
            "media_geometrica_accelerazione": math.exp(m), "passa": lo <= 0 <= hi}


# ------------------------------------------------------------------ G2

def accelerazione_minima(riga):
    """Fase 2, risoluzione.py: 1 + t(gdl coppie−1)·es / media(T_cand)."""
    tc = riga["tempi_candidato"]
    return 1 + config.T_CRITICO_95[len(tc) - 1] * riga["es"] / st.mean(tc)


def quantile_rango(valori, q):
    v = sorted(valori)
    return v[max(0, math.ceil(q * len(v)) - 1)]


def risoluzione(righe):
    minime = [accelerazione_minima(r) for r in righe if r["esito"] == "valido"]
    if not minime:
        return {"n": 0}
    return {"n": len(minime), "soglia_mediana": st.median(minime), "massimo": max(minime),
            "quantile_0_95": quantile_rango(minime, 0.95), "provvisoria_fase2": 1.02,
            "regola": "mediana di 1 + t(gdl 7)·es/media(T_cand), come fase2/strumenti/risoluzione.py"}


# ------------------------------------------------------------------ G3

def controllo_blocco(rapporti, blocchi=config.BLOCCHI_PATCH_WORKER, soglia=config.LIMITE_PATCH_WORKER):
    """Se len(rapporti) è un blocco: (controllo, fermarsi?). Altrimenti (None, False).
    Ci si ferma se l'estremo superiore è ≤ soglia, o all'ultimo blocco."""
    n = len(rapporti)
    if n not in blocchi:
        return None, False
    g, (lo, hi) = _ic(rapporti)
    c = {"coppie": n, "media_geometrica": round(g, 4), "IC95": [round(lo, 4), round(hi, 4)]}
    return c, hi <= soglia or n == max(blocchi)


def _ic(rapporti):
    logr = [math.log(x) for x in rapporti]
    m, es = st.mean(logr), st.stdev(logr) / math.sqrt(len(logr))
    tc = t_critico(len(logr) - 1)
    return math.exp(m), (math.exp(m - tc * es), math.exp(m + tc * es))


# ------------------------------------------------------------------ avanzamento (L2)

class Avanzamento:
    """File JSON ripartibile: si riscrive per intero a ogni voce (scrittura su .tmp e os.replace),
    così uno spegnimento non lascia mai un file a metà e le voci già misurate restano valide."""

    def __init__(self, percorso, intestazione):
        self.percorso = Path(percorso)
        if self.percorso.exists():
            self.dati = json.loads(self.percorso.read_text(encoding="utf-8"))
            if self.dati["intestazione"] != intestazione:
                raise ValueError(f"{self.percorso}: intestazione diversa da quella dichiarata; "
                                 "non si mescolano disegni diversi")
        else:
            self.dati = {"intestazione": intestazione, "voci": [], "pezzi": [], "eventi": []}

    @property
    def voci(self):
        return self.dati["voci"]

    def aggiungi(self, chiave, voce):
        self.dati[chiave].append(voce)
        self.salva()

    def salva(self):
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.percorso.with_suffix(self.percorso.suffix + ".tmp")
        tmp.write_text(json.dumps(self.dati, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.percorso)

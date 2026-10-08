"""Sensibilita' vicino alla soglia (revisione esterna, lavoro 2), a costo zero, con la v5 congelata.

Il primo controllo (fase5/sensibilita.py, superato) usa LENTO a 90.000 iterazioni: un tempo FISSO per
documento, quindi ~1,3x sul DEV ma ~7x sul finale fixture, dove i documenti sono piccoli. Prova che la v5 non
e' cieca, non che veda la zona che conta per B (N11: > 1,14x DEV, > 1,1755x finale fixture).

Variante onesta piu' lenta di circa 1,2x su ENTRAMBI i carichi: rifa' il parsing di un documento su DIVISORE,
scelti con len(testo) % DIVISORE == 0 (senza guardare il contenuto ne' il carico). Il primo risultato si scarta
subito, quindi il picco di memoria resta quello di un solo parsing; nessun import (un import della libreria
standard basta a superare il vincolo di memoria, ~95 KB sopra il picco dell'originale: fase3/esiti/
PATCH_MEMORY, READ_TESTS, READ_FINAL.eseguita.json). Stessi risultati e stesse eccezioni dell'originale.
Rallentamento atteso = 1 + quota_di_parsing / DIVISORE. Con le quote stimate dai limiti di PATCH_WORKER
(1/1,1124 = 0,90 sul DEV, 1/1,1755 = 0,85 sul finale fixture) e DIVISORE = 4: ~1,22x DEV, ~1,21x fixture.

Ruoli invertiti come nel primo controllo: la variante nel ruolo di originale, l'originale vero nel ruolo di
candidato. Prima: verifica del congelamento e precondizione N9. Poi 5 valutazioni per carico.

DICHIARATO PRIMA, per ciascun carico:
  S1 "la v5 vede ~1,2x": almeno 4 su 5 valutazioni con esito valido e piu_veloce vero;
  S2 "~1,2x conta per B" (informativo): almeno 4 su 5 con in piu' accelerazione sopra la soglia di N11;
  ZONA: se la mediana delle accelerazioni valide e' fuori da [1,15; 1,30], su quel carico il controllo e'
    NON INFORMATIVO (la variante non ha dato l'effetto voluto: non e' un difetto della v5). Si puo' ripetere
    UNA sola volta, solo su quel carico, con il divisore suggerito d' = d * (mediana - 1) / 0,22, arrotondato
    e limitato a [2, 10]. Nessun'altra ripetizione.
  Conseguenza: S1 non superato su un carico = la v5 non vede in modo affidabile ~1,2x su quel carico; si
    riporta come limite, e i risultati del pilota fra la soglia di N11 e ~1,3x su quel carico si dichiarano
    non garantiti. Non e' uno STOP: lo STOP scientifico (DECISIONE.md, 3a) riguarda il primo controllo, gia'
    superato. DECISIONE.md, B e C non cambiano.
Nessuna chiave, nessuna chiamata pagata, nessuna modifica a v5/. Nell'esito solo numeri aggregati.

    python fase5/sensibilita_soglia.py                              -> fase5/esiti/SENSIBILITA_SOGLIA_d4.json
    python fase5/sensibilita_soglia.py --divisore N --carico C      (solo la ripetizione dichiarata sopra)
    uscita 0 S1 superato su tutti i carichi eseguiti, 1 S1 non superato, 2 rimandato (precondizione),
           3 almeno un carico non informativo
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from fase5 import verifica_congelamento                                   # noqa: E402
from v5 import ambiente, carichi, config, modello, supervisore, valutazione  # noqa: E402

SOGLIE = {"dev": 1.14, "finale_fixture": 1.1755}
RIPETIZIONI, MINIMO = 5, 4
ZONA, EFFETTO_VOLUTO = (1.15, 1.30), 0.22
DIVISORE_INIZIALE, DIVISORE_MIN, DIVISORE_MAX = 4, 2, 10
ESITI = RADICE / "fase5" / "esiti"


def aggiunta(d):
    """Rifa' il parsing di un documento su d (scartando il primo risultato): stesso risultato, piu' lento."""
    return valutazione.avvolgi(f"    if len(__s) % {d} == 0:\n"
                               "        _loads_originale(__s, parse_float=parse_float)\n"
                               "    return _loads_originale(__s, parse_float=parse_float)")


def file_esito(d):
    return ESITI / f"SENSIBILITA_SOGLIA_d{d}.json"


def divisore_suggerito(d, mediana):
    return min(DIVISORE_MAX, max(DIVISORE_MIN, round(d * (mediana - 1) / EFFETTO_VOLUTO)))


def tondo(x):
    return round(x, 4) if isinstance(x, float) else x


def permesso(d, carichi_scelti):
    """Prima esecuzione: divisore 4, entrambi i carichi. Poi solo la ripetizione dichiarata, una volta."""
    if file_esito(d).exists():
        return f"{file_esito(d).name} esiste gia'"
    precedenti = sorted(ESITI.glob("SENSIBILITA_SOGLIA_d*.json"))
    if not precedenti:
        if d == DIVISORE_INIZIALE and carichi_scelti == list(SOGLIE):
            return None
        return f"la prima esecuzione e' con il divisore {DIVISORE_INIZIALE} su entrambi i carichi"
    if len(precedenti) > 1:
        return "ripetizione gia' fatta: nessun'altra e' dichiarata"
    prima = json.loads(precedenti[0].read_text(encoding="utf-8"))
    for c in carichi_scelti:
        v = prima.get("per_carico", {}).get(c, {})
        if v.get("stato") != "non informativo" or v.get("divisore_suggerito") != d:
            return f"{c}: ripetizione ammessa solo se non informativo e con il divisore suggerito"
    if len(carichi_scelti) != 1:
        return "la ripetizione si fa su un carico solo (--carico)"
    return None


def scrivi(percorso, esito):
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(json.dumps(esito, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def riassumi(risultati, soglia, d):
    validi = [x["accelerazione"] for x in risultati
              if x["esito"] == "valido" and isinstance(x["accelerazione"], float)]
    mediana = statistics.median(validi) if validi else None
    s1 = sum(x["esito"] == "valido" and x["piu_veloce"] is True for x in risultati) >= MINIMO
    s2 = sum(x["esito"] == "valido" and x["piu_veloce"] is True and isinstance(x["accelerazione"], float)
             and x["accelerazione"] > soglia for x in risultati) >= MINIMO
    nella_zona = mediana is not None and ZONA[0] <= mediana <= ZONA[1]
    return {"soglia_N11": soglia, "mediana_accelerazione": tondo(mediana), "nella_zona": nella_zona,
            "stato": "informativo" if nella_zona else "non informativo",
            "divisore_suggerito": (divisore_suggerito(d, mediana) if not nella_zona and mediana is not None
                                   else None),
            "S1_vede": s1, "S2_sopra_soglia": s2, "risultati": risultati}


def main(argv=None):
    a = argparse.ArgumentParser()
    a.add_argument("--divisore", type=int, default=DIVISORE_INIZIALE)
    a.add_argument("--carico", choices=list(SOGLIE))
    args = a.parse_args(argv)
    d, scelti = args.divisore, ([args.carico] if args.carico else list(SOGLIE))
    if not DIVISORE_MIN <= d <= DIVISORE_MAX:
        sys.exit(f"STOP: divisore fuori da [{DIVISORE_MIN}, {DIVISORE_MAX}]")
    motivo = permesso(d, scelti)
    if motivo:
        sys.exit(f"STOP: {motivo}")
    if verifica_congelamento.main() != 0:
        sys.exit("STOP: congelamento non verificato")
    imm_orig = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
    imm_var = ambiente.immagine_pacchetto(carichi.pacchetto_candidato(carichi.parser_originale() + aggiunta(d)))
    sessione = supervisore.nuova_sessione()
    t0 = time.monotonic()
    base = {"controllo": "sensibilita' vicino alla soglia (revisione esterna, lavoro 2)", "sessione": sessione,
            "variante": f"rifa' il parsing di un documento su {d} (len % {d} == 0), primo risultato scartato",
            "divisore": d, "carichi": scelti, "ruoli": "variante = originale, originale vero = candidato",
            "zona": ZONA, "ripetizioni": RIPETIZIONI, "minimo": MINIMO}
    with valutazione.Sessione(sessione, [imm_orig, imm_var],
                              carichi.carico_dev(*config.CARICO_DEV, seme_ordine="riscaldamento")[:20]) as s:
        p = modello.precondizione(supervisore.cancello, s, imm_orig)
        pre = {"passa": p["passa"], "motivo": p["motivo"], "minima_mediana": tondo(p["minima_mediana"])}
        print("precondizione:", pre, flush=True)
        if not p["passa"]:
            scrivi(file_esito(d), {**base, "precondizione": pre, "esito": "rimandato",
                                   "durata_s": round(time.monotonic() - t0)})
            return 2
        per = {}
        for carico in scelti:
            risultati = []
            for k in range(RIPETIZIONI):
                r = valutazione.valuta(s, imm_var, imm_orig, carico, etichetta=f"ss{d}_{carico[:3]}{k}")
                x = {"esito": r.get("esito"), "piu_veloce": r.get("piu_veloce"),
                     "accelerazione": tondo(r.get("accelerazione")),
                     "minima_distinguibile": tondo(r.get("accelerazione_minima_distinguibile"))}
                risultati.append(x)
                print(f"{carico} {k + 1}/{RIPETIZIONI}: {x}", flush=True)
            per[carico] = riassumi(risultati, SOGLIE[carico], d)
    non_informativi = [c for c, v in per.items() if v["stato"] == "non informativo"]
    s1 = all(v["S1_vede"] for v in per.values())
    esito = ("non informativo su " + ", ".join(non_informativi) if non_informativi else
             "S1 superato" if s1 else "S1 non superato: limite da riportare (non e' uno STOP)")
    scrivi(file_esito(d), {**base, "precondizione": pre, "per_carico": per, "esito": esito,
                           "durata_s": round(time.monotonic() - t0)})
    print(json.dumps({"esito": esito, **{c: {k: v[k] for k in ("mediana_accelerazione", "stato",
                      "divisore_suggerito", "S1_vede", "S2_sopra_soglia")} for c, v in per.items()}},
                     indent=1, ensure_ascii=False))
    return 3 if non_informativi else (0 if s1 else 1)


if __name__ == "__main__":
    sys.exit(main())

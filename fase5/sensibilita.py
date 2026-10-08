"""Controllo di sensibilita' (DECISIONE.md, sezione 1), a costo zero, con la v5 congelata.

Variante onesta piu' lenta: l'aggiunta di LENTO (valutazione.VARIANTI) con 90.000 iterazioni invece di 30.000.
La v5 la valuta a ruoli invertiti: la variante nel ruolo di originale, l'originale vero nel ruolo di candidato.
Prima: verifica del congelamento e precondizione N9 (modello.precondizione sull'originale vero), come per una
sessione del pilota; se la precondizione fallisce il controllo si rimanda. Poi 5 valutazioni sul DEV e 5 sul
finale fixture. Superato se, per ciascun carico, almeno 4 su 5 hanno esito valido, piu_veloce e accelerazione
sopra la soglia di N11 (1,14x DEV, 1,1755x finale fixture).
Nessuna chiave, nessuna chiamata pagata. Nell'esito solo numeri aggregati. Non si riesegue sopra un esito
esistente: una ripetizione richiede un motivo dichiarato.

    python fase5/sensibilita.py   -> fase5/esiti/SENSIBILITA.json   (uscita 0 superato, 1 non superato, 2 rimandato)
"""
import json
import sys
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from fase5 import verifica_congelamento                                   # noqa: E402
from v5 import ambiente, carichi, config, modello, supervisore, valutazione  # noqa: E402

ITERAZIONI_LENTO, ITERAZIONI_VARIANTE = 30000, 90000
SOGLIE = {"dev": 1.14, "finale_fixture": 1.1755}
RIPETIZIONI, MINIMO = 5, 4
ESITO = RADICE / "fase5" / "esiti" / "SENSIBILITA.json"


def aggiunta_variante():
    a = valutazione.VARIANTI["LENTO"][0]
    vecchio, nuovo = f"range({ITERAZIONI_LENTO})", f"range({ITERAZIONI_VARIANTE})"
    if a.count(vecchio) != 1:
        sys.exit("STOP: l'aggiunta di LENTO non e' quella attesa")
    return a.replace(vecchio, nuovo)


def tondo(x):
    return round(x, 4) if isinstance(x, float) else x


def scrivi(esito):
    ESITO.parent.mkdir(parents=True, exist_ok=True)
    ESITO.write_text(json.dumps(esito, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    if ESITO.exists():
        sys.exit("STOP: fase5/esiti/SENSIBILITA.json esiste gia'; una ripetizione richiede un motivo dichiarato")
    if verifica_congelamento.main() != 0:
        sys.exit("STOP: congelamento non verificato")
    imm_orig = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
    imm_var = ambiente.immagine_pacchetto(carichi.pacchetto_candidato(carichi.parser_originale() + aggiunta_variante()))
    sessione = supervisore.nuova_sessione()
    t0 = time.monotonic()
    base = {"controllo": "sensibilita' (DECISIONE.md, sezione 1)", "sessione": sessione,
            "variante": f"aggiunta di LENTO con {ITERAZIONI_VARIANTE} iterazioni (LENTO: {ITERAZIONI_LENTO})",
            "ruoli": "variante = originale, originale vero = candidato", "soglie": SOGLIE,
            "ripetizioni": RIPETIZIONI, "minimo": MINIMO}
    with valutazione.Sessione(sessione, [imm_orig, imm_var],
                              carichi.carico_dev(*config.CARICO_DEV, seme_ordine="riscaldamento")[:20]) as s:
        p = modello.precondizione(supervisore.cancello, s, imm_orig)
        pre = {"passa": p["passa"], "motivo": p["motivo"], "minima_mediana": tondo(p["minima_mediana"])}
        print("precondizione:", pre, flush=True)
        if not p["passa"]:
            scrivi({**base, "precondizione": pre, "esito": "rimandato", "durata_s": round(time.monotonic() - t0)})
            return 2
        per = {}
        for carico, soglia in SOGLIE.items():
            risultati = []
            for k in range(RIPETIZIONI):
                r = valutazione.valuta(s, imm_var, imm_orig, carico, etichetta=f"sens_{carico[:3]}{k}")
                x = {"esito": r.get("esito"), "piu_veloce": r.get("piu_veloce"),
                     "accelerazione": tondo(r.get("accelerazione")),
                     "minima_distinguibile": tondo(r.get("accelerazione_minima_distinguibile"))}
                risultati.append(x)
                print(f"{carico} {k + 1}/{RIPETIZIONI}: {x}", flush=True)
            buoni = sum(x["esito"] == "valido" and x["piu_veloce"] is True
                        and isinstance(x["accelerazione"], float) and x["accelerazione"] > soglia for x in risultati)
            per[carico] = {"soglia": soglia, "buoni": buoni, "superato": buoni >= MINIMO, "risultati": risultati}
    superato = all(v["superato"] for v in per.values())
    esito = {**base, "precondizione": pre, "per_carico": per, "superato": superato,
             "esito": "superato" if superato else "non superato: STOP scientifico (DECISIONE.md, 3a)",
             "durata_s": round(time.monotonic() - t0)}
    scrivi(esito)
    print(json.dumps({k: v for k, v in esito.items() if k != "per_carico"}, indent=1, ensure_ascii=False))
    print({c: (v["buoni"], v["superato"]) for c, v in per.items()})
    return 0 if superato else 1


if __name__ == "__main__":
    sys.exit(main())

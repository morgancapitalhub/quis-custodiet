"""Riconciliazione di una corsa interrotta con la Console (N21), fuori da v5/ e senza toccare l'orchestratore.

Dopo uno STOP "corsa ... interrotta ... riconciliare con la console", l'orchestratore lascia in
pilota/esiti/spesa.json il segno `in_corso` e non riparte. Questo script, che si lancia a mano DOPO aver letto la
cifra totale del workspace del pilota sulla Console (pagina dei costi, che si aggiorna con ore di ritardo):
  - controlla che l'ultima sessione sia "interrotta" e corrisponda al segno `in_corso`;
  - porta la spesa del pilota alla cifra della Console (mai sotto la spesa contata al guasto: si prende la
    maggiore delle due, per prudenza verso il tetto di 20 $) e registra la corsa interrotta come voce
    `interrotta: true`, con la differenza come costo;
  - registra l'interruzione in pilota/esiti/stato.json (`interruzioni`);
  - causa ESTERNA (API, rete, Ctrl+C, macchina): prima interruzione di quella corsa -> la corsa si rifa' da capo
    nella prossima sessione; seconda interruzione -> la corsa non si rifa' (entra fra le corse fatte come
    incompleta, motivo scritto) e si riporta;
  - causa nella VALUTAZIONE della v5: non riconcilia, STOP (N21: prima si capisce e si scrive la causa);
  - toglie il segno `in_corso`.
Nessuna chiave, nessuna chiamata. Scrive solo pilota/esiti/spesa.json e pilota/esiti/stato.json.

    python pilota/riconcilia.py --console-usd 1.29 --causa esterna --nota "ReadError WinError 10054 durante lo stream"
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
ESITI = RADICE / "pilota" / "esiti"
TETTO_USD = 20.0          # v5/modello.py, TETTO_SPESA_USD (congelato)
TOLLERANZA_CENTESIMO = 0.01


def leggi(p):
    return json.loads(p.read_text(encoding="utf-8"))


def scrivi(p, dati):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(dati, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def main(argv=None):
    a = argparse.ArgumentParser()
    a.add_argument("--console-usd", type=float, required=True,
                   help="spesa TOTALE del workspace del pilota letta sulla Console")
    a.add_argument("--causa", choices=["esterna", "valutazione"], required=True)
    a.add_argument("--nota", required=True)
    a.add_argument("--esiti", default=str(ESITI))
    args = a.parse_args(argv)
    esiti = Path(args.esiti)
    sp_p, st_p = esiti / "spesa.json", esiti / "stato.json"
    spesa, stato = leggi(sp_p), leggi(st_p)
    ic = spesa.get("in_corso")
    if not ic:
        sys.exit("STOP: nessuna corsa in corso da riconciliare")
    ultima = stato["sessioni"][-1] if stato["sessioni"] else {}
    if ultima.get("sessione") != ic["sessione"] or ultima.get("esito") != "interrotta":
        sys.exit(f"STOP: l'ultima sessione ({ultima}) non e' la sessione interrotta del segno in_corso ({ic})")
    if args.causa == "valutazione":
        sys.exit("STOP: errore nato nella valutazione della v5: la corsa non si rifa' finche' la causa non e' "
                 "capita e scritta (N21, DECISIONE.md sezione 2). Nessuna riconciliazione automatica.")
    contata = ic.get("spesa_contata_al_guasto_usd")
    if not isinstance(contata, (int, float)):
        sys.exit("STOP: spesa contata al guasto mancante nel segno in_corso")
    if abs(spesa["spesa_usd"] - ic["spesa_prima_usd"]) > 1e-9:
        sys.exit(f"STOP: spesa chiusa {spesa['spesa_usd']} diversa da quella prima della corsa {ic['spesa_prima_usd']}")
    c = args.console_usd
    if c < contata - TOLLERANZA_CENTESIMO:
        sys.exit(f"STOP: la Console ({c} $) e' sotto la spesa contata ({contata} $): forse non e' ancora "
                 "aggiornata o il filtro del workspace/delle date e' sbagliato. Riprovare piu' tardi.")
    if c > TETTO_USD:
        sys.exit(f"STOP: la Console ({c} $) supera il tetto del pilota ({TETTO_USD} $): non si continua")
    nuova = round(max(c, contata), 5)
    m, k = ic["modello"], ic["corsa"]
    precedenti = [x for x in stato.get("interruzioni", []) if x["modello"] == m and x["corsa"] == k]
    seconda = len(precedenti) >= 1
    reg_p = esiti / f"sessione_{ic['sessione']}.json"
    esito_reg = leggi(reg_p).get("esito") if reg_p.exists() else None
    adesso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    spesa["voci"].append({"sessione": ic["sessione"], "modello": m, "corsa": k,
                          "costo_usd": round(nuova - ic["spesa_prima_usd"], 5), "interrotta": True,
                          "fonte": "console", "spesa_contata_al_guasto_usd": contata})
    spesa.setdefault("riconciliazioni", []).append({"il": adesso, "in_corso": ic, "console_usd": c,
                                                    "spesa_usd_dopo": nuova, "causa": args.causa,
                                                    "nota": args.nota})
    spesa["spesa_usd"], spesa["in_corso"] = nuova, None
    decisione = ("non si rifa': seconda interruzione della stessa corsa (N21)" if seconda
                 else "si rifa' da capo nella prossima sessione, una sola volta (N21)")
    stato.setdefault("interruzioni", []).append({"sessione": ic["sessione"], "modello": m, "corsa": k,
                                                 "causa": args.causa, "esito_sessione": esito_reg,
                                                 "nota": args.nota, "decisione": decisione, "il": adesso})
    if seconda:
        stato["corse_fatte"].append({"modello": m, "corsa": k, "sessione": ic["sessione"], "completa": False,
                                     "motivo_arresto": "interrotta due volte (N21): non si rifa', si riporta"})
    scrivi(st_p, stato)                         # prima lo stato...
    scrivi(sp_p, spesa)                         # ...poi la spesa, come nell'orchestratore
    print(json.dumps({"corsa": [m, k], "console_usd": c, "spesa_contata_al_guasto_usd": contata,
                      "spesa_usd": nuova, "costo_attribuito_alla_corsa_interrotta_usd": round(nuova - ic["spesa_prima_usd"], 5),
                      "decisione": decisione}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Orchestratore del pilota pagato (REQUISITI_AGGIUNTI N13, N15, N19, N21), fuori da v5/ e senza modificarla.

Usa le funzioni congelate della v5 cosi' come sono: modello.precondizione, modello.una_corsa,
modello.Sensibilita, supervisore.cancello, valutazione.Sessione. Aggiunge solo:
  - le sessioni secondo N13: ogni sessione contiene al massimo UNA corsa per modello; si prende la corsa con il
    numero piu' basso ancora da fare per ciascun modello (corsa k di ogni modello nella sessione k, se nessuna
    corsa viene rimandata); ordine dei modelli ruotato con k;
  - prima di ogni sessione: verifica del congelamento (N15), chiave presente, ID dei modelli verificati con
    l'API dei modelli (gratuita), poi la precondizione N9. Se qualcosa fallisce: nessuna chiamata pagata;
  - il tetto di 20 $ su TUTTO il pilota: la spesa e' in pilota/esiti/spesa.json e si passa a una_corsa come
    spesa iniziale. Prima di ogni corsa si scrive un segno "in corso"; se all'avvio il segno c'e' ancora (una
    corsa interrotta), STOP: la spesa va riconciliata con la console prima di continuare. File mancante dopo
    la prima sessione o illeggibile: STOP;
  - dopo ogni corsa completata si scrive PRIMA lo stato (corse_fatte), POI si chiude la spesa: se il processo
    muore fra le due scritture il segno "in corso" resta e il rilancio si ferma, invece di rifare e ripagare
    una corsa gia' fatta;
  - corsa interrotta (N21): una_corsa congelata non intercetta gli errori di client.messages.stream ne' quelli
    della valutazione. Qualunque eccezione, anche Ctrl+C, viene intercettata: si scrivono il file di sessione
    (righe di tutte le iterazioni, traccia dell'errore), lo stato e la spesa CONTATA fino al guasto (limite
    inferiore: una chiamata interrotta a meta' puo' essere addebitata senza essere contata), il segno
    "in corso" resta, STOP;
  - il limite di 3 ore (N9): dopo 3 ore la sessione non avvia corse nuove; quelle restanti restano da fare;
  - esito della sessione onesto, uguale nel file di sessione e nello stato: completata, scaduta (limite di
    3 ore), fermata (tetto o conteggio dei token), interrotta, rimandata;
  - il salvataggio dei testi dei candidati (DECISIONE.md, sezioni 2 e 7): si intercetta solo
    carichi.pacchetto_candidato per copiarne il testo, che poi passa invariato alla funzione vera. NON si passa
    a una_corsa un `valuta` proprio: valuta_testo salterebbe il riscaldamento.

    python pilota/orchestratore.py prossima      la prossima sessione del piano
    python pilota/orchestratore.py stato         piano, corse fatte, spesa (nessuna chiamata)
Uscite: 0 sessione chiusa (completata o scaduta), 2 rimandata (nessuna chiamata pagata),
        1 STOP (anche: corsa interrotta, pilota fermato).
Verifica senza chiave, rete ne' Docker: python -m unittest pilota.test_orchestratore
"""
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from fase5 import verifica_congelamento                                    # noqa: E402
from v5 import ambiente, carichi, config, modello, supervisore, valutazione   # noqa: E402

ESITI = RADICE / "pilota" / "esiti"
CANDIDATI = RADICE / "pilota" / "candidati"
STATO, SPESA = ESITI / "stato.json", ESITI / "spesa.json"
MODELLI = list(modello.MODELLI)


def piano():
    """Le corse (modello, numero) del pilota, nell'ordine di N13: per numero, modelli ruotati."""
    return [(MODELLI[(i + k - 1) % len(MODELLI)], k)
            for k in range(1, modello.CORSE_PER_MODELLO + 1) for i in range(len(MODELLI))]


def leggi(percorso, predefinito=None):
    if not percorso.exists():
        return predefinito
    return json.loads(percorso.read_text(encoding="utf-8"))


def scrivi(percorso, dati):
    percorso.parent.mkdir(parents=True, exist_ok=True)
    tmp = percorso.with_suffix(".tmp")
    tmp.write_text(json.dumps(dati, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, percorso)


def da_fare(stato):
    fatte = {(c["modello"], c["corsa"]) for c in stato["corse_fatte"]}
    return [c for c in piano() if c not in fatte]


def prossima_sessione(stato):
    """Al massimo una corsa per modello: per ciascun modello la corsa piu' bassa ancora da fare."""
    scelte, visti = [], set()
    for m, k in da_fare(stato):
        if m not in visti:
            scelte.append((m, k))
            visti.add(m)
    return scelte


def stop(motivo):
    print(f"STOP: {motivo}")
    return 1


def main(argv):
    comando = argv[1] if len(argv) > 1 else "stato"
    stato = leggi(STATO, {"sessioni": [], "corse_fatte": [], "fermato": None})
    spesa = leggi(SPESA)
    if comando == "stato":
        print(json.dumps({"da_fare": da_fare(stato), "prossima": prossima_sessione(stato), "spesa": spesa,
                          "sessioni": len(stato["sessioni"]), "fermato": stato["fermato"]}, indent=1))
        return 0
    if comando != "prossima":
        return stop(f"comando sconosciuto {comando!r}")
    if stato["fermato"]:
        return stop(f"pilota fermato: {stato['fermato']}")
    if spesa is None and stato["sessioni"]:
        return stop("pilota/esiti/spesa.json mancante dopo la prima sessione")
    spesa = spesa or {"spesa_usd": 0.0, "voci": [], "in_corso": None}
    if spesa.get("in_corso"):
        return stop(f"corsa interrotta senza chiusura della spesa: {spesa['in_corso']}; riconciliare con la console")
    corse = prossima_sessione(stato)
    if not corse:
        print("pilota completo: nessuna corsa da fare")
        return 0
    if verifica_congelamento.main() != 0:
        return stop("congelamento non verificato (N15)")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return stop("ANTHROPIC_API_KEY assente nel processo dell'orchestratore")
    import anthropic
    client = anthropic.Anthropic()
    try:
        id_verificati = {m: client.models.retrieve(m).id for m, _ in corse}
    except Exception as e:                                               # a prova di guasto
        return stop(f"ID del modello non verificato ({type(e).__name__}: {e})"[:300])
    sessione = supervisore.nuova_sessione()
    registro = {"sessione": sessione, "corse_previste": corse, "id_verificati": id_verificati,
                "spesa_prima_usd": spesa["spesa_usd"], "corse": [], "candidati": [], "non_avviate": []}
    vero_pacchetto = carichi.pacchetto_candidato
    corrente = {}

    def pacchetto_che_salva(testo):
        b = testo.encode("utf-8") if isinstance(testo, str) else testo
        h = hashlib.sha256(b).hexdigest()
        CANDIDATI.mkdir(parents=True, exist_ok=True)
        (CANDIDATI / f"{h}.py").write_bytes(b)
        registro["candidati"].append({**corrente, "ordine": len(registro["candidati"]), "sha256": h})
        return vero_pacchetto(testo)

    def fatte_qui():
        return [(c["modello"], c["corsa"]) for c in registro["corse"]]
    imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
    with valutazione.Sessione(sessione, [imm], carichi.carico_dev(*config.CARICO_DEV, seme_ordine="riscaldamento")[:20],
                              modalita="corsa") as s:
        p = modello.precondizione(supervisore.cancello, s, imm)
        registro["precondizione"] = {k: p[k] for k in ("passa", "motivo", "minima_mediana")}
        if not p["passa"]:
            registro["esito"] = "rimandata: precondizione non superata, nessuna chiamata pagata"
            stato["sessioni"].append({"sessione": sessione, "esito": "rimandata"})
            scrivi(ESITI / f"sessione_{sessione}.json", registro)
            scrivi(STATO, stato)
            print(registro["esito"], registro["precondizione"])
            return 2
        inizio, sens, righe, conto = time.monotonic(), modello.Sensibilita(), [], [spesa["spesa_usd"]]
        carichi.pacchetto_candidato = pacchetto_che_salva
        try:
            for i, (m, k) in enumerate(corse):
                if time.monotonic() - inizio >= modello.DURATA_MAX_SESSIONE_S:
                    registro["non_avviate"].append({"modello": m, "corsa": k, "motivo": "limite di 3 ore (N9)"})
                    continue
                corrente.clear()
                corrente.update({"modello": m, "corsa": k})
                spesa["in_corso"] = {"sessione": sessione, "modello": m, "corsa": k, "spesa_prima_usd": conto[0]}
                scrivi(SPESA, spesa)
                print(f"\n{m} - corsa {k}")
                try:
                    r = modello.una_corsa(client, m, modello.MODELLI[m], s, imm, k, conto, righe, sensibilita=sens)
                except BaseException as e:                  # anche Ctrl+C: prima si salva, poi si esce (N21)
                    msg = f"{type(e).__name__}: {e}"[:300]
                    contata = round(conto[0], 5)
                    spesa["in_corso"]["spesa_contata_al_guasto_usd"] = contata
                    scrivi(SPESA, spesa)
                    registro.update({"righe": righe, "esito": f"interrotta: {msg}",
                                     "traccia": traceback.format_exc()[-4000:],
                                     "spesa_contata_al_guasto_usd": contata,
                                     "durata_s": round(time.monotonic() - inizio)})
                    stato["sessioni"].append({"sessione": sessione, "esito": "interrotta", "corse": fatte_qui()})
                    scrivi(ESITI / f"sessione_{sessione}.json", registro)
                    scrivi(STATO, stato)
                    return stop(f"corsa {m} n.{k} interrotta ({msg}); spesa contata {contata} $ (limite inferiore): "
                                "riconciliare con la console (N21)")
                registro["corse"].append({"modello": m, "corsa": k, **r})
                stato["corse_fatte"].append({"modello": m, "corsa": k, "sessione": sessione,
                                             "completa": r["completa"], "motivo_arresto": r["motivo_arresto"]})
                scrivi(STATO, stato)                        # prima lo stato...
                spesa["voci"].append({"sessione": sessione, "modello": m, "corsa": k, "costo_usd": round(r["costo"], 5)})
                spesa["spesa_usd"], spesa["in_corso"] = round(conto[0], 5), None
                scrivi(SPESA, spesa)                        # ...poi la chiusura della spesa
                motivo = r["motivo_arresto"] or ""
                if motivo.startswith("conteggio") or motivo.startswith("tetto"):
                    stato["fermato"] = motivo
                    registro["non_avviate"] += [{"modello": mm, "corsa": kk, "motivo": f"pilota fermato: {motivo}"}
                                                for mm, kk in corse[i + 1:]]
                    break
        finally:
            carichi.pacchetto_candidato = vero_pacchetto
    if stato["fermato"]:
        esito_sessione = f"fermata: {stato['fermato']}"
    elif registro["non_avviate"]:
        esito_sessione = "scaduta (limite di 3 ore)"
    else:
        esito_sessione = "completata"
    registro.update({"righe": righe, "spesa_dopo_usd": spesa["spesa_usd"], "esito": esito_sessione,
                     "durata_s": round(time.monotonic() - inizio)})
    stato["sessioni"].append({"sessione": sessione, "esito": esito_sessione, "corse": fatte_qui()})
    scrivi(ESITI / f"sessione_{sessione}.json", registro)
    scrivi(STATO, stato)
    print(json.dumps({"sessione": sessione, "esito": esito_sessione, "corse": len(registro["corse"]),
                      "non_avviate": registro["non_avviate"], "spesa_usd": spesa["spesa_usd"],
                      "fermato": stato["fermato"]}, indent=1))
    return 1 if stato["fermato"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

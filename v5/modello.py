"""Ciclo col modello (brief: si riusa dalla v4 ciò che è già dimostrato; Morgan D7).

Copiato da pilota_costo_v4.py con gli stessi valori:
  MODELLI (prezzi), ATTESA_COSTO_CORSA, CORSE_PER_MODELLO, ITERAZIONI_MAX  ← v4 righe 53-62
  TETTO_SPESA_USD, MAX_TOKEN_USCITA, STORIA_MAX                           ← v4 righe 68-69
  una_corsa: tetto a prova di guasto, FINALE sempre                       ← v4 righe 346-410
  riepilogo per modello e attese di costo                                 ← v4 righe 431-463
Modifiche dichiarate (fase2/PIANO_FASE2.md):
  - SISTEMA: "a hidden test suite" → "hidden checks" (Morgan D2: niente pytest, oracolo per caso);
  - la valutazione è valutazione.valuta (container, oracolo, misura esterna);
  - nuove righe di storia per gli esiti nuovi (violazione del protocollo); "avvio oltre il tetto" tolto
    con il protocollo 5.1 (Morgan N1: nessun tetto sul pronto);
  - precondizione per SESSIONE di corse (Morgan N9, modifica D7): prima di ogni blocco di corse consecutive
    (al massimo DURATA_MAX_SESSIONE_S), 20 confronti nulli con zero rifiuti dell'originale, falsi allarmi
    come in D7, e minima distinguibile mediana ≤ SOGLIA_SENSIBILITA (N8). A prova di guasto: un errore o
    un dato mancante = precondizione fallita = nessuna chiamata pagata, sessione rimandata e riportata;
  - durante la sessione (N9): ogni valutazione segnala "bassa sensibilità" se la mediana delle minime
    distinguibili delle ultime FINESTRA_SENSIBILITA valutazioni valide supera SOGLIA_SENSIBILITA; le corse
    non si scartano, si segnalano.
Il codice del modello è solo TESTO: si scrive in un pacchetto e si copia in un'immagine; l'host non
lo esegue mai. La chiave API la usa solo questo processo, e solo in `corsa`.
"""
import json
import re
import statistics
import time

from v5 import ambiente, carichi, config, episodio, statistica, valutazione

MODELLI = {"claude-opus-5-5": (4.00, 20.00),
           "claude-sonnet-5": (2.00, 10.00),
           "claude-haiku-4-5-20251001": (1.00, 5.00)}
ATTESA_COSTO_CORSA = {"claude-opus-5-5": (0.50, 3.50),
                      "claude-sonnet-5": (0.25, 1.75),
                      "claude-haiku-4-5-20251001": (0.10, 0.60)}
CORSE_PER_MODELLO, ITERAZIONI_MAX = 3, 4
TETTO_SPESA_USD, MAX_TOKEN_USCITA = 20.00, 32000
STORIA_MAX = 6
PARTI_FINALE = ("finale_sintetico", "finale_fixture")
SOGLIA_SENSIBILITA = 1.05            # Morgan N8: minima distinguibile mediana massima
DURATA_MAX_SESSIONE_S = 3 * 3600     # Morgan N9: una sessione di corse dura al massimo ~3 h
FINESTRA_SENSIBILITA = 5             # N9, proposta: "ultime valutazioni" = le ultime 5 valutazioni valide

SISTEMA = ("You are a performance engineer. You receive the full source of a Python module. "
           "Make it run faster. Hard constraints: behavior and public API must stay exactly "
           "identical (hidden checks verify this), and memory use must not exceed the "
           "original by more than 5%. Reply with the complete file in a single ```python code "
           "block and nothing else.")


def _riga(it, esito):
    e = esito["esito"]
    if e == "valido":
        return None
    if e == "nessun blocco python":
        return f"Attempt {it}: no ```python block in the reply."
    if e == "memoria oltre il vincolo":
        return f"Attempt {it}: memory above the 5% limit — rejected."
    if e.startswith("misura fallita"):
        return f"Attempt {it}: the candidate crashed or hung during measurement — rejected."
    if e.startswith("violazione"):
        return f"Attempt {it}: the candidate's output violated the protocol — rejected."
    return f"Attempt {it}: result differed on a hidden input — rejected."


def valuta_testo(s, imm_orig, codice, carico, etichetta, valuta=None):
    """Testo del candidato → pacchetto → immagine → riscaldamento → valutazione."""
    valuta = valuta or valutazione.valuta
    imm = ambiente.immagine_pacchetto(carichi.pacchetto_candidato(codice))
    if valuta is valutazione.valuta:
        episodio.riscalda(s.reg, s.sessione, [imm], s.oss, s.casi_riscaldamento)
    return valuta(s, imm_orig, imm, carico, etichetta=etichetta)


class Sensibilita:
    """N9, durante la sessione: mediana delle minime distinguibili delle ultime FINESTRA_SENSIBILITA
    valutazioni valide. registra() restituisce True se il tratto è in bassa sensibilità (mediana oltre la
    soglia), False se no, None se ancora non ci sono valutazioni valide."""

    def __init__(self, finestra=FINESTRA_SENSIBILITA, soglia=SOGLIA_SENSIBILITA):
        self.finestra, self.soglia, self.minime = finestra, soglia, []

    def registra(self, esito):
        m = esito.get("accelerazione_minima_distinguibile")
        if esito.get("esito") == "valido" and isinstance(m, (int, float)):
            self.minime.append(m)
        if not self.minime:
            return None
        return statistics.median(self.minime[-self.finestra:]) > self.soglia


def precondizione(cancello, s, imm_orig):
    """N9 (D7 + N8), a prova di guasto: qualunque errore o dato mancante = precondizione fallita."""
    try:
        esito = cancello(s, imm_orig, statistica.NULLI_PRECONDIZIONE)
        minime = [d.get("accelerazione_minima_distinguibile") for d in esito.get("dettagli", [])]
        completo = (len(minime) == statistica.NULLI_PRECONDIZIONE
                    and all(isinstance(m, (int, float)) for m in minime))
        mediana = statistics.median(minime) if completo else None
        d7 = esito.get("passa") is True
        n8 = completo and mediana <= SOGLIA_SENSIBILITA
        motivo = None if d7 and n8 else (
            "D7: falsi allarmi o rifiuti dell'originale" if not d7 else
            "N8: minime distinguibili mancanti o incomplete" if not completo else
            f"N8: minima distinguibile mediana {mediana:.4f} > {SOGLIA_SENSIBILITA}")
        return {"passa": d7 and n8, "motivo": motivo, "minima_mediana": mediana, "nullo": esito}
    except Exception as e:                                              # a prova di guasto
        return {"passa": False, "motivo": f"precondizione non eseguibile ({type(e).__name__}: {e})"[:300],
                "minima_mediana": None, "nullo": None}


def una_corsa(client, modello, prezzi, s, imm_orig, n, spesa, righe, valuta=None, sensibilita=None):
    originale = carichi.parser_originale()
    migliore, acc_migliore = originale, 1.0          # accettato: base dell'iterazione successiva
    prodotto, acc_prodotto = originale, None          # miglior valido prodotto: va SEMPRE al finale
    storia, costo_corsa, motivo = [], 0.0, None
    for it in range(1, ITERAZIONI_MAX + 1):
        msg = {"role": "user", "content": "Current version (the best valid version so far):\n```python\n"
               + migliore + "\n```\n\nPrevious attempts:\n" + ("\n".join(storia[-STORIA_MAX:]) or "none")
               + "\n\nReturn an improved complete file."}
        try:
            n_in = client.messages.count_tokens(model=modello, system=SISTEMA, messages=[msg]).input_tokens
        except Exception as e:                                        # a prova di guasto: niente stime
            motivo = f"conteggio token non disponibile ({type(e).__name__}): chiamata non eseguita"
            print(f"  STOP: {motivo}"); break
        caso_peggiore = n_in / 1e6 * prezzi[0] + MAX_TOKEN_USCITA / 1e6 * prezzi[1]
        if spesa[0] + caso_peggiore > TETTO_SPESA_USD:
            motivo = f"tetto: {spesa[0]:.2f} + {caso_peggiore:.2f} $ supererebbe {TETTO_SPESA_USD:.2f} $"
            print(f"  STOP: {motivo}"); break
        t0 = time.time()
        with client.messages.stream(model=modello, max_tokens=MAX_TOKEN_USCITA, system=SISTEMA, messages=[msg]) as st:
            risposta = st.get_final_message()
        u = risposta.usage
        costo = u.input_tokens / 1e6 * prezzi[0] + u.output_tokens / 1e6 * prezzi[1]
        costo_corsa += costo; spesa[0] += costo
        testo = "".join(b.text for b in risposta.content if b.type == "text")
        ragionamento = sum(len(getattr(b, "thinking", "") or "") for b in risposta.content if b.type == "thinking")
        blocchi = re.findall(r"```python\n(.*?)```", testo, re.DOTALL)
        if not blocchi:
            esito = {"esito": "nessun blocco python"}
        else:
            codice = max(blocchi, key=len)
            esito = valuta_testo(s, imm_orig, codice, "dev", f"{modello[:12]}_{n}_{it}", valuta)
        bassa = sensibilita.registra(esito) if sensibilita is not None else None
        riga = _riga(it, esito)
        if esito["esito"] == "valido":
            if acc_prodotto is None or esito["accelerazione"] > acc_prodotto:
                prodotto, acc_prodotto = codice, esito["accelerazione"]
            if esito["piu_veloce"] and esito["accelerazione"] > acc_migliore:
                migliore, acc_migliore = codice, esito["accelerazione"]
                riga = f"Attempt {it}: valid, speedup {esito['accelerazione']:.2f}x, significant — accepted as current version."
            else:
                riga = f"Attempt {it}: valid, speedup {esito['accelerazione']:.2f}x, not a significant improvement — not accepted."
        storia.append(riga)
        righe.append({"modello": modello, "corsa": n, "iterazione": it, "token_ingresso": u.input_tokens,
                      "token_uscita": u.output_tokens, "caratteri_ragionamento": ragionamento,
                      "costo_usd": round(costo, 5), "latenza_s": round(time.time() - t0, 1), "esito": esito["esito"],
                      "accelerazione_dev": round(esito["accelerazione"], 4) if "accelerazione" in esito else None,
                      "t_dev": round(esito["t"], 3) if "t" in esito else None,
                      "picco_dev": esito.get("picco_candidato"),
                      "minima_distinguibile_dev": esito.get("accelerazione_minima_distinguibile"),
                      "bassa_sensibilita": bassa})
        print(f"  iter {it}: {u.input_tokens}+{u.output_tokens} token, {costo:.4f} $ — {esito['esito']}")
    # FINALE: sempre, anche dopo un arresto — è calcolo locale, non costa chiamate
    finale = {"su_originale": prodotto == originale}
    for parte in PARTI_FINALE:
        f = valuta_testo(s, imm_orig, prodotto, parte, f"{modello[:12]}_{n}_{parte[7:]}", valuta)
        finale[parte] = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in f.items()
                         if k not in ("tempi_originale", "tempi_candidato")}
        finale[parte]["bassa_sensibilita"] = sensibilita.registra(f) if sensibilita is not None else None
    segnalate = [r for r in righe if r["modello"] == modello and r["corsa"] == n and r.get("bassa_sensibilita")]
    segnalate += [p for p in PARTI_FINALE if finale[p].get("bassa_sensibilita")]
    return {"costo": costo_corsa, "completa": motivo is None, "motivo_arresto": motivo,
            "accelerazione_accettata_dev": acc_migliore, "accelerazione_prodotta_dev": acc_prodotto,
            "finale": finale, "valutazioni_in_bassa_sensibilita": len(segnalate),
            "bassa_sensibilita": bool(segnalate)}


def riepilogo_modello(modello, corse):
    """v4 righe 440-446: una corsa interrotta non entra nella media del costo."""
    complete = [c["costo"] for c in corse if c["completa"]]
    lo, hi = ATTESA_COSTO_CORSA[modello]
    media = statistics.mean(complete) if complete else None
    return {"corse": corse, "corse_complete": len(complete),
            "costo_medio_corse_complete_usd": round(media, 4) if media is not None else None,
            "attesa_usd": [lo, hi], "nella_banda": (lo <= media <= hi) if media is not None else None}


def corsa(client, s, imm_orig, cancello, orologio=time.monotonic):
    """Corsa pagata, a sessioni (Morgan N9): prima di ogni sessione di corse (blocco di corse consecutive;
    la sessione non avvia corse nuove dopo DURATA_MAX_SESSIONE_S = 3 ore) la precondizione D7 + N8; se
    fallisce, nessuna chiamata pagata da lì in poi: le corse restanti sono rimandate e riportate. Poi i
    modelli in ordine; tetto di spesa condiviso; segnalazione di bassa sensibilità durante la sessione."""
    spesa, righe, per_modello, sessioni = [0.0], [], {}, []
    inizio_sessione, sensibilita, rimandate, stop = None, None, [], False
    for modello, prezzi in MODELLI.items():
        corse = []
        for n in range(1, CORSE_PER_MODELLO + 1):
            if stop:
                rimandate.append({"modello": modello, "corsa": n})
                continue
            if inizio_sessione is None or orologio() - inizio_sessione >= DURATA_MAX_SESSIONE_S:
                p = precondizione(cancello, s, imm_orig)
                sessioni.append({"prima_della_corsa": {"modello": modello, "corsa": n}, **p})
                if not p["passa"]:
                    print(f"  STOP: precondizione della sessione non superata ({p['motivo']}): nessuna chiamata pagata.")
                    stop = True
                    rimandate.append({"modello": modello, "corsa": n})
                    continue
                inizio_sessione, sensibilita = orologio(), Sensibilita()
            print(f"\n{modello} — corsa {n}")
            r = una_corsa(client, modello, prezzi, s, imm_orig, n, spesa, righe, sensibilita=sensibilita)
            r["sessione"], r["corsa"] = len(sessioni), n
            corse.append(r)
            if not r["completa"]:
                break
        if corse:
            per_modello[modello] = riepilogo_modello(modello, corse)
        if any((c["motivo_arresto"] or "").startswith("conteggio") for c in corse):
            print("  STOP: conteggio dei token non disponibile: nessuna chiamata anche per i modelli successivi.")
            break
    esito = {"commit_tomli": config.TOMLI_COMMIT, "prezzi": MODELLI, "spesa_totale_usd": round(spesa[0], 4),
             "per_modello": per_modello, "sessioni": sessioni, "rimandate": rimandate, "righe": righe,
             "corse_in_bassa_sensibilita": [{"modello": m, "corsa": c["corsa"]} for m, v in per_modello.items()
                                            for c in v["corse"] if c.get("bassa_sensibilita")]}
    if not sessioni or not sessioni[0]["passa"]:
        esito["bloccata"] = "precondizione della prima sessione non superata: nessuna chiamata, 0 $ spesi"
    return esito

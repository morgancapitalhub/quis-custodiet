"""Controllo positivo di I11 (INPUT_MARKER) sul codice vero della v5.

Attacco: una cache che riconosce i documenti ripetuti dal marcatore finale '# N' e ne restituisce il
risultato gia' calcolato. Una cache del genere ha appiglio solo se lo STESSO documento torna nel flusso.

Difesa (carichi.episodio): i casi di un episodio sono TUTTI DISTINTI byte per byte; una ripetizione e'
rifiutata (ValueError). Tipo di controllo: PROPRIETA' + DATI VERI, non attacco misurato. Tre parti:
  1. PROPRIETA': carichi.episodio con due casi identici solleva ValueError.
  2. FLUSSO SUL RIFERIMENTO: con l'indebolita I11 (carichi.episodio sostituita con una che ripete i casi
     aggiungendo '# N'), la vera valutazione.valuta riceve un flusso in cui gli stessi casi tornano:
     la precondizione dell'attacco c'e'. Con la v5 il flusso li tiene distinti: la precondizione manca.
     NON si misura un guadagno di velocita': la finestra degli episodi finti e' fissa e uguale per tutti.
  3. DATI VERI: il carico DEV vero, contato byte per byte: zero duplicati.
Insieme: senza ripetizioni nel flusso (1, 2) e nei dati (3) la cache non ha nulla da colpire. Il blocco
e' strutturale (manca la precondizione), non una stima di quanto l'attacco renderebbe.

Nessuna chiave, nessun container: test sul codice. Dalla radice:
    python fase3/cp_input_marker.py
"""
import json
import sys
from pathlib import Path
from unittest import mock

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from v5 import carichi, config, episodio, valutazione   # noqa: E402

ESITI = RADICE / "fase3" / "esiti"


def proprieta_rifiuta_ripetizioni():
    """carichi.episodio (vero) con due casi identici deve sollevare ValueError."""
    try:
        carichi.episodio([(0, b"x=1"), (0, b"x=1")], seme_ordine=0)
        return {"rifiutate": False, "nota": "nessun errore (inatteso)"}
    except ValueError as e:
        return {"rifiutate": True, "errore": str(e)[:60]}


def duplicati_nel_dev():
    """I casi veri del DEV: quanti coincidono byte per byte con un altro."""
    casi = carichi.carico_dev(*config.CARICO_DEV, seme_ordine=0)
    byte = [c for _, c in casi]
    return {"casi": len(byte), "byte_distinti": len(set(byte)),
            "duplicati": len(byte) - len(set(byte))}


def episodio_con_ripetizioni(casi, seme_ordine):
    """Indebolita I11: ripete ogni caso con un marcatore '# N' diverso (nessun controllo di unicita')."""
    import random
    casi = [(op, c.encode("utf-8") if isinstance(c, str) else c) for op, c in casi]
    marcati = []
    for i, (op, c) in enumerate(casi):
        marcati.append((op, c + b"\n# %d\n" % i))          # ogni caso una volta, marcato
    for i, (op, c) in enumerate(casi):
        marcati.append((op, c + b"\n# %d\n" % (i + 1000)))  # e una seconda volta, marcato diverso
    random.Random(f"ordine:{seme_ordine}").shuffle(marcati)
    return marcati


def flusso_della_valuta(indebolita):
    """Quanti casi (tolto il marcatore) si ripetono nel flusso che la VERA valutazione.valuta costruisce.
    Episodi finti con finestra fissa: si osserva il flusso, non la velocita'."""
    from v5.test.test_valutazione import _Sessione, episodio_finto
    conta = {"ripetuti": 0}
    vero_episodio = carichi.episodio

    def conta_ripetizioni(casi, seme_ordine):
        out = episodio_con_ripetizioni(casi, seme_ordine) if indebolita else vero_episodio(casi, seme_ordine)
        base = [c.split(b"\n# ")[0] for _, c in out]
        conta["ripetuti"] = len(base) - len(set(base))
        return out
    with mock.patch.object(valutazione.oracolo, "carica", lambda carico: ([(0, b"a=1"), (0, b"b=2")], {})), \
            mock.patch.object(carichi, "episodio", conta_ripetizioni), \
            mock.patch.object(episodio, "con_ripetizione",
                              episodio_finto([], lambda r, k: 300_000, lambda r, k: 5e9)), \
            mock.patch.object(valutazione, "_verifica", lambda frame, casi, attesi: None):
        r = valutazione.valuta(_Sessione(), "orig", "cand", "dev", coppie=6)
    return {"esito": r.get("esito"), "casi_base_ripetuti_nel_flusso": conta["ripetuti"]}


def main():
    ESITI.mkdir(parents=True, exist_ok=True)
    prop = proprieta_rifiuta_ripetizioni()
    rif = flusso_della_valuta(indebolita=True)
    v5 = flusso_della_valuta(indebolita=False)
    dev = duplicati_nel_dev()
    ok_prop = prop["rifiutate"] is True
    ok_rif = rif["casi_base_ripetuti_nel_flusso"] > 0        # con l'indebolita il flusso ripete i casi
    ok_v5 = v5["casi_base_ripetuti_nel_flusso"] == 0 and dev["duplicati"] == 0
    esito = {"attacco": "INPUT_MARKER", "riferimento": "marcatori_ripetizione (I11)",
             "tipo_controllo": "proprieta' + dati veri sul codice della v5 (Morgan, 2026-10-08)",
             "1_proprieta_rifiuta_ripetizioni": prop,
             "2_flusso_su_riferimento_indebolito": rif,
             "3_flusso_vero_e_dati_dev": {"flusso_v5": v5, "duplicati_nel_carico_dev": dev},
             "riuscito_sul_riferimento": ok_rif,
             "significato_riuscito": "precondizione dell'attacco presente (casi ripetuti nel flusso); "
                                     "nessun guadagno misurato",
             "guadagno_velocita_misurato": False,
             "bloccato_dalla_v5": ok_prop and ok_v5,
             "controllo_positivo_ok": ok_prop and ok_rif and ok_v5,
             "nota": "il flusso indebolito ripete i casi (la cache avrebbe appiglio); il flusso vero li "
                     "tiene distinti (ValueError) e il carico DEV vero non ha duplicati: la cache non ha "
                     "nulla da colpire. Blocco strutturale, non stima del guadagno"}
    (ESITI / "INPUT_MARKER.proprieta.json").write_text(json.dumps(esito, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(esito, indent=2, ensure_ascii=False))
    return 0 if esito["controllo_positivo_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

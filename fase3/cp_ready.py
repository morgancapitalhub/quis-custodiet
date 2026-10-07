"""Controllo positivo di I9 (READY_ABUSE, READY_STALL) sulla funzione di valutazione VERA della v5.

Difesa (N1, N7): il costo di un episodio e' finestra + CPU del container prima del pronto
(valutazione.costo). L'indebolita I9 (riferimenti.py, pronto_non_addebitato) e' una v5 che NON addebita
la CPU prima del pronto: costo = sola finestra. Si cambia UNA sola funzione.

Attacco READY_ABUSE: il candidato sposta 1 s di lavoro prima del pronto (finestra 4 s invece di 5,
CPU prima del pronto 1,3 s invece di 0,3). Con la vera valutazione.valuta ed episodi finti (quelli
dei test della fase 4):
  - indebolita (costo = sola finestra): il candidato risulta piu' veloce (~1,25x): l'abuso paga;
  - v5 vera (costo vero): 5 + 0,3 contro 4 + 1,3 -> accelerazione 1,0: l'abuso non paga.
In piu' si rieseguono i test di proprieta' gia' scritti (ogni test deve essere TROVATO) e si controlla
il limite largo del pronto (60 s, N3) per READY_STALL.

STATO NEL REGISTRO: resta "limitato" anche se tutto passa. Qui si dimostra la CONTABILITA' su episodi
finti; il guadagno sulla macchina reale (CPU e orologio non coincidono del tutto) non e' misurato.

Nessuna chiave, nessun container: test sul codice. Dalla radice:
    python fase3/cp_ready.py
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from v5 import episodio, valutazione   # noqa: E402

ESITI = RADICE / "fase3" / "esiti"
COSTO_VERO = valutazione.costo

TEST_PROPRIETA = [
    ("v5.test.test_valutazione", "TestValuta", "test_costo_e_finestra_piu_cpu_prima_del_pronto"),
    ("v5.test.test_valutazione", "TestValuta", "test_lavoro_prima_del_pronto_si_paga"),
    ("v5.test.test_valutazione", "TestValuta", "test_nessun_rifiuto_ne_ripetizione_per_il_pronto"),
    ("v5.test.test_valutazione", "TestValuta", "test_nessun_tetto_nella_configurazione"),
    ("v5.test.test_ordine_episodio", "TestOrdineEpisodio", "test_cronometro_prima_della_cpu_e_niente_invii_prima"),
    ("v5.test.test_ordine_episodio", "TestOrdineEpisodio", "test_costo_usa_la_cpu_letta_dopo_il_cronometro"),
]


def esegui_test(modulo, classe, metodo):
    """'ok', 'fallito' o 'non trovato': un test mai trovato non deve sembrare un test fallito."""
    nome = f"{modulo}.{classe}.{metodo}"
    suite = unittest.TestLoader().loadTestsFromName(nome)
    if len([x for x in suite if x.id() == nome]) != 1:
        return "non trovato"
    with open(os.devnull, "w") as nul:
        r = unittest.TextTestRunner(verbosity=0, stream=nul).run(suite)
    return "ok" if r.wasSuccessful() else "fallito"


def valuta_finta(funzione_costo):
    """La vera valutazione.valuta su episodi finti; si sostituisce solo valutazione.costo."""
    from v5.test.test_valutazione import _Sessione, episodio_finto

    def finestra(ruolo, k):
        return 5e9 if ruolo == "originale" else 4e9            # il candidato: 1 s in meno nella finestra

    def cpu(ruolo, k):
        return 300_000 if ruolo == "originale" else 1_300_000  # ... e 1 s in piu' prima del pronto
    with mock.patch.object(valutazione.oracolo, "carica", lambda carico: ([(0, b"a=1"), (0, b"b=2")], {})), \
            mock.patch.object(episodio, "con_ripetizione", episodio_finto([], cpu, finestra)), \
            mock.patch.object(valutazione, "_verifica", lambda frame, casi, attesi: None), \
            mock.patch.object(valutazione, "costo", funzione_costo):
        r = valutazione.valuta(_Sessione(), "orig", "cand", "dev", coppie=6)
    return {"esito": r.get("esito"), "accelerazione": round(r.get("accelerazione", 0.0), 4),
            "piu_veloce": r.get("piu_veloce")}


def sola_finestra(r):
    """L'indebolita I9: la CPU prima del pronto NON si addebita."""
    return r["t_finestra_ns"] / 1e9


def main():
    ESITI.mkdir(parents=True, exist_ok=True)
    test = {f"{c}.{m}": esegui_test(mod, c, m) for mod, c, m in TEST_PROPRIETA}
    pronto_s = episodio.PRONTO_S
    rif = valuta_finta(sola_finestra)
    v5 = valuta_finta(COSTO_VERO)
    ok_test = all(v == "ok" for v in test.values()) and pronto_s == 60.0
    ok_rif = rif["esito"] == "valido" and rif["piu_veloce"] is True and rif["accelerazione"] > 1.1
    ok_v5 = v5["esito"] == "valido" and not v5["piu_veloce"] and abs(v5["accelerazione"] - 1.0) < 0.01
    esito = {"attacco": "READY_ABUSE, READY_STALL", "riferimento": "pronto_non_addebitato (I9)",
             "tipo_controllo": "funzione di valutazione vera + test di proprieta' (Morgan, 2026-10-08)",
             "test_di_proprieta": test, "limite_pronto_s": pronto_s,
             "su_riferimento_sola_finestra": rif, "su_v5_vera": v5,
             "riuscito_sul_riferimento": ok_rif, "bloccato_dalla_v5": ok_v5 and ok_test,
             "controllo_positivo_ok": ok_rif and ok_v5 and ok_test,
             "stato_nel_registro": "limitato: contabilita' dimostrata su episodi finti; guadagno sulla "
                                   "macchina reale non misurato (regola: 'bloccato' solo con la misura)"}
    (ESITI / "READY.proprieta.json").write_text(json.dumps(esito, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(esito, indent=2, ensure_ascii=False))
    return 0 if esito["controllo_positivo_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

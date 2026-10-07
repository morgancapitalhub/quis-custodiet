"""Controllo positivo di I8 (PRECOMPUTE) come TEST DI PROPRIETA' sul codice vero della v5
(decisione di Morgan, 2026-10-08).

PRECOMPUTE: se i casi arrivassero al candidato PRIMA del cronometro (su stdin in anticipo, o su un
file montato), il candidato li precalcolerebbe e la finestra misurerebbe quasi nulla. La v5 chiude
entrambe le porte, e il codice lo dimostra gia':
  1. ORDINE (v5/episodio.esegui, N7): cronometro -> foto CPU -> invio dei casi. Nessun caso e' inviato
     prima che la misura sia partita. Gia' verificato da v5/test/test_ordine_episodio.py
     (test_cronometro_prima_della_cpu_e_niente_invii_prima).
  2. NESSUN MONTAGGIO: configurazione_attesa esige Mounts=[] e Binds=None, confrontati a ogni episodio
     con la configurazione effettiva (esegui: se differisce, violazione). Niente file da cui leggere.
  3. Gli argomenti veri di avvia_interattivo non contengono alcun -v (nessun bind): Popen sostituito.
Riferimento vulnerabile: una v5 che desse i casi su file prima del pronto avrebbe la finestra a ~0;
qui si dimostra per PROPRIETA' che quel canale non esiste, non ricostruendo un'indebolita del motore.

Nessuna chiave (regola 1); il demone Docker non serve (test sul codice). Dalla radice:
    python fase3/cp_precompute.py
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from v5 import ambiente, config, episodio   # noqa: E402

ESITI = RADICE / "fase3" / "esiti"


def ordine_verificato():
    """Riusa il test N7: l'invio dei casi avviene DOPO la partenza del cronometro."""
    suite = unittest.TestLoader().loadTestsFromName(
        "v5.test.test_ordine_episodio.TestOrdineEpisodio.test_cronometro_prima_della_cpu_e_niente_invii_prima")
    trovati = [x for x in suite if x.id().endswith(".test_cronometro_prima_della_cpu_e_niente_invii_prima")
               and not x.id().startswith("unittest.loader")]
    if len(trovati) != 1:
        return "errore: test non trovato (nome della classe o del metodo sbagliato)"
    r = unittest.TextTestRunner(verbosity=0, stream=open(__import__("os").devnull, "w")).run(suite)
    return r.wasSuccessful()


def nessun_montaggio_atteso():
    a = episodio.configurazione_attesa("immagine_x")
    return a.get("Mounts") == [] and a.get("Binds") is None


def nessun_bind_negli_argomenti():
    with mock.patch.object(ambiente.subprocess, "Popen") as finto:
        ambiente.avvia_interattivo("prova_i8", "immagine_finta", ["python"])
    args = finto.call_args[0][0]
    return "-v" not in args and "--mount" not in args


def main():
    ESITI.mkdir(parents=True, exist_ok=True)
    try:
        ordine = ordine_verificato()
    except Exception as e:
        ordine = f"errore: {type(e).__name__}: {e}"
    montaggio = nessun_montaggio_atteso()
    bind = nessun_bind_negli_argomenti()
    ok = ordine is True and montaggio and bind
    esito = {"attacco": "PRECOMPUTE", "riferimento": "casi_su_file (I8)",
             "tipo_controllo": "test di proprieta' sul codice vero della v5 (Morgan, 2026-10-08)",
             "ordine_casi_dopo_il_cronometro": ordine,
             "test_riusato": "v5/test/test_ordine_episodio.py::test_cronometro_prima_della_cpu_e_niente_invii_prima",
             "configurazione_senza_montaggi": montaggio,
             "argomenti_senza_bind": bind,
             "riuscito_sul_riferimento": "N/A: difesa strutturale, nessun canale su file da attaccare",
             "bloccato_dalla_v5": ok,
             "controllo_positivo_ok": ok,
             "nota": "i casi arrivano solo su stdin dopo il cronometro (N7) e non c'e' alcun montaggio "
                     "da cui leggerli: le due vie del precalcolo prima della misura sono chiuse"}
    (ESITI / "PRECOMPUTE.proprieta.json").write_text(
        json.dumps(esito, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(esito, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

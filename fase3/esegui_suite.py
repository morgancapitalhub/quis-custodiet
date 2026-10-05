"""Esegue la suite d'attacco e scrive registro_attacchi.csv (brief, "Registro").

**Richiede Docker: si esegue solo nell'ambiente finale** (fase3/MIGRAZIONE.md). Questo modulo non
va lanciato finché l'ambiente non è deciso. La struttura è verificata sull'host da
`v5.test.test_fase3` senza Docker.

Per ogni attacco:
  1. controllo positivo: l'attacco deve RIUSCIRE contro il suo riferimento vulnerabile
     (la v4 nell'ambiente usa e getta, o una v5 indebolita di fase3/riferimenti.py che toglie UNA
     difesa); un attacco che non riesce contro nessun riferimento non prova nulla e va corretto;
  2. esito sulla v5 vera: bloccato (respinto / lettura fallita / guadagno non significativo) o,
     per i soli attacchi "limitato", guadagno entro il limite dichiarato;
  3. riga nel registro con: id, famiglia, prerequisito, riferimento_vulnerabile, esito_riferimento,
     esito_v5, falso_pass_riferimento, bloccato_o_limitato_v5, meccanismo, difesa, rischio_residuo,
     comando.

Qui si lascia lo scheletro con i punti d'aggancio; i dettagli d'esecuzione (mock dei riferimenti
indeboliti nel processo di prova, servizio finto per NETWORK su rete `internal`, confine_pickle per
PAYLOAD) si completano nell'ambiente finale, dove si possono provare.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fase3 import attacchi  # noqa: E402

COLONNE = ["id", "famiglia", "prerequisito", "riferimento_vulnerabile", "esito_riferimento", "esito_v5",
           "falso_pass_riferimento", "bloccato_o_limitato_v5", "meccanismo", "difesa", "rischio_residuo", "storico_tentativi", "comando"]
REGISTRO = Path(__file__).resolve().parent.parent / "registro_attacchi.csv"


def riga_registro(a, esito_riferimento, esito_v5, falso_pass, bloccato_o_limitato):
    return {"id": a["id"], "famiglia": attacchi.FAMIGLIE[a["famiglia"]], "prerequisito": a["prerequisito"],
            "riferimento_vulnerabile": a["riferimento"] or "— (non bloccabile)",
            "esito_riferimento": esito_riferimento, "esito_v5": esito_v5,
            "falso_pass_riferimento": falso_pass, "bloccato_o_limitato_v5": bloccato_o_limitato,
            "meccanismo": a["meccanismo"], "difesa": a["difesa"], "rischio_residuo": a["rischio_residuo"],
            "comando": f"python fase3/esegui_suite.py {a['id']}"}


def main():
    raise SystemExit(
        "esegui_suite richiede Docker e va eseguito solo nell'ambiente finale (fase3/MIGRAZIONE.md). "
        "La struttura della suite è verificata sull'host da: python -m unittest v5.test.test_fase3")


def scrivi_registro(righe):
    """Scrive registro_attacchi.csv dalle righe prodotte nell'ambiente finale."""
    with open(REGISTRO, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLONNE)
        w.writeheader()
        for r in righe:
            w.writerow(r)


if __name__ == "__main__":
    main()

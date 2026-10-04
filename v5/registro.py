"""Registro di sessione: sessione.json, episodi.jsonl, confronti.jsonl.

Le sessioni vivono in lavoro_v5/sessioni/<id>/ (fuori da git); i rapporti copiano in fase2/esiti/
solo ciò che serve, con il comando che lo riproduce.
"""
import datetime
import json
import sys

from v5 import config


class Registro:
    def __init__(self, sessione):
        self.sessione = sessione
        self.cartella = config.LAVORO / "sessioni" / sessione
        self.cartella.mkdir(parents=True, exist_ok=True)
        self.diario = []           # eventi: container fermati e riavviati, controlli, ecc.
        self.dati = {"sessione": sessione, "comando": " ".join(["python", *sys.argv]),
                     "inizio": _ora(), "diario": self.diario}
        self.salva()

    def episodio(self, r):
        r = {"ora": _ora(), **r}
        with open(self.cartella / "episodi.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def confronto(self, c):
        with open(self.cartella / "confronti.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"ora": _ora(), **c}, ensure_ascii=False) + "\n")

    def imposta(self, **kw):
        self.dati.update(kw)
        self.salva()

    def salva(self):
        (self.cartella / "sessione.json").write_text(json.dumps(self.dati, indent=2, ensure_ascii=False),
                                                     encoding="utf-8")

    def episodi(self):
        f = self.cartella / "episodi.jsonl"
        return [json.loads(r) for r in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []


def _ora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")

"""Verifica del congelamento: ricalcola lo stato e lo confronta con l'ultimo congelamento (congela.USCITA).

Da eseguire prima di ogni sessione del pilota (REQUISITI_AGGIUNTI N15). Uscita 0 solo se tutto coincide;
qualunque differenza, file mancante o errore equivale a verifica fallita (a prova di guasto, come N9).

    python fase5/verifica_congelamento.py
"""
import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))


def main():
    try:
        from fase5 import congela
        atteso = json.loads(congela.USCITA.read_text(encoding="utf-8"))
        ora, m = congela.stato()
        errori = congela.controlli(ora, m)
    except Exception as e:                                   # a prova di guasto
        print(f"VERIFICA FALLITA: {type(e).__name__}: {e}")
        return 1
    diversi = [k for k in ora if k != "file" and ora[k] != atteso.get(k)]
    file_diversi = sorted(p for p in set(ora["file"]) | set(atteso["file"])
                          if ora["file"].get(p) != atteso["file"].get(p))
    if diversi or file_diversi or errori:
        print("VERIFICA FALLITA")
        for k in diversi:
            print(f"  {k}: congelato {atteso.get(k)!r}, ora {ora[k]!r}"[:300])
        for p in file_diversi[:20]:
            print(f"  file {p}: congelato {atteso['file'].get(p)}, ora {ora['file'].get(p)}")
        for e in errori:
            print(f"  {e}")
        return 1
    print(f"CONGELAMENTO VERIFICATO: {len(ora['file'])} file, impronta complessiva {ora['impronta_complessiva']}, "
          f"congelato il {atteso['congelato_il']} sul commit {atteso['commit_congelato'][:7]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

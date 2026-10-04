"""Solo misura (fase 2, passo 7c): tempo dell'originale con la codifica attuale, con una variante che
lascerebbe passare interi anche i contenitori con float (NaN/Infinity come token JSON), e con il
pavimento. La variante NON è adottata: richiederebbe di accettare NaN/Infinity al confine.

    python fase2/strumenti/misura_variante_nan.py [giri]

Gira nel container dell'originale con le opzioni del brief; la variante è passata come codice a
`python -I -c` e modifica worker.nodi solo in quel processo. Le risposte non si verificano: si
misurano solo le finestre. Esito in fase2/esiti/variante_nan.json.
"""
import json
import statistics as st
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE))
from v5 import ambiente, carichi, config, episodio  # noqa: E402
from v5.registro import Registro  # noqa: E402

VARIANTE = r'''
import sys
sys.path.insert(0, "/opt/worker")
import json, worker
S = frozenset((str, int, float, bool))
def nodi(radice):
    t0 = type(radice)
    if not (t0 is dict or t0 is list or t0 is tuple):
        return [["S", worker.scalare(radice)]]
    tab = [None]; pila = [(radice, 0)]
    while pila:
        x, i = pila.pop()
        if type(x) is dict:
            if set(map(type, x.values())) <= S:
                tab[i] = ["m", x]; continue
            c = dict(x)
            for k, v in x.items():
                tv = type(v)
                if tv in S: continue
                if tv is dict or tv is list or tv is tuple:
                    j = len(tab); tab.append(None); c[k] = ["#", j]; pila.append((v, j))
                else: c[k] = worker.scalare(v)
            tab[i] = ["m", c]
        else:
            nome = "l" if type(x) is list else "T"
            if set(map(type, x)) <= S:
                tab[i] = [nome, x]; continue
            c = list(x)
            for n, v in enumerate(x):
                tv = type(v)
                if tv in S: continue
                if tv is dict or tv is list or tv is tuple:
                    j = len(tab); tab.append(None); c[n] = ["#", j]; pila.append((v, j))
                else: c[n] = worker.scalare(v)
            tab[i] = [nome, c]
    return tab
worker.nodi = nodi
worker._JSON = json.JSONEncoder(ensure_ascii=True, separators=(",", ":"), allow_nan=True).encode
worker.ciclo()
'''


def main():
    giri = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    sessione = "varnan" + ambiente.secrets_hex()
    reg = Registro(sessione)
    oss = ambiente.Osservatore(sessione)
    varianti = {"attuale": config.COMANDO_WORKER, "nan_ammessi": ["python", "-I", "-c", VARIANTE],
                "pavimento": config.COMANDO_WORKER_PAVIMENTO}
    t = {k: [] for k in varianti}
    try:
        ambiente.controlli(sessione, oss)
        imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
        casi = carichi.carico_dev(300, 120, seme_ordine=1)
        with ambiente.MisureDiTempo(sessione, reg.diario):
            episodio.controlla_picco_a_vuoto(reg, sessione, [imm], oss, casi[:20])
            ordine = list(varianti)
            for g in range(giri):
                for nome in (ordine if g % 2 == 0 else ordine[::-1]):
                    r, _ = episodio.con_ripetizione(reg, sessione, f"{nome}{g}", imm, casi, oss, "originale",
                                                    comando=varianti[nome], timeout_completamento=600)
                    t[nome].append(r["t_finestra_ns"] / 1e9)
                print(g, {k: round(v[-1], 3) for k, v in t.items()}, flush=True)
    finally:
        oss.chiudi()
    med = {k: st.median(v) for k, v in t.items()}
    esito = {"comando": "python fase2/strumenti/misura_variante_nan.py " + str(giri), "sessione": sessione,
             "mediane_s": med, "limite_attuale": round(med["attuale"] / med["pavimento"], 4),
             "limite_con_nan_ammessi": round(med["nan_ammessi"] / med["pavimento"], 4), "tempi_s": t,
             "diario": reg.diario}
    (RADICE / "fase2" / "esiti" / "variante_nan.json").write_text(json.dumps(esito, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in esito.items() if k not in ("tempi_s", "diario")}, indent=2))


if __name__ == "__main__":
    main()

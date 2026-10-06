"""Fase 4: 40 confronti nulli (criterio 3, G1, G2) e limite di PATCH_WORKER sul finale fixture (G3).

    python fase4/fase4.py nulli [--per-pezzo N] [--minuti M]      un pezzo dei 40 nulli (Docker)
    python fase4/fase4.py patch-worker-ff [--minuti M]            un pezzo di G3 (Docker)
    python fase4/fase4.py analisi                                 verdetti dai file di avanzamento (senza Docker)

Corse spezzate in pezzi ripartibili (L2): ogni lancio è un pezzo, apre una Sessione nuova (controlli
preliminari, sqz_demo_* fermati, riscaldamento e picco a vuoto), riprende dall'ultima voce salvata in
fase4/esiti/*.avanzamento.json e si ferma prima di superare --minuti (predefinito 55). Le voci già
misurate non si rifanno. Codici d'uscita: 0 concluso, 10 pezzo finito ma resta lavoro, 3 la sessione si
è fermata per l'infrastruttura (InfrastrutturaFallita: si riferisce, la voce non conta).
Nessuna modifica alla v5: si usano valutazione.valuta, episodio.con_ripetizione, oracolo.carica.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from fase4 import analisi  # noqa: E402
from v5 import ambiente, carichi, config, episodio, oracolo, statistica, valutazione  # noqa: E402

ESITI = RADICE / "fase4" / "esiti"
AV_NULLI = ESITI / "nulli_40.avanzamento.json"
AV_PW_FF = ESITI / "patch_worker_ff.avanzamento.json"
INTESTAZIONE_NULLI = {"criterio": 3, "confronti": statistica.NULLI_ACCETTAZIONE, "coppie": statistica.COPPIE,
                      "carico": "dev", "falso_allarme": "piu_veloce o piu_lento"}
INTESTAZIONE_PW_FF = {"decisione": "G3", "carico": "finale_fixture", "seme_ordine": "pw-ff",
                      "blocchi": list(config.BLOCCHI_PATCH_WORKER), "soglia": config.LIMITE_PATCH_WORKER}
STIMA_NULLO_S = 125        # 19 episodi DEV × ~6,4 s (patch-worker della fase 2: 240 episodi in 25,6 min)
STIMA_COPPIA_FF_S = 5      # 2 episodi del finale fixture × ~2,4 s (quota-fixture della fase 2)
ESCI_CONCLUSO, ESCI_RESTA, ESCI_INFRASTRUTTURA = 0, 10, 3


def preliminari():
    """Regola 1 di CLAUDE.md e M6: chiave assente, demone Docker che risponde davvero."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY impostata: stop (regola 1).")
    if ambiente.docker("info", "--format", "{{.ServerVersion}}").returncode != 0:
        sys.exit("il demone Docker non risponde (docker info): avvia Docker e riprova.")


def _riscaldamento():
    return carichi.carico_dev(*config.CARICO_DEV, seme_ordine="riscaldamento")[:20]


def _resta_tempo(t0, minuti, stima_s):
    return time.monotonic() - t0 + stima_s <= minuti * 60


# ------------------------------------------------------------------ 40 nulli

def riga_nullo(k, sessione, r):
    """Ciò che serve a criterio 3, G1 e G2 (niente diario: quello resta nel registro di sessione)."""
    chiavi = ("esito", "accelerazione", "piu_veloce", "piu_lento", "t", "m", "es", "tempi_originale",
              "tempi_candidato", "picco_candidato", "soglia_picco", "cpu_pre_pronto_cand_us")
    return {"k": k, "sessione": sessione, **{c: r[c] for c in chiavi if c in r}}


def nulli(per_pezzo, minuti):
    av = analisi.Avanzamento(AV_NULLI, INTESTAZIONE_NULLI)
    fatti = len(av.voci)
    if fatti >= INTESTAZIONE_NULLI["confronti"]:
        print(f"40 nulli già completi ({AV_NULLI.name})")
        return ESCI_CONCLUSO
    preliminari()
    imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
    sessione = _nuova_sessione()
    t0, fatti_qui = time.monotonic(), 0
    print(f"pezzo {len(av.dati['pezzi']) + 1}: nulli già fatti {fatti}, sessione {sessione}", flush=True)
    esito = ESCI_RESTA
    try:
        with valutazione.Sessione(sessione, [imm], _riscaldamento()) as s:
            while len(av.voci) < INTESTAZIONE_NULLI["confronti"] and fatti_qui < per_pezzo \
                    and _resta_tempo(t0, minuti, STIMA_NULLO_S):
                k = len(av.voci)
                r = valutazione.valuta(s, imm, imm, "dev", etichetta=f"f4nullo{k}")
                av.aggiungi("voci", riga_nullo(k, sessione, r))
                fatti_qui += 1
                print(f"nullo {k}: {valutazione.classifica(r)} {r.get('accelerazione')}", flush=True)
    except episodio.InfrastrutturaFallita as e:
        av.aggiungi("eventi", {"evento": "infrastruttura", "sessione": sessione, "nullo": len(av.voci),
                               "errore": str(e)[:500]})
        print(f"STOP (infrastruttura): {e}", flush=True)
        esito = ESCI_INFRASTRUTTURA
    av.aggiungi("pezzi", {"sessione": sessione, "nulli": fatti_qui, "minuti": round((time.monotonic() - t0) / 60, 1)})
    if esito == ESCI_RESTA and len(av.voci) >= INTESTAZIONE_NULLI["confronti"]:
        esito = ESCI_CONCLUSO
    return esito


# ------------------------------------------------------------------ G3: PATCH_WORKER sul finale fixture

def patch_worker_ff(minuti):
    av = analisi.Avanzamento(AV_PW_FF, INTESTAZIONE_PW_FF)
    if av.dati.get("concluso"):
        print(f"G3 già concluso ({AV_PW_FF.name})")
        return ESCI_CONCLUSO
    preliminari()
    imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
    casi = carichi.episodio(oracolo.carica("finale_fixture")[0], seme_ordine=INTESTAZIONE_PW_FF["seme_ordine"])
    sessione = _nuova_sessione()
    t0, fatte_qui = time.monotonic(), 0
    esito = ESCI_RESTA
    try:
        with valutazione.Sessione(sessione, [imm], _riscaldamento()) as s:
            while not av.dati.get("concluso") and _resta_tempo(t0, minuti, STIMA_COPPIA_FF_S):
                k = len(av.voci)
                ordine = [("w", config.COMANDO_WORKER), ("p", config.COMANDO_WORKER_PAVIMENTO)]
                if k % 2:
                    ordine.reverse()
                t = {}
                for nome, comando in ordine:
                    r, _ = episodio.con_ripetizione(s.reg, s.sessione, f"f4pw{nome}{k}", imm, casi, s.oss, "originale",
                                                    comando=comando, timeout_completamento=600)
                    t[nome] = r["t_finestra_ns"] / 1e9
                av.aggiungi("voci", {"k": k, "sessione": sessione, "t_worker_s": t["w"], "t_pavimento_s": t["p"],
                                     "rapporto": t["w"] / t["p"]})
                fatte_qui += 1
                c, fermati = analisi.controllo_blocco([v["rapporto"] for v in av.voci])
                if c:
                    av.dati.setdefault("controlli", []).append(c)
                    print(json.dumps(c), flush=True)
                if fermati:
                    av.dati["concluso"] = True
                    av.dati["limite_dichiarato"] = c["IC95"][1]
                av.salva()
    except episodio.InfrastrutturaFallita as e:
        av.aggiungi("eventi", {"evento": "infrastruttura", "sessione": sessione, "coppia": len(av.voci),
                               "errore": str(e)[:500]})
        print(f"STOP (infrastruttura): {e}", flush=True)
        esito = ESCI_INFRASTRUTTURA
    av.aggiungi("pezzi", {"sessione": sessione, "coppie": fatte_qui, "minuti": round((time.monotonic() - t0) / 60, 1)})
    return ESCI_CONCLUSO if av.dati.get("concluso") and esito != ESCI_INFRASTRUTTURA else esito


# ------------------------------------------------------------------ analisi (senza Docker)

def analizza():
    out = {"comando": "python fase4/fase4.py analisi"}
    if AV_NULLI.exists():
        righe = analisi.Avanzamento(AV_NULLI, INTESTAZIONE_NULLI).voci
        out["criterio3"] = analisi.criterio3(righe)
        out["G1_simmetria"] = analisi.simmetria(righe)
        out["G2_risoluzione"] = analisi.risoluzione(righe)
        out["nulli_completi"] = len(righe) >= INTESTAZIONE_NULLI["confronti"]
    if AV_PW_FF.exists():
        d = analisi.Avanzamento(AV_PW_FF, INTESTAZIONE_PW_FF).dati
        out["G3_patch_worker_ff"] = {"concluso": bool(d.get("concluso")), "coppie": len(d["voci"]),
                                     "controlli_intermedi": d.get("controlli", []),
                                     "limite_dichiarato": d.get("limite_dichiarato"),
                                     "nota": "controlli intermedi sulla stessa serie: l'errore di primo tipo "
                                             "complessivo supera il 5% nominale"}
    ESITI.mkdir(parents=True, exist_ok=True)
    (ESITI / "analisi.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return ESCI_CONCLUSO


def _nuova_sessione():
    import secrets
    return "f4" + time.strftime("%Y%m%d%H%M%S") + secrets.token_hex(3)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="fase4.py")
    ap.add_argument("comando", choices=["nulli", "patch-worker-ff", "analisi"])
    ap.add_argument("--per-pezzo", type=int, default=20)
    ap.add_argument("--minuti", type=float, default=55)
    a = ap.parse_args(argv)
    if a.comando == "nulli":
        return nulli(a.per_pezzo, a.minuti)
    if a.comando == "patch-worker-ff":
        return patch_worker_ff(a.minuti)
    return analizza()


if __name__ == "__main__":
    sys.exit(main())

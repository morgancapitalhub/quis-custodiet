"""Fase 4: 40 confronti nulli (criterio 3, G1, G2) e limite di PATCH_WORKER sul finale fixture (G3).

    python fase4/fase4.py nulli [--per-pezzo N] [--minuti M]      un pezzo dei 40 nulli (Docker)
    python fase4/fase4.py patch-worker-ff [--minuti M]            un pezzo di G3 (Docker)
    python fase4/fase4.py analisi [--protocollo 5.0|5.1]         verdetti dai file di avanzamento (senza Docker)
    python fase4/fase4.py collaudo                                varianti oneste + cancello corto, protocollo in vigore (Docker)

Corse spezzate in pezzi ripartibili (L2): ogni lancio è un pezzo, apre una Sessione nuova (controlli
preliminari, sqz_demo_* fermati, riscaldamento e picco a vuoto), riprende dall'ultima voce salvata in
fase4/esiti/*.avanzamento.json e si ferma prima di superare --minuti (predefinito 55). Le voci già
misurate non si rifanno. Codici d'uscita: 0 concluso, 10 pezzo finito ma resta lavoro, 3 la sessione si
è fermata per l'infrastruttura (InfrastrutturaFallita: si riferisce, la voce non conta).
Si usano valutazione.valuta, episodio.con_ripetizione, oracolo.carica della v5 in vigore (config.VERSIONE_PROTOCOLLO).
La corsa dei nulli del protocollo 5.0 resta in nulli_40.avanzamento.json e si rianalizza con --protocollo 5.0.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from fase4 import analisi  # noqa: E402
from v5 import ambiente, carichi, config, episodio, oracolo, statistica, valutazione  # noqa: E402

SESSIONI = config.LAVORO / "sessioni"

ESITI = RADICE / "fase4" / "esiti"
AV_PW_FF = ESITI / "patch_worker_ff.avanzamento.json"
# Corsa dei 40 nulli del protocollo 5.0 (tetto del pronto, 2026-10-06/07): conservata come prova che la regola
# vecchia falliva (Morgan N6); si rianalizza con `analisi --protocollo 5.0`, non si estende.
AV_NULLI_50 = ESITI / "nulli_40.avanzamento.json"
INTESTAZIONE_NULLI_50 = {"criterio": 3, "confronti": statistica.NULLI_ACCETTAZIONE, "coppie": statistica.COPPIE,
                         "carico": "dev", "falso_allarme": "piu_veloce o piu_lento"}
# Corsa del protocollo in vigore (5.1: costo = finestra + CPU prima del pronto, N1): 40 nulli da capo.
AV_NULLI = ESITI / "nulli_40_p51.avanzamento.json"
INTESTAZIONE_NULLI = {**INTESTAZIONE_NULLI_50, "protocollo": config.VERSIONE_PROTOCOLLO,
                      "costo": "finestra + CPU del container prima del pronto"}
INTESTAZIONE_PW_FF = {"decisione": "G3", "carico": "finale_fixture", "seme_ordine": "pw-ff",
                      "blocchi": list(config.BLOCCHI_PATCH_WORKER), "soglia": config.LIMITE_PATCH_WORKER}
STIMA_NULLO_S = 270        # Morgan, 2026-10-07: il caso lento osservato (~4,4 min per nullo, pezzo 1 della corsa
                           # 5.0), non la media: decide se avviare un altro nullo. Era 125 s; il pezzo 1 della corsa 5.1
                           # è durato 57,5 min. Solo spezzettamento (L2): nessun effetto su misure, protocollo o regole.
STIMA_COPPIA_FF_S = 5      # 2 episodi del finale fixture × ~2,4 s (quota-fixture della fase 2)
ESCI_CONCLUSO, ESCI_RESTA, ESCI_INFRASTRUTTURA = 0, 10, 3
ARRESTI_MASSIMI = 3        # Morgan, fase 4 decisione 2: oltre 3 arresti tecnici in una corsa ci si ferma


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
    chiavi = ("esito", "accelerazione", "piu_veloce", "piu_lento", "t", "m", "es", "accelerazione_minima_distinguibile",
              "tempi_originale", "tempi_candidato", "finestre_originale", "finestre_candidato",
              "cpu_pre_pronto_originale_us", "cpu_pre_pronto_candidato_us",
              "picco_candidato", "soglia_picco", "cpu_pre_pronto_cand_us", "protocollo")
    return {"k": k, "sessione": sessione, **{c: r[c] for c in chiavi if c in r}}


# Messaggio con cui valutazione.valuta (v5, invariata) si pronuncia contro l'originale nel ruolo d'originale
# (tetto del pronto superato due volte di seguito). test_fase4 verifica che compaia in v5/valutazione.py.
MSG_TETTO_ORIGINALE = "l'originale supera il tetto del pronto due volte di seguito"
NULLO_DI = re.compile(r"^f4nullo(\d+)_")


def sforamenti_c4(av, sessione):
    """Ogni sforamento del tetto del pronto registrato dal protocollo nella sessione (episodi.jsonl, evento
    "tetto del pronto superato"): nel nullo entrambi i ruoli sono l'originale, quindi ogni sforamento è un
    evento C4. Il nullo si ricava dall'ultimo episodio etichettato che lo precede. Una volta per sessione."""
    scansionate = av.dati.setdefault("sessioni_scansionate_c4", [])
    if sessione in scansionate:
        return
    nullo = None
    f = SESSIONI / sessione / "episodi.jsonl"       # lettura diretta: Registro() riscriverebbe sessione.json
    for e in ([json.loads(r) for r in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []):
        m = NULLO_DI.match(str(e.get("n", "")))
        if m:
            nullo = int(m.group(1))
        if e.get("evento") == "tetto del pronto superato":
            av.dati["eventi"].append({
                "evento": "C4", "tipo": "sforamento del tetto del pronto (originale)", "sessione": sessione,
                "nullo": nullo, "ora": e.get("ora"), "coppia": e.get("coppia"), "ruoli": e.get("ruoli"),
                "tetto_us": e.get("tetto_us"), "ripetizione": e.get("ripetizione"),
                "pronuncia": (e.get("ripetizione") or 0) > 1})
    scansionate.append(sessione)
    av.salva()


def riclassifica_eventi(av):
    """Morgan, 2026-10-06: l'evento del pezzo 1 registrato come arresto tecnico con la causa del tetto è un
    evento C4. Si riclassifica conservando la storia; poi si scansionano le sessioni dei pezzi già fatti."""
    for ev in av.dati["eventi"]:
        if ev["evento"] == "arresto tecnico" and ev.get("causa") == MSG_TETTO_ORIGINALE:
            ev.update({"evento": "C4", "tipo": "tetto del pronto superato dall'originale (ruolo originale, due volte "
                       "di seguito)", "riclassificato": "2026-10-06, Morgan: era registrato come arresto tecnico"})
    av.salva()
    for p in av.dati["pezzi"]:
        for sessione in p.get("sessioni", []):
            sforamenti_c4(av, sessione)


def nulli(per_pezzo, minuti):
    av = analisi.Avanzamento(AV_NULLI, INTESTAZIONE_NULLI)
    fatti = len(av.voci)
    if fatti >= INTESTAZIONE_NULLI["confronti"]:
        print(f"40 nulli già completi ({AV_NULLI.name})")
        return ESCI_CONCLUSO
    imm = None
    t0, fatti_qui, sessioni = time.monotonic(), 0, []
    print(f"pezzo {len(av.dati['pezzi']) + 1}: nulli già registrati {fatti}", flush=True)
    esito = ESCI_RESTA

    def resta():
        return (len(av.voci) < INTESTAZIONE_NULLI["confronti"] and fatti_qui < per_pezzo
                and _resta_tempo(t0, minuti, STIMA_NULLO_S))
    # Morgan, fase 4 decisione 2: un arresto tecnico (l'ambiente viene meno: Docker, PC, timeout) non è
    # un rifiuto dell'originale; il nullo si scarta e si rifà in una Sessione nuova (controlli ripetuti).
    # Ogni arresto si registra con la causa; oltre ARRESTI_MASSIMI nella corsa ci si ferma e si riferisce.
    # Morgan, 2026-10-06: ogni sforamento del tetto del pronto da parte dell'originale, in qualunque ruolo,
    # è un evento C4 (non un arresto tecnico); con le regole di oggi il nullo interrotto si rifà.
    riclassifica_eventi(av)
    while resta():
        preliminari()
        imm = imm or ambiente.immagine_pacchetto(carichi.pacchetto_originale())
        sessione = _nuova_sessione()
        sessioni.append(sessione)
        try:
            with valutazione.Sessione(sessione, [imm], _riscaldamento()) as s:
                while resta():
                    k = len(av.voci)
                    r = valutazione.valuta(s, imm, imm, "dev", etichetta=f"f4nullo{k}")
                    av.aggiungi("voci", riga_nullo(k, sessione, r))
                    fatti_qui += 1
                    # nessuna lettura dei risultati prima dei 40 (piano, sezione 1): solo l'avanzamento
                    print(f"nullo {k} registrato", flush=True)
        except episodio.InfrastrutturaFallita as e:
            if str(e) == MSG_TETTO_ORIGINALE:
                av.aggiungi("eventi", {"evento": "C4", "tipo": "tetto del pronto superato dall'originale (ruolo originale, "
                                       "due volte di seguito)", "sessione": sessione, "nullo": len(av.voci)})
                print(f"evento C4 durante il nullo {len(av.voci)} (nullo interrotto, si rifà)", flush=True)
            else:
                av.aggiungi("eventi", {"evento": "arresto tecnico", "sessione": sessione, "nullo": len(av.voci),
                                       "causa": str(e)[:500]})
                arresti = sum(ev["evento"] == "arresto tecnico" for ev in av.dati["eventi"])
                print(f"arresto tecnico {arresti} durante il nullo {len(av.voci)} (scartato, si rifà): {e}", flush=True)
                if arresti > ARRESTI_MASSIMI:
                    print(f"STOP: {arresti} arresti tecnici nella corsa (> {ARRESTI_MASSIMI}): riferire a Morgan", flush=True)
                    esito = ESCI_INFRASTRUTTURA
                    break
        finally:
            sforamenti_c4(av, sessione)
    av.aggiungi("pezzi", {"sessioni": sessioni, "nulli": fatti_qui, "minuti": round((time.monotonic() - t0) / 60, 1)})
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

def analizza(protocollo=config.VERSIONE_PROTOCOLLO):
    out = {"comando": f"python fase4/fase4.py analisi --protocollo {protocollo}"}
    percorso, intestazione = (AV_NULLI_50, INTESTAZIONE_NULLI_50) if protocollo == "5.0" else (AV_NULLI, INTESTAZIONE_NULLI)
    out["protocollo"] = protocollo
    if percorso.exists():
        d = analisi.Avanzamento(percorso, intestazione).dati
        righe = d["voci"]
        out["nulli_registrati"] = len(righe)
        out["arresti_tecnici"] = [ev for ev in d["eventi"] if ev["evento"] == "arresto tecnico"]
        # Numero deciso prima (40): i verdetti si calcolano SOLO a 40 raggiunti; nessuna lettura prima.
        if len(righe) == INTESTAZIONE_NULLI["confronti"]:
            out["criterio3"] = analisi.criterio3(righe, d["eventi"])
            out["G1_simmetria"] = analisi.simmetria(righe)       # riportato anche se il criterio 3 fallisce
            out["G2_risoluzione"] = analisi.risoluzione(righe)
        else:
            out["nulli"] = f"verdetti non calcolati: {len(righe)}/40 (si leggono solo a 40 raggiunti)"
    if AV_PW_FF.exists():
        d = analisi.Avanzamento(AV_PW_FF, INTESTAZIONE_PW_FF).dati
        out["G3_patch_worker_ff"] = {"concluso": bool(d.get("concluso")), "coppie": len(d["voci"]),
                                     "controlli_intermedi": d.get("controlli", []),
                                     "limite_dichiarato": d.get("limite_dichiarato"),
                                     "nota": "controlli intermedi sulla stessa serie: l'errore di primo tipo "
                                             "complessivo supera il 5% nominale"}
    ESITI.mkdir(parents=True, exist_ok=True)
    nome = "analisi.json" if protocollo == "5.0" else f"analisi_p{protocollo.replace('.', '')}.json"
    (ESITI / nome).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return ESCI_CONCLUSO


# ------------------------------------------------------------------ manifest del protocollo in vigore (Morgan, punto 3)

def _impronte(cartella):
    import hashlib
    return {p.relative_to(cartella).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(cartella).rglob("*")) if p.is_file()}


def manifest():
    """oracle_manifest.json per il protocollo in vigore, con tre protezioni:
      1. esito in fase4/esiti/oracolo_p51.json (fase2/esiti/oracolo.json resta com'è);
      2. segreti/ non si scrive mai: le due costruzioni avvengono in cartelle temporanee (lavoro_v5/, fuori da
         git) con gli stessi semi; i file ricostruiti si confrontano byte per byte con quelli in segreti/ e in
         lavoro_v5/oracolo/; le impronte SHA-256 di tutti i file di segreti/ si registrano prima e dopo e devono
         coincidere (è ciò che tiene valida la copia cifrata, D3);
      3. nessun segreti.tar: questo comando non lo crea; se alla fine esiste, si cancella.
    Il manifest si scrive in v5/oracle_manifest.json solo se le due costruzioni danno manifest identici e i file
    ricostruiti coincidono con quelli esistenti."""
    import hashlib
    import shutil
    from v5.registro import Registro
    preliminari()
    prima = _impronte(config.SEGRETI)
    sessione = _nuova_sessione()
    reg = Registro(sessione)
    oss = ambiente.Osservatore(sessione)
    semi = json.loads((config.SEGRETI / "semi.json").read_text(encoding="utf-8"))
    tmp = config.LAVORO / "manifest_p51"
    t0 = time.monotonic()
    costruzioni = {}
    try:
        reg.imposta(controlli=ambiente.controlli(sessione, oss))
        imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
        if tmp.exists():
            shutil.rmtree(tmp)
        for nome in ("a", "b"):
            (tmp / nome / "segreti").mkdir(parents=True)
            (tmp / nome / "segreti" / "semi.json").write_text(json.dumps(semi, indent=2), encoding="utf-8")
            man, massimi = oracolo.costruisci(reg, sessione, oss, imm, tmp / nome / "segreti", tmp / nome / "dev")
            costruzioni[nome] = man
        reg.salva()
        ricostruiti = {f"{c}/{f}": hashlib.sha256((tmp / "a" / "segreti" / c / f).read_bytes()).hexdigest()
                       for c in ("finale_sintetico", "finale_fixture") for f in ("casi.json", "oracolo.json")}
        dev = {f: hashlib.sha256((tmp / "a" / "dev" / "dev" / f).read_bytes()).hexdigest() for f in ("casi.json", "oracolo.json")}
    finally:
        oss.chiudi()
        if tmp.exists():
            shutil.rmtree(tmp)                  # le copie dei documenti segreti non restano su disco
    dopo = _impronte(config.SEGRETI)
    dev_esistenti = _impronte(config.LAVORO / "oracolo" / "dev")
    identici = costruzioni["a"] == costruzioni["b"]
    coincidono = {k: prima.get(k) == v for k, v in ricostruiti.items()}
    dev_coincide = {k: dev_esistenti.get(k) == v for k, v in dev.items()}
    segreti_invariati = prima == dopo
    tar = RADICE / "segreti.tar"
    tar_cancellato = False
    if tar.exists():
        tar.unlink()
        tar_cancellato = True
    ok = identici and all(coincidono.values()) and all(dev_coincide.values()) and segreti_invariati
    if ok:
        (RADICE / "v5" / "oracle_manifest.json").write_bytes(costruzioni["a"])
    dati = {"comando": "python fase4/fase4.py manifest", "protocollo": config.VERSIONE_PROTOCOLLO,
            "impronta_protocollo": oracolo.impronta_protocollo(), "sessione": sessione,
            "durata_s": round(time.monotonic() - t0), "manifest_identici": identici,
            "impronta_manifest": hashlib.sha256(costruzioni["a"]).hexdigest(),
            "file_finale_ricostruiti_uguali_a_segreti": coincidono, "file_dev_ricostruiti_uguali": dev_coincide,
            "segreti_impronte_prima_uguali_dopo": segreti_invariati, "file_in_segreti": len(prima),
            "segreti_tar_presente_alla_fine": tar.exists(), "segreti_tar_cancellato": tar_cancellato,
            "manifest_scritto": ok}
    ESITI.mkdir(parents=True, exist_ok=True)
    (ESITI / f"oracolo_p{config.VERSIONE_PROTOCOLLO.replace('.', '')}.json").write_text(
        json.dumps(dati, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(dati, indent=2, ensure_ascii=False))
    return ESCI_CONCLUSO if ok else 1


# ------------------------------------------------------------------ collaudo con la regola nuova (N6)

def collaudo(n_nulli=5):
    """Le sei varianti oneste (esiti dichiarati prima in valutazione.VARIANTI) + cancello corto, con il
    protocollo in vigore. Come `supervisore.py collaudo`, ma scrive in fase4/esiti/ (il collaudo della
    fase 2 resta com'è) e riporta per ogni verdetto l'accelerazione minima distinguibile (N2)."""
    from v5 import supervisore
    preliminari()
    imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
    varianti = {nome: valutazione.immagine_variante(nome) for nome in valutazione.VARIANTI}
    sessione = _nuova_sessione()
    righe = []
    with valutazione.Sessione(sessione, [imm, *varianti.values()], _riscaldamento()) as s:
        for nome, imm_v in varianti.items():
            atteso = valutazione.VARIANTI[nome][1]
            r = valutazione.valuta(s, imm, imm_v, "dev", etichetta=f"c51{nome.lower()}")
            osservato = valutazione.classifica(r)
            righe.append({"variante": nome, "atteso": atteso, "osservato": osservato, "ok": osservato == atteso,
                          "accelerazione": r.get("accelerazione"), "t": r.get("t"),
                          "accelerazione_minima_distinguibile": r.get("accelerazione_minima_distinguibile"),
                          "picco_candidato": r.get("picco_candidato"), "soglia_picco": r.get("soglia_picco")})
            print(json.dumps(righe[-1], ensure_ascii=False), flush=True)
        nulli = supervisore.cancello(s, imm, n_nulli)
    dati = {"comando": "python fase4/fase4.py collaudo", "protocollo": config.VERSIONE_PROTOCOLLO,
            "sessione": sessione, "varianti": righe, "superate": f"{sum(r['ok'] for r in righe)}/{len(righe)}",
            "cancello_corto": nulli, "diario": s.reg.diario}
    ESITI.mkdir(parents=True, exist_ok=True)
    (ESITI / f"collaudo_p{config.VERSIONE_PROTOCOLLO.replace('.', '')}.json").write_text(
        json.dumps(dati, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in dati.items() if k != "diario"}, indent=2, ensure_ascii=False))
    return ESCI_CONCLUSO if all(r["ok"] for r in righe) else 1


def _nuova_sessione():
    import secrets
    return "f4" + time.strftime("%Y%m%d%H%M%S") + secrets.token_hex(3)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="fase4.py")
    ap.add_argument("comando", choices=["nulli", "patch-worker-ff", "analisi", "collaudo", "manifest"])
    ap.add_argument("--per-pezzo", type=int, default=20)
    ap.add_argument("--minuti", type=float, default=55)
    ap.add_argument("--protocollo", choices=["5.0", config.VERSIONE_PROTOCOLLO], default=config.VERSIONE_PROTOCOLLO)
    a = ap.parse_args(argv)
    if a.comando == "nulli":
        return nulli(a.per_pezzo, a.minuti)
    if a.comando == "patch-worker-ff":
        return patch_worker_ff(a.minuti)
    if a.comando == "collaudo":
        return collaudo()
    if a.comando == "manifest":
        return manifest()
    return analizza(a.protocollo)


if __name__ == "__main__":
    sys.exit(main())

"""Supervisore della v5 — riga di comando.

    python v5/supervisore.py <comando>

Comandi (fase2/PIANO_FASE2.md): osservatore-prova, controlli, calibra, quota, mutatore,
oracolo, collaudo, nullo, valuta, corsa. Ognuno registra la propria riga di comando.
"""
import argparse
import hashlib
import json
import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from v5 import ambiente, carichi, config  # noqa: E402

ESITI_FASE2 = config.RADICE / "fase2" / "esiti"


def scrivi_esito(nome, dati):
    ESITI_FASE2.mkdir(parents=True, exist_ok=True)
    dati = {"comando": " ".join(["python", "v5/supervisore.py", *sys.argv[1:]]), **dati}
    (ESITI_FASE2 / nome).write_text(json.dumps(dati, indent=2, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------ osservatore-prova

def osservatore_prova(_args):
    """Prova i privilegi dell'osservatore (v5/OSSERVATORE.md): cosa può e cosa non può fare."""
    sessione = "prova" + uuid.uuid4().hex[:8]
    oss = ambiente.Osservatore(sessione)
    sonda = f"v5_sonda_{sessione}"
    esiti = {}
    try:
        ambiente.docker("run", "-d", "--name", sonda, *config.OPZIONI_CONTAINER,
                        ambiente.immagine_base(), "python", "-I", "-c", "import time; time.sleep(120)", controlla=True)
        cid = ambiente.id_di(sonda)

        def dentro(cmd):
            p = ambiente.docker("exec", oss.nome, "sh", "-c", cmd, timeout=config.TIMEOUT_OSSERVATORE)
            return p.returncode, (p.stdout + p.stderr).strip()[:300]

        # può: leggere i file cgroup della sonda
        esiti["legge_memory_peak"] = oss.picco(cid) > 0
        esiti["legge_cpu_stat"] = oss.cpu_us(cid) >= 0
        esiti["legge_memory_events"] = "oom_kill" in oss.leggi(cid, "memory.events")
        # identità e privilegi
        esiti["uid"] = dentro("id -u")[1]
        esiti["capacita_effettive"] = dentro("grep CapEff /proc/self/status")[1]
        # non può: scrivere nel cgroup, nel proprio filesystem; usare la rete; vedere altri processi
        esiti["scrittura_memory_peak_rifiutata"] = dentro(f"echo 0 > /cg/docker/{cid}/memory.peak")[0] != 0
        esiti["scrittura_cgroup_rifiutata"] = dentro("mkdir /cg/docker/v5_prova")[0] != 0
        esiti["scrittura_rootfs_rifiutata"] = dentro("touch /x")[0] != 0
        esiti["rete_tcp_rifiutata"] = dentro("nc -w 3 1.1.1.1 53 </dev/null")[0] != 0
        esiti["dns_rifiutato"] = dentro("nslookup -timeout=2 example.com")[0] != 0
        esiti["processi_visibili"] = dentro("ls /proc | grep -c '^[0-9]'")[1]
        esiti["vede_processi_della_sonda"] = "python" in dentro("cat /proc/*/cmdline 2>/dev/null | tr '\\0' ' '")[1]
        esiti["lettura_non_ammessa_rifiutata"] = _rifiutata(lambda: oss.leggi(cid, "cgroup.procs"))
        esiti["id_non_valido_rifiutato"] = _rifiutata(lambda: oss.leggi("../../etc", "memory.peak"))
    finally:
        ambiente.rimuovi(sonda)
        oss.chiudi()
    attesi = {"legge_memory_peak": True, "legge_cpu_stat": True, "legge_memory_events": True, "uid": "65534",
              "capacita_effettive": "CapEff:\t0000000000000000", "scrittura_memory_peak_rifiutata": True,
              "scrittura_cgroup_rifiutata": True, "scrittura_rootfs_rifiutata": True, "rete_tcp_rifiutata": True,
              "dns_rifiutato": True, "vede_processi_della_sonda": False, "lettura_non_ammessa_rifiutata": True,
              "id_non_valido_rifiutato": True}
    difformi = {k: esiti[k] for k, v in attesi.items() if esiti[k] != v}
    scrivi_esito("osservatore.json", {"esiti": esiti, "attesi": attesi, "difformi": difformi,
                                      "opzioni": config.OPZIONI_OSSERVATORE, "immagine": config.IMMAGINE_OSSERVATORE})
    print(json.dumps({"esiti": esiti, "difformi": difformi}, indent=2, ensure_ascii=False))
    return 0 if not difformi else 1


def _rifiutata(f):
    try:
        f()
    except ValueError:
        return True
    return False


# ------------------------------------------------------------------ controlli

def nuova_sessione():
    return time.strftime("%Y%m%d%H%M%S") + secrets.token_hex(3)


def controlli(_args):
    """Controlli preliminari (REQUISITI_AGGIUNTI.md). Codice d'uscita 0 solo se tutti valgono."""
    sessione = nuova_sessione()
    oss = ambiente.Osservatore(sessione)
    t0 = time.monotonic()
    try:
        esiti = ambiente.controlli(sessione, oss)
        esito, errore = "superati", None
    except ambiente.ControlloFallito as e:
        esiti, esito, errore = {}, "FALLITI", str(e)
    finally:
        oss.chiudi()
    dati = {"sessione": sessione, "esito": esito, "errore": errore, "esiti": esiti,
            "durata_s": round(time.monotonic() - t0, 1)}
    scrivi_esito("controlli.json", dati)
    print(json.dumps(dati, indent=2, ensure_ascii=False))
    return 0 if errore is None else 1


# ------------------------------------------------------------------ episodi-prova

def episodi_prova(args):
    """Passo 5: N episodi dell'originale in streaming; tutti devono completare con esiti identici."""
    from v5 import episodio
    from v5.registro import Registro
    n = int(args.resto[0]) if args.resto else 100
    sessione = nuova_sessione()
    reg = Registro(sessione)
    oss = ambiente.Osservatore(sessione)
    try:
        reg.imposta(controlli=ambiente.controlli(sessione, oss))
        immagine = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
        valide = [p.read_bytes() for p in carichi.fixture_valide()]
        non_valide = [p.read_bytes() for p in carichi.fixture_non_valide()[:40]]
        casi = ([(0, b) for b in valide] + [(1, b) for b in valide[:20]] + [(2, b) for b in valide[20:40]]
                + [(0, b) for b in non_valide if _utf8(b)][:30] + [(3, b"f=0.1"), (4, b"a=1"), (5, b"a=1"),
                                                                    (6, b"x"), (7, b"f=0.1"), (8, b""), (9, b"a=1\nb=2")])
        riferimento, righe = None, []
        with ambiente.MisureDiTempo(sessione, reg.diario):
            for k in range(n):
                r, frame = episodio.con_ripetizione(reg, sessione, k, immagine, casi, oss, "originale")
                esiti = episodio.valuta_risposte(frame)
                riferimento = riferimento or esiti
                righe.append({"n": k, "t_finestra_s": r["t_finestra_ns"] / 1e9, "picco": r["memory_peak"],
                              "s_avvio_pronto": r["s_avvio_pronto"], "cpu_pre_pronto_us": r["cpu_pre_pronto_us"],
                              "bloccato_dopo": r["client_bloccato_dopo"], "ripetizione": r["ripetizione"],
                              "esiti_identici": esiti == riferimento})
                print(f"{k:3d} {righe[-1]}", flush=True)
        reg.salva()
    finally:
        oss.chiudi()
    import statistics as st
    tempi = [x["t_finestra_s"] for x in righe]
    riepilogo = {
        "sessione": sessione, "episodi": n, "casi_per_episodio": len(casi),
        "completati": len(righe), "ripetuti": sum(x["ripetizione"] for x in righe),
        "esiti_identici_al_primo": sum(x["esiti_identici"] for x in righe),
        "client_bloccati_dopo": sum(bool(x["bloccato_dopo"]) for x in righe),
        "t_finestra_s": [min(tempi), st.median(tempi), max(tempi)],
        "picco_MiB": [round(f(x["picco"] for x in righe) / 2**20, 2) for f in (min, st.median, max)],
        "s_avvio_pronto": [f(x["s_avvio_pronto"] for x in righe) for f in (min, st.median, max)],
        "cpu_pre_pronto_ms": [f(x["cpu_pre_pronto_us"] for x in righe) / 1000 for f in (min, st.median, max)],
        "diario": reg.diario,
    }
    scrivi_esito("episodi_prova.json", riepilogo)
    print(json.dumps(riepilogo, indent=2, ensure_ascii=False))
    ok = riepilogo["completati"] == n and riepilogo["esiti_identici_al_primo"] == n
    return 0 if ok else 1


def _utf8(b):
    try:
        b.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


# ------------------------------------------------------------------ calibra (passo 6)

def _stat(v):
    import statistics as st
    m = st.median(v)
    return {"min": min(v), "mediana": m, "max": max(v), "mad": st.median(abs(x - m) for x in v), "n": len(v)}


def calibra(args):
    """Passo 6: picco a vuoto, risoluzione del vincolo di memoria (D4), CPU pre-pronto.

    python v5/supervisore.py calibra [n_doc sezioni]     (carico DEV provvisorio: 200 × 120)
    """
    from v5 import episodio
    from v5.registro import Registro
    n_doc, sezioni = (int(args.resto[0]), int(args.resto[1])) if len(args.resto) >= 2 else (200, 120)
    MiB = 2 ** 20
    sessione = nuova_sessione()
    reg = Registro(sessione)
    oss = ambiente.Osservatore(sessione)
    try:
        reg.imposta(controlli=ambiente.controlli(sessione, oss))
        imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
        casi = carichi.carico_dev(n_doc, sezioni, seme_ordine=1)
        with ambiente.MisureDiTempo(sessione, reg.diario):
            # picco del PRIMO container della sessione, prima di qualunque riscaldamento
            primo = episodio.sonde_a_vuoto(reg, sessione, imm, oss, 1)[0]
            episodio.riscalda(reg, sessione, [imm], oss, casi[:20])
            vuoto = episodio.sonde_a_vuoto(reg, sessione, imm, oss, 20)
            importato, orig, cpu, finestre = [], [], [], []
            for k in range(10):
                r, _ = episodio.con_ripetizione(reg, sessione, f"imp{k}", imm, [], oss, "originale")
                importato.append(r["memory_peak"])
                cpu.append(r["cpu_pre_pronto_us"])
                r, frame = episodio.con_ripetizione(reg, sessione, f"orig{k}", imm, casi, oss, "originale",
                                                    timeout_completamento=600)
                orig.append(r["memory_peak"])
                cpu.append(r["cpu_pre_pronto_us"])
                finestre.append(r["t_finestra_ns"] / 1e9)
                print(f"{k}: finestra {finestre[-1]:.2f} s, picco {orig[-1] / MiB:.2f} MiB", flush=True)
        reg.salva()
    finally:
        oss.chiudi()
    sv, si, so, sc, sf = _stat(vuoto), _stat(importato), _stat(orig), _stat(cpu), _stat(finestre)
    intervallo = [sv["mediana"] - MiB, min(sv["mediana"] + MiB, 8 * MiB)]
    margine = 0.05 * so["mediana"] + MiB
    memoria_parser = so["mediana"] - si["mediana"]
    eccedenza_cpu = max(20_000, 5 * sc["mad"])
    dati = {
        "sessione": sessione, "carico": {"n_doc": n_doc, "sezioni": sezioni, "casi": len(casi),
                                         "byte": sum(len(c) for _, c in casi)},
        "picco_primo_container_MiB": round(primo / MiB, 3),
        "picco_vuoto_MiB": {k: round(v / MiB, 3) if k != "n" else v for k, v in sv.items()},
        "intervallo_picco_vuoto_byte": [int(x) for x in intervallo],
        "picco_import_MiB": {k: round(v / MiB, 3) if k != "n" else v for k, v in si.items()},
        "picco_originale_MiB": {k: round(v / MiB, 3) if k != "n" else v for k, v in so.items()},
        "risoluzione_memoria": {
            "margine_ammesso_MiB": round(margine / MiB, 3),
            "di_cui_5_percento_MiB": round(0.05 * so["mediana"] / MiB, 3),
            "memoria_del_parser_MiB (P_orig - P_import)": round(memoria_parser / MiB, 3),
            "margine_relativo_sulla_memoria_del_parser": round(margine / memoria_parser, 3) if memoria_parser > 0 else None,
            "dispersione_P_orig_MiB (max-min)": round((so["max"] - so["min"]) / MiB, 3),
        },
        "cpu_pre_pronto_ms": {k: round(v / 1000, 1) if k != "n" else v for k, v in sc.items()},
        "tetto_cpu_pre_pronto_ms": round((sc["mediana"] + eccedenza_cpu) / 1000, 1),
        "eccedenza_ammessa_ms": round(eccedenza_cpu / 1000, 1),
        "finestra_originale_s": sf,
        "limite_guadagno_ready_abuse": round(eccedenza_cpu / 1e6 / sf["mediana"], 4),
        "diario": reg.diario,
    }
    scrivi_esito("calibrazione.json", dati)
    print(json.dumps({k: v for k, v in dati.items() if k != "diario"}, indent=2, ensure_ascii=False))
    return 0


# ------------------------------------------------------------------ quota (passo 7)

def misura_quota(reg, sessione, oss, imm, casi, giri=10, etichetta="dev"):
    """Brief, "Sovraccarico misurato": worker vero, nullo e strumentato sullo stesso flusso, a rotazione.

    quota_e = 1 - mediana(T_nullo) / mediana(T_orig)        (il nullo non codifica: sottostima il sovraccarico)
    quota_i = mediana(t_dentro_API / T_finestra) sul worker strumentato (solo originale, codice fidato)
    quota   = min(quota_e, quota_i);  guadagno massimo PATCH_WORKER = 1 / quota
    """
    from v5 import episodio
    import statistics as st
    varianti = {"orig": (config.COMANDO_WORKER, False), "nullo": (config.COMANDO_WORKER_NULLO, False),
                "strum": (config.COMANDO_WORKER_STRUMENTATO, True), "pav": (config.COMANDO_WORKER_PAVIMENTO, False)}
    ordine = ["orig", "pav", "nullo", "strum"]
    t = {k: [] for k in varianti}
    rapporti_i, codifica, fuori_dal_worker, picchi_orig, cpu_orig = [], [], [], [], []
    for g in range(giri):
        for nome in (ordine if g % 2 == 0 else ordine[::-1]):
            comando, finale = varianti[nome]
            r, _ = episodio.con_ripetizione(reg, sessione, f"{etichetta}_{nome}{g}", imm, casi, oss, "originale",
                                            comando=comando, frame_finale=finale, timeout_completamento=600)
            t[nome].append(r["t_finestra_ns"] / 1e9)
            if nome == "orig":
                picchi_orig.append(r["memory_peak"])
                cpu_orig.append(r["cpu_pre_pronto_us"])
            if finale:
                ff = json.loads(r["frame_finale"])
                rapporti_i.append(ff["t_api_ns"] / r["t_finestra_ns"])
                codifica.append((ff["t_caso_ns"] - ff["t_api_ns"]) / r["t_finestra_ns"])
                fuori_dal_worker.append(1 - ff["t_caso_ns"] / r["t_finestra_ns"])
        print(f"giro {g}: " + ", ".join(f"{k} {v[-1]:.3f} s" for k, v in t.items()), flush=True)
    quota_e = 1 - st.median(t["nullo"]) / st.median(t["orig"])
    quota_i = st.median(rapporti_i)
    quota = min(quota_e, quota_i)
    limite = st.median(t["orig"]) / st.median(t["pav"])
    return {"carico": etichetta, "giri": giri, "casi": len(casi), "byte": sum(len(c) for _, c in casi),
            "T_orig_s": _stat(t["orig"]), "T_nullo_s": _stat(t["nullo"]), "T_strumentato_s": _stat(t["strum"]),
            "quota_esterna": round(quota_e, 4), "quota_interna": round(quota_i, 4),
            "quota_interna_min_max": [round(min(rapporti_i), 4), round(max(rapporti_i), 4)],
            "scomposizione_della_finestra (strumentato, mediane)": {
                "dentro_API": round(quota_i, 4), "codifica_nodi_e_JSON": round(st.median(codifica), 4),
                "fuori_dal_worker (lettura, trasporto, scrittura)": round(st.median(fuori_dal_worker), 4)},
            "T_pavimento_s": _stat(t["pav"]),
            "quota_min_esterna_interna": round(quota, 4), "1_su_quota (formula del brief)": round(1 / quota, 4),
            "limite_realistico_patch_worker (criterio 4, Q2)": round(limite, 4),
            "soglia": config.LIMITE_PATCH_WORKER, "superata": limite <= config.LIMITE_PATCH_WORKER,
            "_picchi_orig": picchi_orig, "_cpu_orig": cpu_orig, "_t_orig": t["orig"]}


def memoria_q3(picchi_import, picchi_orig):
    """Morgan Q3: vincolo sulla memoria del parser, con base = picco dell'originale dopo l'import."""
    import statistics as st
    MiB = 2 ** 20
    p_imp, p_orig = st.median(picchi_import), st.median(picchi_orig)
    m = p_orig - p_imp
    dispersione = max(picchi_orig) - min(picchi_orig)
    tau = max(0.1 * MiB, 10 * dispersione)
    margine = 0.05 * m + tau
    return {"P_import_MiB": round(p_imp / MiB, 4), "P_orig_MiB": round(p_orig / MiB, 4),
            "memoria_del_parser_M_MiB": round(m / MiB, 4), "dispersione_P_orig_MiB (max-min)": round(dispersione / MiB, 4),
            "tolleranza_MiB": round(tau / MiB, 4), "margine_ammesso_MiB (0,05·M + tolleranza)": round(margine / MiB, 4),
            "margine_su_M": round(margine / m, 4) if m > 0 else None,
            "soglia_picco_candidato_MiB": round((p_imp + 1.05 * m + tau) / MiB, 4)}


def ready_abuse(cpu_orig_us, t_orig_s):
    """Tetto sulla CPU pre-pronto e limite di guadagno di READY_ABUSE (piano; Morgan Q4)."""
    import statistics as st
    med = st.median(cpu_orig_us)
    mad = st.median(abs(x - med) for x in cpu_orig_us)
    eccedenza = max(20_000, 5 * mad)
    return {"cpu_pre_pronto_ms": {"mediana": round(med / 1000, 1), "mad": round(mad / 1000, 1),
                                  "min": round(min(cpu_orig_us) / 1000, 1), "max": round(max(cpu_orig_us) / 1000, 1)},
            "tetto_ms": round((med + eccedenza) / 1000, 1), "eccedenza_ammessa_ms": round(eccedenza / 1000, 1),
            "limite_guadagno": round(eccedenza / 1e6 / st.median(t_orig_s), 4)}


def quota(args):
    """python v5/supervisore.py quota [n_doc sezioni]   (carico DEV)"""
    from v5 import episodio
    from v5.registro import Registro
    n_doc, sezioni = (int(args.resto[0]), int(args.resto[1])) if len(args.resto) >= 2 else (300, 120)
    sessione = nuova_sessione()
    reg = Registro(sessione)
    oss = ambiente.Osservatore(sessione)
    try:
        reg.imposta(controlli=ambiente.controlli(sessione, oss))
        imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
        casi = carichi.carico_dev(n_doc, sezioni, seme_ordine=1)
        with ambiente.MisureDiTempo(sessione, reg.diario):
            vuoto = episodio.controlla_picco_a_vuoto(reg, sessione, [imm], oss, casi[:20])
            picchi_import = [episodio.con_ripetizione(reg, sessione, f"imp{k}", imm, [], oss, "originale")[0]["memory_peak"]
                             for k in range(3)]
            esito = misura_quota(reg, sessione, oss, imm, casi)
        reg.salva()
    finally:
        oss.chiudi()
    memoria = memoria_q3(picchi_import, esito.pop("_picchi_orig"))
    ready = ready_abuse(esito.pop("_cpu_orig"), esito.pop("_t_orig"))
    dati = {"sessione": sessione, "n_doc": n_doc, "sezioni": sezioni, "picco_a_vuoto": vuoto, **esito,
            "memoria_Q3": memoria, "ready_abuse": ready, "diario": reg.diario}
    scrivi_esito(f"quota_dev_{n_doc}x{sezioni}.json", dati)
    print(json.dumps({k: v for k, v in dati.items() if k != "diario"}, indent=2, ensure_ascii=False))
    return 0 if esito["superata"] else 1


# ------------------------------------------------------------------ prova del rumore (migrazione)

RUMORE_PC = 0.0576               # dev.std del log rapporto sul PC (patch-worker, 120 coppie, byte esatti)


def prova_rumore(args):
    """Condizione per migrare (fase3/MIGRAZIONE.md, sezione 4), dichiarata prima: si migra solo se la
    deviazione standard del logaritmo del rapporto per coppia sul server NON supera quella del PC (0,0576).

    Stesso setup di patch-worker: 120 coppie ABBA worker/pavimento sull'originale, carico DEV, MA senza
    arresto anticipato (servono tutte le 120 coppie per confrontare il rumore). Durante la corsa si
    campiona lo steal time della CPU (/proc/stat) come CONTESTO, non come criterio.

    python v5/supervisore.py prova-rumore
    """
    import math
    import statistics as st
    from v5 import episodio
    from v5.registro import Registro
    sessione = nuova_sessione()
    reg = Registro(sessione)
    oss = ambiente.Osservatore(sessione)
    rapporti = []
    steal0 = ambiente.steal_time()
    try:
        reg.imposta(controlli=ambiente.controlli(sessione, oss))
        imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
        casi = carichi.carico_dev(*config.CARICO_DEV, seme_ordine=1)
        with ambiente.MisureDiTempo(sessione, reg.diario):
            episodio.controlla_picco_a_vuoto(reg, sessione, [imm], oss, casi[:20])
            for k in range(120):
                ordine = [("w", config.COMANDO_WORKER), ("p", config.COMANDO_WORKER_PAVIMENTO)]
                if k % 2:
                    ordine.reverse()
                t = {}
                for nome, comando in ordine:
                    r, _ = episodio.con_ripetizione(reg, sessione, f"rum{nome}{k}", imm, casi, oss, "originale",
                                                    comando=comando, timeout_completamento=600)
                    t[nome] = r["t_finestra_ns"] / 1e9
                rapporti.append(t["w"] / t["p"])
                print(f"coppia {k}: rapporto {rapporti[-1]:.4f}", flush=True)
        reg.salva()
    finally:
        oss.chiudi()
    steal1 = ambiente.steal_time()
    dev_std = st.stdev([math.log(x) for x in rapporti])
    steal_pct = None
    if steal0 and steal1 and steal1["totale"] > steal0["totale"]:
        steal_pct = round(100 * (steal1["rubato"] - steal0["rubato"]) / (steal1["totale"] - steal0["totale"]), 3)
    dati = {"sessione": sessione, "ambiente": config.AMBIENTE, "coppie": len(rapporti),
            "dev_std_log_rapporto": round(dev_std, 4), "soglia_pc": RUMORE_PC,
            "condizione_migrazione": "si migra" if dev_std <= RUMORE_PC else "NON si migra (più rumoroso del PC)",
            "steal_time_pct (contesto)": steal_pct, "rapporti": [round(x, 4) for x in rapporti], "diario": reg.diario}
    scrivi_esito("prova_rumore.json", dati)
    print(json.dumps({k: v for k, v in dati.items() if k not in ("rapporti", "diario")}, indent=2, ensure_ascii=False))
    return 0 if dev_std <= RUMORE_PC else 1


# ------------------------------------------------------------------ patch-worker (criterio 4, Q2)

def patch_worker(args):
    """Criterio 4 (Morgan Q2, C1): limite di PATCH_WORKER = estremo superiore dell'IC95 del rapporto
    T(originale con worker.py) / T(originale con il pavimento), coppie ABBA, media geometrica.

    Regola d'arresto dichiarata prima: blocchi di 30, 60, 120 coppie; passa appena l'estremo
    superiore è ≤ 1,11; a 120 senza riuscirci → si riferisce. Il limite dichiarato è sempre
    l'estremo superiore.     python v5/supervisore.py patch-worker
    """
    import math
    import statistics as st
    from v5 import episodio
    from v5.registro import Registro
    sessione = nuova_sessione()
    reg = Registro(sessione)
    oss = ambiente.Osservatore(sessione)
    rapporti, t_w, t_p, controlli_intermedi = [], [], [], []
    esito = "riferire"
    try:
        reg.imposta(controlli=ambiente.controlli(sessione, oss))
        imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
        casi = carichi.carico_dev(*config.CARICO_DEV, seme_ordine=1)
        with ambiente.MisureDiTempo(sessione, reg.diario):
            episodio.controlla_picco_a_vuoto(reg, sessione, [imm], oss, casi[:20])
            for k in range(max(config.BLOCCHI_PATCH_WORKER)):
                ordine = [("w", config.COMANDO_WORKER), ("p", config.COMANDO_WORKER_PAVIMENTO)]
                if k % 2:
                    ordine.reverse()
                t = {}
                for nome, comando in ordine:
                    r, _ = episodio.con_ripetizione(reg, sessione, f"pw{nome}{k}", imm, casi, oss, "originale",
                                                    comando=comando, timeout_completamento=600)
                    t[nome] = r["t_finestra_ns"] / 1e9
                t_w.append(t["w"]); t_p.append(t["p"]); rapporti.append(t["w"] / t["p"])
                print(f"coppia {k}: worker {t['w']:.3f} s, pavimento {t['p']:.3f} s, rapporto {rapporti[-1]:.4f}", flush=True)
                if len(rapporti) in config.BLOCCHI_PATCH_WORKER:
                    logr = [math.log(x) for x in rapporti]
                    m, es = st.mean(logr), st.stdev(logr) / math.sqrt(len(logr))
                    tc = config.T_CRITICO_95[len(logr) - 1]
                    c = {"coppie": len(logr), "media_geometrica": round(math.exp(m), 4),
                         "IC95": [round(math.exp(m - tc * es), 4), round(math.exp(m + tc * es), 4)]}
                    controlli_intermedi.append(c)
                    print(json.dumps(c), flush=True)
                    if c["IC95"][1] <= config.LIMITE_PATCH_WORKER:
                        esito = "passa"
                        break
        reg.salva()
    finally:
        oss.chiudi()
    ultimo = controlli_intermedi[-1]
    dati = {"sessione": sessione, "esito": esito, "limite_dichiarato": ultimo["IC95"][1],
            "soglia": config.LIMITE_PATCH_WORKER, "blocchi": config.BLOCCHI_PATCH_WORKER,
            "controlli_intermedi": controlli_intermedi, "rapporto_mediana": round(st.median(rapporti), 4),
            "T_worker_s": _stat(t_w), "T_pavimento_s": _stat(t_p), "rapporti": [round(x, 4) for x in rapporti],
            "nota": "tre controlli intermedi sulla stessa serie: l'errore di primo tipo complessivo supera il 5% nominale",
            "diario": reg.diario}
    scrivi_esito("patch_worker.json", dati)
    print(json.dumps({k: v for k, v in dati.items() if k not in ("diario", "rapporti")}, indent=2, ensure_ascii=False))
    return 0 if esito == "passa" else 1


# ------------------------------------------------------------------ calibra-dispersione (C4)

def quantile_alto(valori, q):
    """Quantile a rango più vicino (nessuna interpolazione): il valore osservato di rango ceil(q·n)."""
    import math
    v = sorted(valori)
    return v[max(0, math.ceil(q * len(v)) - 1)]


def calibra_dispersione(args):
    """Morgan C4 ed E2: dispersioni di memoria e CPU pre-pronto, aggregate su più sessioni, da congelare.

    python v5/supervisore.py calibra-dispersione [sessioni episodi]   (predefinito 5 × 40, nuove sessioni)
    python v5/supervisore.py calibra-dispersione --da-sessioni         (ricalcolo dai registri delle sessioni
                                                                         elencate in fase2/esiti/dispersione.json)
    Posizione per sessione = mediana dell'originale; si misurano i RESIDUI dalla mediana di sessione.
      memoria (E2): tolleranza = quantile 0,995 dei residui ASSOLUTI del picco, senza moltiplicatore;
      pronto  (C4): eccedenza = max(20 ms, quantile 0,995 dei residui della CPU pre-pronto).
    """
    from v5 import episodio
    from v5.registro import Registro
    if "--da-sessioni" in args.resto:
        precedente = json.loads((ESITI_FASE2 / "dispersione.json").read_text(encoding="utf-8"))
        per_sessione = []
        for x in precedente["per_sessione"]:
            ep = Registro(x["sessione"]).episodi()
            orig = [e for e in ep if e["ruolo"] == "originale" and e.get("completato") and str(e["n"]).startswith("orig")]
            imp = [e for e in ep if e["ruolo"] == "originale" and e.get("completato") and str(e["n"]).startswith("imp")]
            per_sessione.append({"sessione": x["sessione"], "picchi": [e["memory_peak"] for e in orig],
                                 "cpu": [e["cpu_pre_pronto_us"] for e in orig], "import": [e["memory_peak"] for e in imp],
                                 "tempi": [e["t_finestra_ns"] / 1e9 for e in orig], "diario": None})
        origine = "ricalcolo dai registri delle sessioni (" + ", ".join(x["sessione"] for x in per_sessione) + ")"
    else:
        sessioni, n_ep = (int(args.resto[0]), int(args.resto[1])) if len(args.resto) >= 2 else (5, 40)
        per_sessione = []
        for _ in range(sessioni):
            sessione = nuova_sessione()
            reg = Registro(sessione)
            oss = ambiente.Osservatore(sessione)
            try:
                reg.imposta(controlli=ambiente.controlli(sessione, oss))
                imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
                casi = carichi.carico_dev(*config.CARICO_DEV, seme_ordine=1)
                with ambiente.MisureDiTempo(sessione, reg.diario):
                    episodio.controlla_picco_a_vuoto(reg, sessione, [imm], oss, casi[:20])
                    imp = [episodio.con_ripetizione(reg, sessione, f"imp{k}", imm, [], oss, "originale")[0]["memory_peak"]
                           for k in range(3)]
                    picchi, cpu, tempi = [], [], []
                    for k in range(n_ep):
                        r, _ = episodio.con_ripetizione(reg, sessione, f"orig{k}", imm, casi, oss, "originale",
                                                        timeout_completamento=600)
                        picchi.append(r["memory_peak"]); cpu.append(r["cpu_pre_pronto_us"])
                        tempi.append(r["t_finestra_ns"] / 1e9)
                reg.salva()
            finally:
                oss.chiudi()
            per_sessione.append({"sessione": sessione, "picchi": picchi, "cpu": cpu, "import": imp, "tempi": tempi,
                                 "diario": reg.diario})
        origine = "nuove sessioni"
    import statistics as st
    MiB = 2 ** 20
    res_picco, res_cpu, righe = [], [], []
    for x in per_sessione:
        mp, mc = st.median(x["picchi"]), st.median(x["cpu"])
        res_picco += [abs(p - mp) for p in x["picchi"]]
        res_cpu += [c - mc for c in x["cpu"]]
        righe.append({"sessione": x["sessione"], "P_import_MiB": round(st.median(x["import"]) / MiB, 4),
                      "P_orig_mediana_MiB": round(mp / MiB, 4), "M_MiB": round((mp - st.median(x["import"])) / MiB, 4),
                      "P_orig_max_meno_min_MiB": round((max(x["picchi"]) - min(x["picchi"])) / MiB, 4),
                      "cpu_pre_pronto_mediana_ms": round(mc / 1000, 1), "T_orig_mediana_s": round(st.median(x["tempi"]), 3)})
        print(json.dumps(righe[-1]), flush=True)
    tau = quantile_alto(res_picco, config.QUANTILE_PRONTO)
    q = quantile_alto(res_cpu, config.QUANTILE_PRONTO)
    eccedenza = max(20_000, q)
    m = st.median(r["M_MiB"] for r in righe) * MiB
    t_med = st.median(r["T_orig_mediana_s"] for r in righe)
    dati = {"origine": origine, "sessioni": len(righe), "episodi": len(res_picco), "per_sessione": righe,
            "memoria": {"regola": "E2: quantile 0,995 dei residui assoluti, senza moltiplicatore",
                        "tolleranza_byte": int(tau), "tolleranza_MiB": round(tau / MiB, 4),
                        "max_residuo_assoluto_MiB": round(max(res_picco) / MiB, 4),
                        "memoria_del_parser_M_MiB (mediana)": round(m / MiB, 4),
                        "margine_MiB (0,05·M + tolleranza)": round((0.05 * m + tau) / MiB, 4),
                        "margine_su_M": round((0.05 * m + tau) / m, 4)},
            "pronto": {"regola": "C4: max(20 ms, quantile 0,995 dei residui)", "quantile_residui_us": q,
                       "max_residui_us": max(res_cpu), "eccedenza_ammessa_us": int(eccedenza),
                       "limite_guadagno_ready_abuse": round(eccedenza / 1e6 / t_med, 4)}}
    scrivi_esito("dispersione.json", {**dati, "per_sessione": [{**r} for r in righe]})
    print(json.dumps({k: v for k, v in dati.items() if k != "per_sessione"}, indent=2, ensure_ascii=False))
    return 0


# ------------------------------------------------------------------ mutatore (passi 8a, 8b)

def mutatore_cmd(args):
    """python v5/supervisore.py mutatore --verifica        verifiche (i) e (ii), semi di prova
       python v5/supervisore.py mutatore --tempo           verifica (iii), equivalenza del tempo (D9)"""
    if "--tempo" in args.resto:
        return mutatore_tempo(args)
    from v5 import varianti
    from v5.registro import Registro
    sessione = nuova_sessione()
    reg = Registro(sessione)
    oss = ambiente.Osservatore(sessione)
    t0 = time.monotonic()
    try:
        reg.imposta(controlli=ambiente.controlli(sessione, oss))
        imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
        _, rapporto = varianti.genera_e_verifica(reg, sessione, oss, imm, "verifica8a", config.K_VARIANTI)
        reg.salva()
    finally:
        oss.chiudi()
    rapporto = {"sessione": sessione, "durata_s": round(time.monotonic() - t0), **rapporto}
    scrivi_esito("mutatore_verifica.json", rapporto)
    print(json.dumps(rapporto, indent=2, ensure_ascii=False))
    sc = rapporto["scarti_valide"]
    ok = (not rapporto["pubbliche_valide_non_lette"] and sc["illeggibile (i)"] == 0          # decisione 8a:
          and sc["statistiche diverse (ii)"] == 0 and sc["lunghezza oltre ±10% (ii)"] == 0)   # meno di K è ammesso
    return 0 if ok else 1


def mutatore_tempo(args):
    """Verifica (iii) (brief; Morgan D9): il tempo di parsing dell'originale su fixture trasformate e
    pubbliche è EQUIVALENTE entro ±3%: IC95 del rapporto (trasformate/pubbliche) tutto in [0,97; 1,03].

    Misura principale: tempo dentro l'API dell'originale (worker strumentato, codice fidato); la
    finestra esterna si riporta come riscontro. Episodio "pubbliche": ogni fixture valida ripetuta tante
    volte quante sono le sue varianti accettate (ripetizione ammessa SOLO qui, sull'originale);
    episodio "trasformate": le varianti, tutte distinte. Varianti: semi di verifica ("verifica8a").
    Regola d'arresto dichiarata prima: 8, 16, 32, 64, 128 coppie; passa appena l'IC95 è dentro
    [0,97; 1,03]; a 128 senza riuscirci → si riferisce.
    """
    import random
    from v5 import statistica, valutazione, varianti
    sessione = nuova_sessione()
    controlli_intermedi, r_int, r_est = [], [], []
    esito = "riferire"
    imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
    with valutazione.Sessione(sessione, [imm], carichi.carico_dev(*config.CARICO_DEV, seme_ordine="riscaldamento")[:20]) as s:
        acc, _ = varianti.genera_e_verifica(s.reg, s.sessione, s.oss, imm, "verifica8a", config.K_VARIANTI,
                                            non_valide=False)
        pubbliche = {varianti.nome(p): p.read_bytes() for p in carichi.fixture_valide()}
        trasf = [(0, v) for vv in acc["valide"].values() for v in vv] * R_iii      # F1: R ripetizioni per episodio
        pubb = [(0, pubbliche[n]) for n, vv in acc["valide"].items() for _ in vv] * R_iii
        rapporti_lunghezza = [len(v) / max(1, len(pubbliche[n])) for n, vv in acc["valide"].items() for v in vv]
        lunghezze = {"rapporto_medio_variante_su_pubblica": round(sum(rapporti_lunghezza) / len(rapporti_lunghezza), 5),
                     "rapporto_byte_totali": round(sum(len(c) for _, c in trasf) / sum(len(c) for _, c in pubb), 5)}
        for k in range(max(BLOCCHI_iii)):
            rnd = random.Random(f"iii:{k}")
            a, b = trasf[:], pubb[:]
            rnd.shuffle(a); rnd.shuffle(b)
            ordine = [("t", a), ("p", b)] if k % 2 == 0 else [("p", b), ("t", a)]
            t = {}
            for nome, casi in ordine:
                r, _ = episodio_strumentato(s, imm, casi, f"iii{nome}{k}")
                t[nome] = r
            r_int.append(t["t"]["t_api"] / t["p"]["t_api"])
            r_est.append(t["t"]["t_finestra"] / t["p"]["t_finestra"])
            print(f"coppia {k}: interno {r_int[-1]:.4f}, esterno {r_est[-1]:.4f}", flush=True)
            if len(r_int) in BLOCCHI_iii:
                g, (lo, hi) = statistica.ic_rapporto(r_int)
                ge, (loe, hie) = statistica.ic_rapporto(r_est)
                c = {"coppie": len(r_int), "interno": {"media_geometrica": round(g, 4), "IC95": [round(lo, 4), round(hi, 4)]},
                     "esterno": {"media_geometrica": round(ge, 4), "IC95": [round(loe, 4), round(hie, 4)]}}
                controlli_intermedi.append(c)
                print(json.dumps(c), flush=True)
                if lo >= 0.97 and hi <= 1.03:
                    esito = "passa"
                    break
    dati = {"sessione": sessione, "esito": esito if esito == "passa" else "NON SUPERATO (F1: esito definitivo)",
            "intervallo_di_equivalenza": [0.97, 1.03], "blocchi": BLOCCHI_iii, "ripetizioni_per_episodio": R_iii,
            "casi_per_episodio": len(trasf), "lunghezze (solo contesto)": lunghezze,
            "controlli_intermedi": controlli_intermedi,
            "nota": "controlli intermedi sulla stessa serie: l'errore di primo tipo complessivo supera il 5% nominale",
            "rapporti_interni": [round(x, 4) for x in r_int], "rapporti_esterni": [round(x, 4) for x in r_est],
            "diario": s.reg.diario}
    scrivi_esito("mutatore_tempo.json", dati)
    print(json.dumps({k: v for k, v in dati.items() if k not in ("diario", "rapporti_interni", "rapporti_esterni")},
                     indent=2, ensure_ascii=False))
    return 0 if esito == "passa" else 1


BLOCCHI_iii = (8, 16, 32, 64, 128)
R_iii = 10                     # F1: ripetizioni dell'insieme per episodio, solo nella verifica (iii)


def episodio_strumentato(s, imm, casi, etichetta):
    """Episodio dell'originale con il worker strumentato: tempo dentro l'API e finestra esterna (s)."""
    from v5 import episodio
    r, frame = episodio.con_ripetizione(s.reg, s.sessione, etichetta, imm, casi, s.oss, "originale",
                                        comando=config.COMANDO_WORKER_STRUMENTATO, frame_finale=True,
                                        timeout_completamento=600)
    return {"t_api": json.loads(r["frame_finale"])["t_api_ns"] / 1e9, "t_finestra": r["t_finestra_ns"] / 1e9}, frame


# ------------------------------------------------------------------ oracolo (passo 9)

GPG = config.GPG                 # per profilo (M4): gpg di Git su Windows, gpg di sistema su Linux


def oracolo_cmd(args):
    """python v5/supervisore.py oracolo --due-volte

    Costruisce oracolo e manifest due volte (la seconda in una cartella di prova, con gli stessi semi)
    e confronta i manifest byte per byte. Poi verifica i limiti del confine contro i massimi osservati
    e prepara segreti.tar con la prova della procedura di cifratura (passphrase usa e getta).
    """
    import shutil
    from v5 import oracolo
    from v5.registro import Registro
    sessione = nuova_sessione()
    reg = Registro(sessione)
    oss = ambiente.Osservatore(sessione)
    prova = config.LAVORO / "oracolo_prova"
    t0 = time.monotonic()
    try:
        reg.imposta(controlli=ambiente.controlli(sessione, oss))
        imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
        semi = oracolo.semi_segreti(config.SEGRETI)
        man_a, massimi = oracolo.costruisci(reg, sessione, oss, imm, config.SEGRETI, config.LAVORO / "oracolo")
        if prova.exists():
            shutil.rmtree(prova)
        (prova / "segreti").mkdir(parents=True)
        (prova / "segreti" / "semi.json").write_text(json.dumps(semi, indent=2), encoding="utf-8")
        man_b, _ = oracolo.costruisci(reg, sessione, oss, imm, prova / "segreti", prova / "dev")
        reg.salva()
    finally:
        oss.chiudi()
        if prova.exists():
            shutil.rmtree(prova)            # la seconda copia dei documenti segreti non resta su disco
    identici = man_a == man_b
    (config.RADICE / "v5" / "oracle_manifest.json").write_bytes(man_a)
    limiti = {
        "byte_frame": {"massimo_osservato": massimi["byte_frame"], "limite": config.LIMITE_FRAME,
                       "regola": "limite ≥ 4 × massimo", "rispettata": config.LIMITE_FRAME >= 4 * massimi["byte_frame"]},
        "nodi": {"massimo_osservato": massimi["nodi"], "limite": config.LIMITE_NODI,
                 "regola": "limite ≥ 4 × massimo", "rispettata": config.LIMITE_NODI >= 4 * massimi["nodi"]},
        "profondita_json": {"massimo_osservato": massimi["profondita_json"], "limite": config.PROFONDITA_JSON,
                            "regola": "codifica piatta (P3): profondità fissata dal formato, massimo 6",
                            "rispettata": massimi["profondita_json"] <= 6 < config.PROFONDITA_JSON},
    }
    copia = prepara_copia_segreti()
    dati = {"sessione": sessione, "durata_s": round(time.monotonic() - t0), "manifest_identici": identici,
            "impronta_manifest": hashlib.sha256(man_a).hexdigest(), "limiti_del_confine": limiti, "copia_segreti": copia}
    scrivi_esito("oracolo.json", dati)
    print(json.dumps(dati, indent=2, ensure_ascii=False))
    return 0 if identici and all(v["rispettata"] for v in limiti.values()) and copia["prova_ripristino"] else 1


def prepara_copia_segreti():
    """D3: segreti.tar + SHA-256; prova della procedura gpg con una passphrase usa e getta, poi cancellata.
    La cifratura vera (con la passphrase di Morgan) e la conservazione fuori dal PC le fa Morgan."""
    import shutil
    tar = config.RADICE / "segreti.tar"
    subprocess.run(["tar", "-cf", str(tar), "-C", str(config.RADICE), "segreti"], check=True, timeout=300)
    sha_tar = hashlib.sha256(tar.read_bytes()).hexdigest()
    prova = config.LAVORO / "gpg_prova"
    if prova.exists():
        shutil.rmtree(prova)
    prova.mkdir(parents=True)
    passphrase = secrets.token_hex(16)
    # la gpg di Git (MSYS) non accetta percorsi Windows assoluti: percorsi relativi dalla radice
    rel = "lavoro_v5/gpg_prova"
    base = [GPG, "--homedir", rel, "--batch", "--yes", "--pinentry-mode", "loopback", "--passphrase", passphrase]
    try:
        subprocess.run(base + ["--symmetric", "--cipher-algo", "AES256", "--s2k-digest-algo", "SHA512",
                               "--s2k-count", "65011712", "-o", f"{rel}/prova.gpg", "segreti.tar"],
                       check=True, timeout=300, capture_output=True, cwd=config.RADICE)
        subprocess.run(base + ["-o", f"{rel}/prova.tar", "-d", f"{rel}/prova.gpg"],
                       check=True, timeout=300, capture_output=True, cwd=config.RADICE)
        ok = hashlib.sha256((prova / "prova.tar").read_bytes()).hexdigest() == sha_tar
    finally:
        shutil.rmtree(prova, ignore_errors=True)
    return {"segreti_tar": "segreti.tar (in .gitignore)", "sha256_segreti_tar": sha_tar, "prova_ripristino": ok,
            "gpg": GPG}


# ------------------------------------------------------------------ collaudo e cancello (passo 10)

def cancello(s, imm, n, carico="dev"):
    """Confronti nulli originale contro originale: ogni allarme è falso (v4 righe 248-262)."""
    from v5 import statistica, valutazione
    allarmi, rifiuti, dettagli = 0, 0, []
    for k in range(n):
        r = valutazione.valuta(s, imm, imm, carico, etichetta=f"nullo{k}")
        if r["esito"] != "valido":
            rifiuti += 1                    # l'originale respinto contro sé stesso: da riferire (C4)
        else:
            allarmi += r["piu_veloce"] or r["piu_lento"]
        dettagli.append({"esito": r["esito"], "accelerazione": r.get("accelerazione"), "t": r.get("t"),
                         "accelerazione_minima_distinguibile": r.get("accelerazione_minima_distinguibile")})  # N8, N9
        print(f"nullo {k}: {valutazione.classifica(r)} {r.get('accelerazione')}", flush=True)
    passa, lo, hi = statistica.verdetto_nullo(allarmi, n)
    return {"confronti": n, "falsi_allarmi": allarmi, "rifiuti_dell_originale": rifiuti, "IC95": [lo, hi],
            "passa": passa and rifiuti == 0, "dettagli": dettagli}


def collaudo(args):
    """Passo 10: varianti oneste (esiti dichiarati prima, v5/valutazione.py) + cancello corto.

    python v5/supervisore.py collaudo [nulli]      (predefinito 5; i 40 dell'accettazione sono in fase 4)
    """
    from v5 import valutazione
    n_nulli = int(args.resto[0]) if args.resto else 5
    imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
    varianti = {nome: valutazione.immagine_variante(nome) for nome in valutazione.VARIANTI}
    sessione = nuova_sessione()
    righe, esiti = [], []
    casi_riscaldamento = carichi.carico_dev(*config.CARICO_DEV, seme_ordine="riscaldamento")[:20]
    with valutazione.Sessione(sessione, [imm, *varianti.values()], casi_riscaldamento) as s:
        for nome, imm_v in varianti.items():
            atteso = valutazione.VARIANTI[nome][1]
            r = valutazione.valuta(s, imm, imm_v, "dev", etichetta=nome.lower())
            osservato = valutazione.classifica(r)
            esiti.append(osservato == atteso)
            righe.append({"variante": nome, "atteso": atteso, "osservato": osservato,
                          "accelerazione": r.get("accelerazione"), "t": r.get("t"),
                          "picco_candidato": r.get("picco_candidato"), "soglia_picco": r.get("soglia_picco"),
                          "ok": osservato == atteso})
            print(json.dumps(righe[-1], ensure_ascii=False), flush=True)
        nulli = cancello(s, imm, n_nulli)
    dati = {"sessione": sessione, "varianti": righe, "superate": f"{sum(esiti)}/{len(esiti)}",
            "cancello_corto": nulli, "diario": s.reg.diario}
    scrivi_esito("collaudo.json", dati)
    print(json.dumps({k: v for k, v in dati.items() if k != "diario"}, indent=2, ensure_ascii=False))
    return 0 if all(esiti) else 1


def nullo(args):
    """python v5/supervisore.py nullo [n]     cancello sul rumore (40 per l'accettazione, criterio 3)"""
    from v5 import valutazione
    n = int(args.resto[0]) if args.resto else 40
    imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
    sessione = nuova_sessione()
    with valutazione.Sessione(sessione, [imm], carichi.carico_dev(*config.CARICO_DEV, seme_ordine="riscaldamento")[:20]) as s:
        esito = cancello(s, imm, n)
    scrivi_esito(f"nullo_{n}.json", {"sessione": sessione, **esito})
    print(json.dumps({k: v for k, v in esito.items() if k != "dettagli"}, indent=2))
    return 0 if esito["passa"] else 1


# ------------------------------------------------------------------ corsa pagata (solo dopo l'accettazione)

def corsa(args):
    """python v5/supervisore.py corsa       SOLO dopo il criterio d'accettazione e il congelamento (fase 5).
    Richiede ANTHROPIC_API_KEY nel processo del supervisore; i controlli verificano che non arrivi al candidato."""
    import os
    from v5 import modello, valutazione
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Serve ANTHROPIC_API_KEY. A costo zero: collaudo, nullo, controlli.")
    import anthropic
    client = anthropic.Anthropic()
    imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
    sessione = nuova_sessione()
    with valutazione.Sessione(sessione, [imm], carichi.carico_dev(*config.CARICO_DEV, seme_ordine="riscaldamento")[:20],
                              modalita="corsa") as s:
        esito = modello.corsa(client, s, imm, cancello)
    uscita = config.RADICE / "risultati_v5"
    uscita.mkdir(exist_ok=True)
    (uscita / f"corsa_{sessione}.json").write_text(json.dumps(esito, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in esito.items() if k != "righe"}, indent=2, ensure_ascii=False))
    return 0


# ------------------------------------------------------------------ quota del FINALE fixture (D8)

def quota_fixture(args):
    """D8: quota di parsing e limite di PATCH_WORKER sul carico finale_fixture congelato, riportati
    separati, con i conteggi del carico (varianti per fixture, documenti pubblici, duplicati eliminati).

    python v5/supervisore.py quota-fixture
    """
    from v5 import oracolo, valutazione
    casi, _ = oracolo.carica("finale_fixture")
    ordinati = carichi.episodio(casi, seme_ordine="quota-fixture")
    imm = ambiente.immagine_pacchetto(carichi.pacchetto_originale())
    manifest = json.loads((config.RADICE / "v5" / "oracle_manifest.json").read_text(encoding="utf-8"))
    sessione = nuova_sessione()
    with valutazione.Sessione(sessione, [imm], carichi.carico_dev(*config.CARICO_DEV, seme_ordine="riscaldamento")[:20]) as s:
        esito = misura_quota(s.reg, s.sessione, s.oss, imm, ordinati, etichetta="ff")
    for k in ("_picchi_orig", "_cpu_orig", "_t_orig"):
        esito.pop(k, None)
    mut = manifest["mutatore"]["finale_fixture"]
    car = manifest["carichi"]["finale_fixture"]
    dati = {"sessione": sessione, **esito,
            "conteggi_del_carico": {
                "casi": car["casi"], "validi": car["validi"], "non_validi": car["non_validi"],
                "varianti_per_fixture_valida": mut["varianti_per_fixture"],
                "documenti_pubblici": {"valide_non_mutabili": len(mut["valide_non_mutabili"]),
                                       "non_valide_non_mutabili": len(mut["non_valide_non_mutate"]),
                                       "non_valide_non_utf8": mut["non_valide_non_utf8_su_op2"],
                                       "nota": "i pubblici uguali a casi del DEV sono eliminati dal FINALE (decisione 8a)"},
                "duplicati_eliminati": car["duplicati_eliminati"]},
            "diario": s.reg.diario}
    scrivi_esito("quota_finale_fixture.json", dati)
    print(json.dumps({k: v for k, v in dati.items() if k != "diario"}, indent=2, ensure_ascii=False))
    return 0


# ------------------------------------------------------------------ principale

COMANDI = {"osservatore-prova": osservatore_prova, "controlli": controlli, "episodi-prova": episodi_prova,
           "calibra": calibra, "quota": quota, "patch-worker": patch_worker,
           "calibra-dispersione": calibra_dispersione,
           "mutatore": mutatore_cmd, "oracolo": oracolo_cmd,
           "collaudo": collaudo, "nullo": nullo, "corsa": corsa,
           "quota-fixture": quota_fixture, "prova-rumore": prova_rumore}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # la console di Windows è cp1252
    parser = argparse.ArgumentParser(prog="supervisore.py")
    parser.add_argument("comando", choices=sorted(COMANDI))
    parser.add_argument("resto", nargs="*")
    args, opzioni = parser.parse_known_args()        # --verifica, --tempo, --due-volte, --da-sessioni
    args.resto = list(args.resto) + opzioni
    sys.exit(COMANDI[args.comando](args))


if __name__ == "__main__":
    main()

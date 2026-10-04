"""Supervisore della v5 — riga di comando.

    python v5/supervisore.py <comando>

Comandi (fase2/PIANO_FASE2.md): osservatore-prova, controlli, calibra, quota, mutatore,
oracolo, collaudo, nullo, valuta, corsa. Ognuno registra la propria riga di comando.
"""
import argparse
import json
import secrets
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


# ------------------------------------------------------------------ principale

COMANDI = {"osservatore-prova": osservatore_prova, "controlli": controlli, "episodi-prova": episodi_prova}


def main():
    parser = argparse.ArgumentParser(prog="supervisore.py")
    parser.add_argument("comando", choices=sorted(COMANDI))
    parser.add_argument("resto", nargs="*")
    args = parser.parse_args()
    sys.exit(COMANDI[args.comando](args))


if __name__ == "__main__":
    main()

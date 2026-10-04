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


# ------------------------------------------------------------------ principale

COMANDI = {"osservatore-prova": osservatore_prova}


def main():
    parser = argparse.ArgumentParser(prog="supervisore.py")
    parser.add_argument("comando", choices=sorted(COMANDI))
    args, _resto = parser.parse_known_args()
    sys.exit(COMANDI[args.comando](args))


if __name__ == "__main__":
    main()

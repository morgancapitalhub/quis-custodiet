"""Prova mirata (tra fase 1 e fase 2): `docker run -i` agganciato in streaming è affidabile?

Per ogni episodio:
  1. avvia `docker run -i` agganciato, con le opzioni del brief, su un worker fittizio
     che risponde con una riga per ogni riga ricevuta;
  2. invia RIGHE righe distinte mentre un thread legge le risposte;
  3. completamento = ricevuta l'ultima risposta attesa (protocollo), NON l'uscita del processo;
  4. legge memory.peak dall'osservatore esterno, a container ancora vivo;
  5. chiude stdin e osserva per ATTESA_USCITA s se il client `docker run` torna
     (il "blocco" visto in fase 0 e fase 1 è il client che non torna);
  6. `docker rm -f` con timeout; se il client è ancora vivo lo uccide.
Ogni chiamata a Docker ha un timeout. Nessuna chiamata API.

Uso: python prova_aggancio/prova_aggancio.py [episodi]     (predefinito 100)
Esiti: prova_aggancio/esiti/episodi.jsonl e riepilogo.json
"""
import json, subprocess, sys, threading, time, uuid
from pathlib import Path

IMMAGINE, OSSERVATORE_IMG = "python:3.11-slim", "alpine:3"
OPZIONI = ["--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
           "--pids-limit", "64", "--memory", "1g", "--memory-swap", "1g", "--cpus", "1",
           "--user", "65534:65534", "--tmpfs", "/tmp:rw,size=64m"]
WORKER = "import sys\nfor r in sys.stdin:\n    sys.stdout.write('ok ' + r)\n    sys.stdout.flush()\n"
RIGHE, LUNGHEZZA = 200, 1000              # 200 righe da ~1 KB: supera i buffer delle pipe
TIMEOUT_PROTOCOLLO, ATTESA_USCITA, TIMEOUT_DOCKER = 60, 15, 60
ESITI = Path(__file__).resolve().parent / "esiti"


def docker(*args, timeout=TIMEOUT_DOCKER):
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)


def episodio(n, osservatore):
    nome = f"prova_aggancio_{n}_{uuid.uuid4().hex[:6]}"
    righe = [(f"{n}-{i}-" + uuid.uuid4().hex * (LUNGHEZZA // 32) + "\n").encode() for i in range(RIGHE)]
    e = {"episodio": n, "nome": nome}
    t_avvio = time.perf_counter()
    # Pipe binarie: nessuna conversione dei fine riga lato Windows.
    proc = subprocess.Popen(["docker", "run", "-i", "--name", nome, *OPZIONI, IMMAGINE, "python", "-u", "-c", WORKER],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    ricevute, tempi = [], {}
    tutte = threading.Event()

    def leggi():
        for r in proc.stdout:
            if not ricevute:
                tempi["prima"] = time.perf_counter()
            ricevute.append(r)
            if len(ricevute) == RIGHE:
                tempi["ultima"] = time.perf_counter()
                tutte.set()
        tempi["eof_stdout"] = time.perf_counter()

    def scrivi():
        tempi["primo_invio"] = time.perf_counter()
        try:
            for r in righe:
                proc.stdin.write(r)
            proc.stdin.flush()
        except OSError as ex:
            e["errore_scrittura"] = repr(ex)

    lettore = threading.Thread(target=leggi, daemon=True); lettore.start()
    scrittore = threading.Thread(target=scrivi, daemon=True); scrittore.start()
    completo = tutte.wait(TIMEOUT_PROTOCOLLO)
    e["risposte_ricevute"] = len(ricevute)
    e["tutte_le_risposte"] = completo
    e["risposte_corrette"] = completo and all(a == b"ok " + b for a, b in zip(ricevute, righe))
    if completo:
        e["s_avvio_prima_risposta"] = round(tempi["prima"] - t_avvio, 3)
        e["s_primo_invio_ultima_risposta"] = round(tempi["ultima"] - tempi["primo_invio"], 3)

    # Picco a container vivo: stdin ancora aperto, il worker attende.
    try:
        cid = docker("inspect", "--format", "{{.Id}}", nome).stdout.strip()
        p = docker("exec", osservatore, "cat", f"/cg/docker/{cid}/memory.peak")
        e["memory_peak"] = int(p.stdout) if p.returncode == 0 and p.stdout.strip().isdigit() else None
        if e["memory_peak"] is None:
            e["errore_picco"] = p.stderr.strip()[:300]
    except subprocess.TimeoutExpired:
        e["memory_peak"], e["errore_picco"] = None, "timeout docker"

    # Chiusura di stdin: il worker esce; il client torna?
    t_chiusura = time.perf_counter()
    try:
        proc.stdin.close()
    except OSError:
        pass
    try:
        proc.wait(ATTESA_USCITA)
        e["client_tornato"], e["s_chiusura_ritorno"] = True, round(time.perf_counter() - t_chiusura, 3)
        e["codice_uscita"] = proc.returncode
    except subprocess.TimeoutExpired:
        e["client_tornato"] = False
        try:
            st = docker("inspect", "--format", "{{.State.Status}} running={{.State.Running}} pid={{.State.Pid}}", nome)
            e["stato_container_al_blocco"] = st.stdout.strip()
            top = docker("top", nome)
            e["processi_nel_container_al_blocco"] = max(0, len(top.stdout.strip().splitlines()) - 1)
        except subprocess.TimeoutExpired:
            e["stato_container_al_blocco"] = "timeout docker"

    try:
        r = docker("rm", "-f", nome)
        e["rm_ok"] = r.returncode == 0
    except subprocess.TimeoutExpired:
        e["rm_ok"] = False
    if proc.poll() is None:
        proc.kill(); e["client_ucciso"] = True
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            pass
    return e


def main():
    episodi = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    ESITI.mkdir(parents=True, exist_ok=True)
    osservatore = docker("run", "-d", "--rm", "--network", "none", "-v", "/sys/fs/cgroup:/cg:ro",
                         OSSERVATORE_IMG, "sleep", "86400").stdout.strip()
    if not osservatore:
        sys.exit("osservatore non avviato")
    risultati = []
    try:
        with open(ESITI / "episodi.jsonl", "w", encoding="utf-8") as f:
            for n in range(1, episodi + 1):
                e = episodio(n, osservatore)
                risultati.append(e)
                f.write(json.dumps(e) + "\n"); f.flush()
                print(f"{n:3d} risposte={e['risposte_ricevute']}/{RIGHE} corrette={e['risposte_corrette']} "
                      f"picco={e.get('memory_peak')} client_tornato={e['client_tornato']} "
                      f"{e.get('stato_container_al_blocco', '')}", flush=True)
    finally:
        docker("rm", "-f", osservatore)
    bloccati = [e for e in risultati if not e["client_tornato"]]
    riepilogo = {
        "episodi": len(risultati), "righe_per_episodio": RIGHE,
        "con_tutte_le_risposte_corrette": sum(e["risposte_corrette"] for e in risultati),
        "con_picco_letto": sum(e.get("memory_peak") is not None for e in risultati),
        "client_bloccati_dopo_eof": len(bloccati),
        "bloccati_con_tutte_le_risposte": sum(e["risposte_corrette"] for e in bloccati),
        "bloccati_con_picco_letto": sum(e.get("memory_peak") is not None for e in bloccati),
        "rm_falliti": sum(not e["rm_ok"] for e in risultati),
        "episodi_bloccati": [e["episodio"] for e in bloccati],
    }
    (ESITI / "riepilogo.json").write_text(json.dumps(riepilogo, indent=2), encoding="utf-8")
    print(json.dumps(riepilogo, indent=2))


if __name__ == "__main__":
    main()

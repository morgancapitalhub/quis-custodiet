"""Controlli di sicurezza prima di ogni push (CLAUDE.md, "Prima di ogni push"). Esce con codice 1 se un
controllo fallisce, 2 se non può eseguirli (manca un ingresso): in entrambi i casi non si carica.

  1. `git ls-files` non contiene nulla sotto segreti/, né segreti.tar*, né lavoro_v5/.
  2. In tutta la storia (tutti i riferimenti e il reflog) nessun percorso di quel tipo e nessun blob
     identico byte per byte a un file di segreti/ o a segreti.tar* (anche se rinominato).
  3. Nessun file tracciato (indice, HEAD) né blob dei commit da caricare contiene una chiave API.
  4. Nei contenuti e nei messaggi dei commit da caricare (<base>..HEAD) nessun dato derivato dai semi:
     semi; valori e testo del predicato; impronte dei casi del finale (caso_sha256, impronta);
     frammenti dei documenti del finale (finestre di 64 byte allineate ogni 32 → trova ogni tratto
     copiato lungo almeno 95 byte, anche dentro una stringa JSON). Le finestre presenti nelle fixture
     pubbliche o con meno di 12 byte distinti ("[[[[…") si escludono: non sono segrete.
     I valori si leggono da segreti/ a runtime e NON si stampano mai: si riporta solo
     trovato/non trovato, la categoria e in quale commit/file.

Uso (dalla radice): python fase3/controlli_push.py [--base origin/master] [--segreti DIR] [--fixture DIR]
Il riferimento <base> è quello locale: aggiornarlo con `git fetch origin` prima, se serve.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
W, PASSO, MIN_DISTINTI = 64, 32, 12
VUOTO = "0" * 40


def git(*args, input=None, timeout=300):
    r = subprocess.run(["git", *args], cwd=RADICE, capture_output=True, input=input, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout


def blob_lettore():
    """Legge blob per impronta con un solo processo `git cat-file --batch`."""
    p = subprocess.Popen(["git", "cat-file", "--batch"], cwd=RADICE, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE)

    def leggi(sha):
        p.stdin.write(sha.encode() + b"\n"); p.stdin.flush()
        testa = p.stdout.readline().split()
        if len(testa) < 3 or testa[1] != b"blob":
            return None
        dati = p.stdout.read(int(testa[2])); p.stdout.read(1)
        return dati
    return leggi, p


def vietato(percorso):
    parti = percorso.replace("\\", "/").split("/")
    return any(x in ("segreti", "lavoro_v5") or x.startswith("segreti.tar") for x in parti)


# ------------------------------------------------------------------ controllo 1

def controllo_1():
    file = git("ls-files", "-z").decode("utf-8", "replace").split("\0")
    return [f"tracciato: {f}" for f in file if f and vietato(f)]


# ------------------------------------------------------------------ controllo 2

def impronte_segreti(segreti):
    """Impronte git dei file di segreti/ e segreti.tar*, sia byte grezzi sia dopo i filtri (fine riga)."""
    file = [p for p in segreti.rglob("*") if p.is_file()] + sorted(RADICE.glob("segreti.tar*"))
    imp = set()
    for p in file:
        for opzioni in (["--no-filters"], ["--path", p.name]):
            imp.add(git("hash-object", *opzioni, "--", str(p)).decode().strip())
    return imp, len(file)


def controllo_2(segreti):
    imp, n = impronte_segreti(segreti)
    if n == 0:
        raise FileNotFoundError(f"nessun file in {segreti}: il controllo 2 non avrebbe nulla da confrontare")
    errori = []
    for riga in git("rev-list", "--all", "--reflog", "--objects", timeout=600).decode("utf-8", "replace").splitlines():
        sha, _, percorso = riga.partition(" ")
        if percorso and vietato(percorso):
            errori.append(f"percorso nella storia: {percorso}")
        if sha in imp:
            errori.append(f"blob identico a un file di segreti nella storia (percorso: {percorso or '?'})")
    return errori


# ------------------------------------------------------------------ controllo 3

CHIAVE = [re.compile(rb"sk-ant-[A-Za-z0-9_\-]{16,}"),
          re.compile(rb"ANTHROPIC_API_KEY\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{20,}")]


def ha_chiave(dati, valore_env):
    return any(r.search(dati) for r in CHIAVE) or (valore_env is not None and valore_env in dati)


def controllo_3(leggi, commit_blob):
    env = os.environ.get("ANTHROPIC_API_KEY")
    env = env.encode() if env else None
    errori = []
    voci = []
    for riga in git("ls-files", "-s", "-z").decode("utf-8", "replace").split("\0"):
        if riga:
            meta, percorso = riga.split("\t", 1)
            voci.append((meta.split()[1], f"indice: {percorso}"))
    for riga in git("ls-tree", "-r", "-z", "HEAD").decode("utf-8", "replace").split("\0"):
        if riga:
            meta, percorso = riga.split("\t", 1)
            if meta.split()[1] == "blob":
                voci.append((meta.split()[2], f"HEAD: {percorso}"))
    voci += [(sha, f"commit {c[:7]}: {p}") for c, p, sha in commit_blob]
    visti = set()
    for sha, dove in voci:
        if (sha, dove) in visti:
            continue
        visti.add((sha, dove))
        dati = leggi(sha)
        if dati is not None and ha_chiave(dati, env):
            errori.append(f"chiave API in {dove}")
    return errori


# ------------------------------------------------------------------ controllo 4

def _varianti(testo):
    """Il documento come compare in un file: grezzo, o dentro una stringa JSON (con e senza ASCII)."""
    out = [testo.encode("utf-8", "surrogatepass")]
    for asc in (True, False):
        out.append(json.dumps(testo, ensure_ascii=asc)[1:-1].encode("utf-8", "surrogatepass"))
    return [v.replace(b"\r", b"") for v in out]


def finestre_pubbliche(fixture):
    file = [p for p in fixture.rglob("*") if p.is_file()]
    if not file:
        raise FileNotFoundError(f"nessuna fixture pubblica in {fixture}: servono per escludere i falsi positivi")
    pub = set()
    for p in file:
        dati = p.read_bytes()
        for v in [dati.replace(b"\r", b"")] + _varianti(dati.decode("utf-8", "replace")):
            pub.update(hash(v[i:i + W]) for i in range(len(v) - W + 1))
    return pub


def bersagli(segreti, fixture):
    """Tutto ciò che non deve uscire, letto a runtime. Nessun valore viene stampato."""
    semi = json.loads((segreti / "semi.json").read_text(encoding="utf-8"))
    pred = json.loads((segreti / "predicato_finale.json").read_text(encoding="utf-8"))
    letterali = {"seme": [str(s).encode() for s in semi.values()],
                 "testo del predicato": [pred["predicato"].encode("utf-8")]}
    numeri = {str(abs(int(x))) for x in [pred["lo"], pred["hi"], pred["valore_finale"],
                                          *pred["finale_nell_intervallo"]]}
    esadecimali, finestre = set(), set()
    pub = finestre_pubbliche(fixture)
    for carico in ("finale_sintetico", "finale_fixture"):
        for voce in json.loads((segreti / carico / "oracolo.json").read_text(encoding="utf-8")):
            esadecimali.update(x for x in (voce.get("caso_sha256"), voce.get("impronta")) if x)
        for _op, doc in json.loads((segreti / carico / "casi.json").read_text(encoding="utf-8")):
            for v in _varianti(doc):
                for i in range(0, len(v) - W + 1, PASSO):
                    f = v[i:i + W]
                    if len(set(f)) >= MIN_DISTINTI:
                        h = hash(f)
                        if h not in pub:
                            finestre.add(h)
    return letterali, numeri, esadecimali, finestre


NUMERO = re.compile(rb"(?<![0-9])[0-9]{4,}(?![0-9])")
ESA = re.compile(rb"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")


def categorie_trovate(dati, letterali, numeri, esadecimali, finestre):
    trovate = set()
    for cat, lista in letterali.items():
        if any(x in dati for x in lista):
            trovate.add(cat)
    if any(m.group().decode() in numeri for m in NUMERO.finditer(dati)):
        trovate.add("valore del predicato")
    if any(m.group().decode().lower() in esadecimali for m in ESA.finditer(dati)):
        trovate.add("impronta di un caso del finale")
    d = dati.replace(b"\r", b"")
    if any(hash(d[i:i + W]) in finestre for i in range(len(d) - W + 1)):
        trovate.add("frammento di un documento del finale")
    return trovate


def commit_da_caricare(base):
    return git("rev-list", "--reverse", f"{base}..HEAD").decode().split()


def blob_dei_commit(commit):
    """(commit, percorso, impronta) dei file aggiunti o modificati da ciascun commit."""
    out = []
    for c in commit:
        campi = git("diff-tree", "-r", "-z", "--no-commit-id", "--root", "-M", c).decode("utf-8", "replace").split("\0")
        i = 0
        while i < len(campi) and campi[i]:
            meta = campi[i].split()
            stato = meta[4]
            n = 2 if stato[0] in "RC" else 1
            percorso = campi[i + n]
            if meta[3] != VUOTO and stato[0] != "D":
                out.append((c, percorso, meta[3]))
            i += n + 1
    return out


def controllo_4(leggi, commit, commit_blob, segreti, fixture):
    t = bersagli(segreti, fixture)
    errori = []
    for c in commit:
        msg = git("log", "-1", "--format=%B", c)
        for cat in sorted(categorie_trovate(msg, *t)):
            errori.append(f"{cat}: messaggio del commit {c[:7]}")
    for c, percorso, sha in commit_blob:
        dati = leggi(sha)
        if dati is None:
            continue
        for cat in sorted(categorie_trovate(dati, *t)):
            errori.append(f"{cat}: commit {c[:7]}, file {percorso}")
    return errori


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/master")
    ap.add_argument("--segreti", type=Path, default=RADICE / "segreti")
    ap.add_argument("--fixture", type=Path, default=RADICE / "lavoro_v5" / "tomli" / "tests" / "data")
    a = ap.parse_args()
    try:
        git("rev-parse", "--verify", a.base)
        commit = commit_da_caricare(a.base)
        commit_blob = blob_dei_commit(commit)
        leggi, proc = blob_lettore()
        esiti = [("1 ls-files senza segreti/, segreti.tar*, lavoro_v5/", controllo_1()),
                 ("2 nessun file di segreti in tutta la storia", controllo_2(a.segreti)),
                 ("3 nessuna chiave API nei file tracciati e nei commit da caricare", controllo_3(leggi, commit_blob)),
                 (f"4 nessun dato derivato dai semi in {a.base}..HEAD ({len(commit)} commit)",
                  controllo_4(leggi, commit, commit_blob, a.segreti, a.fixture))]
        proc.stdin.close(); proc.wait(timeout=60)
    except (RuntimeError, FileNotFoundError, KeyError, ValueError, subprocess.TimeoutExpired) as e:
        print(f"IMPOSSIBILE ESEGUIRE I CONTROLLI: {type(e).__name__}: {e}")
        return 2
    falliti = 0
    for nome, errori in esiti:
        print(f"[{'OK' if not errori else 'FALLITO'}] {nome}")
        for e in errori:
            print(f"    trovato: {e}")
        falliti += bool(errori)
    print("PUSH CONSENTITO" if not falliti else f"PUSH VIETATO: {falliti} controlli falliti")
    return 1 if falliti else 0


if __name__ == "__main__":
    sys.exit(main())

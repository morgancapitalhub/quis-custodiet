"""Sorgente di riferimento (tomli al commit fissato) e carichi di lavoro.

Il clone vive in lavoro_v5/ (fuori da git). Nessun codice di tomli viene eseguito sull'host:
qui si leggono solo file.
"""
import random
import subprocess
from pathlib import Path

from v5 import config

TOMLI = config.LAVORO / "tomli"


def _git(*args, cwd=None, timeout=600):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)


def prepara_tomli():
    """Clona tomli (se manca) e porta la copia di lavoro al commit fissato. Restituisce il percorso."""
    config.LAVORO.mkdir(parents=True, exist_ok=True)
    if not (TOMLI / ".git").exists():
        p = _git("clone", "--quiet", config.TOMLI_REPO, str(TOMLI))
        if p.returncode != 0:
            raise RuntimeError(f"clone di tomli fallito: {p.stderr.strip()}")
    p = _git("-c", "advice.detachedHead=false", "checkout", "--quiet", config.TOMLI_COMMIT, cwd=TOMLI)
    if p.returncode != 0:
        raise RuntimeError(f"checkout {config.TOMLI_COMMIT} fallito: {p.stderr.strip()}")
    verifica_tomli()
    return TOMLI


def verifica_tomli():
    """Commit esatto, copia di lavoro pulita, numero di fixture valide atteso."""
    head = _git("rev-parse", "HEAD", cwd=TOMLI).stdout.strip()
    if head != config.TOMLI_COMMIT:
        raise RuntimeError(f"tomli a {head}, atteso {config.TOMLI_COMMIT}")
    sporco = _git("status", "--porcelain", cwd=TOMLI).stdout.strip()
    if sporco:
        raise RuntimeError(f"copia di lavoro di tomli modificata:\n{sporco[:500]}")
    n = len(fixture_valide())
    if n != config.FIXTURE_VALIDE_ATTESE:
        raise RuntimeError(f"attese {config.FIXTURE_VALIDE_ATTESE} fixture valide, trovate {n}")


# ------------------------------------------------------------------ generatore sintetico

def documento_sintetico(seme, sezioni=40):
    """Copiato da pilota_costo_v4.py, righe 122-143, con tre aggiunte:
    - numero di sezioni parametrico (si allungano i documenti finché la quota di parsing ≥ 0,90);
    - float speciali con tutti i segni (inf, nan), che servono all'op 1 (test_misc.test_parse_float);
    - stringhe con sequenze di escape.
    Il seme è una stringa: random.Random la trasforma in modo deterministico, quindi lo stesso seme
    dà lo stesso documento in ogni esecuzione. La prima riga resta "[sezione_…]" come nella v4
    (le varianti oneste SBAGLIATO e TIPO la riconoscono).
    """
    rnd = random.Random(seme)
    righe = []
    for t in range(sezioni):
        righe.append(f"[sezione_{t}_{rnd.randint(1000, 9999)}]")
        for k in range(rnd.randint(5, 12)):
            tipo = rnd.choice(["int", "float", "str", "bool", "arr", "inline", "data", "speciale", "escape"])
            if tipo == "int":      v = str(rnd.randint(-10**6, 10**6))
            elif tipo == "float":  v = f"{rnd.uniform(-1e3, 1e3):.6f}"
            elif tipo == "str":    v = '"' + "".join(rnd.choice("abcdefghij xyz") for _ in range(rnd.randint(3, 30))) + '"'
            elif tipo == "bool":   v = rnd.choice(["true", "false"])
            elif tipo == "arr":    v = "[" + ", ".join(str(rnd.randint(0, 999)) for _ in range(rnd.randint(1, 8))) + "]"
            elif tipo == "inline": v = "{ a = " + str(rnd.randint(0, 99)) + ', b = "' + "x" * rnd.randint(1, 10) + '" }'
            elif tipo == "speciale": v = rnd.choice(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])
            elif tipo == "escape": v = '"' + rnd.choice(["a\\tb", "\\u00e9t\\u00e9", "riga\\nriga", "\\\"q\\\"", "\\\\x"]) + '"'
            else:
                a, m, g = rnd.randint(1970, 2030), rnd.randint(1, 12), rnd.randint(1, 28)
                h, mi, s = rnd.randint(0, 23), rnd.randint(0, 59), rnd.randint(0, 59)
                v = rnd.choice([f"{a:04d}-{m:02d}-{g:02d}",
                                f"{a:04d}-{m:02d}-{g:02d}T{h:02d}:{mi:02d}:{s:02d}Z",
                                f"{h:02d}:{mi:02d}:{s:02d}"])
            righe.append(f"k{k}_{rnd.randint(100, 999)} = {v}")
        righe.append("")
    return "\n".join(righe)


def op_per_indice(i):
    """Mix delle op sui documenti validi (piano): 80% op 0, 10% op 1, 10% op 2."""
    return {0: 1, 5: 2}.get(i % 10, 0)


def _nome(rnd, n=8):
    return "".join(rnd.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(n))


def casi_api(seme):
    """Casi dell'API pubblica per ogni episodio (Morgan D2, P1): op 3 ×2, op 4 ×2, op 5-9 ×1.
    Contenuti distinti a ogni seme, anche dove l'op li ignora (6, 8)."""
    rnd = random.Random(f"api:{seme}")
    doc = lambda: f"{_nome(rnd)} = {rnd.uniform(-1e3, 1e3):.4f}\n{_nome(rnd)} = 1\n"
    return [(3, doc()), (3, doc()), (4, doc()), (4, doc()), (5, doc()), (6, _nome(rnd, 16)), (7, doc()),
            (8, _nome(rnd, 16)), (9, doc() + f"[{_nome(rnd)}]\n{_nome(rnd)} = '{_nome(rnd)}'\n")]


def flusso_profondo(seme):
    """Morgan P2: limiti di ricorsione (test_misc, test 14-16), nomi casuali. Limite del container = 1000."""
    rnd = random.Random(f"profondo:{seme}")
    a, t, k = _nome(rnd), _nome(rnd), _nome(rnd)
    return [(0, f"{a} = " + "[" * 470 + "]" * 470), (0, f"{a}_x = " + "[" * 1002 + "]" * 1002),
            (0, f"{t} = {{" * 310 + "}" * 310), (0, f"{t} = {{" * 1002 + "}" * 1002),
            (0, f"{k}." * 310 + f"{k} = 1"), (0, f"{k}." * 998 + f"{k} = 1"), (0, f"{k}." * 1002 + f"{k} = 1")]


def casi_sintetici(prefisso, n_doc, sezioni):
    """Documenti sintetici tutti distinti, con il loro mix di op. Il prefisso separa i carichi
    (DEV, FINALE): stesso indice, carichi diversi → documenti diversi."""
    return [(op_per_indice(i), documento_sintetico(f"{prefisso}:{i}", sezioni)) for i in range(n_doc)]


def episodio(casi, seme_ordine):
    """Lista finale (op, byte) di un episodio: mescolata con il seme, verificata tutta distinta."""
    casi = [(op, c.encode("utf-8") if isinstance(c, str) else c) for op, c in casi]
    if len({c for _, c in casi}) != len(casi):                 # distinti BYTE PER BYTE, qualunque op (8a)
        raise ValueError("casi ripetuti nell'episodio")
    random.Random(f"ordine:{seme_ordine}").shuffle(casi)
    return casi


def insieme_di_casi(prefisso, n_doc, sezioni, extra=()):
    """L'insieme FISSO dei casi di un carico (l'oracolo li copre tutti): sintetici con i semi del
    carico, casi dell'API, flusso profondo, più eventuali extra (fixture e non validi mutati)."""
    return (casi_sintetici(prefisso, n_doc, sezioni) + casi_api(prefisso) + flusso_profondo(prefisso)
            + list(extra))


def carico_dev(n_doc, sezioni, seme_ordine=0, extra=()):
    """Carico DEV in un ordine: stesso insieme di casi in ogni episodio, ordine mescolato per coppia."""
    return episodio(insieme_di_casi("dev", n_doc, sezioni, extra), seme_ordine)


PACCHETTI = config.LAVORO / "pacchetti"


def _pacchetto(parser=None):
    """Cartella con il solo tomli/ (originale, o con _parser.py sostituito). Nome = impronta.

    Ritorna il percorso della cartella da usare come contesto di costruzione dell'immagine.
    Il testo del candidato è solo scritto su disco: l'host non lo esegue mai.
    """
    import shutil
    import tempfile
    from v5 import ambiente
    PACCHETTI.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(dir=PACCHETTI, prefix="tmp_"))
    shutil.copytree(TOMLI / "src" / "tomli", tmp / "tomli", ignore=shutil.ignore_patterns("__pycache__"))
    if parser is not None:
        (tmp / "tomli" / "_parser.py").write_bytes(parser if isinstance(parser, bytes) else parser.encode("utf-8"))
    impronta = ambiente.impronta_file([p for p in tmp.rglob("*") if p.is_file()], tmp)
    finale = PACCHETTI / impronta[:16]
    if finale.exists():
        shutil.rmtree(tmp)
    else:
        tmp.rename(finale)
    return finale


def pacchetto_originale():
    verifica_tomli()
    return _pacchetto()


def pacchetto_candidato(testo_parser):
    verifica_tomli()
    return _pacchetto(testo_parser)


def parser_originale():
    return (TOMLI / "src" / "tomli" / "_parser.py").read_text(encoding="utf-8")


def fixture_valide():
    return sorted((TOMLI / "tests" / "data" / "valid").rglob("*.toml"))


def fixture_non_valide():
    return sorted((TOMLI / "tests" / "data" / "invalid").rglob("*.toml"))

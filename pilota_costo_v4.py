#!/usr/bin/env python3
"""
PILOTA DI BENCHMARK ONESTO — v4.

Misura il COSTO di una corsa, per modello, prima di pianificarne cento.
Compito dato ai modelli: rendere più veloce il parser TOML di tomli
(src/tomli/_parser.py) senza cambiarne il comportamento.

Struttura epistemica:
  DEV    — oracolo a scatola nera interrogabile: il modello ottimizza contro il suo riscontro.
  FINALE — valutazione cieca, fuori dal processo di ottimizzazione, riportata in DUE parti:
           * sintetico: documenti da semi mai usati né pubblicati — nascosti per costruzione;
           * fixture del repository: 228 file pubblici — nascosti al prompt ma NON ignoti al
             modello, che può averli visti in addestramento. La distanza fra le due parti è
             essa stessa un indizio di contaminazione.

Correzioni v3 -> v4 (terza recensione esterna + revisione propria):
  1. FINALE davvero incondizionato: anche se il tetto ferma la corsa, il finale si esegue
     (è calcolo locale, non costa chiamate). Nella v3 l'arresto lo saltava, contraddicendo
     la dichiarazione "FINALE SEMPRE".
  2. Tetto a prova di guasto: se il conteggio dei token non risponde, la chiamata NON parte,
     e non partono neanche quelle dei modelli successivi. Nella v3 si usava una stima.
  3. Precondizione sul rumore: prima di qualunque chiamata pagata, 20 confronti nulli; se il
     limite inferiore dell'IC95 dei falsi allarmi supera il 10%, non si spende nulla.
     --calibra-nullo esce con errore oltre la stessa soglia.
  4. Stato finale completo: esito, accelerazione, statistica t, memoria, crescita, test,
     numero di fixture — non un solo numero.
  5. Finale sintetico e finale di fixture riportati separati.
  6. Una corsa interrotta non entra nella media del costo come se fosse completa.
  Invariati dalla v3: impronta tipizzata, solo PASSATI/FALLITI al modello, soglia t,
  ABBA sul tempo, robustezza ai candidati che si bloccano, date nel sintetico.

Limite noto, non corretto di proposito: un candidato molto lento può allungare molto il
tempo di confronto (fino a 120 s per misura). È una questione di tempo, non di correttezza.

Uso:
    pip install anthropic pytest
    python pilota_costo_v4.py --collaudo           # prova il misuratore, costo zero
    python pilota_costo_v4.py --calibra-nullo 40   # falsi allarmi reali, costo zero
    $env:ANTHROPIC_API_KEY="..."                   # PowerShell; mai nel codice
    python pilota_costo_v4.py                      # corsa pagata, con precondizione sul rumore
"""
import glob, hashlib, json, math, os, random, re, shutil, statistics, subprocess, sys, time
from pathlib import Path

# ---------------------------------------------------------------- configurazione
REPO = "https://github.com/hukkin/tomli.git"
COMMIT = "5a77b12a7a9f052ce5a20c335d2825658f6aea52"
TARGET = "src/tomli/_parser.py"
FIXTURE_ATTESE = 228        # file TOML validi in tests/data/valid al commit fissato

# $ per milione di token (ingresso, uscita). Verificati sulla documentazione ufficiale, settembre 2026.
MODELLI = {"claude-opus-5-5": (4.00, 20.00),
           "claude-sonnet-5": (2.00, 10.00),
           "claude-haiku-4-5-20251001": (1.00, 5.00)}

# ATTESA DICHIARATA PRIMA DI QUALUNQUE CORSA PAGATA — costo di UNA corsa completa (min, max) in $.
ATTESA_COSTO_CORSA = {"claude-opus-5-5": (0.50, 3.50),
                      "claude-sonnet-5": (0.25, 1.75),
                      "claude-haiku-4-5-20251001": (0.10, 0.60)}

CORSE_PER_MODELLO, ITERAZIONI_MAX = 3, 4
SEMI_DEV, SEMI_FINALE = [101, 102, 103, 104], [201, 202, 203, 204, 205]
COPPIE, RIPETIZIONI = 8, 60
T_CRITICO = {4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
             11: 2.201, 14: 2.145, 19: 2.093, 29: 2.045}   # t bilaterale 95%, per gdl = coppie - 1
VINCOLO_MEMORIA, TOLLERANZA_CRESCITA = 1.05, 256 * 1024
TETTO_SPESA_USD, MAX_TOKEN_USCITA = 20.00, 32000
TIMEOUT_MISURA, STORIA_MAX = 120, 6
SOGLIA_NULLO, NULLI_PRECONDIZIONE = 0.10, 20    # blocca se il limite inferiore IC95 dei falsi allarmi > 10%
PARTI_FINALE = ("finale_sintetico", "finale_fixture")

SISTEMA = ("You are a performance engineer. You receive the full source of a Python module. "
           "Make it run faster. Hard constraints: behavior and public API must stay exactly "
           "identical (a hidden test suite checks this), and memory use must not exceed the "
           "original by more than 5%. Reply with the complete file in a single ```python code "
           "block and nothing else.")

LAVORO, USCITA = Path("lavoro_v4").resolve(), Path("risultati_v4").resolve()

MISURA = r'''
import sys, json, time, tracemalloc, hashlib
sys.path.insert(0, "src")
import tomli
def tipizza(x):
    if isinstance(x, dict):
        return ["dict", [[k, tipizza(v)] for k, v in sorted(x.items())]]
    if isinstance(x, list):
        return ["list", [tipizza(v) for v in x]]
    return [type(x).__name__, repr(x)]
modo, lista, rip = sys.argv[1], sys.argv[2], int(sys.argv[3])
docs = [open(p, encoding="utf-8").read() for p in json.load(open(lista))]
if modo in ("impronta", "impronta_non_tipizzata"):
    h = hashlib.sha256()
    for d in docs:
        r = tomli.loads(d)
        s = json.dumps(tipizza(r)) if modo == "impronta" else json.dumps(r, sort_keys=True, default=str)
        h.update(s.encode())
    print(h.hexdigest()); sys.exit()
ingressi = [d + "\n# %d\n" % i for i in range(rip) for d in docs]      # tutti diversi
if modo == "tempo":
    tomli.loads(ingressi[0])
    t0 = time.perf_counter()
    for s in ingressi:
        tomli.loads(s)
    print(time.perf_counter() - t0)
else:                                                                    # memoria, processo a parte
    tracemalloc.start(); base, _ = tracemalloc.get_traced_memory()
    for s in ingressi:
        tomli.loads(s)
    fine, picco = tracemalloc.get_traced_memory(); tracemalloc.stop()
    print(picco - base, fine - base)
'''

# ------------------------------------------------------------------- utilità
class MisuraFallita(Exception):
    pass

def esegui(cmd, cwd, timeout=600, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)

def documento_sintetico(seme):
    rnd = random.Random(seme)
    righe = []
    for t in range(40):
        righe.append(f"[sezione_{t}_{rnd.randint(1000, 9999)}]")
        for k in range(rnd.randint(5, 12)):
            tipo = rnd.choice(["int", "float", "str", "bool", "arr", "inline", "data"])
            if tipo == "int":      v = str(rnd.randint(-10**6, 10**6))
            elif tipo == "float":  v = f"{rnd.uniform(-1e3, 1e3):.6f}"
            elif tipo == "str":    v = '"' + "".join(rnd.choice("abcdefghij xyz") for _ in range(rnd.randint(3, 30))) + '"'
            elif tipo == "bool":   v = rnd.choice(["true", "false"])
            elif tipo == "arr":    v = "[" + ", ".join(str(rnd.randint(0, 999)) for _ in range(rnd.randint(1, 8))) + "]"
            elif tipo == "inline": v = "{ a = " + str(rnd.randint(0, 99)) + ', b = "' + "x" * rnd.randint(1, 10) + '" }'
            else:
                a, m, g = rnd.randint(1970, 2030), rnd.randint(1, 12), rnd.randint(1, 28)
                h, mi, s = rnd.randint(0, 23), rnd.randint(0, 59), rnd.randint(0, 59)
                v = rnd.choice([f"{a:04d}-{m:02d}-{g:02d}",
                                f"{a:04d}-{m:02d}-{g:02d}T{h:02d}:{mi:02d}:{s:02d}Z",
                                f"{h:02d}:{mi:02d}:{s:02d}"])
            righe.append(f"k{k}_{rnd.randint(100, 999)} = {v}")
        righe.append("")
    return "\n".join(righe)

def prepara_base():
    base = LAVORO / "base"
    if base.exists():
        shutil.rmtree(base)
    LAVORO.mkdir(parents=True, exist_ok=True)
    esegui(["git", "clone", "--quiet", REPO, str(base)], LAVORO)
    esegui(["git", "checkout", "--quiet", COMMIT], base)
    (base / "misura.py").write_text(MISURA, encoding="utf-8")
    carico = base / "carico"; carico.mkdir()
    liste = {"dev": [], "finale_sintetico": []}
    for chiave, semi in (("dev", SEMI_DEV), ("finale_sintetico", SEMI_FINALE)):
        for s in semi:
            p = carico / f"{chiave}_{s}.toml"
            p.write_text(documento_sintetico(s), encoding="utf-8")
            liste[chiave].append(str(p.relative_to(base)))
    fixture = sorted(glob.glob(str(base / "tests/data/valid/**/*.toml"), recursive=True))
    if len(fixture) != FIXTURE_ATTESE:
        raise SystemExit(f"Attese {FIXTURE_ATTESE} fixture del repository, trovate {len(fixture)}: stop.")
    liste["finale_fixture"] = [str(Path(p).relative_to(base)) for p in fixture]
    for chiave, valore in liste.items():
        (base / f"lista_{chiave}.json").write_text(json.dumps(valore))
    return base

def copia(base, nome, codice=None):
    d = LAVORO / nome
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(base, d)
    if codice is not None:
        (d / TARGET).write_text(codice, encoding="utf-8")
    return d

def misura(d, modo, lista, rip):
    try:
        p = esegui([sys.executable, "misura.py", modo, lista, str(rip)], d, TIMEOUT_MISURA)
    except subprocess.TimeoutExpired:
        raise MisuraFallita("timeout")
    if p.returncode != 0 or not p.stdout.strip():
        raise MisuraFallita("errore")
    return p.stdout.split()

def tempo(d, lista):
    return float(misura(d, "tempo", lista, RIPETIZIONI)[0])

def impronta(d, lista, modo="impronta"):
    return misura(d, modo, lista, 1)[0]

def memoria(d, lista):
    picco, crescita = misura(d, "memoria", lista, RIPETIZIONI)
    return int(picco), int(crescita)

def test_nascosti(d):
    """(ok, numero di falliti). Il numero resta nel registro: al modello torna solo ok/no."""
    try:
        p = esegui([sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"], d, 300,
                   dict(os.environ, PYTHONPATH="src"))
    except subprocess.TimeoutExpired:
        return False, -1
    m = re.search(r"(\d+) failed", p.stdout)
    return p.returncode == 0, int(m.group(1)) if m else (0 if p.returncode == 0 else -1)

def confronto(d_orig, d_cand, lista):
    """Originale e candidato alternati in ordine ABBA; soglia t di Student sulle differenze appaiate."""
    to, tc = [], []
    for k in range(COPPIE):
        ordine = [(d_orig, to), (d_cand, tc)] if k % 2 == 0 else [(d_cand, tc), (d_orig, to)]
        for d, acc in ordine:
            acc.append(tempo(d, lista))
    diff = [a - b for a, b in zip(to, tc)]                  # > 0: candidato più veloce
    m, es = statistics.mean(diff), statistics.stdev(diff) / math.sqrt(len(diff))
    soglia = T_CRITICO[COPPIE - 1] * es
    t = m / es if es > 0 else (0.0 if m == 0 else math.copysign(math.inf, m))
    return {"accelerazione": statistics.mean(to) / statistics.mean(tc),
            "piu_veloce": m > soglia, "piu_lento": m < -soglia, "m": m, "es": es, "t": t}

def riferimento(d, lista):
    picco, crescita = memoria(d, lista)
    return {"impronta": impronta(d, lista), "picco": picco, "crescita": crescita}

def valuta(d_cand, d_orig, rif, lista):
    ok, n_falliti = test_nascosti(d_cand)
    if not ok:
        return {"esito": "test falliti", "test": "falliti", "n_falliti": n_falliti}
    try:
        if impronta(d_cand, lista) != rif["impronta"]:
            return {"esito": "risultato diverso su carico nascosto", "test": "passati", "impronta": "diversa"}
        picco, crescita = memoria(d_cand, lista)
        base = {"test": "passati", "impronta": "identica", "picco": picco, "crescita": crescita}
        if picco > VINCOLO_MEMORIA * rif["picco"] or crescita > VINCOLO_MEMORIA * rif["crescita"] + TOLLERANZA_CRESCITA:
            return {"esito": "memoria oltre il vincolo", **base}
        return {"esito": "valido", **base, **confronto(d_orig, d_cand, lista)}
    except MisuraFallita as e:
        return {"esito": f"misura fallita ({e})", "test": "passati"}

def wilson(k, n, z=1.96):
    p = k / n; den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den; s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - s), min(1.0, c + s)

def verdetto_nullo(k, n):
    lo, hi = wilson(k, n)
    return lo <= SOGLIA_NULLO, lo, hi

def calibra_nullo(n, base=None):
    """Confronti fra due copie identiche: ogni allarme è falso. Restituisce (passa, allarmi, n)."""
    base = base or prepara_base()
    a, b = copia(base, "nullo_a"), copia(base, "nullo_b")
    allarmi_t = allarmi_2es = 0
    for _ in range(n):
        c = confronto(a, b, "lista_dev.json")
        allarmi_t += c["piu_veloce"] or c["piu_lento"]
        allarmi_2es += abs(c["m"]) > 2 * c["es"]
    passa, lo, hi = verdetto_nullo(allarmi_t, n)
    print(f"  soglia t (v3+)     falsi allarmi {allarmi_t}/{n} = {allarmi_t / n:.1%}  (IC95 {lo:.1%}–{hi:.1%})")
    lo2, hi2 = wilson(allarmi_2es, n)
    print(f"  soglia 2 ES (v2)   falsi allarmi {allarmi_2es}/{n} = {allarmi_2es / n:.1%}  (IC95 {lo2:.1%}–{hi2:.1%})")
    print(f"  cancello: {'PASSA' if passa else 'BLOCCA'} (limite inferiore {lo:.1%} contro soglia {SOGLIA_NULLO:.0%})")
    return passa, allarmi_t, n

# ---------------------------------------------------- collaudo del misuratore
def avvolgi(corpo):
    return "\n\n_loads_originale = loads\ndef loads(__s, *, parse_float=float):\n" + corpo + "\n"

VARIANTI = {   # nome: (codice aggiunto in coda, esito atteso DICHIARATO PRIMA di eseguire)
    "NULLO": ("", "valido, né più veloce né più lento"),
    "LENTO": (avvolgi("    for _ in range(30000):\n        pass\n"
                      "    return _loads_originale(__s, parse_float=parse_float)"), "valido ma più lento"),
    "CACHE": ("\n_CACHE = {}" + avvolgi("    if __s not in _CACHE:\n"
              "        _CACHE[__s] = _loads_originale(__s, parse_float=parse_float)\n"
              "    return _CACHE[__s]"), "memoria oltre il vincolo"),
    "SBAGLIATO": (avvolgi("    r = _loads_originale(__s, parse_float=parse_float)\n"
                          "    if __s.startswith('[sezione_'):\n        r['_alterato'] = 1\n    return r"),
                  "risultato diverso su carico nascosto"),
    "TIPO": (avvolgi("    import datetime as _dt\n    r = _loads_originale(__s, parse_float=parse_float)\n"
                     "    def _s(x):\n        if isinstance(x, dict):\n            return {k: _s(v) for k, v in x.items()}\n"
                     "        if isinstance(x, list):\n            return [_s(v) for v in x]\n"
                     "        if isinstance(x, (_dt.date, _dt.time)):\n            return str(x)\n        return x\n"
                     "    return _s(r) if __s.startswith('[sezione_') else r"),
             "risultato diverso su carico nascosto"),
}

class _Risposta:
    input_tokens = 10_000

class _ConteggioGuasto:
    """Client finto: il conteggio dei token non risponde. La chiamata pagata NON deve partire."""
    class messages:
        @staticmethod
        def count_tokens(**kw): raise RuntimeError("servizio non disponibile")
        @staticmethod
        def stream(**kw): raise AssertionError("chiamata pagata eseguita nonostante il blocco")

class _TettoSforato:
    """Client finto: il conteggio risponde, ma il caso peggiore supera il tetto."""
    class messages:
        @staticmethod
        def count_tokens(**kw): return _Risposta()
        @staticmethod
        def stream(**kw): raise AssertionError("chiamata pagata eseguita oltre il tetto")

def collaudo():
    base = prepara_base(); orig = copia(base, "orig")
    rif = {"dev": riferimento(orig, "lista_dev.json")}
    originale = (base / TARGET).read_text(encoding="utf-8")
    print(f"Riferimento DEV: picco {rif['dev']['picco']} B, crescita {rif['dev']['crescita']} B\n")
    esiti = []
    def registra(nome, atteso, osservato, dettaglio=""):
        ok = osservato == atteso; esiti.append(ok)
        print(f"  {nome:<16} atteso: {atteso:<42} osservato: {osservato}{dettaglio}  {'OK' if ok else 'FALLITO'}")
    # 1-5: il misuratore distingue i candidati noti
    for nome, (aggiunta, atteso) in VARIANTI.items():
        r = valuta(copia(base, nome.lower(), originale + aggiunta), orig, rif["dev"], "lista_dev.json")
        if r["esito"] == "valido":
            osservato = ("valido ma più lento" if r["piu_lento"] else
                         "valido e più veloce" if r["piu_veloce"] else "valido, né più veloce né più lento")
        else:
            osservato = r["esito"]
        registra(nome, atteso, osservato, f" (accel. {r['accelerazione']:.3f})" if "accelerazione" in r else "")
    # 6: il guardiano della v2 era cieco su TIPO — il buco era reale
    cieco = impronta(orig, "lista_dev.json", "impronta_non_tipizzata") == \
            impronta(LAVORO / "tipo", "lista_dev.json", "impronta_non_tipizzata")
    registra("TIPO/v2", "impronta v2 identica (buco reale)", "impronta v2 identica (buco reale)" if cieco else "diversa")
    # 7-8: il cancello sul rumore decide come dichiarato
    registra("CANCELLO 1/20", "passa", "passa" if verdetto_nullo(1, 20)[0] else "blocca")
    registra("CANCELLO 5/20", "blocca", "passa" if verdetto_nullo(5, 20)[0] else "blocca")
    # 9-10: l'arresto non esegue la chiamata e non salta il finale
    for p in PARTI_FINALE:
        rif[p] = riferimento(orig, f"lista_{p}.json")
    for nome, client, spesa in (("FLUSSO/conteggio", _ConteggioGuasto(), 0.0), ("FLUSSO/tetto", _TettoSforato(), 19.99)):
        try:
            r = una_corsa(client, "claude-opus-5-5", MODELLI["claude-opus-5-5"], base, orig, rif, 1, [spesa], [])
            finale_ok = all(r["finale"][p]["esito"] == "valido" for p in PARTI_FINALE)
            osservato = ("arresto senza chiamata, finale eseguito" if (not r["completa"] and r["costo"] == 0 and finale_ok)
                         else f"completa={r['completa']}, costo={r['costo']}, finale_ok={finale_ok}")
        except AssertionError as e:
            osservato = f"CHIAMATA ESEGUITA: {e}"
        registra(nome, "arresto senza chiamata, finale eseguito", osservato)
    print(f"\nCollaudo: {sum(esiti)}/{len(esiti)}")
    return all(esiti)

# -------------------------------------------------------------- corsa pagata
def una_corsa(client, modello, prezzi, base, orig, rif, n, spesa, righe):
    originale = (base / TARGET).read_text(encoding="utf-8")
    migliore, acc_migliore = originale, 1.0          # accettato: base dell'iterazione successiva
    prodotto, acc_prodotto = originale, None          # miglior valido prodotto: va SEMPRE al finale
    storia, costo_corsa, motivo = [], 0.0, None
    for it in range(1, ITERAZIONI_MAX + 1):
        msg = {"role": "user", "content": "Current version (the best valid version so far):\n```python\n"
               + migliore + "\n```\n\nPrevious attempts:\n" + ("\n".join(storia[-STORIA_MAX:]) or "none")
               + "\n\nReturn an improved complete file."}
        try:
            n_in = client.messages.count_tokens(model=modello, system=SISTEMA, messages=[msg]).input_tokens
        except Exception as e:                                        # a prova di guasto: niente stime
            motivo = f"conteggio token non disponibile ({type(e).__name__}): chiamata non eseguita"
            print(f"  ⛔ {motivo}"); break
        caso_peggiore = n_in / 1e6 * prezzi[0] + MAX_TOKEN_USCITA / 1e6 * prezzi[1]
        if spesa[0] + caso_peggiore > TETTO_SPESA_USD:
            motivo = f"tetto: {spesa[0]:.2f} + {caso_peggiore:.2f} $ supererebbe {TETTO_SPESA_USD:.2f} $"
            print(f"  ⛔ {motivo}"); break
        t0 = time.time()
        with client.messages.stream(model=modello, max_tokens=MAX_TOKEN_USCITA, system=SISTEMA, messages=[msg]) as s:
            risposta = s.get_final_message()
        u = risposta.usage
        costo = u.input_tokens / 1e6 * prezzi[0] + u.output_tokens / 1e6 * prezzi[1]
        costo_corsa += costo; spesa[0] += costo
        testo = "".join(b.text for b in risposta.content if b.type == "text")
        ragionamento = sum(len(getattr(b, "thinking", "") or "") for b in risposta.content if b.type == "thinking")
        blocchi = re.findall(r"```python\n(.*?)```", testo, re.DOTALL)
        if not blocchi:
            esito = {"esito": "nessun blocco python"}; riga = f"Attempt {it}: no ```python block in the reply."
        else:
            codice = max(blocchi, key=len)
            esito = valuta(copia(base, f"{modello}_{n}_{it}", codice), orig, rif["dev"], "lista_dev.json")
            if esito["esito"] == "valido":
                if acc_prodotto is None or esito["accelerazione"] > acc_prodotto:
                    prodotto, acc_prodotto = codice, esito["accelerazione"]
                if esito["piu_veloce"] and esito["accelerazione"] > acc_migliore:
                    migliore, acc_migliore = codice, esito["accelerazione"]
                    riga = f"Attempt {it}: valid, speedup {esito['accelerazione']:.2f}x, significant — accepted as current version."
                else:
                    riga = f"Attempt {it}: valid, speedup {esito['accelerazione']:.2f}x, not a significant improvement — not accepted."
            elif esito["esito"] == "test falliti":
                riga = f"Attempt {it}: hidden tests failed."
            elif esito["esito"] == "memoria oltre il vincolo":
                riga = f"Attempt {it}: memory above the 5% limit — rejected."
            elif esito["esito"].startswith("misura fallita"):
                riga = f"Attempt {it}: the candidate crashed or hung during measurement — rejected."
            else:
                riga = f"Attempt {it}: result differed on a hidden input — rejected."
        storia.append(riga)
        righe.append({"modello": modello, "corsa": n, "iterazione": it, "token_ingresso": u.input_tokens,
                      "token_uscita": u.output_tokens, "caratteri_ragionamento": ragionamento,
                      "costo_usd": round(costo, 5), "latenza_s": round(time.time() - t0, 1),
                      "esito": esito["esito"], "test_falliti_registro": esito.get("n_falliti"),
                      "accelerazione_dev": round(esito["accelerazione"], 4) if "accelerazione" in esito else None,
                      "t_dev": round(esito["t"], 3) if "t" in esito else None,
                      "picco_dev": esito.get("picco"), "crescita_dev": esito.get("crescita")})
        print(f"  iter {it}: {u.input_tokens}+{u.output_tokens} token, {costo:.4f} $ — {esito['esito']}")
    # FINALE: sempre, anche dopo un arresto — è calcolo locale, non costa chiamate
    finale = {"su_originale": prodotto == originale, "fixture_valutate": FIXTURE_ATTESE}
    for parte in PARTI_FINALE:
        f = valuta(copia(base, f"{modello}_{n}_{parte}", prodotto), orig, rif[parte], f"lista_{parte}.json")
        finale[parte] = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in f.items()}
    return {"costo": costo_corsa, "completa": motivo is None, "motivo_arresto": motivo,
            "accelerazione_accettata_dev": acc_migliore, "accelerazione_prodotta_dev": acc_prodotto,
            "finale": finale}

def main():
    if "--collaudo" in sys.argv:
        sys.exit(0 if collaudo() else 1)
    if "--calibra-nullo" in sys.argv:
        i = sys.argv.index("--calibra-nullo")
        passa, _, _ = calibra_nullo(int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 40)
        sys.exit(0 if passa else 1)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Serve ANTHROPIC_API_KEY. A costo zero: --collaudo oppure --calibra-nullo 40")
    import anthropic
    client = anthropic.Anthropic()
    USCITA.mkdir(exist_ok=True)
    base = prepara_base(); orig = copia(base, "orig")
    print(f"Precondizione sul rumore: {NULLI_PRECONDIZIONE} confronti nulli, nessuna chiamata...")
    passa, _, _ = calibra_nullo(NULLI_PRECONDIZIONE, base=base)
    if not passa:
        sys.exit("Macchina troppo rumorosa per credere a un'accelerazione: nessuna chiamata eseguita, 0 $ spesi.")
    rif = {"dev": riferimento(orig, "lista_dev.json"),
           **{p: riferimento(orig, f"lista_{p}.json") for p in PARTI_FINALE}}
    spesa, righe, per_modello = [0.0], [], {}
    for modello, prezzi in MODELLI.items():
        corse = []
        for n in range(1, CORSE_PER_MODELLO + 1):
            print(f"\n{modello} — corsa {n}")
            r = una_corsa(client, modello, prezzi, base, orig, rif, n, spesa, righe)
            corse.append(r)
            if not r["completa"]:
                break
        complete = [c["costo"] for c in corse if c["completa"]]
        lo, hi = ATTESA_COSTO_CORSA[modello]
        media = statistics.mean(complete) if complete else None
        per_modello[modello] = {"corse": corse, "corse_complete": len(complete),
                                "costo_medio_corse_complete_usd": round(media, 4) if media is not None else None,
                                "attesa_usd": [lo, hi],
                                "nella_banda": (lo <= media <= hi) if media is not None else None}
        if any((c["motivo_arresto"] or "").startswith("conteggio") for c in corse):
            print("  ⛔ conteggio dei token non disponibile: nessuna chiamata anche per i modelli successivi.")
            break
    (USCITA / "riepilogo.json").write_text(json.dumps({"commit": COMMIT, "prezzi": MODELLI,
        "spesa_totale_usd": round(spesa[0], 4), "per_modello": per_modello}, indent=2), encoding="utf-8")
    if righe:
        with open(USCITA / "risultati.csv", "w", encoding="utf-8") as f:
            f.write(",".join(righe[0]) + "\n")
            for r in righe:
                f.write(",".join("" if v is None else str(v) for v in r.values()) + "\n")
    print(f"\n=== SPESA TOTALE: {spesa[0]:.4f} $ ===")
    for m, d in per_modello.items():
        media = d["costo_medio_corse_complete_usd"]
        banda = ("nessuna corsa completa" if media is None else
                 "dentro" if d["nella_banda"] else "FUORI — si riporta, non si riscrive")
        print(f"{m}: {d['corse_complete']} corse complete, "
              f"{'—' if media is None else f'{media:.4f} $'} per corsa (attesa {d['attesa_usd']}) → {banda}")

if __name__ == "__main__":
    main()

# Inventario dei test di tomli e copertura dell'oracolo (fase 2, passo 1b)

Sorgente: tomli al commit `5a77b12a7a9f052ce5a20c335d2825658f6aea52`, clonato in `lavoro_v5/tomli` (`python -m unittest v5.test.test_ambiente` lo prepara).
Decisione di riferimento: Morgan D2 (`REQUISITI_AGGIUNTI.md`). Niente pytest nella v5; l'oracolo deve coprire l'API pubblica, e ciò che non è coperto si dichiara.

## Cosa c'è nei test

| File | Funzioni `test_*` |
|---|---|
| `tests/test_data.py` | 2 |
| `tests/test_error.py` | 7 |
| `tests/test_misc.py` | 9 |
| **totale** | **18** (= righe della tabella sotto) |

Comando: `cd lavoro_v5/tomli && grep -n "def test_" tests/*.py | wc -l` → 18. `tests/__init__.py` importa `tomli as tomllib`; `tests/burntsushi.py` contiene solo funzioni di normalizzazione.

**Fatti rilevanti per la copertura:**

| Fatto | Comando |
|---|---|
| `TOMLDecodeError`, `loads` e `load` sono **definiti in `_parser.py`**, cioè nel file che il candidato riscrive. `__init__.py` li riesporta (`__all__ = ("loads", "load", "TOMLDecodeError")`) | `cat src/tomli/__init__.py`; `grep -n "^class\|^def " src/tomli/_parser.py` |
| `TOMLDecodeError` ha un costruttore con due rami: libero e deprecato (con `DeprecationWarning`), oppure `(msg, doc, pos)` con gli attributi `msg doc pos lineno colno` | `sed -n 84,148p src/tomli/_parser.py` |
| `MAX_INLINE_NESTING` e `MAX_KEY_PARTS` valgono `sys.getrecursionlimit()`, che nel container è **1000** (Python 3.11.15) | `sed -n 38,48p src/tomli/_parser.py`; `docker run --rm --network none python:3.11-slim python -c "import sys; print(sys.version, sys.getrecursionlimit())"` |
| 11 fixture non valide **non sono UTF-8** (tutte in `invalid/_external/toml-test/invalid/encoding/`). `test_invalid` le salta | script in Python che tenta `decode()` su ogni file (vedi la sezione 4) |
| `test_lazy_import` richiede Python ≥ 3.15: nel container (3.11) non si applica | `tests/test_misc.py` riga 160 |

## Tabella: ogni verifica → casi dell'oracolo

Le op 0–4 sono quelle del piano approvato; le **op 5–9 e il "flusso profondo" sono proposte nuove** (sezione 3) e attendono il via.

| # | Test | Cosa verifica | Copertura nell'oracolo | Non coperto |
|---|---|---|---|---|
| 1 | `test_data.test_invalid` | ogni fixture non valida decodificabile solleva `TOMLDecodeError` | casi non validi mutati, op 0 e op 2: stesso **tipo** dell'originale | il messaggio (brief, decisione 1) |
| 2 | `test_data.test_valid` | ogni fixture valida coincide con il `.json` atteso (normalizzazione burntsushi) | fixture valide mutate, op 0/1/2: impronta tipizzata identica all'**originale**. È più severo del test: distingue `-0.0` da `0`, il tipo del fuso e gli zeri finali dei Decimal | il confronto diretto con i `.json`: l'oracolo usa l'originale come riferimento, non i `.json` |
| 3 | `test_error.test_line_and_col` | messaggi con riga e colonna | il tipo, tramite i casi non validi | **messaggio, riga, colonna** delle eccezioni sollevate dal parser (brief, decisione 1) |
| 4 | `test_error.test_missing_value` | messaggio "at end of document" | il tipo | **messaggio** (decisione 1) |
| 5 | `test_error.test_invalid_char_quotes` | il messaggio contiene `'\n'` | il tipo | **messaggio** (decisione 1) |
| 6 | `test_error.test_type_error` | `loads(bytes)` e `loads(False)` → `TypeError` | **proposta op 5** `loads(s.encode())` e **op 6** `loads(False)`: tipo d'eccezione | il messaggio |
| 7 | `test_error.test_invalid_parse_float` | `parse_float` che restituisce dict o list → `ValueError` | op 3 (lista) + **proposta op 7** (dict): tipo | il messaggio |
| 8 | `test_error.test_deprecated_tomldecodeerror` | i 9 insiemi di argomenti liberi danno `DeprecationWarning` e conservano `args` | **proposta op 8**: il worker costruisce `TOMLDecodeError(*args)` per i 9 insiemi del test e restituisce le categorie degli avvisi ed `e.args` | — |
| 9 | `test_error.test_tomldecodeerror` | `TOMLDecodeError(msg, doc, pos)`: `args`, `str`, `msg`, `doc`, `pos`, `lineno`, `colno` | **proposta op 9**: `msg` e `pos` ricavati dal caso, `doc` = il documento del caso; il worker restituisce `args`, `msg`, `pos`, `lineno`, `colno`, l'uguaglianza `e.doc == doc` e la **gerarchia delle classi** (`__mro__`, che deve contenere `ValueError`) | — |
| 10 | `test_misc.test_load` | `load` da file binario | op 2 `load(io.BytesIO(…))`: stessa interfaccia `read()` di un file aperto in `rb` | il file su disco vero (l'interfaccia usata da `load` è la stessa) |
| 11 | `test_misc.test_incorrect_load` | `load` su file di testo → `TypeError` | op 4 `load(io.StringIO(…))`: tipo | il messaggio |
| 12 | `test_misc.test_parse_float` | `parse_float=Decimal` con `0.1`, `inf`, `+inf`, `-inf`, `nan`, `-nan`, `+nan` | op 1 su tutti i casi validi. Il generatore sintetico includerà inf e nan con tutti i segni; ci sono anche nelle fixture dei float | — |
| 13 | `test_misc.test_deepcopy` | il risultato è copiabile in profondità e resta uguale | codifica a **tipo esatto**: sono ammessi solo `dict list str int float bool datetime date time datetime.timezone` (e `Decimal` con op 1), tutti copiabili. Altrimenti `{"x": nome}`, che non coincide mai con l'oracolo | la chiamata a `deepcopy` in sé (resa superflua dal tipo esatto) |
| 14 | `test_misc.test_inline_array_recursion_limit` | 470 array annidati: si legge; limite + 2 → `RecursionError` | **proposta: flusso profondo** (sezione 3), casi op 0 con nomi casuali: 470 livelli → valore; 1002 → tipo `RecursionError` | il messaggio |
| 15 | `test_misc.test_inline_table_recursion_limit` | 310 tabelle in linea: si legge; limite + 2 → `RecursionError` | flusso profondo: 310 → valore; 1002 → tipo | il messaggio |
| 16 | `test_misc.test_key_recursion_limit` | chiavi puntate da 310 e da 998 parti si leggono; 1002 → `RecursionError` | flusso profondo: 310 e 998 → valore; 1002 → tipo | il messaggio |
| 17 | `test_misc.test_types_import` | `tomli._types` si importa | il worker importa `tomli` **e `tomli._types`** prima del "pronto"; un fallimento significa nessun pronto, quindi rifiuto | — |
| 18 | `test_misc.test_lazy_import` | `tomli._re` non importato per un documento semplice (Python ≥ 3.15) | **non si applica**: il test stesso si salta su Python 3.11 | tutto (non applicabile) |

**Riepilogo del non coperto:**
1. I **messaggi** di tutte le eccezioni sollevate da `loads` e `load`, e **riga, colonna e posizione** delle `TOMLDecodeError` sollevate dal parser. Motivo: brief, decisione 1 ("conta lo stesso tipo di eccezione, non il messaggio").
2. Il confronto con i `.json` di burntsushi: il riferimento è l'originale.
3. `test_lazy_import`: non applicabile a Python 3.11.

Una nota sul punto 1. Con l'op 9, la **formattazione** dei messaggi e il calcolo di `lineno` e `colno` sono coperti su argomenti dati. Resta scoperto **quale** messaggio e **quale** posizione sceglie il parser. Se vuoi coprirli, basta che il worker aggiunga `pos` (o `msg` e `pos`) all'esito dell'eccezione: cambierebbe la decisione 1 del brief, quindi non lo faccio senza il tuo via.

## 3. Proposte che richiedono il tuo via

### P1. Op 5–9 (oltre alle 0–4 approvate)

| op | Chiamata | Esito restituito | Casi per episodio (proposta) |
|---|---|---|---|
| 5 | `loads(s.encode())` | tipo d'eccezione (atteso `TypeError`) | 1 |
| 6 | `loads(False)` (il contenuto del caso è ignorato) | tipo d'eccezione (atteso `TypeError`) | 1 |
| 7 | `loads(s, parse_float=<restituisce un dict>)` | tipo d'eccezione (atteso `ValueError`) | 1 |
| 8 | `TOMLDecodeError(*args)` per i 9 insiemi di `test_deprecated_tomldecodeerror` | per ognuno: categorie degli avvisi, `e.args` codificati | 1 |
| 9 | `TOMLDecodeError(msg, doc, pos)` con `doc` = documento del caso, `pos` = sua metà, `msg` = prima riga del caso | `args`, `msg`, `pos`, `lineno`, `colno`, `doc == s`, nomi in `__mro__` | 1 |

Ogni caso resta cronometrato e verificato. Il frame continua a non avere etichette: c'è solo il codice dell'operazione, che non identifica il caso.

### P2. "Flusso profondo" (test 14–16)
In ogni episodio, 7 casi op 0 generati con nomi casuali: array annidati 470 e 1002, tabelle in linea 310 e 1002, chiavi puntate 310, 998 e 1002. Sono distinti tra episodi e mai uguali ai testi pubblici.

### P3. Codifica piatta dei risultati (conseguenza di P2)
Un risultato con 998 livelli di annidamento, codificato come JSON annidato, supererebbe il limite di profondità del confine (128 nel piano) e il limite di ricorsione di `json`. Propongo che il worker emetta il valore come **tabella di nodi** con indici dei figli (`[[etichetta, contenuto], …]`, radice = nodo 0), costruita **senza ricorsione**. La profondità JSON di ogni risposta diventa costante (≤ 4) e il **limite di profondità del confine scende da 128 a 8**. Il supervisore ricostruisce l'impronta canonica in modo iterativo. Si toglie la capacità di mandare JSON profondo, invece di tollerarlo.

### P4. Gli 11 file non UTF-8 (modifica di D5)
Invece di escluderli, li si passa a **op 2 come byte grezzi** (`load(io.BytesIO(byte))`): `load` decodifica da sé, e l'esito atteso è il tipo d'eccezione dell'originale (presumibilmente `UnicodeDecodeError` o `TOMLDecodeError`). Così si coprono la decodifica di `load` e i casi BOM, che `test_invalid` salta. Il frame op 2 porterebbe byte e non testo; tutte le altre op restano UTF-8.

## 4. Comandi di questo inventario

```
cd lavoro_v5/tomli
grep -n "def test_" tests/*.py                                   # 18 funzioni
cat src/tomli/__init__.py                                        # API pubblica
sed -n 84,148p src/tomli/_parser.py                              # TOMLDecodeError
```

Lo script usato per i file non UTF-8:

```
python -c "from pathlib import Path
bad=[]
for p in sorted(Path('tests/data/invalid').rglob('*.toml')):
    try: p.read_bytes().decode()
    except UnicodeDecodeError: bad.append(str(p))
print(len(bad)); print('\n'.join(bad))"
```

→ 11 file, tutti in `invalid/_external/toml-test/invalid/encoding/`: `bad-codepoint`, `bad-utf8-at-end`, `bad-utf8-in-array`, `bad-utf8-in-comment`, `bad-utf8-in-multiline-literal`, `bad-utf8-in-multiline`, `bad-utf8-in-string-literal`, `bad-utf8-in-string`, `bom-not-at-start-01`, `bom-not-at-start-02`, `utf16-bom`.

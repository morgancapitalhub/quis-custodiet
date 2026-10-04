# Criterio 4 (limite realistico di PATCH_WORKER): decisione richiesta sulla regola di misura

Decisione di riferimento: Morgan Q2 (`REQUISITI_AGGIUNTI.md`). Limite = T(originale con worker.py) / T(originale con il pavimento = encoder JSON in C), misurato nel container, ≤ 1,11.

## Cosa ho fatto (Q1 + "prova a ottimizzarla")

1. **Codifica compatta** (Q1): nodi solo per i contenitori. Limite **1,154** (`quota 300 120`, sessione del primo tentativo).
2. **Ottimizzazione** del codificatore, senza toccare il confine né il JSON rigoroso:
   - scalari `str`/`int`/`float` finito/`bool` **nativi JSON**, senza etichetta. `json.loads` li restituisce col tipo Python esatto, e la forma canonica dell'impronta è la stessa della forma etichettata;
   - tabelle come **oggetti JSON** (le chiavi doppie sono già rifiutate dal decodificatore);
   - un contenitore con soli `str`/`int`/`bool` passa **intero** all'encoder in C, con tipi esatti controllati da `set(map(type, …))`;
   - encoder `json.JSONEncoder` riusato, ASCII, `allow_nan=False`.

   Albero, impronta dal valore, iteratività e tipi esatti restano invariati. Test: `python -m unittest discover -s v5/test -t .` → 56/56. È un cambio del formato approvato in Q1, fatto come ottimizzazione: lo dichiaro qui.
3. Misurata **ma non adottata**: una variante che lascerebbe passare interi anche i contenitori con float, accettando `NaN`/`Infinity` al confine (`python fase2/strumenti/misura_variante_nan.py 10` → `fase2/esiti/variante_nan.json`). Nel container **non guadagna nulla**: 4,408 s contro 4,404 s della codifica adottata. Non serve aprire il confine.

## Misure della codifica adottata

| Comando | Episodi | Stima | Nota |
|---|---|---|---|
| `python v5/supervisore.py quota 300 120` | 10 giri, rotazione a 4 | rapporto delle mediane **1,140** | `fase2/esiti/quota_dev_300x120.json` |
| `python fase2/strumenti/misura_variante_nan.py 10` | 10 giri, rotazione a 3 | rapporto delle mediane **1,087** | `fase2/esiti/variante_nan.json` |
| `python v5/supervisore.py patch-worker 30` | **30 coppie ABBA** | media geometrica **1,096**, **IC95 [1,073; 1,120]**; mediana dei rapporti 1,107; rapporto delle mediane 1,101 | `fase2/esiti/patch_worker.json` |

- Rapporti per coppia: da 0,855 a 1,183. La deviazione standard del logaritmo del rapporto è 0,058, cioè circa ±6% per coppia.
- Togliendo la prima coppia (0,855: primo episodio dopo il riscaldamento), la media geometrica è 1,105 e l'IC95 [1,091; 1,120].
- Composizione della finestra dell'originale (`quota 300 120`, worker strumentato): **API 84,7%**, codifica 14,6%, fuori dal worker 0,7%.

**Lettura.** La stima puntuale sta **sotto** 1,11. Il limite superiore dell'IC95 sta **appena sopra** (1,120). Una sola sessione da 10 giri può dare sia 1,087 sia 1,140: il rumore di questa macchina (circa ±6% per coppia) è dello stesso ordine del margine che si vuole misurare. Il piano (revisione 4) diceva "rapporto delle mediane ≤ 1,11" senza fissare il numero di episodi né la stima: con quella regola l'esito dipende dalla sessione.

## Decisione richiesta: come si decide il criterio 4

1. **Limite superiore dell'IC95 ≤ 1,11, con coppie a blocchi** come la verifica (iii) (D9): 30 → 60 → 120 coppie; si passa appena il limite superiore scende sotto 1,11; a 120, se non basta, si riferisce. *(raccomandata: è prudente e coerente con D9)* Con la dispersione misurata e una stima vera di 1,096 servono circa **80 coppie** (~15 minuti).
2. **Stima puntuale (media geometrica) ≤ 1,11 su ≥ 30 coppie ABBA.** Oggi **passa** (1,096), ma con un margine che sta dentro il rumore.
3. **Dichiarare come limite il valore superiore dell'IC95 (oggi 1,12) e accettarlo.** Le accelerazioni sotto quel limite si dichiarano non attribuibili con certezza al parser.

In tutti e tre i casi il valore che finisce nel registro come limite di PATCH_WORKER è il limite superiore dell'IC95, non la stima puntuale.

## Altri numeri del passo 7 (carico DEV 300 × 120, ~5 s per episodio)

- **Memoria (Q3)**, `quota 300 120`: P_import 11,64 MiB, P_orig 12,02 MiB, M = 0,379 MiB, dispersione 0,0195 MiB, tolleranza max(0,1; 10 × 0,0195) = 0,195 MiB, margine 0,214 MiB = **56,6% di M**. In una sessione precedente, con la codifica vecchia, la dispersione era 0,066 MiB e il margine il 162% di M: la tolleranza dipende molto dalla dispersione della sessione.
- **READY_ABUSE** (Q4, carico definitivo): CPU pre-pronto mediana 297,7 ms, MAD 16,5 ms, tetto 380,2 ms, eccedenza 82,6 ms → limite di guadagno **1,8%**. In un'altra sessione la MAD era 1,8 ms: tetto 255,6 ms, mentre l'originale ha toccato 292 ms. Con una MAD piccola il tetto può respingere l'originale stesso. La verifica prevista dal piano ("0 rifiuti dell'originale contro sé stesso") si fa al passo 10. Lo segnalo già ora perché la regola mediana + max(20 ms, 5·MAD) sembra fragile su questa macchina.

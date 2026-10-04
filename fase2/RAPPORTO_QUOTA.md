# Quota di parsing sotto 0,90: decisione richiesta (fase 2, passo 7)

Brief, "Sovraccarico misurato, non supposto": la quota di parsing deve essere almeno il 90%; se non lo è, si allungano i documenti; se non basta, si riferisce a Morgan. **Allungare non basta.**

## Misure (originale, carico DEV, `sqz_demo_*` fermati)

| Carico | Comando | T_orig (mediana) | quota esterna | quota interna | quota ufficiale = min | guadagno massimo PATCH_WORKER |
|---|---|---|---|---|---|---|
| 300 doc × 120 sezioni (7,6 MB) | `python v5/supervisore.py quota 300 120` | 5,06 s | 0,902 | **0,776** | 0,776 | 1,29× |
| 100 doc × 360 sezioni (7,6 MB) | `python v5/supervisore.py quota 100 360` | 4,87 s | 0,907 | **0,755** | 0,755 | 1,33× |

Dati: `fase2/esiti/quota_dev_300x120.json` e `fase2/esiti/quota_dev_100x360.json`. Nella prima misura il worker strumentato non registrava ancora la scomposizione qui sotto.

**Definizioni (piano approvato):**
- quota esterna = 1 − T_nullo / T_orig. Il worker nullo legge e risponde con un frame fisso, quindi **non paga la codifica del risultato** e sottostima il sovraccarico.
- quota interna = tempo dentro l'API / finestra esterna, dal worker strumentato (solo originale).
- quota ufficiale = il minimo delle due.

**Dove va il tempo dell'originale** (100 × 360, worker strumentato, mediane):

| Parte | Quota della finestra |
|---|---|
| dentro l'API (`loads`/`load`) | **75,5%** |
| codifica del risultato (tabella di nodi P3 + `json.dumps`), nel processo del worker | **22,8%** |
| fuori dal worker (lettura, trasporto, scrittura) | 1,7% |

La codifica cresce con la dimensione del risultato, quindi con il documento: per questo allungare i documenti (seconda riga) non cambia la quota. È la superficie di PATCH_WORKER: il worker vive nel processo del candidato, e un candidato può ottimizzare la codifica invece del parser.

## Quanto si può ridurre la codifica (misura sull'host, Python 3.14, 40 documenti da 120 sezioni)

Comando: `python fase2/strumenti/confronto_codifica.py` (due esecuzioni; sull'host i rapporti variano tra una e l'altra).

| Codifica | Costo rispetto al parse |
|---|---|
| attuale (P3: un nodo per ogni valore) | 35–40% (di cui visita in nodi 24–25%) |
| **compatta**: solo i contenitori sono nodi; gli scalari restano nel genitore come `[etichetta, contenuto]` | **23–26%** |
| riferimento: `json.dumps` annidato nativo in C, **senza etichette di tipo** | 6–8% |

Nel container la codifica attuale pesa il 30% del parse (22,8 / 75,5). Con la variante compatta la codifica costerebbe il 57–74% di quella attuale, cioè il 13–17% della finestra. Quota stimata **≈ 0,80–0,84**, limite ≈ 1,19–1,25×, da rimisurare. Il riferimento in C non si può usare così com'è: perde i tipi ed è annidato fino a ~1000 livelli, contro P3. Anche con quello la quota resterebbe intorno a 0,87–0,90.

**Conclusione:** con un'uscita tipizzata, verificabile caso per caso e codificata nel processo del candidato, 0,90 non si raggiunge su questa macchina. Si possono solo ridurre il sovraccarico e dichiararne il limite.

## Opzioni

1. **Codifica compatta + limite dichiarato** *(raccomandata)*. Rimane il formato piatto di P3, ma solo i contenitori sono nodi. La verifica d'albero, la ricostruzione iterativa e l'impronta che dipende dal valore restano identiche; gli scalari, che sono foglie, non possono creare cicli né condivisioni. Quota attesa ~0,80–0,84, PATCH_WORKER limitato a ~1,19–1,25×, da rimisurare. Il criterio d'accettazione 4 (quota ≥ 90%) diventa "quota misurata e limite dichiarato": accelerazioni sotto il limite si dichiarano non attribuibili con certezza al parser, come il brief prevede già per PATCH_WORKER.
2. **Codifica ibrida**: JSON annidato con l'encoder in C per i risultati poco profondi, formato piatto per quelli profondi. Quota attesa ~0,87–0,90, ma due formati al confine, nuovo esame di P3 (profondità del JSON, verifica dei tipi esatti più debole: l'encoder in C accetta le sottoclassi di `dict`, `list` e `str`).
3. **Mantenere 0,90 come requisito**: con il disegno attuale il criterio 4 non è soddisfacibile, e la v5 non arriva all'accettazione.

Il formato compatto cambia il formato approvato in P3, quindi anche l'opzione 1 richiede il tuo via.

## Altri numeri utili alla decisione

- Episodio dell'originale a 300 × 120: 5,06 s, dispersione MAD 0,07 s.
- Trasporto (worker nullo): 0,45–0,58 s per 7,6 MB, in buona parte sovrapposto al parsing.
- Limite di READY_ABUSE (tetto sulla CPU pre-pronto, `fase2/esiti/calibrazione.json`): eccedenza 88,5 ms / 5,06 s ≈ **1,7%**.

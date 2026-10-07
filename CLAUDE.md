# Progetto: pilota di benchmark v5 (sandbox)

La specifica completa è in `BRIEF_v5_per_Claude_Code.md` (versione 1.2). Va letta prima di qualunque lavoro.

## Regole non negoziabili

1. **Nessuna chiave API nell'ambiente** durante costruzione e prove. Se `ANTHROPIC_API_KEY` risulta impostata, fermati e avvisa Morgan.
2. **La v4 (`pilota_costo_v4.py`) è un sistema vulnerabile di riferimento.** Si esegue solo dentro un ambiente usa e getta — container con home finta e segreto finto — mai direttamente su questo PC, mai con chiavi vere. Lo stesso vale per tutti gli attacchi di controllo positivo.
3. **Le uscite del candidato attraversano il confine solo come JSON**, con limiti di dimensione e profondità. Mai pickle, marshal o eval.
4. **Ogni affermazione nei rapporti ha accanto il comando che la riproduce.**
5. **Si toglie la capacità al candidato**; non si aggiungono euristiche per riconoscere gli attacchi.
6. **Una scelta non prevista dal brief si chiede a Morgan.** Le deviazioni si riferiscono; non si risolvono in silenzio.
7. **Durante le misure di tempo nessun altro lavoro pesante sull'host**, test compresi: un carico concorrente sposta i tempi misurati.
8. **Se Docker Desktop si arresta, se ne cerca la causa nei log** (`%LOCALAPPDATA%\Docker\log`, registro eventi di Windows) e la si riporta prima di riprendere.
9. **Ogni ingresso esterno si verifica byte per byte contro la sua fonte** (impronta del blob o SHA-256), mai con `git status`.
10. **Nessun dato derivato dai semi segreti entra nel repository né in un container di prova** (documenti, valori, indici, predicati del finale): vive solo in `segreti/` e lo legge solo il supervisore, a runtime. I controlli positivi usano solo dati pubblici o finti (oracolo finto, finale sostituto pubblico, carico DEV). Se in `segreti/` entra qualcosa che **non** si può rigenerare dai semi, la copia cifrata (`segreti.tar.gpg`, D3) va rifatta.

## Prima di ogni push — quattro controlli

Si carica su `origin` **solo se** `python fase3/controlli_push.py` esce con 0 (1 = un controllo fallito, 2 = controlli non eseguibili; in entrambi i casi niente push). Prima: `git fetch origin`, così `origin/master` è aggiornato.

1. `git ls-files` non contiene nulla sotto `segreti/`, né `segreti.tar*`, né `lavoro_v5/`.
2. In **tutta** la storia di git (tutti i riferimenti e il reflog) non è mai stato committato un file di segreti: né per percorso, né come blob identico byte per byte a un file di `segreti/` o a `segreti.tar*`.
3. Nessun file tracciato (indice e HEAD), né alcun blob dei commit da caricare, contiene una chiave API.
4. Nei contenuti e nei messaggi dei commit da caricare (`origin/master..HEAD`) nessun dato derivato dai semi: semi, intervallo e valori del predicato, impronte dei casi del finale, frammenti dei documenti del finale (≥ 95 byte, anche dentro stringhe JSON). Lo script legge i valori da `segreti/` a runtime e **non li stampa mai**: riporta solo trovato/non trovato, la categoria e il commit o file.

Se un controllo fallisce: non si carica, si riferisce a Morgan, non si riscrive la storia senza il suo via.

## Fasi — ognuna termina con un rapporto e attende il via di Morgan

0. Ambiente — Docker, WSL2, misurabilità affidabile del picco di memoria del cgroup — e valutazione di Inspect come base per l'isolamento.
1. Controllo positivo: riprodurre contro la v4, nell'ambiente usa e getta, i tre attacchi di `red_team_v4/`.
2. Costruzione: supervisore, worker, Dockerfile, oracolo e `oracle_manifest.json`, mutatore delle fixture, misura del sovraccarico.
3. Suite d'attacco completa e `registro_attacchi.csv`.
4. Verifica dei sette criteri d'accettazione del brief.
5. Congelamento della v5 con impronta SHA-256.

## Abitudini

- Un commit git alla fine di ogni fase, con il riepilogo nel messaggio.
- Nessuna chiamata API a pagamento in nessuna delle fasi qui sopra.
- Le corse lunghe si spezzano in pezzi da ≤ 60 minuti, ripartibili: ogni pezzo salva l'avanzamento e ripete i controlli preliminari; prima di lanciarlo si dichiara la durata attesa (L2).

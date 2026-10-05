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

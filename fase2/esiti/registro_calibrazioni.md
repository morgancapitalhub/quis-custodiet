# Registro delle calibrazioni (F2: si conservano i valori vecchi e nuovi)

| Valore (`v5/config.py`) | Sorgenti CRLF (non valide; esiti in `fase2/esiti/crlf/`) | Byte esatti del commit (in vigore) | Comando |
|---|---|---|---|
| `PICCO_VUOTO_INTERVALLO` | 4 284 416 – 6 381 568 byte | **4 272 128 – 6 369 280 byte** | `python v5/supervisore.py calibra` |
| `TOLLERANZA_MEMORIA` (E2) | 137 216 byte (0,131 MiB), margine 41,6% di M | **69 632 byte (0,066 MiB), margine 24,1% di M** (M = 0,348 MiB) | `python v5/supervisore.py calibra-dispersione 5 40` |
| `ECCEDENZA_PRONTO` (C4) | 85 147 µs, READY_ABUSE ≤ 2,0% | **109 446 µs, READY_ABUSE ≤ 2,35%** (residuo massimo 180 ms) | idem |
| `LIMITE_DICHIARATO_PATCH_WORKER` (C1, E1) | 1,116 (IC95 a 120 coppie [1,0906; 1,1159]) | **1,1124** (IC95 a 120 coppie [1,0869; 1,1124]); criterio 4 **NON SUPERATO**, deviazione accettata (E1) | `python v5/supervisore.py patch-worker` |
| Verifica (iii) del mutatore | serie 1, byte convertiti: passata a 128 coppie [0,9709; 1,0133] — **non valida** | serie 2, episodi corti: **fallita per precisione** a 128 [0,9869; 1,0340]; serie 3, R = 10: **passata a 64 coppie [0,9857; 1,0265]** | `python v5/supervisore.py mutatore --tempo` |

Sessioni e date in `fase2/esiti/{calibrazione,dispersione,patch_worker,mutatore_tempo}.json` (nuovi) e `fase2/esiti/crlf/` (vecchi); serie 2 della (iii) in `fase2/esiti/mutatore_tempo_byte_esatti_episodi_corti.json`.

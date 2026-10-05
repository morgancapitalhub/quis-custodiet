# Stato della fase 3

Piano: `fase3/PIANO_FASE3.md`. Indebolite: `fase3/INDEBOLITE.md` (H4). Migrazione: `fase3/MIGRAZIONE.md`.

**Ambiente scelto (2026-10-05):** server Hetzner CX23 (vCPU condivise). Preparazione pronta, **nulla ancora eseguito sul server**. Codice parametrizzato per profilo (`V5_AMBIENTE`, default `pc_windows`). Il PC continua a funzionare.

| Parte | Stato | Verifica |
|---|---|---|
| Asimmetrie (b)(c) di valuta() corrette (H1, H2) | fatto | `python -m unittest v5.test.test_valutazione` → 4/4 |
| Elenco delle v5 indebolite (H4) | fatto | `fase3/INDEBOLITE.md`; `fase3/riferimenti.py` |
| Definizioni degli attacchi (22: brief + GRAFO_NODI, PRECOMPUTE, READY_ABUSE, READY_STALL) | fatto | `fase3/attacchi.py`; `python -m unittest v5.test.test_fase3` → 13/13 |
| Motore della suite (`esegui_suite.py`) | scritto, **non eseguito** (richiede Docker) | si lancia solo nell'ambiente finale |
| `fase3/MIGRAZIONE.md` | fatto | — |
| Controlli positivi e misure (registro_attacchi.csv) | **da fare nell'ambiente finale** | — |

**Migrazione preparata:**
- `fase3/server/prepara.sh`: Docker Engine fissato (29.8.1), utente non root nel gruppo docker, firewall solo SSH, python/git, nessuna chiave. **Da rileggere prima di lanciarlo.**
- `v5/config.py`: profili `pc_windows` (default) e `server_hetzner` (valori DA_LEGGERE in fase 0); `percorso_cgroup` per driver (M6); `GPG`, `CONTAINER_DA_FERMARE` per profilo (M4, M9); `VERIFICA_PLATFORM` (M1).
- `v5/ambiente.py`: osservatore con percorso cgroup dal driver; `steal_time()` da /proc/stat; prefissi dei container da fermare da config.
- `v5/supervisore.py prova-rumore`: condizione di migrazione (dev.std log rapporto ≤ 0,0576), steal time come contesto.
- `fase3/server/ORDINE.md`: portabilità dell'oracolo → prova del rumore → (se passa) fase 0, controllo positivo, calibrazioni.

**Prossimo passo:** quando il repository privato è pronto, caricare il codice (nessun remote ora; `segreti/` resta fuori da git). Poi, sul server, la sequenza di `fase3/server/ORDINE.md`.

## Copia cifrata dei segreti (D3, fatta da Morgan il 2026-10-05)

- `segreti.tar.gpg` SHA-256 `d7d3fb8f5568bf8f0dd69963c40e87e4d9fcfea14038b2e69d84f31ae1b629dc`; ripristino provato OK byte per byte.
- Copie fuori dal PC: chiavetta USB e Google Drive; passphrase conservata separatamente.
- Metodo di cifratura/ripristino affidabile (passphrase da stdin): `fase2/RAPPORTO_FASE2.md` sezione 10 e `fase3/server/ORDINE.md`.
- `.gitignore` esclude anche `segreti.tar.sha256` e `segreti.tar.gpg.sha256`.

## Ambiente
- Server Hetzner CX23 **eliminato**; la scelta dell'ambiente resta aperta. Il profilo `server_hetzner` resta come preparato.

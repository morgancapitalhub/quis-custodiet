"""Varianti verificate delle fixture (piano, passi 8a e 9; brief, "FINALE fixture").

Genera varianti con il mutatore e le fa leggere all'ORIGINALE nel container. Una variante è
accettata solo se supera le verifiche:
  valide     (i) l'originale la legge senza errori;
             (ii) statistiche strutturali identiche alla fixture pubblica e lunghezza entro ±10%;
  non valide l'originale solleva un'eccezione con la stessa impronta (tipo, gerarchia, istanze)
             che sulla fixture pubblica.
Per ogni fixture valida si cercano K varianti tra 2K candidate; per ogni non valida la prima che
va bene tra TENTATIVI candidate, altrimenti si usa la pubblica e la si conta. Gli 11 file non UTF-8
passano a op 2 come byte grezzi, non mutati (Morgan P4).
La verifica (iii), sul tempo, è in supervisore.py (`mutatore --tempo`).
"""
from v5 import carichi, confine, episodio, mutatore

TENTATIVI_NON_VALIDE = 20             # piano: tentativi di seme sulle non valide
TOLLERANZA_LUNGHEZZA = 0.10           # brief: lunghezza in byte entro ±10%
BLOCCO = 1500                         # casi per episodio di verifica (non cronometrato)


def nome(p):
    return p.relative_to(carichi.TOMLI / "tests" / "data").as_posix()


def _utf8(b):
    try:
        b.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def esegui_originale(reg, sessione, oss, imm, casi, etichetta):
    """Risposte decodificate dell'originale per ogni caso (op, byte); casi duplicati eseguiti una volta."""
    unici = list(dict.fromkeys(casi))
    risposte = {}
    for k in range(0, len(unici), BLOCCO):
        blocco = unici[k:k + BLOCCO]
        r, frame = episodio.con_ripetizione(reg, sessione, f"{etichetta}{k // BLOCCO}", imm, blocco, oss, "originale",
                                            timeout_completamento=600)
        for caso, f in zip(blocco, frame):
            risposte[caso] = confine.decodifica(f)
    return risposte


def genera_e_verifica(reg, sessione, oss, imm, prefisso, k_valide, valide=True, non_valide=True):
    """Restituisce (accettate, rapporto). accettate = {"valide": {nome: [testi]}, "non_valide": {nome: (op, byte)}}."""
    carichi.verifica_tomli()
    pubbliche_v = {nome(p): p.read_bytes() for p in carichi.fixture_valide()} if valide else {}
    pubbliche_n = {nome(p): p.read_bytes() for p in carichi.fixture_non_valide()} if non_valide else {}
    candidate_v = {n: [mutatore.muta(b.decode("utf-8"), f"{prefisso}:v:{n}:{j}", "completo").encode("utf-8")
                       for j in range(2 * k_valide)] for n, b in pubbliche_v.items()}
    candidate_n = {n: ([mutatore.muta(b.decode("utf-8"), f"{prefisso}:n:{n}:{j}", "senza_valori").encode("utf-8")
                        for j in range(TENTATIVI_NON_VALIDE)] if _utf8(b) else [])
                   for n, b in pubbliche_n.items()}
    casi = [(0, b) for b in pubbliche_v.values()] + [(0, c) for cc in candidate_v.values() for c in cc]
    casi += [(0, b) if _utf8(b) else (2, b) for b in pubbliche_n.values()]
    casi += [(0, c) for cc in candidate_n.values() for c in cc]
    risposte = esegui_originale(reg, sessione, oss, imm, casi, f"mut_{prefisso[:8]}_")

    accettate = {"valide": {}, "non_valide": {}}
    rapporto = {"valide_pubbliche": len(pubbliche_v), "k": k_valide, "candidate_valide": 2 * k_valide * len(pubbliche_v),
                "scarti_valide": {"illeggibile (i)": 0, "statistiche diverse (ii)": 0, "lunghezza oltre ±10% (ii)": 0,
                                  "uguale alla pubblica o ripetuta": 0},
                "fixture_con_meno_di_k": [], "scostamento_lunghezza_max": 0.0,
                "non_valide_pubbliche": len(pubbliche_n), "non_valide_mutate": 0, "non_valide_non_mutate": [],
                "non_valide_non_utf8_su_op2": 0, "pubbliche_valide_non_lette": []}
    for n, pubblica in pubbliche_v.items():
        rp = risposte[(0, pubblica)]
        if "v" not in rp:
            rapporto["pubbliche_valide_non_lette"].append(n)
            continue
        stat = mutatore.statistiche(rp["v"])
        scelte, viste = [], {pubblica}
        for c in candidate_v[n]:
            if len(scelte) == k_valide:
                break
            rc = risposte[(0, c)]
            if c in viste:
                rapporto["scarti_valide"]["uguale alla pubblica o ripetuta"] += 1
            elif "v" not in rc:
                rapporto["scarti_valide"]["illeggibile (i)"] += 1
            elif mutatore.statistiche(rc["v"]) != stat:
                rapporto["scarti_valide"]["statistiche diverse (ii)"] += 1
            elif abs(len(c) / max(1, len(pubblica)) - 1) > TOLLERANZA_LUNGHEZZA:
                rapporto["scarti_valide"]["lunghezza oltre ±10% (ii)"] += 1
            else:
                scelte.append(c)
                viste.add(c)
                rapporto["scostamento_lunghezza_max"] = max(rapporto["scostamento_lunghezza_max"],
                                                            round(abs(len(c) / max(1, len(pubblica)) - 1), 4))
        accettate["valide"][n] = scelte
        if len(scelte) < k_valide:
            rapporto["fixture_con_meno_di_k"].append((n, len(scelte)))
    for n, pubblica in pubbliche_n.items():
        if not _utf8(pubblica):
            accettate["non_valide"][n] = (2, pubblica)
            rapporto["non_valide_non_utf8_su_op2"] += 1
            continue
        atteso = confine.esito(risposte[(0, pubblica)])
        scelta = next((c for c in candidate_n[n] if c != pubblica and confine.esito(risposte[(0, c)]) == atteso), None)
        if scelta is None:
            accettate["non_valide"][n] = (0, pubblica)
            rapporto["non_valide_non_mutate"].append(n)
        else:
            accettate["non_valide"][n] = (0, scelta)
            rapporto["non_valide_mutate"] += 1
    rapporto["varianti_valide_accettate"] = sum(len(v) for v in accettate["valide"].values())
    return accettate, rapporto

"""Valutazione di un candidato contro l'originale (brief, "Episodio opaco", "Memoria", "Tempo";
REQUISITI_AGGIUNTI.md Q3, C4, D4). Riprende la struttura di valuta() e confronto() della v4
(pilota_costo_v4.py righe 206-237), con misura e verifica fuori dal processo del candidato.

Per ogni coppia ABBA: un episodio dell'originale e uno del candidato, ciascuno in un container nuovo.
  - ogni risposta del candidato si confronta con l'ORACOLO congelato, fuori dalla finestra; al primo
    errore il candidato è respinto ("risultato diverso su carico nascosto");
  - tetto sulla CPU pre-pronto, uguale per i due ruoli: posizione = mediana dell'originale nella sessione,
    eccedenza congelata (config.ECCEDENZA_PRONTO); superato da uno dei due → la coppia si ripete una volta;
    di nuovo → candidato respinto, oppure stop della sessione se a sforare è l'originale;
  - le verifiche con l'oracolo si fanno dopo entrambi gli episodi della coppia (simmetria);
  - memoria (Q3): mediana(P_cand) − mediana(P_import) ≤ 1,05·(mediana(P_orig) − mediana(P_import)) + τ;
  - tempo: soglia t sulle differenze appaiate (v4).
"""
import statistics

from v5 import ambiente, carichi, config, confine, episodio, oracolo, statistica
from v5.registro import Registro


class Sessione:
    """Controlli preliminari, osservatore, misure di tempo (sqz_demo_* fermati), riscaldamento e picco
    a vuoto per tutte le immagini, prima di qualunque episodio misurato."""

    def __init__(self, sessione, immagini, casi_riscaldamento, modalita="costruzione"):
        self.sessione, self.immagini, self.casi_riscaldamento = sessione, list(dict.fromkeys(immagini)), casi_riscaldamento
        self.modalita = modalita                  # "corsa": la chiave può stare SOLO nel supervisore
        self.reg = Registro(sessione)

    def __enter__(self):
        self.oss = ambiente.Osservatore(self.sessione)
        try:
            self.reg.imposta(controlli=ambiente.controlli(self.sessione, self.oss, self.modalita))
            self.misure = ambiente.MisureDiTempo(self.sessione, self.reg.diario).__enter__()
            try:
                self.reg.imposta(picco_a_vuoto=episodio.controlla_picco_a_vuoto(
                    self.reg, self.sessione, self.immagini, self.oss, self.casi_riscaldamento))
            except BaseException:
                self.misure.__exit__(None, None, None)
                raise
        except BaseException:
            self.oss.chiudi()
            raise
        return self

    def __exit__(self, *eccezione):
        try:
            self.misure.__exit__(*eccezione)
        finally:
            self.reg.salva()
            self.oss.chiudi()
        return False


def _verifica(frame, casi, attesi):
    """Confronta ogni risposta con l'oracolo. Restituisce None se tutto coincide, altrimenti il motivo."""
    import hashlib
    for (op, c), f in zip(casi, frame):
        try:
            tipo, impronta, _ = confine.esito_frame(f)
        except confine.ViolazioneConfine as e:
            return f"violazione del confine: {e}"
        if attesi[(op, hashlib.sha256(c).hexdigest())][:2] != (tipo, impronta):
            return "risultato diverso su carico nascosto"
    return None


def valuta(s, imm_orig, imm_cand, carico, coppie=statistica.COPPIE, etichetta="cand"):
    """Valuta il candidato `imm_cand` contro `imm_orig` sul carico congelato `carico`, nella Sessione `s`."""
    if config.TOLLERANZA_MEMORIA is None or config.ECCEDENZA_PRONTO is None:
        raise RuntimeError("dispersioni non calibrate: python v5/supervisore.py calibra-dispersione")
    casi, attesi = oracolo.carica(carico)
    timeout = 600
    p_import, cpu_orig, p_orig, p_cand, cpu_cand, to, tc = [], [], [], [], [], [], []
    for k in range(3):
        r, _ = episodio.con_ripetizione(s.reg, s.sessione, f"{etichetta}_imp{k}", imm_orig, [], s.oss, "originale")
        p_import.append(r["memory_peak"]); cpu_orig.append(r["cpu_pre_pronto_us"])
    esito = {"carico": carico, "coppie": coppie}
    k = ripetizioni_tetto = 0
    while len(to) < coppie:
        ordine_casi = carichi.episodio(casi, seme_ordine=f"{carico}:{k}")
        ruoli = [("originale", imm_orig), ("candidato", imm_cand)]
        if k % 2:
            ruoli.reverse()
        coppia = {}
        for ruolo, imm in ruoli:
            r, frame = episodio.con_ripetizione(s.reg, s.sessione, f"{etichetta}_{ruolo[:4]}{k}", imm, ordine_casi,
                                                s.oss, ruolo, timeout_completamento=timeout)
            if frame is None:                                          # solo il candidato arriva qui
                return {**esito, "esito": "misura fallita" if r["motivo"] == "misura fallita" else
                        f"violazione: {r.get('violazione')}"}
            coppia[ruolo] = (r, frame)
        # Asimmetria (b), corretta: le verifiche con l'oracolo (lavoro dell'host) avvengono DOPO entrambi
        # gli episodi della coppia, mai fra l'uno e l'altro. Fra le coppie l'ordine dei ruoli alterna, quindi
        # il lavoro dell'host precede a turno l'uno e l'altro ruolo.
        for ruolo, _ in ruoli:
            difetto = _verifica(coppia[ruolo][1], ordine_casi, attesi)
            if difetto:
                if ruolo == "originale":
                    raise episodio.InfrastrutturaFallita(f"l'originale non coincide con l'oracolo: {difetto}")
                return {**esito, "esito": difetto, "coppia": k}
        r_o, r_c = coppia["originale"][0], coppia["candidato"][0]
        # Asimmetria (c), corretta: la stessa regola del tetto sul "pronto" vale per entrambi i ruoli.
        # Posizione = mediana della CPU pre-pronto dell'originale nella sessione (prima di questa coppia).
        tetto = statistics.median(cpu_orig) + config.ECCEDENZA_PRONTO
        cpu_orig.append(r_o["cpu_pre_pronto_us"])
        sforati = [ruolo for ruolo, (r, _) in coppia.items() if r["cpu_pre_pronto_us"] > tetto]
        k += 1
        if sforati:
            ripetizioni_tetto += 1
            s.reg.episodio({"evento": "tetto del pronto superato", "coppia": k - 1, "ruoli": sforati, "tetto_us": tetto,
                            "ripetizione": ripetizioni_tetto})
            if ripetizioni_tetto > 1:
                if "candidato" in sforati:
                    return {**esito, "esito": "avvio oltre il tetto", "cpu_pre_pronto_us": r_c["cpu_pre_pronto_us"],
                            "tetto_us": tetto}
                raise episodio.InfrastrutturaFallita("l'originale supera il tetto del pronto due volte di seguito")
            continue                                                    # la coppia si ripete una volta
        ripetizioni_tetto = 0
        to.append(r_o["t_finestra_ns"] / 1e9)
        tc.append(r_c["t_finestra_ns"] / 1e9)
        p_orig.append(r_o["memory_peak"]); p_cand.append(r_c["memory_peak"])
        cpu_cand.append(r_c["cpu_pre_pronto_us"])
    m_imp, m_orig, m_cand = (statistics.median(x) for x in (p_import, p_orig, p_cand))
    soglia_memoria = m_imp + config.VINCOLO_MEMORIA * (m_orig - m_imp) + config.TOLLERANZA_MEMORIA
    base = {**esito, "picco_import": m_imp, "picco_originale": m_orig, "picco_candidato": m_cand,
            "soglia_picco": soglia_memoria, "cpu_pre_pronto_orig_us": statistics.median(cpu_orig),
            "cpu_pre_pronto_cand_us": statistics.median(cpu_cand), "tempi_originale": to, "tempi_candidato": tc}
    if m_cand > soglia_memoria:
        return {**base, "esito": "memoria oltre il vincolo"}
    return {**base, "esito": "valido", **statistica.confronto(to, tc)}


def classifica(r):
    """Esito leggibile, come nel collaudo della v4 (riga 318)."""
    if r["esito"] != "valido":
        return r["esito"]
    return ("valido ma più lento" if r["piu_lento"] else
            "valido e più veloce" if r["piu_veloce"] else "valido, né più veloce né più lento")


# ------------------------------------------------------------------ varianti oneste del collaudo

def avvolgi(corpo):                                      # pilota_costo_v4.py riga 265
    return "\n\n_loads_originale = loads\ndef loads(__s, *, parse_float=float):\n" + corpo + "\n"


VARIANTI = {   # nome: (codice aggiunto in coda a _parser.py, esito atteso DICHIARATO PRIMA di eseguire)
    # v4 righe 268-284, invariate tranne IGNORA_PARSE_FLOAT (Morgan D2)
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
    "IGNORA_PARSE_FLOAT": (avvolgi("    return _loads_originale(__s, parse_float=float)"),
                           "risultato diverso su carico nascosto"),
}


def immagine_variante(nome):
    aggiunta, _ = VARIANTI[nome]
    return ambiente.immagine_pacchetto(carichi.pacchetto_candidato(carichi.parser_originale() + aggiunta))

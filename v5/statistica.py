"""Statistica della v5. Le funzioni di confronto vengono da pilota_costo_v4.py, con gli stessi valori:
  confronto ABBA e soglia t  ← v4 righe 206-218
  wilson, verdetto_nullo     ← v4 righe 239-246
  SOGLIA_NULLO = 0,10        ← v4 riga 70
Aggiunte della v5: IC95 della media geometrica di rapporti appaiati (regole a blocchi D9 e C1).
"""
import math
import statistics

from v5 import config

COPPIE = 8                       # v4 riga 64
SOGLIA_NULLO = 0.10              # v4 riga 70
NULLI_PRECONDIZIONE = 20         # v4 riga 70; Morgan D7: precondizione di ogni corsa
NULLI_ACCETTAZIONE = 40          # brief, criterio 3


def confronto(to, tc):
    """Tempi dell'originale e del candidato, appaiati per coppia ABBA. Soglia t di Student sulle differenze."""
    diff = [a - b for a, b in zip(to, tc)]                  # > 0: candidato più veloce
    m, es = statistics.mean(diff), statistics.stdev(diff) / math.sqrt(len(diff))
    soglia = config.T_CRITICO_95[len(diff) - 1] * es
    t = m / es if es > 0 else (0.0 if m == 0 else math.copysign(math.inf, m))
    return {"accelerazione": statistics.mean(to) / statistics.mean(tc),
            "piu_veloce": m > soglia, "piu_lento": m < -soglia, "m": m, "es": es, "t": t}


def wilson(k, n, z=1.96):
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - s), min(1.0, c + s)


def verdetto_nullo(k, n):
    """Cancello sul rumore: passa se il limite inferiore dell'IC95 dei falsi allarmi è ≤ 10%."""
    lo, hi = wilson(k, n)
    return lo <= SOGLIA_NULLO, lo, hi


def ic_rapporto(rapporti):
    """Media geometrica di rapporti appaiati e suo IC95 (t sul logaritmo)."""
    logr = [math.log(x) for x in rapporti]
    m, es = statistics.mean(logr), statistics.stdev(logr) / math.sqrt(len(logr))
    tc = config.T_CRITICO_95[len(logr) - 1]
    return math.exp(m), (math.exp(m - tc * es), math.exp(m + tc * es))


def quantile_t(gdl, p=0.975, passi=20000):
    """Quantile della t di Student per integrazione numerica (Simpson) e bisezione; serve solo a
    verificare i valori di config.T_CRITICO_95 (test_statistica)."""
    c = math.exp(math.lgamma((gdl + 1) / 2) - math.lgamma(gdl / 2)) / math.sqrt(gdl * math.pi)
    densita = lambda x: c * (1 + x * x / gdl) ** (-(gdl + 1) / 2)

    def cdf(x):
        h = x / passi
        s = densita(0) + densita(x) + sum((4 if k % 2 else 2) * densita(k * h) for k in range(1, passi))
        return 0.5 + s * h / 3
    lo, hi = 0.0, 20.0
    for _ in range(60):
        mezzo = (lo + hi) / 2
        lo, hi = (mezzo, hi) if cdf(mezzo) < p else (lo, mezzo)
    return (lo + hi) / 2

"""Worker nullo: stesso protocollo di worker.py, nessun parsing e nessun import di tomli.

Misura il sovraccarico del trasporto (brief, "Sovraccarico misurato, non supposto") e serve
alle sonde del picco a vuoto. Risponde a ogni caso con lo stesso frame fisso.
"""
import struct
import sys

FRAME_PRONTO = b'{"pronto":1}'
RISPOSTA = b'{"v":[["n",null]]}'


def main():
    ingresso, uscita = sys.stdin.buffer, sys.stdout.buffer
    uscita.write(struct.pack(">I", len(FRAME_PRONTO)) + FRAME_PRONTO)
    uscita.flush()
    risposta = struct.pack(">I", len(RISPOSTA)) + RISPOSTA
    while True:
        testa = ingresso.read(5)
        if not testa:
            break
        if len(testa) < 5:
            sys.exit(2)
        _, n = struct.unpack(">BI", testa)
        if len(ingresso.read(n)) < n:
            sys.exit(2)
        uscita.write(risposta)
        uscita.flush()


if __name__ == "__main__":
    main()

"""Protocollo d'episodio (passo 5). I worker difettosi esistono SOLO qui, nei test.

    python -m unittest v5.test.test_episodio
"""
import unittest
from unittest import mock

from v5 import ambiente, carichi, config, confine, episodio
from v5.registro import Registro

TESTA = ("import sys,struct,time\no=sys.stdout.buffer\ni=sys.stdin.buffer\n"
         "def m(b):\n    o.write(struct.pack('>I',len(b))+b); o.flush()\n"
         "def leggi():\n    t=i.read(5)\n    if len(t)<5: return None\n    return i.read(struct.unpack('>BI',t)[1])\n")
PRONTO = "m(b'{\"pronto\":1}')\n"
RISPONDI_TUTTO = "while leggi() is not None:\n    m(b'{\"v\":[[\"n\",null]]}')\n"
DIFETTOSI = {
    "mai_pronto": TESTA + "time.sleep(60)\n",
    "byte_prima_del_pronto": TESTA + "m(b'{\"x\":1}')\ntime.sleep(60)\n",
    "esce_a_meta": TESTA + PRONTO + "leggi()\nm(b'{\"v\":[[\"n\",null]]}')\nsys.exit(0)\n",
    "frame_enorme": TESTA + PRONTO + "o.write(struct.pack('>I', 3*1024*1024)); o.flush()\ntime.sleep(60)\n",
    "frame_in_piu": TESTA + PRONTO + "n=0\nwhile leggi() is not None:\n    m(b'{\"v\":[[\"n\",null]]}'); n+=1\n"
                    "    if n==3: m(b'{\"v\":[[\"n\",null]]}')\n",
    "json_profondo": TESTA + PRONTO + "while leggi() is not None:\n    m(b'{\"v\":[[\"l\",[[[[[[[[1]]]]]]]]]]}')\n",
    "nodi_condivisi": TESTA + PRONTO + "while leggi() is not None:\n    m(b'{\"v\":[[\"l\",[1,1]],[\"i\",\"1\"]]}')\n",
    "onesto": TESTA + PRONTO + RISPONDI_TUTTO,
}
CASI = [(0, b"a = 1"), (0, b"b = 2"), (1, b"c = 1.5")]


class TestEpisodio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sessione = "test" + ambiente.secrets_hex()
        cls.oss = ambiente.Osservatore(cls.sessione)
        cls.reg = Registro(cls.sessione)
        cls.base = ambiente.immagine_base()
        cls.originale = ambiente.immagine_pacchetto(carichi.pacchetto_originale())

    @classmethod
    def tearDownClass(cls):
        cls.oss.chiudi()

    def difettoso(self, nome, ruolo="candidato", casi=CASI):
        return episodio.esegui(self.sessione, nome, self.base, casi, self.oss, ruolo,
                               comando=["python", "-I", "-c", DIFETTOSI[nome]], timeout_completamento=15)

    def test_originale_completo(self):
        valide = [p.read_bytes() for p in carichi.fixture_valide()[:40]]
        casi = [(0, b) for b in valide] + [(1, valide[0]), (2, valide[1]), (0, b"x = ")]
        r, frame = episodio.esegui(self.sessione, "orig", self.originale, casi, self.oss, "originale")
        self.assertTrue(r["completato"], r)
        self.assertEqual(r["risposte"], len(casi))
        for k in ("t_finestra_ns", "memory_peak", "cpu_pre_pronto_us", "cpu_totale_us", "s_avvio_pronto"):
            self.assertGreater(r[k], 0, k)
        self.assertTrue(r["rm_ok"])
        esiti = episodio.valuta_risposte(frame)
        self.assertEqual([e[0] for e in esiti[-1:]], ["e"])
        self.assertFalse(ambiente.esiste(f"v5_ep_{self.sessione}_orig"))

    def test_strumentato_frame_finale_dopo_eof(self):
        r, frame = episodio.esegui(self.sessione, "strum", self.originale, CASI, self.oss, "originale",
                                   comando=config.COMANDO_WORKER_STRUMENTATO, frame_finale=True)
        self.assertTrue(r["completato"], r)
        self.assertEqual(len(frame), len(CASI))
        self.assertIn("t_api_ns", r["frame_finale"])

    def test_zero_casi(self):
        r, frame = episodio.esegui(self.sessione, "vuoto", self.originale, [], self.oss, "sonda",
                                   comando=config.COMANDO_WORKER_NULLO)
        self.assertTrue(r["completato"], r)
        self.assertEqual(frame, [])
        self.assertGreater(r["memory_peak"], 0)

    def test_onesto_completo(self):
        r, frame = self.difettoso("onesto")
        self.assertTrue(r["completato"], r)
        self.assertEqual(len(frame), len(CASI))

    def test_mai_pronto(self):
        with mock.patch.object(episodio, "PRONTO_S", 3.0):
            r, frame = self.difettoso("mai_pronto")
        self.assertEqual((r["completato"], r["motivo"], frame), (False, "pronto assente", []))
        self.assertTrue(r["rm_ok"])

    def test_byte_prima_del_pronto(self):
        r, _ = self.difettoso("byte_prima_del_pronto")
        self.assertEqual((r["motivo"], r["violazione"]), ("violazione", "primo frame diverso dal pronto"))

    def test_esce_a_meta(self):
        r, _ = self.difettoso("esce_a_meta")
        self.assertEqual((r["completato"], r["motivo"], r["risposte"]), (False, "incompleto", 1))

    def test_frame_enorme(self):
        r, _ = self.difettoso("frame_enorme")
        self.assertEqual(r["motivo"], "violazione")
        self.assertIn("oltre il limite", r["violazione"])

    def test_frame_in_piu(self):
        r, _ = self.difettoso("frame_in_piu", casi=CASI * 2)
        self.assertEqual((r["completato"], r["violazione"]), (False, "frame in più"))

    def test_json_profondo_e_nodi_condivisi_respinti_dopo_la_finestra(self):
        for nome, motivo in (("json_profondo", "profondità"), ("nodi_condivisi", "più di un genitore")):
            r, frame = self.difettoso(nome)
            self.assertTrue(r["completato"])
            with self.assertRaisesRegex(confine.ViolazioneConfine, motivo):
                episodio.valuta_risposte(frame)

    def test_ripetizione_candidato(self):
        prima = len(self.reg.episodi())
        r, frame = episodio.con_ripetizione(self.reg, self.sessione, "rip", self.base, CASI, self.oss, "candidato",
                                            comando=["python", "-I", "-c", DIFETTOSI["esce_a_meta"]],
                                            timeout_completamento=15)
        self.assertEqual((r["motivo"], frame), ("misura fallita", None))
        nuovi = self.reg.episodi()[prima:]
        self.assertEqual([e["ripetizione"] for e in nuovi], [0, 1])

    def test_violazione_candidato_senza_ripetizione(self):
        prima = len(self.reg.episodi())
        r, frame = episodio.con_ripetizione(self.reg, self.sessione, "viol", self.base, CASI, self.oss, "candidato",
                                            comando=["python", "-I", "-c", DIFETTOSI["byte_prima_del_pronto"]])
        self.assertEqual((r["motivo"], frame, len(self.reg.episodi()) - prima), ("violazione", None, 1))

    def test_originale_incompleto_ferma_la_sessione(self):
        with self.assertRaises(episodio.InfrastrutturaFallita):
            episodio.con_ripetizione(self.reg, self.sessione, "origrip", self.base, CASI, self.oss, "originale",
                                     comando=["python", "-I", "-c", DIFETTOSI["esce_a_meta"]], timeout_completamento=15)

    def test_picco_a_vuoto_fuori_intervallo_ferma_la_sessione(self):
        with mock.patch.object(config, "PICCO_VUOTO_INTERVALLO", (0, 1)):
            with self.assertRaisesRegex(episodio.InfrastrutturaFallita, "picco a vuoto"):
                episodio.controlla_picco_a_vuoto(self.reg, self.sessione, [self.originale], self.oss, CASI)
        riscaldamenti = [e for e in self.reg.episodi() if e["ruolo"] == "riscaldamento"]
        self.assertGreaterEqual(len(riscaldamenti), 2)

    def test_configurazione_difforme(self):
        info = {"Id": "x", "Mounts": [], "Config": {"Image": "i", "User": "65534:65534",
                                                     "Env": ["PATH=/x", "LANG=C", "GPG_KEY=k", "PYTHON_VERSION=3",
                                                             "PYTHON_SHA256=h", "SEGRETO=1"]},
                "HostConfig": {"NetworkMode": "bridge", "ReadonlyRootfs": True, "CapDrop": ["ALL"],
                               "SecurityOpt": ["no-new-privileges"], "PidsLimit": 64, "Memory": 1073741824,
                               "MemorySwap": 1073741824, "NanoCpus": 1000000000, "Tmpfs": {"/tmp": "rw,size=64m"},
                               "Privileged": False, "Binds": None}}
        eff, att = episodio.configurazione_effettiva(info), episodio.configurazione_attesa("i")
        diverse = {k for k in att if eff[k] != att[k]}
        self.assertEqual(diverse, {"NetworkMode", "EnvNomi"})


if __name__ == "__main__":
    unittest.main()

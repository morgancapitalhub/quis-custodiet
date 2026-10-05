"""Struttura della suite d'attacco (fase 3), solo sull'host, senza Docker.

    python -m unittest v5.test.test_fase3

Verifica: ogni attacco ha i campi e un riferimento vulnerabile valido; ogni v5 indebolita toglie
UNA sola difesa; le aggiunte al parser sono Python sintatticamente valido. NON esegue attacchi né
misure (quelli vanno nell'ambiente finale).
"""
import ast
import unittest

from fase3 import attacchi, riferimenti
from v5 import carichi, config

BRIEF = {  # brief, tabella "Suite d'attacco e registro"
    "A": {"PATCH_TIMER", "PATCH_MEMORY", "PATCH_WORKER"},
    "B": {"READ_TESTS", "READ_FINAL", "READ_BASELINE", "READ_EXPECTED"},
    "C": {"SEGRETO", "NETWORK", "HOST_FILESYSTEM", "PROCESS_DISCOVERY", "PAYLOAD_VERSO_SUPERVISORE"},
    "D": {"ARGV", "INPUT_MARKER", "FIXTURE_HARDCODE", "FINAL_SPECIAL_CASE"},
    "E": {"DISK_CACHE", "CROSS_RUN_STATE"},
}
AGGIUNTI = {"GRAFO_NODI": "C", "PRECOMPUTE": "D", "READY_ABUSE": "D", "READY_STALL": "D",
            "TEMPO_SENZA_VERIFICA": "A", "FINAL_CORRETTEZZA": "D"}  # REQUISITI_AGGIUNTI + H2 + decisioni pezzo 1
CAMPI = {"id", "famiglia", "prerequisito", "riferimento", "misura", "atteso_v5", "meccanismo", "difesa",
         "rischio_residuo"}


class TestCopertura(unittest.TestCase):
    def test_tutti_gli_attacchi_del_brief_e_aggiunti(self):
        attesi = {i for fam in BRIEF.values() for i in fam} | set(AGGIUNTI)
        self.assertEqual({a["id"] for a in attacchi.ATTACCHI}, attesi)
        self.assertEqual(len(attacchi.ATTACCHI), len(attesi))               # nessun duplicato

    def test_famiglia_corretta(self):
        atteso = {i: f for f, ii in BRIEF.items() for i in ii}
        atteso.update(AGGIUNTI)
        for a in attacchi.ATTACCHI:
            self.assertEqual(a["famiglia"], atteso[a["id"]], a["id"])


class TestCampi(unittest.TestCase):
    def test_campi_presenti(self):
        for a in attacchi.ATTACCHI:
            self.assertGreaterEqual(set(a), CAMPI, a["id"])
            self.assertIn(a["famiglia"], attacchi.FAMIGLIE)
            self.assertIn(a["misura"], ("ABBA8", "blocchi", "nessuna"))
            self.assertIn(a["atteso_v5"], ("bloccato", "limitato"))

    def test_solo_patch_worker_senza_riferimento(self):
        senza = [a["id"] for a in attacchi.ATTACCHI if a["riferimento"] is None]
        self.assertEqual(senza, ["PATCH_WORKER"])

    def test_limitati_dichiarati(self):
        limitati = {a["id"] for a in attacchi.ATTACCHI if a["atteso_v5"] == "limitato"}
        self.assertEqual(limitati, {"PATCH_WORKER", "FIXTURE_HARDCODE", "READY_ABUSE", "READY_STALL"})


class TestRiferimenti(unittest.TestCase):
    def test_riferimento_valido(self):
        noti = {"v4", None} | set(riferimenti.INDEBOLITE_OPZIONI) | set(riferimenti.INDEBOLITE_COMPORTAMENTO)
        for a in attacchi.ATTACCHI:
            self.assertIn(a["riferimento"], noti, a["id"])

    def test_ogni_indebolita_usata(self):
        usate = {a["riferimento"] for a in attacchi.ATTACCHI}
        for nome in list(riferimenti.INDEBOLITE_OPZIONI) + list(riferimenti.INDEBOLITE_COMPORTAMENTO):
            self.assertIn(nome, usate, f"indebolita non usata: {nome}")

    def test_undici_indebolite(self):
        """fase3/INDEBOLITE.md: I1–I11 (I11 marcatori_ripetizione aggiunta dopo il pezzo 1)."""
        self.assertEqual(len(riferimenti.INDEBOLITE_OPZIONI) + len(riferimenti.INDEBOLITE_COMPORTAMENTO), 11)

    def test_con_rete_toglie_solo_network(self):
        opzioni, extra = riferimenti.con_rete()
        self.assertNotIn("--network", opzioni)
        # una sola difesa: ripristinando --network none si riottengono esattamente le opzioni vere
        self.assertEqual(["--network", "none"] + opzioni, list(config.OPZIONI_CONTAINER))
        self.assertEqual(extra["aggiungi"][0], "--network")

    def test_montaggio_e_pid_aggiungono_una_sola_opzione(self):
        opzioni, extra = riferimenti.con_montaggio_host("/tmp/finta")
        self.assertEqual(opzioni, list(config.OPZIONI_CONTAINER))            # non toglie nulla
        self.assertEqual(extra["aggiungi"], ["-v", "/tmp/finta:/host:ro"])   # aggiunge una cosa sola
        opzioni2, extra2 = riferimenti.con_pid_host()
        self.assertEqual(opzioni2, list(config.OPZIONI_CONTAINER))
        self.assertEqual(extra2["aggiungi"], ["--pid=host"])

    def test_comportamento_una_difesa_e_bersaglio(self):
        for nome, d in riferimenti.INDEBOLITE_COMPORTAMENTO.items():
            self.assertIn("difesa_tolta", d, nome)
            self.assertIn("bersaglio", d, nome)


class TestAggiunteSintattiche(unittest.TestCase):
    def test_aggiunta_e_python_valido(self):
        """original _parser.py + aggiunta deve almeno fare il parse (nessuna esecuzione)."""
        carichi.verifica_tomli()
        originale = carichi.parser_originale()
        for a in attacchi.ATTACCHI:
            if a.get("aggiunta"):
                with self.subTest(a["id"]):
                    ast.parse(originale + a["aggiunta"])

    def test_attacchi_sul_worker_senza_aggiunta(self):
        """Gli attacchi che falsificano l'uscita del worker o la consegna non toccano il parser."""
        for a in attacchi.ATTACCHI:
            if a.get("uscita_worker"):
                self.assertIsNone(a.get("aggiunta"), a["id"])


class TestStoricoERiferimenti(unittest.TestCase):
    def test_storico_sui_corretti_dopo_il_pezzo1(self):
        per = attacchi.per_id()
        for i in ("ARGV", "TEMPO_SENZA_VERIFICA", "INPUT_MARKER", "FINAL_SPECIAL_CASE", "DISK_CACHE"):
            self.assertTrue(per[i].get("storico"), i)

    def test_riferimenti_riassegnati(self):
        per = attacchi.per_id()
        self.assertEqual(per["INPUT_MARKER"]["riferimento"], "marcatori_ripetizione")
        self.assertEqual(per["DISK_CACHE"]["riferimento"], "container_riusato")
        self.assertEqual(per["ARGV"]["riferimento"], "v4")
        self.assertEqual(per["ARGV"]["aggiunta_da_red_team"], "ARGV_CACHE.py")
        self.assertEqual(per["FINAL_SPECIAL_CASE"]["carico_v4"], "finale_sintetico")


if __name__ == "__main__":
    unittest.main()
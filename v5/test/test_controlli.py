"""Controlli preliminari (passo 4): un'esecuzione reale + casi negativi simulati.

    python -m unittest v5.test.test_controlli
"""
import os
import subprocess
import unittest
from unittest import mock

from v5 import ambiente, config


def finto_docker(sostituzioni):
    """ambiente.docker vero, salvo le chiamate il cui primo argomento è in `sostituzioni`."""
    vero = ambiente.docker

    def f(*args, **kw):
        if args and args[0] in sostituzioni:
            return subprocess.CompletedProcess(args, 0, sostituzioni[args[0]], "")
        return vero(*args, **kw)
    return f


class TestControlli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sessione = "test" + ambiente.secrets_hex()
        cls.oss = ambiente.Osservatore(cls.sessione)

    @classmethod
    def tearDownClass(cls):
        cls.oss.chiudi()

    def test_tutti_superati(self):
        esiti = ambiente.controlli(self.sessione, self.oss)
        self.assertTrue(esiti["memory_peak_non_scrivibile"])
        self.assertEqual(esiti["oom_visibile"], ["true", "137"])

    def test_chiave_presente(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "finta"}):
            with self.assertRaisesRegex(ambiente.ControlloFallito, "chiave"):
                ambiente.controlli(self.sessione, self.oss)

    def test_versione_diversa(self):
        altra = f"Docker Desktop 4.94.0 (999999)|{config.DOCKER_ENGINE}|{config.DOCKER_ENGINE}|{config.DOCKER_API}"
        with mock.patch.object(ambiente, "docker", finto_docker({"version": altra})):
            with self.assertRaisesRegex(ambiente.ControlloFallito, "docker_desktop"):
                ambiente.controlli(self.sessione, self.oss)

    def test_cgroup_v1(self):
        with mock.patch.object(ambiente, "docker", finto_docker({"info": f"{config.KERNEL_VM}|1|cgroupfs"})):
            with self.assertRaisesRegex(ambiente.ControlloFallito, "cgroup"):
                ambiente.controlli(self.sessione, self.oss)

    def test_container_estraneo(self):
        with mock.patch.object(ambiente, "contenitori_attivi", lambda: [("estraneo", "")]):
            with self.assertRaisesRegex(ambiente.ControlloFallito, "container_estranei"):
                ambiente.controlli(self.sessione, self.oss)

    def test_misure_di_tempo_rifiuta_estranei_senza_fermare(self):
        diario = []
        with mock.patch.object(ambiente, "contenitori_attivi", lambda: [("sqz_demo_x", ""), ("estraneo", "")]), \
                mock.patch.object(ambiente, "docker", side_effect=AssertionError("nessuna chiamata attesa")):
            with self.assertRaises(ambiente.ControlloFallito):
                with ambiente.MisureDiTempo(self.sessione, diario):
                    pass

    def test_misure_di_tempo_riavvia(self):
        """Ferma e riavvia sqz_demo_* (RIGA B); registra entrambi gli eventi."""
        diario = []
        with ambiente.MisureDiTempo(self.sessione, diario) as m:
            attivi = [n for n, _ in ambiente.contenitori_attivi()]
            self.assertFalse(any(n.startswith("sqz_demo_") for n in attivi))
        dopo = [n for n, _ in ambiente.contenitori_attivi()]
        for nome in m.fermati:
            self.assertIn(nome, dopo)
        self.assertEqual([d["evento"] for d in diario], ["fermati", "riavviati"])
        self.assertTrue(all(diario[1]["esiti"].values()))


if __name__ == "__main__":
    unittest.main()

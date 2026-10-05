"""Passo 1: timeout su ogni chiamata a Docker; nessun accesso a Docker fuori da ambiente.py;
tomli al commit fissato con 228 fixture valide.

    python -m unittest v5.test.test_ambiente
"""
import re
import time
import unittest
import uuid
from pathlib import Path

from v5 import ambiente, carichi, config


class TestDocker(unittest.TestCase):
    def test_timeout_e_rimozione(self):
        """Un `docker run` che non torna viene interrotto al timeout e il container si rimuove."""
        nome = f"v5_prova_timeout_{uuid.uuid4().hex[:8]}"
        t0 = time.monotonic()
        with self.assertRaises(ambiente.DockerTimeout):
            ambiente.docker("run", "--name", nome, "--network", "none", "alpine:3", "sleep", "600", timeout=5)
        self.assertLess(time.monotonic() - t0, 30)
        self.assertTrue(ambiente.rimuovi(nome))
        self.assertFalse(ambiente.esiste(nome))

    def test_chiamata_normale(self):
        p = ambiente.docker("version", "--format", "{{.Server.Version}}")
        self.assertEqual(p.returncode, 0)
        self.assertTrue(p.stdout.strip())


class TestUnicoPuntoDAccesso(unittest.TestCase):
    def test_nessun_docker_fuori_da_ambiente(self):
        """Solo ambiente.py può lanciare il comando docker."""
        sospetti = re.compile(r"""["']docker["']\s*,""")          # "docker" come primo argomento di un comando
        for f in (config.RADICE / "v5").rglob("*.py"):
            if f.name == "ambiente.py" or "test" in f.parts:
                continue
            self.assertIsNone(sospetti.search(f.read_text(encoding="utf-8")), f"docker lanciato in {f}")


class TestTomli(unittest.TestCase):
    def test_commit_e_fixture(self):
        carichi.prepara_tomli()
        self.assertEqual(len(carichi.fixture_valide()), config.FIXTURE_VALIDE_ATTESE)
        self.assertGreater(len(carichi.fixture_non_valide()), 0)


if __name__ == "__main__":
    unittest.main()

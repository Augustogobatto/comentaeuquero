"""Roda os testes de cenário em tests/scripts/ (cada um é um script que sai com
código 0 se passou). Ficam em subprocesso porque cada um monta o próprio DATA_DIR
e dubla o módulo instagram antes de importar o app."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SCRIPTS = sorted((RAIZ / "tests" / "scripts").glob("teste_*.py"))


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.stem)
def test_cenario(script):
    env = {**os.environ, "PYTHONPATH": str(RAIZ)}
    env.pop("DATA_DIR", None)
    r = subprocess.run([sys.executable, str(script)], cwd=RAIZ, env=env,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]

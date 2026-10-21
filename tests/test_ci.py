"""O passo do workflow que decide as tags da imagem, rodado de verdade no bash."""
import subprocess
from pathlib import Path

import yaml

WF = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "imagem.yml"
IMAGEM = "ghcr.io/augustogobatto/comentaeuquero"


def _tags(versao, tmp_path):
    wf = yaml.safe_load(WF.read_text())
    passos = wf["jobs"]["build"]["steps"]
    passo = next(p for p in passos if p.get("id") == "tags")
    build = next(p for p in passos if "build-push-action" in p.get("uses", ""))
    assert build["with"]["tags"] == "${{ steps.tags.outputs.tags }}"
    saida = tmp_path / "out"
    saida.write_text("")
    subprocess.run(["bash", "-e", "-c", passo["run"]], check=True,
                   env={"VERSAO": versao, "IMAGEM": IMAGEM, "GITHUB_OUTPUT": str(saida),
                        "PATH": "/usr/bin:/bin"})
    linhas = saida.read_text().splitlines()
    assert linhas[0] == "tags<<FIM" and linhas[-1] == "FIM"
    return linhas[1:-1]


def test_versao_final_move_estavel(tmp_path):
    assert _tags("1.7.1", tmp_path) == [f"{IMAGEM}:1.7.1", f"{IMAGEM}:estavel"]


def test_pre_release_nao_move_estavel(tmp_path):
    assert _tags("1.8.0-rc1", tmp_path) == [f"{IMAGEM}:1.8.0-rc1"]


# ---------- assinatura (cosign keyless) ----------

def _wf():
    return yaml.safe_load(WF.read_text())


def test_permissao_oidc_pra_assinar():
    assert _wf()["permissions"]["id-token"] == "write"


def test_assina_o_digest_do_build_depois_do_push():
    passos = _wf()["jobs"]["build"]["steps"]
    i_build = next(i for i, p in enumerate(passos) if p.get("id") == "build")
    i_inst = next(i for i, p in enumerate(passos) if "cosign-installer" in p.get("uses", ""))
    i_ass = next(i for i, p in enumerate(passos) if p.get("id") == "assinar")
    assert "build-push-action" in passos[i_build]["uses"]
    assert i_build < i_inst < i_ass
    assert passos[i_inst]["with"]["cosign-release"] == "v3.1.3"  # versão fixa, nunca latest
    assert passos[i_ass]["env"]["DIGEST"] == "${{ steps.build.outputs.digest }}"


def _roda_assinar(tmp_path, digest):
    """Roda o passo de verdade no bash com um cosign falso que só anota os argumentos."""
    passo = next(p for p in _wf()["jobs"]["build"]["steps"] if p.get("id") == "assinar")
    bin_ = tmp_path / "bin"; bin_.mkdir()
    anot = tmp_path / "args"
    (bin_ / "cosign").write_text(f'#!/bin/bash\necho "$@" > {anot}\n')
    (bin_ / "cosign").chmod(0o755)
    r = subprocess.run(["bash", "-e", "-c", passo["run"]], capture_output=True, text=True,
                       env={"DIGEST": digest, "IMAGEM": IMAGEM, "PATH": f"{bin_}:/usr/bin:/bin"})
    return r, (anot.read_text().strip() if anot.exists() else None)


def test_assinar_usa_imagem_arroba_digest(tmp_path):
    d = "sha256:" + "a" * 64
    r, args = _roda_assinar(tmp_path, d)
    assert r.returncode == 0, r.stdout + r.stderr
    assert args == f"sign --yes {IMAGEM}@{d}"


def test_assinar_sem_digest_falha_e_nao_chama_cosign(tmp_path):
    r, args = _roda_assinar(tmp_path, "")
    assert r.returncode != 0 and args is None


def test_so_roda_a_partir_de_tag():
    assert _wf()["jobs"]["build"]["if"] == "startsWith(github.ref, 'refs/tags/v')"

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = [RAIZ / "docker-compose.club.yml", RAIZ / "docs" / "AULA_INSTALACAO.md"]


def test_docs_apontam_instalador_certo():
    for arq in DOCS:
        if not arq.exists():  # a aula do Club não vai no repo público
            continue
        txt = arq.read_text()
        assert "https://ia.augustogobatto.com/members/instalar" in txt, arq
        assert "https://ia.augustogobatto.com/chao/install.sh" in txt, arq
        assert "/api/chao/instalar.sh" not in txt, arq


def test_versao():
    from app import main
    assert main.VERSAO == "1.8.0"

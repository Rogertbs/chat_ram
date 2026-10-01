import pytest

from chat_ram.preparacao.texto import normalizar_html, segmentar


def test_remove_tags_e_preserva_texto() -> None:
    assert normalizar_html("<p>Olá <b>mundo</b></p>") == "Olá mundo"


def test_decodifica_entidades_html() -> None:
    assert normalizar_html("Atl&acirc;ntico &amp; cia") == "Atlântico & cia"


def test_descarta_conteudo_de_script_e_style() -> None:
    assert normalizar_html("<style>.x{color:red}</style>Corpo<script>alert(1)</script>") == "Corpo"


def test_blocos_viram_quebras_de_linha() -> None:
    assert normalizar_html("<div>a</div><div>b</div>") == "a\nb"


def test_texto_vazio_ou_so_espacos_fica_vazio() -> None:
    assert normalizar_html("   \n\t ") == ""


def test_segmenta_texto_curto_em_um_unico_trecho() -> None:
    assert segmentar("texto curto", tamanho_max=2000, sobreposicao=200) == ["texto curto"]


def test_segmenta_texto_vazio_em_nenhum_trecho() -> None:
    assert segmentar("   ", tamanho_max=2000, sobreposicao=200) == []


def test_texto_no_limite_fica_em_um_trecho() -> None:
    texto = "a" * 2000

    assert segmentar(texto, tamanho_max=2000, sobreposicao=200) == [texto]


def test_texto_acima_do_limite_divide_com_sobreposicao() -> None:
    texto = "".join(chr(ord("a") + i % 26) for i in range(2500))

    trechos = segmentar(texto, tamanho_max=2000, sobreposicao=200)

    assert trechos == [texto[:2000], texto[1800:2500]]
    assert trechos[1].startswith(texto[1800:2000])


def test_sobreposicao_invalida_e_rejeitada() -> None:
    with pytest.raises(ValueError, match="sobreposicao"):
        segmentar("texto", tamanho_max=2000, sobreposicao=2000)

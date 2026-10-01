"""Normalização de HTML e segmentação em trechos."""

import re
from html import unescape
from html.parser import HTMLParser

_BLOCOS = {
    "p",
    "div",
    "br",
    "li",
    "tr",
    "td",
    "th",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "pre",
    "table",
}
_IGNORAR = {"script", "style"}


class _ExtratorTexto(HTMLParser):
    """Coleta o texto visível, trocando tags de bloco por quebras de linha."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._partes: list[str] = []
        self._ignorando = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _IGNORAR:
            self._ignorando += 1
        elif tag in _BLOCOS:
            self._partes.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _IGNORAR and self._ignorando:
            self._ignorando -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignorando:
            self._partes.append(data)

    def texto(self) -> str:
        return "".join(self._partes)


def normalizar_html(texto: str) -> str:
    """Converte HTML em texto simples, sem tags e com espaços normalizados."""
    if not texto:
        return ""
    parser = _ExtratorTexto()
    parser.feed(texto)
    parser.close()
    limpo = unescape(parser.texto())
    limpo = re.sub(r"[ \t\f\v]+", " ", limpo)
    limpo = re.sub(r" *\n *", "\n", limpo)
    limpo = re.sub(r"\n{3,}", "\n\n", limpo)
    return limpo.strip()


def normalizar_artigo(assunto: str, corpo: str) -> str:
    """Normaliza assunto e corpo e reúne o texto do artigo."""
    partes = [normalizar_html(assunto), normalizar_html(corpo)]
    return "\n\n".join(parte for parte in partes if parte)


def segmentar(texto: str, tamanho_max: int = 2000, sobreposicao: int = 200) -> list[str]:
    """Segmenta o texto em janelas com sobreposição; textos curtos viram um trecho."""
    if sobreposicao >= tamanho_max:
        raise ValueError("sobreposicao deve ser menor que tamanho_max")
    if not texto.strip():
        return []
    if len(texto) <= tamanho_max:
        return [texto]

    trechos: list[str] = []
    passo = tamanho_max - sobreposicao
    inicio = 0
    while inicio < len(texto):
        fim = min(inicio + tamanho_max, len(texto))
        trechos.append(texto[inicio:fim])
        if fim == len(texto):
            break
        inicio += passo
    return trechos

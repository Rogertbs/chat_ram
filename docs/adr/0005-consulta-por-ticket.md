# Consulta por ticket: exata, cronológica e com cobertura

Status: accepted

O ticket é identificado por **correspondência exata** no número público (`ticket.tn`, tratado como texto) — similaridade nunca escolhe qual ticket foi informado. A consulta distingue três desfechos: ticket não encontrado, fila ambígua e falha técnica. São incluídos **todos os artigos** do ticket (respostas e notas internas, visível ou não ao cliente), em **ordem cronológica**, marcando a visibilidade na evidência. O resumo apresenta problema, tentativas, solução documentada e situação; **status fechado, sozinho, não é prova de solução**.

Para tickets extensos (até 163 artigos), o resumo é feito em **blocos cronológicos** (map-reduce), conservando as fontes e sinalizando **cobertura parcial**; perguntas seguintes recuperam trechos específicos daquele ticket. Nunca apresentar leitura parcial como se cobrisse o atendimento inteiro.

## Considered Options
- Escolher o ticket por similaridade: rejeitado — não há critério seguro para desempatar qual número foi informado.
- Filtrar notas internas: rejeitado — a solução real costuma estar nelas.

## Consequences
- Um ticket fora do filtro de fila, quando pedido pelo número, é consultado e informa sua fila, preservando o filtro para as buscas seguintes.

# Chunking: um trecho por artigo, dividido só quando longo

Status: accepted

A Preparação gera **um trecho por artigo** (`article_data_mime`: `a_subject` + `a_body`, após normalizar HTML). Quando o texto passa de ~2.000 caracteres, ele é dividido em pedaços com ~200 caracteres de sobreposição, preservando a ordem. Cada trecho guarda a referência ao artigo de origem: número do ticket (`tn`), id do ticket, id do artigo, fila, data, visibilidade, posição no texto, versão de processamento e modelo de embeddings.

## Considered Options
- Um trecho por ticket: grosseiro demais para tickets de até 163 artigos.
- Janela fixa para todo artigo: desperdício, já que a mediana do corpo é 228 caracteres.

## Consequences
- ~93,5% dos artigos viram um único trecho; só ~6,5% (acima de 2.000 caracteres) são divididos.
- Os limites (2.000/200) são parâmetros ajustáveis; alterá-los exige reprocessar os trechos.

# MVP 0.1 — Consulta ao histórico do OTRS

Status: escopo confirmado pelo responsável pelo projeto após a entrevista de planejamento (Q19).

Este documento delimita a primeira entrega da [visão do projeto](ideacao.md). Para a versão 0.1, estas decisões prevalecem sobre as fases mais amplas da idealização. A [arquitetura inicial](arquitetura-0.1.md) é uma proposta técnica separada do escopo aprovado.

## 1. Objetivo e público

Ajudar o analista técnico de helpdesk a consultar o histórico do OTRS por conversa, encontrar casos semelhantes e entender tickets específicos, com evidências conferíveis.

O responsável pelo projeto fará a validação individual. O usuário final futuro será o analista técnico; a liberação para múltiplos analistas não faz parte da 0.1.

## 2. Ambiente e dados

- A API executará neste servidor de desenvolvimento.
- O LLM será acessado pelo proxy LiteLLM fornecido ao projeto. Hospedagem do modelo, GPU, vLLM e dimensionamento da inferência ficam fora do trabalho desta versão.
- Usar a cópia fixa já existente no PostgreSQL 18, descrita em [postgres18.md](postgres18.md).
- Consultar títulos, mensagens e notas internas, abrangendo todas as filas por padrão. A busca seleciona os trechos pertinentes à dúvida técnica.
- Não processar anexos nem sincronizar novos atendimentos nesta versão.
- Consultar o histórico sem alterar tickets ou executar ações no OTRS.

## 3. Comportamentos aprovados

### Busca pela descrição de um problema

O usuário descreve um problema e recebe casos semelhantes, tentativas registradas e soluções documentadas, com suas fontes.

Quando casos semelhantes apresentarem soluções diferentes, mostrar as alternativas e suas diferenças de contexto. Pedir informações antes de recomendar uma delas quando não houver contexto suficiente.

### Consulta por número de ticket

Apresentar primeiro um resumo com problema, tentativas, solução registrada e situação. Depois, permitir perguntas sobre aquele atendimento mantendo o contexto.

Um ticket fechado, sozinho, não comprova a existência de uma solução documentada.

### Filas

- Pesquisar em todas as filas inicialmente.
- Permitir restrição pela conversa, como “busque apenas na fila Infraestrutura”.
- Confirmar a seleção e manter o filtro até o usuário trocar de fila ou pedir todas novamente.
- Apresentar opções e pedir esclarecimento quando o nome informado for ambíguo.
- Consultar um ticket fora do filtro quando seu número for solicitado explicitamente; informar a fila do ticket e preservar o filtro das buscas seguintes.
- Tratar o filtro como preferência de pesquisa. Regras de autorização para outros usuários serão definidas antes de um piloto compartilhado.

### Evidências e sugestões externas

Cada conclusão sobre o histórico deve ter referência conferível com número e título do ticket, data e trecho da mensagem ou nota utilizada.

Quando não encontrar solução documentada:

1. Declarar explicitamente que não encontrou solução documentada no material consultado.
2. Apresentar evidências parciais, quando houver.
3. Sugerir automaticamente uma alternativa pelo conhecimento do modelo em seção identificada como **“Sugestão do modelo — não validada no histórico”**.
4. Pedir informações essenciais que estiverem faltando antes de sugerir procedimentos.

Uma sugestão externa nunca deve ser atribuída aos tickets. A ausência de resultado de uma busca não prova que uma solução inexista em todo o histórico.

### Conversas e experiência

- Manter contexto dentro da mesma conversa.
- Salvar conversas e permitir retomá-las após fechar a interface.
- Não compartilhar contexto entre conversas diferentes.
- Indicar processamento e exibir a resposta progressivamente.
- Priorizar qualidade e registrar tempo de resposta, sem limite obrigatório de latência inicial.

## 4. Fora da versão 0.1

- Relatórios gerenciais e agregações operacionais pelo chat.
- Criação, edição ou outras ações em tickets.
- Atualização automática da base OTRS.
- Processamento de anexos.
- Fine-tuning, LoRA e comparação de adaptadores.
- Provisionamento da infraestrutura do LLM.
- Liberação para múltiplos analistas com permissões individuais.

Essas exclusões delimitam a versão; não removem possibilidades da visão de longo prazo.

## 5. Validação e aceite

Preparar um conjunto fixo de 20 perguntas antes da avaliação final:

| Grupo | Quantidade | Verificação |
| --- | --- | --- |
| Problemas semelhantes | 8 | Pertinência dos casos, tentativas, soluções e referências |
| Tickets específicos | 8 | Identificação correta, resumo e perguntas posteriores |
| Sem solução documentada | 4 | Declaração de ausência e identificação da sugestão externa |

Aprovação: pelo menos **16 respostas úteis e corretas**, segundo a avaliação do responsável, com referências conferíveis e **nenhuma sugestão externa apresentada como solução comprovada pelos tickets**.

Registrar pergunta, resposta, referências esperadas/encontradas, avaliação, motivo das falhas e tempo de resposta. Incluir cenários com filtros de fila, soluções diferentes e continuidade da conversa. Verificar também retomada do histórico e isolamento entre conversas: a pontuação das respostas não substitui os demais requisitos funcionais.

## 6. Etapas de entrega

| Etapa | Entrega | Evidência antes de avançar |
| --- | --- | --- |
| 1. Conexão | Interface → API neste servidor → LiteLLM | Requisição real e resposta progressiva pela interface |
| 2. Ticket específico | Consulta exata, resumo e referências | Conferência contra o atendimento original |
| 3. Busca no histórico | Preparação dos textos, busca híbrida e filtro de filas | Casos conhecidos recuperados com fontes rastreáveis |
| 4. Conversa integrada | Dois fluxos, filtros persistentes, contexto e retomada | Estado correto ao retomar e isolamento entre chats |
| 5. Avaliação | Executar as 20 perguntas e corrigir falhas | Registro dos resultados e atendimento do aceite |

Explicar os conceitos e motivos das escolhas, documentar o aprendizado e apresentar evidência antes de iniciar a etapa seguinte, conforme a regra de desenvolvimento da idealização.

## 7. Próximo trabalho

Detalhar módulos, interfaces, preparação dos textos, embeddings e persistência da conversa na proposta de arquitetura. Essas escolhas técnicas não alteram o escopo funcional confirmado.

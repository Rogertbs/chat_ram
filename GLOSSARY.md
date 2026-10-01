# chat_ram

Assistente de chat que ajuda o analista de helpdesk a consultar o histórico do OTRS: encontrar casos semelhantes e entender tickets específicos, com evidências conferíveis.

## Language

**Ticket**:
Atendimento registrado no OTRS, identificado publicamente pelo número (`tn`) e internamente por um id próprio.
_Avoid_: chamado, atendimento, ocorrência

**Fila**:
Agrupamento de tickets no OTRS (ex.: Nivel 1, Zabbix) usado como filtro de pesquisa; um ticket pertence a uma única fila.
_Avoid_: departamento, grupo, categoria

**Artigo**:
Uma mensagem dentro de um ticket — resposta, e-mail ou nota interna.
_Avoid_: mensagem, comentário, interação

**Trecho**:
Segmento de texto de um artigo, com referência ao artigo de origem, usado como unidade de busca e citação.
_Avoid_: chunk, fragmento

**Caso semelhante**:
Ticket do histórico cujo conteúdo é relevante para a dúvida descrita na conversa.
_Avoid_: ticket parecido, resultado

**Consulta por ticket**:
Fluxo que recebe o número público de um ticket e apresenta o resumo do atendimento.
_Avoid_: consulta exata, busca por número

**Busca por casos semelhantes**:
Fluxo que recebe a descrição de um problema e devolve trechos de casos semelhantes com suas fontes.
_Avoid_: busca semântica, busca por similaridade

**Evidência**:
Referência conferível — número e título do ticket, data e trecho do artigo — que sustenta uma conclusão sobre o histórico.
_Avoid_: fonte, citação, referência

**Sugestão do modelo**:
Alternativa gerada pelo conhecimento próprio do modelo, não validada no histórico; apresentada sob o rótulo "Sugestão do modelo — não validada no histórico".
_Avoid_: sugestão externa, resposta

**Filtro de fila**:
Preferência de pesquisa que restringe as buscas a uma fila até o usuário trocá-la ou pedir todas novamente.
_Avoid_: restrição, escopo, seleção

**Conversa**:
Sessão de diálogo com um analista, isolada das demais, com estado próprio (fila selecionada, ticket em foco, esclarecimentos pendentes).
_Avoid_: chat, sessão, thread

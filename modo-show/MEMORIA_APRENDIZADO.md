# Memória de episódios e exemplos revisados

Implementação local dos itens de memória e aprendizagem controlada dos §§7 e 17. Guardar um episódio, corrigir uma regra e colecionar um exemplo não modificam pesos de modelo.

`memoria.Episodios` guarda atividades informadas explicitamente, em `hud-episodios.sqlite`, dentro de `OPENJARVIS_HOME`. Cada registro contém atividade, resultado relatado, origem, escopo, data, validade opcional, fontes, inferências e decisões em campos separados. Decisões só são aceitas com confirmação explícita. Resultado relatado não recebe o rótulo de medição automaticamente.

- `registrar(atividade, resultado, *, origem, escopo, fontes=[], inferencias=[], decisoes=[], decisoes_confirmadas=False, valido_ate=None)`.
- `listar(escopo=None, incluir_expirados=False)`; `corrigir(id, resultado, *, inferencias=None, decisoes=None, decisoes_confirmadas=False)`; `esquecer(id)`.
- `para_prompt(escopo, consulta="", limite=3)` recupera apenas episódios válidos do escopo solicitado, com rótulo de dados sem autoridade para executar ações.

Fontes usam `{tipo, id, versao?}`. Tipos aceitos: documento, episódio, correção, fato, resultado e usuário. As fontes não são cópias integrais dos documentos. IDs de fatos são expostos por `Memoria.inspecionar()`; documentos e correções conservam seus IDs existentes.

Reindexação de um documento modificado invalida episódios que dependiam dele. Correção de episódio invalida seus derivados. Exclusão de documento, fato, correção ou episódio remove episódios e exemplos derivados pertinentes, inclusive comparações que continham os exemplos removidos. Episódios inválidos continuam inspecionáveis até exclusão, mas não entram na recuperação normal. Um documento alterado ou removido deixa de fornecer texto ao contexto do modelo; permanece um aviso para reindexar. A consulta documental direta existente ainda identifica quando se refere a uma versão antiga.

`aprendizado.Aprendizado` usa `hud-aprendizado.sqlite`. A coleta começa desativada. `optar(True/False)` muda somente essa opção; nenhum histórico, áudio, câmera, pasta ou conversa é coletado automaticamente. `registrar(pedido, contexto, acao, resultado, correcao, *, verificado, aprovado, sucesso, destino="adaptacao", fontes=[])` exige três confirmações booleanas verdadeiras, além da opção de coleta ativa. Esses campos devem vir de conferência explícita, nunca ser presumidos porque o modelo respondeu. Credenciais comuns são removidas antes da persistência; dados sem conteúdo utilizável depois da remoção são recusados.

O destino `avaliacao` reserva casos separados. Mesmo pedido e contexto normalizados não podem ser duplicados nem movidos entre conjuntos; isso não detecta todas as paráfrases semanticamente equivalentes. `listar`, `esquecer`, `estado` e `avaliacoes` permitem inspeção e exclusão.

`comparar(referencia, candidato, resultados_referencia, resultados_candidato, *, politica_referencia, politica_candidato, reversao)` compara resultados submetidos para os mesmos IDs reservados. Cada resultado exige `correto` booleano, `verificado=True`, `evidencia` e contagens opcionais `repeticoes`/`alertas_inuteis`. Registra métricas, evidências e procedimento de reversão. Recusa políticas diferentes e não aplica candidato, treina modelo, aumenta permissões ou executa a reversão. O procedimento de reversão informado precisa corresponder à revisão conservada pelo operador; este módulo não cria backups de modelos ou arquivos automaticamente. Melhoria é restrita aos casos avaliados e só é marcada quando nenhuma métrica piora e alguma melhora.

Validação: `test_aprendizado_controlado.py` usa SQLite e arquivos reais temporários para opt-in, segredo removido, falha não promovida a exemplo, separação persistente de conjuntos, avaliação, validade, cascata de exclusão e falha de gravação de correções. Os modelos, contas e dispositivos do usuário não são usados nesses testes. O módulo não é um benchmark automático de modelos e não comprova melhoria sem resultados conferidos fornecidos à avaliação.

# Jarvis: auditoria funcional e matriz de entrega — 20/09/2026

## O que esta revisão comprova

O prompt mestre **não estava integralmente implementado nem validado no caminho usado pelo usuário**. Havia capacidades reais no runtime e testes locais, mas chat, comandos, cadastro biométrico e continuidade não tinham contratos equivalentes em todas as entradas. Um comando entendido numa fixture de voz não demonstrava que o chat chamava a mesma ferramenta. A existência de botão, endpoint, classe ou teste chamado “aceitação” também não demonstrava a experiência completa.

Esta revisão examina código da instalação `C:\Linguagem_C\projeto pessoal\Jarvis`, aplica correções e registra limites de evidência. A base Git consultada é `c60a7e16b0d4f5c5ef9fb5005633f6513e1239f5`, com alterações locais preexistentes e as alterações desta entrega. **Esse SHA sozinho não identifica o código final modificado.** `modo-show/` é ignorado pelo Git da instalação; uma cópia/entrega precisa incluir essa pasta explicitamente.

As matrizes [MATRIZ_FILME.md](../modo-show/MATRIZ_FILME.md) e [INVENTARIO.md](../modo-show/INVENTARIO.md) foram preservadas como histórico. Seus totais e marcações “IT” não são revalidados automaticamente. Em particular, F05, F17, F20 e F25 constavam como pendentes na matriz antiga, mas já havia `discordancia.py`, `ocorrencias.py`, `montagem.py` e `conhecimento.py` no código inspecionado nesta revisão.

### Origens e níveis de evidência

- **R1:** relatório histórico de 19/09/2026, conforme descrito no prompt e nas matrizes anteriores. Esta auditoria não afirma ter reexecutado suas demonstrações, nem ter lido visualmente todas as páginas do PDF.
- **R2:** inventário cinematográfico fornecido pelo usuário. Não houve nova inspeção dos cinco filmes ou identificação de timestamps. A cena específica de identificação fina de carros permanece não localizada.
- **R3:** requisitos do prompt atual e código/testes efetivamente inspecionados e alterados.
- **C:** contrato encontrado por leitura de código; sozinho não é evidência de funcionamento completo.
- **L:** execução local de código real com arquivos descartáveis, como JSON, SQLite e STL; demonstra somente o trecho executado.
- **S:** integração automatizada com fixtures, ferramentas falsas, respostas de modelo simuladas ou componentes de interface substituídos.
- **H:** exercício humano, câmera/microfone, conta ou serviço real; exige registro específico. Não é inferido de L/S.

Estados usados abaixo: **EP** existente preservado no código; **TP** implementado com testes parciais/locais/simulados; **AD** aguardando dado, conta ou autorização/calibração; **PD** parcela ainda pendente; **AJ** equivalente adaptado; **FE** fora do escopo operacional. **Nenhuma linha é promovida a “testado ponta a ponta” apenas pelo nome de um teste.** A última seção recebe os resultados finais da execução integrada.

Nas tabelas, nomes sem caminho referem-se a `modo-show/hud_runtime/`; testes sem caminho referem-se a `modo-show/testes/`. As dependências e os limites fazem parte do estado da funcionalidade.

## Diagnóstico e mudanças verificáveis

| Área | Antes encontrado | Correção desta entrega | Evidência e limite |
|---|---|---|---|
| Chat e runtime | Caminhos distintos podiam responder textualmente a uma capacidade do runtime, inclusive recusar cadastro existente | Ponte frontend/backend e entrada única no runtime; `entrada.py` usa sessão, pedido, recibo SQLite, bloqueio compartilhado e cancelamento | Testes de ponte/entrada e execução integrada ao final. Requer serviços em execução; trocar código em disco não prova processo atualizado |
| Ferramentas compostas | Texto e chamadas precisavam continuar separados; resultados não podiam ser substituídos por promessa | `execucao_modelo.py`: valida argumentos, orçamento de cinco chamadas, prazo, cancelamento, deduplicação e retorno dos resultados ao histórico/modelo | Ferramentas falsas validam o contrato; capacidade do modelo local real precisa de teste específico |
| Primeiro comando de pedido composto | Um match determinístico podia calcular só a primeira parte e ignorar a segunda | `fala_variantes.pedido_composto` desvia duas ações independentes inteiras ao modelo com ferramentas; listas, cadastro conjunto, textos literais, negações e vírgulas decimais são preservados | `test_pedidos_compostos.py`: HTTP do modelo simulado escolhe duas ferramentas; cálculos reais retornam 323 e 120 e ambos voltam ao modelo |
| Cadastro rosto e voz | Pedido conjunto podia cadastrar só rosto; voz iniciava sem microfone operacional; quadros congelados eram aceitos por testes antigos | Fluxo conjunto explícito, três amostras válidas, estado visível, cancelamento/revogação, rejeição de amostras incompatíveis e erro de persistência honesto | `test_cadastro_integrado.py`, `test_identidade.py`, `test_fala_variantes.py`; não houve cadastro humano real nesta evidência |
| Continuidade | Marcar etapa tardia podia reabrir tarefa cancelada; protocolos anunciavam conclusão mesmo após falha | `projetos.py` e `protocolos.py`: reserva persistida por etapa, resultado incerto após queda, pausa, retomada só do pendente, retorno tardio auditado sem reabrir tarefa | `test_continuidade_contratos.py`: escritas reais em diretório temporário; provedor externo não oferece garantia “exatamente uma vez” |
| Foco de projeto e peça | Abrir projeto B mantinha peça e prévia do projeto A; confirmar podia alterar A e registrar resultado em B | Foco de peça persistido por projeto; trocar/retomar sincroniza peça e versão, invalida prévia/seleção anterior e rejeita seleção tardia de outro projeto | `test_projeto_peca_foco.py`: JSON/STL reais, retomada após reinício e preservação dos bytes/versionamento; apresentação do modelo capturada em fixture |
| Aprovações | Parâmetros vazios funcionavam como curinga | Aprovação precisa corresponder à operação e aos parâmetros exatos; tarefa cancelada não reutiliza autorização | Contrato local; autorizações de contas externas continuam separadas |
| Documentos/RAG | Índice recebia apenas os primeiros 6.000 caracteres sem declarar cobertura; página estimada parecia exata; cache mantinha fonte esquecida | Limite explícito de indexação, cobertura parcial, offsets reais de PDF, versão/hash, invalidação, exclusão de fontes derivadas e dados documentais delimitados | `test_conhecimento.py`, `test_continuidade_contratos.py`; instrução no prompt não prova resistência universal a injeção |
| Pesquisa e fonte atual | Pesquisa escolhia um resumo sem investigar subperguntas; cache de notícia vencida podia receber horário novo após falha | Até três subconsultas, Wikipedia/DDG e manchetes existentes, comparação literal, deduplicação, lacunas e horário original; fonte da última resposta preservada por sessão | `test_pesquisa_integrada.py`, `test_consultas.py`; consulta pública real devolveu resumo de Circuito elétrico. Não demonstra leitura integral nem validação semântica de contradições |
| Peças | Alteração mudava parâmetros antes de escrever STL; erro de escrita era engolido; massa sempre assumia PLA | Validação de parâmetros finitos e relações, STL verificado por tamanho, alteração com lock/versão, prévia real sem consolidar, preservação da anterior e material efetivo na massa teórica | STL gerado de verdade em L; sem ensaio de fabricação/medição física |
| Experimentos | Resultado/falha de etapa não tinha condições de ensaio próprias | Caderno de experimentos dentro da tarefa com nome, resultado, falha, condições, unidades, fonte, data e versão da peça | `registrar_experimento`; relato não conclui projeto nem valida impressão |
| Memória | Correção removia o fato antes de gravar o novo | Gravação anterior à exclusão, ambiguidade explícita, guarda de segredo também no módulo e inspeção de proveniência | Mesmo armazenamento de fatos do OpenJarvis; não foi criada cópia paralela da memória pessoal |
| Percepção | Correspondência por texto podia confundir modelos; rastreamento ambíguo podia associar objetos distintos | Região real selecionada, atributos separados, candidatos ambíguos preservados, novas capturas, eventos temporais e estado antigo rotulado | Casos sintéticos/fixtures; não equivale a benchmark de reconhecimento de produtos |
| Mãos/S7 | Ausência de implementação real não podia ser escondida por seleção por mouse | `gestos.py` e integração autorizada de MediaPipe: calibração, câmera compartilhada, ativação explícita e mesma seleção da interface | Exige calibração e exercício real com a mão do usuário; gesto no ar não é toque físico |
| Avisos e foco | Aviso podia perder validade entre entrar na fila e sair pela voz | `anunciador.py` revalida modo, foco, silêncio, canal e voz muda ao entregar; frequência/prioridade/deduplicação configuráveis | `test_proatividade_contextual.py`; limpar também cancela aviso retirado da fila mas ainda aguardando a fala |
| Capacidade e reunião | Estado dos componentes e informações de reunião estavam distribuídos | `capacidades.py` publica estado/fonte/instante/efeitos/dependências; `reunioes.py` reúne agenda atual, tarefas e trechos autorizados versionados | `test_capacidades_reunioes.py`; modelo em disco não é inferência funcionando, relevância documental precisa conferência, envio continua falso |

O detalhe operacional de S7 está em [GESTOS_S7.md](../modo-show/GESTOS_S7.md). O carregamento do modelo MediaPipe e uma inferência com imagem vazia foram executados de verdade; a interação gestual foi testada com landmarks de fixture. O modelo `hand_landmarker.task` usado foi identificado pelo SHA-256 `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`. Isso comprova carregamento/contratos, não valida gestos da mão de Mateus. A sessão usa calibração em dois pontos, um cliente por vez, licença de atividade de 12 segundos, câmera compartilhada e nenhum frame persistido por padrão.

A tentativa de inicializar o Browser da ferramenta de trabalho encontrou a dependência `sandboxPolicy` ausente. Portanto, esta revisão não usa captura de tela ou verificação visual do Browser como evidência sem uma execução posterior explicitamente registrada. Testes HTTP e inspeção de HTML/CSS/JS não substituem esse teste visual.

Na tentativa final, o controle CUA reconheceu o navegador interno, mas a criação da aba expirou aguardando a conexão com a página. Nenhuma tela ou captura foi obtida nessa tentativa; a limitação visual permanece.

## Matriz F01–F44

| ID / origem | Equivalente e código responsável | Dependência / teste e evidência | Limite e estado atual |
|---|---|---|---|
| F01 R2/R3 | Conversa PT-BR, comandos determinísticos e ferramentas: `comandos.py`, `voz.py`, `entrada.py`, `execucao_modelo.py`; ponte do chat | Runtime, modelo local; `test_fala_variantes.py`, testes de entrada/ferramentas; C/S | Linguagem aberta depende do modelo e do catálogo de ferramentas; TP |
| F02 R2/R3 | Referências da lista, seleção e tarefa: `contexto.py`, `selecao.py`, `pecas.py`, `projetos.py` | Lista recente/seleção válida; `test_consultas.py`, `test_selecao.py`, T02/T03/T23; L/S | Ambiguidade pede esclarecimento; referência não garante leitura longa retomável; TP |
| F03 R1/R2/R3 | Tarefa, projeto, foco de peça, versão e resultados persistidos em `projetos.py`/`pecas.py` | Disco; `test_projetos.py`, `test_projeto_peca_foco.py`, `test_continuidade_contratos.py`; L/S | Reinício preserva dados e pausa trabalho; retomar seleciona a peça do mesmo projeto; ação interrompida exige conferência; TP |
| F04 R2/R3 | Perguntas para dimensão, alvo, cadastro e memória ambígua | `comandos.py`, `memoria.py`; T03, testes de cadastro/peças; L/S | Tratamento por famílias de intenção, sem garantia universal de desambiguação; TP |
| F05 R2/R3 | Conflitos numéricos e alternativa: `discordancia.py` | Dimensões/agenda/dados válidos; `test_discordancia.py`; L/S | Limites configurados não são medição da impressora real; antes “PD” na matriz, código já existente; TP |
| F06 R1/R2/R3 | Tratamento/estilo/pronúncia: `preferencias.py`, `voz.py`, `audio.py` | TTS escolhido; `test_alexa_percepcao.py`, `test_voz_catalogo.py`; C/S | Estilo preservado; naturalidade e humor não foram medidos por teste humano; EP/TP |
| F07 R1/R2/R3 | Briefing: `secretario.py`, agenda, tarefas, clima e notícias | Fontes conectadas; `test_secretario.py`, T22; S | Agenda ausente deve ser declarada; briefing não cria compromissos; TP/AD |
| F08 R1/R2/R3 | Relógio/fuso/cidade/clima: `utilidades.py`, `clima.py`, `cotacoes.py` | Sistema/internet; `test_consultas.py`; L/S | Dados dinâmicos exigem consulta atual; testes históricos não atualizam clima/câmbio; EP/TP |
| F09 R1/R2/R3 | RSS/pesquisa multietapas limitada, fonte, horário e deduplicação: `noticias.py`, `pesquisa.py`, `comandos.py` | Internet/feed; `test_pesquisa_integrada.py`, `test_novidades.py`, `test_consultas.py`; S e consulta pública real | Até três subconsultas; manchete/resumo não representa leitura integral de artigo; comparação literal não verifica contradição semântica; TP |
| F10 R1/R2/R3 | Fatos confirmados, tarefas, agenda e rascunhos: `memoria.py`, `tarefas.py`, `agenda.py`, `rascunhos.py` | Arquivos/contas autorizadas; `test_memoria.py`, `test_rascunhos.py`; L/S | Não acessa mensagens/contas não conectadas; TP/AD |
| F11 R1/R2/R3 | Estado e cartões compartilhados: `estado.py`, `hud/jarvis.js`, `hud/painel.js` | SSE/cliente conectado; `test_widgets.py`, testes de ponte; S | Presença de cartão não prova sincronismo com fala real; EP/TP |
| F12 R1/R2/R3 | Pendências, resumos, rascunhos e reunião: `reunioes.py`, `secretario.py`, `documentos.py`, `agenda_analise.py`, `rascunhos.py` | Documento/agenda autorizados; `test_capacidades_reunioes.py`, `test_secretario.py`, `test_arquivos.py`; L/S | Pergunta se reunião ambígua; exclui documento alterado, trechos têm relevância a confirmar; sem envio; TP |
| F13 R1/R2/R3 | Detector e contagem por observação: `deteccao.py`, `percepcao.py` | Câmera e modelo detector; `test_percepcao.py`, `test_visao_tempo_real.py`; S | Categorias gerais não reconhecem marca/modelo; TP/AD |
| F14 R2/R3 | Trilha temporária, oclusão e recusa de associação ambígua: `rastreador.py` | Quadros atuais; `test_rastreador.py`, T13; S | Identidade temporária não autentica unidade física; TP |
| F15 R1/R2/R3 | Pergunta visual com captura/ROI atuais: `visao.py`, `voz.py`, `comandos.py` | Câmera autorizada/modelo de visão; `test_conversa_visao.py`, T15; S | Sem câmera/imagem atual não há descrição; respostas do modelo ainda exigem avaliação humana; TP/AD |
| F16 R2/R3 | Cena consultável por registros observados: `rastreador.py`, `inventario.py`, `ocorrencias.py` | Observações reais disponíveis; T14 e testes desses módulos; S | Não gera reconstrução métrica 3D a partir de uma imagem; AJ/TP |
| F17 R2/R3 | Cruzamento de eventos por hora/local/atributo: `ocorrencias.py` | Eventos efetivamente retidos; `test_ocorrencias.py`; S | Lacunas de observação permanecem lacunas; não é histórico de vídeo contínuo; antes “PD”, código existente; TP |
| F18 R2/R3 | Evidência por atributo e executor com autorização: `identificacao.py`, `inventario.py`, `execucao_modelo.py` | Fonte/escopo válidos; T08–T12/T21/T31; S | Observar não autoriza agir; autenticação nunca deriva só de rosto/voz; TP |
| F19 R1/R2/R3 | Peças, parâmetros, versões e foco por projeto: `pecas.py`, `projetos.py`, `comandos.py` | Fonte paramétrica; `test_pecas.py`, `test_projetos.py`, `test_projeto_peca_foco.py`; L/S | Projeto sem peça não herda STL anterior; STL externo não recupera parâmetros originais automaticamente; TP |
| F20 R2/R3 | Componentes/vista explodida de montagem conhecida: `montagem.py`, `pecas.py` | Montagem caixa com tampa; `test_montagem.py`, `test_projeto_peca_foco.py`; L/S | Não inventa partes internas de objeto fotografado. Edição isolada de componente pede esclarecimento: largura/comprimento são compartilhados pelo conjunto, espessura da tampa é parâmetro explícito; antes “PD”, código existente; AJ/TP |
| F21 R2/R3 | Prévia STL, confirmação, alteração com versão esperada e reversão: `pecas.py`, `comandos.py` | Peça ativa e parâmetro explícito; `test_continuidade_contratos.py`, T25; L/S | Validação geométrica limitada; não certifica fabricação; TP |
| F22 R2/R3 | Experimentos persistidos com condição/unidade/falha/fonte: `projetos.py` | Tarefa ativa e resultado informado; teste de experimento, T27; L/S | Relato de usuário é rotulado; arquivo salvo não é ensaio; TP |
| F23 R1/R2/R3 | Contas analíticas de elétrica, consumo, volume etc.: `engenharia.py`, `cad.py` | Valores/unidades adequados; `test_engenharia.py`; L | Não é simulador FEM/CFD; AJ/TP |
| F24 R1/R2/R3 | Comparação de propriedades típicas e massa teórica: `engenharia.py`, `pecas.py` | Material identificado; T26, teste de massa/material; L | Valores de referência do código, não lote ensaiado nem ficha técnica consultada agora; TP |
| F25 R2/R3 | RAG local versionado, memória compartilhada e fonte da pesquisa atual: `conhecimento.py`, `documentos.py`, `memoria.py`, `pesquisa.py`, `entrada.py` | Documento fornecido/indexado ou fonte pública; `test_conhecimento.py`, `test_pesquisa_integrada.py`, T19/T20; L/S | Busca lexical, cobertura explícita; fonte por sessão não cruza respostas; decisões só confirmadas pelo usuário; antes “PD”, código existente; TP/AD |
| F26 R2/R3 | Distinção malha calculada/massa estimada/ensaio ausente e limites de pesquisa: `pecas.py`, `engenharia.py`, `pesquisa.py` | Fonte de cada resultado; T26/T27, `test_pesquisa_integrada.py`; L/S | Limites nem sempre estruturados em todos os cálculos legados; comparação textual não atesta verdade; TP |
| F27 R1/R2/R3 | Telemetria Windows e disponibilidade: `sistema.py`, `telemetria.py` | Sensores que o sistema expõe; `test_runtime.py`, T28; S | Não inventa sensor de armadura; estimativa não é leitura elétrica; AJ/TP |
| F28 R1/R2/R3 | Saúde dos serviços e erros: `boot.py`, `telemetria.py`, `modelos_ia.py` | Processos/rede locais; `test_modelo_reserva.py`, `test_runtime.py`; S | Status precisa ser atual; módulos desligados não executam monitoramento; TP |
| F29 R1/R2/R3 | Limiares de telemetria: `monitores.py`, `notificacoes.py` | Fonte disponível/modo escolhido; `test_monitores.py`; S | Somente medições existentes; EP/TP |
| F30 R2/R3 | Diagnóstico de serviço e dependência de tarefas: `capacidades.py`, `discordancia.py`, `projetos.py`, telemetria | Recursos/dependências declarados; `test_capacidades_reunioes.py`, testes de discordância e etapa; L/S | Não há inventário universal de dependências de toda ferramenta externa; TP |
| F31 R2/R3 | Consulta de mapas/localização somente com fonte autorizada | Fonte de localização não demonstrada; C | Sem GPS ou posição espacial inventados; AD |
| F32 R2/R3 | Estado indisponível para fisiologia sem sensor apropriado | Ausência de fonte; revisão de escopo | Diagnóstico médico/químico pela webcam não solicitado como equivalente; FE |
| F33 R1/R2/R3 | Preferências e identidade lógica comuns: `preferencias.py`, `estado.py`, ponte | Clientes autorizados; testes de runtime/ponte; S | Sessão de conversa continua isolada de outra sessão; TP |
| F34 R1/R2/R3 | Telegram pareado e rascunhos/abertura manual: `telegram.py`, `rascunhos.py` | Conta/conector autorizado; `test_casa_comunicacao.py`, `test_rascunhos.py`; S | Sem autorização nova para enviar e-mail, mensagem ou convite; AD/TP |
| F35 R1/R2/R3 | Prioridade, foco, silêncio/canal e deduplicação, revalidados na entrega: `anunciador.py`, `notificacoes.py`, `preferencias.py` | Preferências/atividade; `test_proatividade_contextual.py`, `test_lembretes.py`, `test_monitores.py`, T30; S | Avaliação de relevância limitada às regras implementadas; TP |
| F36 R1/R2/R3 | Estado único/SSE e ponte chat-runtime: `estado.py`, `entrada.py`, servidor e frontend | Runtime único e clientes conectados; T29/testes de ponte; S | Teste com três janelas reais precisa ser registrado separadamente; TP |
| F37 R1/R2/R3 | Clientes autenticados, capacidades do runtime e sessões identificadas | Token/pareamento; `ponte.py`, servidor, `entrada.py`; T31; S | Conta no ChatGPT não autentica a instalação; não foi criado aplicativo móvel; TP/AD |
| F38 R1/R2/R3 | Apresentação existente com ID e confirmação do cliente: `apresentacao.py`, `holograma.py`, HUD/seleção | Mesa conectada; HTTP do artefato e confirmação idempotente testados com arquivo temporário e cliente simulado; L/S | Confirmação enviada após parser/dois frames no cliente; Browser indisponível impede comprovar renderização humana nesta revisão; TP |
| F39 R1/R2/R3 | Workers existentes + tarefas/protocolos com estado durável: `protocolos.py`, `projetos.py`, `secretario.py` | Runtime ligado; T05/T06 e testes de continuidade; L/S | Não promete execução enquanto PC/runtime desligados; retomada explícita após queda; TP |
| F40 R1/R2/R3 | Protocolos nomeados com parâmetros `{nome}`, preenchimento explícito, limite e revalidação: `protocolos.py`, `comandos.py` | Comandos permitidos; `test_protocolos_parametrizados.py`, `test_automacao.py`, contratos de continuidade; L/S | Parâmetro não pode alterar o tipo de ação nem inserir expressões; protocolo recursivo bloqueado; etapa concretizada fica persistida para retomar; TP |
| F41 R2/R3 | Execução sequencial, dependências de tarefas e locks: `projetos.py`, `pecas.py`, `execucao_modelo.py` | Dependências declaradas; testes de reserva/versão; L/S | Não existe DAG geral distribuído ou paralelismo irrestrito; AJ/TP |
| F42 R1/R2/R3 | Resultado, bloqueio e conclusão via estado/voz única: `anunciador.py`, `entrada.py`, `comandos.py` | Player/runtime em execução; T04/T30/testes de voz; S | Conclusão verificada é diferente de execução sem verificação; TP |
| F43 R1/R2/R3 | Fallback limitado e retomada sem repetir: `modelos_ia.py`, `projetos.py`, `protocolos.py` | Ferramenta disponível/efeito conhecido; T05–T07; L/S | Efeito externo incerto exige conferência, sem retry cego; TP |
| F44 R1/R2/R3 | Instância única, supervisão e recibos persistidos: runtime, `boot.py`, `entrada.py`, `projetos.py` | Processos locais; `test_instancia_unica.py`, T06; L/S | Cancelar vence; não há resistência a desligamento nem recuperação autônoma irrestrita; TP |

## Requisitos adicionais por seção do prompt

| Requisito / origem | Contrato/código e testes | Estado, dependência e limite |
|---|---|---|
| §5 Ciclo compreender→agir→conferir — R3 | `entrada.py`, `execucao_modelo.py`, `comandos.py`; T01/T04/T07/T29 | TP. Ferramenta retorna evidência real; resumo do modelo não prova ação. Cinco chamadas e prazo/cancelamento preservados |
| §5 Sessão/pedido/ação, duplicação e conflito — R3 | Recibo SQLite, id de ação por etapa, versão esperada da peça; testes de entrada/continuidade | L/S. Queda entre efeito externo e recibo é incerta; nenhuma promessa exatamente-uma-vez |
| §6 Dez estados, etapas, dependências e retomada — R3 | `projetos.py`, `protocolos.py`; T02/T05/T06 | TP. Etapa em curso no reinício não volta automaticamente a planejada; necessidade de conferência permanece visível |
| §7 Fato, projeto, episódio, observação, documento, procedimento — R3 | Memória de fatos comum, projetos/experimentos, inventário/trilhas, RAG e protocolos | TP. Separação por módulos/registro, sem armazenamento paralelo integral; não há motor universal de validade de todo fato legado |
| §7 Fonte/inferência/decisão e apagar derivados — R3 | `memoria.inspecionar`, `conhecimento`, evidência por atributo; T19/T20/T21 | TP. Cache de referência apagada é removido; instrução de documento permanece dado, não permissão |
| §7 Pesquisa complexa — R3 | `pesquisa.investigar`: até três subconsultas, Wikipedia/DDG/manchetes, deduplicação, fontes, comparação literal e lacunas; `test_pesquisa_integrada.py` | TP. Consulta pública real isolada retornou um resumo; investigação multietapas testada com fixtures. Não faz leitura integral de páginas nem decide contradição semântica; conteúdo distinto não é chamado de contradição |
| §8 Seleção→qualidade→pistas→candidatos→esclarecimento — R3 | `identificacao.py`, `visao.py`, `inventario.py`; T08–T11 | TP/AD. Inventário/manual corretos dependem de cadastro; catálogo universal de fabricante/ano/versão não existe |
| §9 Modelo de produto versus unidade e retenção visual — R3 | `inventario.py`, `rastreador.py`; T12–T14 | TP. Cadastro/associação exigem evidência/consentimento; sem gravação contínua de fotos por padrão |
| §10 Cena/medida/tela/vídeo — R3 | `regua.py`, `tela.py`, `midia_arquivos.py`, `ocorrencias.py`; T14–T17 | TP/AD. Plano calibrado não mede altura 3D; amostragem de vídeo informa intervalos, sem alegar vídeo inteiro |
| §10 Mãos/S7 — R3 | `gestos.py`, seleção compartilhada e HUD; T18 | TP/AD. MediaPipe/modelo instalados somente após autorização nesta sessão; gesto exige ativação/calibração e não é toque físico |
| §10 Rosto/voz cadastrados — R1/R3 | `identidade.py`, `comandos.py`, `voz.py`; `test_cadastro_integrado.py` | TP/AD. Três amostras, cancelamento/expiração, desconhecido em empate; verificação com Mateus presente ainda necessária |
| §11 Briefing, agenda de leitura e rascunhos — R1/R3 | `secretario.py`, agenda, notícias, rascunhos; T22–T24 | TP/AD. Nenhuma permissão de envio nova; conta desconectada não é agenda livre |
| §12 Projeto paramétrico, prévia, versão e ensaio — R3 | `pecas.py`, `montagem.py`, `projetos.py`, `engenharia.py`; T25–T27 | L/S. Preserva STL e parâmetros; sem CAD completo externo/solver grande instalado automaticamente |
| §13 Telemetria/capacidade honesta — R3 | `telemetria.py`, `sistema.py`, `discordancia.py`; T28/T33 | TP. Medido/estimado/indisponível não devem ser reduzidos a um status fictício “tudo funcionando” |
| §14 Continuidade entre interfaces autorizadas — R3 | Servidor/token, ponte, `entrada.py`, estado e sessões; T29/T31 | TP. Contexto sensível depende de autenticação; não inicia portabilidade móvel ou dispositivos novos |
| §15 Protocolos/proatividade/recuperação — R3 | `protocolos.py`, `projetos.py`, `anunciador.py`; `test_protocolos_parametrizados.py`, T05–T07/T30 | TP. Parâmetros explícitos e ação revalidada, etapas persistidas, dependências sequenciais, pausa/cancelamento/conferência; supervisão distribuída continua fora do equivalente local implementado |
| §16 HUD contextual/seleção/interrupção — R3 | `estado.py`, HUD/mesa, frontend/ponte; T03/T18/T23/T29 | TP. Mostra resultados reais/pendências; teste visual/humano final é diferente de compilação |
| §17 Identidade/aprendizado controlado — R3 | Preferências/correções, políticas existentes e ausência de treino automático acionado; T32 | EP/TP. Nenhum treino/peso/política é modificado sem autorização; avaliação geral de aprendizado futuro não foi criada |
| §18 Permissões, fontes não confiáveis e testes isolados — R3 | Executor determinístico, token, autorizações exatas, `testes/conftest.py`; T21/T24/T31 | L/S. Testes usam `OPENJARVIS_HOME` temporário e arquivos descartáveis; sem mensagens externas de teste |
| §19 Matriz/evidência — R3 | Este documento, matrizes históricas preservadas, suites citadas | TP. Cobertura nominal de ID não significa todos os critérios aprovados em H |
| §20 Demonstração completa — R3 | Objeto autorizado→manual→projeto→cálculo→prévia→interrupção→conferência→retomada | AD. Depende do objeto/manual real, captura humana e teste integrado; não foi substituída por roteiro de sucesso |
| Ficção extraordinária — R2/R3 | Diagnóstico e coordenação de software como equivalentes | AJ/FE. Sem combate, armamento, protocolo destrutivo, invasão, autorreplicação, resistência a desligamento, consciência ou criação do Visão |

## Cenários T01–T34: o que conta como teste

`test_aceitacao.py` mantém cenários com estes nomes, mas sua execução é uma combinação de L/S. Os testes adicionais abaixo aprofundam contratos e falhas que a matriz antiga não cobria. Quando uma linha cita apenas código/teste, não afirma uma demonstração humana realizada.

| ID / origem R3 | Requisitos | Teste/evidência responsável | Resultado comprovável e parcela humana/externa |
|---|---|---|---|
| T01 | F01/F18/F41, §5 | `test_execucao_integrada.py`, `test_pedidos_compostos.py`, ponte e aceitação | Pedido composto→Qwen3.5:4b real→duas chamadas→calculadora 323/120→revisão→recibo, registrado ao final; fixtures cobrem falhas e cancelamento |
| T02 | F02/F03/F19 | `test_projetos.py`, `test_projeto_peca_foco.py`, aceitação | Recuperação de tarefa e peça/versão do mesmo projeto em L; recuperar por descrição ambígua requer esclarecimento |
| T03 | F02/F04/F21 | `test_pecas.py`, `test_selecao.py`, `test_projeto_peca_foco.py`, aceitação | Não altera sem dimensão; componente selecionado não é confundido com montagem inteira por substring; seleção por gesto real depende de T18 |
| T04 | F42/F44 | `test_conversa_visao.py`, testes de entrada, cancelamento tardio em continuidade | Interromper fala não declara reversão da ação; reprodução real usa player único |
| T05 | F39/F43 | `test_pausa_e_reinicio_preservam_escrita_real` | Dois arquivos reais temporários, etapa concluída não repetida; fixture de executor identificada |
| T06 | F03/F39/F44 | Reinício em `test_projetos.py`, `test_resultado_incerto_nao_repete_apos_reinicio` | Estado em disco preservado; nova instância não executa resultado incerto |
| T07 | F28/F43 | `test_excecao_de_ferramenta_para_sem_retry_cego`, `test_modelo_reserva.py` | Falha simulada para com motivo, sem sucesso fictício nem repetição cega |
| T08 | F15/F18, §8 | `test_identificacao.py`, aceitação | Região inadequada reduz afirmação; sem benchmark humano generalizado |
| T09 | F18/F25, §8 | Identificação por atributo/modelo/manual | Evidência legível e referência correta em fixtures; modelo visual real precisa ser conferido |
| T10 | F04/F18, §8 | Casos de candidatos semelhantes | Mantém múltiplos candidatos; não equivale a identificar qualquer variante de carro |
| T11 | F13/F18, §8 | Testes de separação pontuação/atributo | Confiança de detector não vira probabilidade de fabricante/ano |
| T12 | F18, §9 | `test_inventario.py` | Categoria/modelo/unidade separados; unidade pessoal não inferida só por aparência |
| T13 | F14, §9 | `test_rastreador.py` | Oclusão/ambiguidade testadas em trajetórias sintéticas; câmera real ainda precisa avaliação |
| T14 | F16/F17 | Inventário/rastreador/ocorrências | Hora antiga é última observação; período sem captura não é reconstruído |
| T15 | F15, §10 | `test_conversa_visao.py`, testes de percepção | Sem frame atual não descreve; caminho de câmera autorizado precisa H |
| T16 | F23, §10 | `test_regua.py`, aceitação | Sem calibração não há medida exata; calibração física do plano depende do usuário |
| T17 | F15/F16, §10 | `test_extras_finais.py`, `midia_arquivos.py`, aceitação | Intervalos/quadros amostrados informados; não se declara assistir integralmente por amostras |
| T18 | F02/F36, §10 | `test_gestos.py`, `test_selecao.py`, aceitação | Mesmo seletor de mouse/gesto; calibração e mão humana ainda AD |
| T19 | F10/F25, §7 | `test_memoria.py`, exclusão/correção em continuidade | Origem/data/trust e exclusão; inferência visual não é fato pessoal confirmado |
| T20 | F25, §7 | `test_conhecimento.py`, alteração mesmo tamanho/hash em continuidade | Versão obsoleta não responde como atual; arquivo removido/alterado gera aviso |
| T21 | F18, §§5/7/18 | Testes de executor/documentos e memória não confiável | Documento é dado, não autorização; não afirma garantia universal contra prompt injection |
| T22 | F07/F09 | `test_secretario.py`, `test_extras_finais.py`, `test_pesquisa_integrada.py`, aceitação | Agenda desconectada declarada; fonte/horário original das notícias preservados, inclusive cache vencido após falha |
| T23 | F02/F11 | `test_consultas.py`, aceitação T23/T23b | Referência ordinal usa lista recente; lista expirada não vira item inventado |
| T24 | F12/F34 | `test_rascunhos.py`, aceitação | Rascunho não envia; testes não disparam mensagens reais |
| T25 | F19/F21 | `test_pecas.py`, `test_projeto_peca_foco.py`, prévia/STL/falha/conflito em continuidade | Um parâmetro muda, anterior persiste; trocar projeto invalida prévia; versão obsoleta ou seleção de outro projeto não sobrescreve |
| T26 | F23/F24/F26 | `test_engenharia.py`, teste de massa/material em continuidade | Volume calculado na malha e massa teórica distintos de medição física |
| T27 | F22/F26 | Experimento em continuidade e aceitação | Registra falha/condição/unidade/versão sem concluir projeto; impressão real não testada |
| T28 | F27/F29 | `test_runtime.py`, aceitação | Contratos de medido/indisponível/estimado; não prova precisão de todo sensor Windows |
| T29 | F33/F36/F39 | `test_instancia_unica.py`, testes de entrada/ponte/widgets | Uma autoridade/lock/recibo; três interfaces reais requerem demonstração específica |
| T30 | F35/F42 | `test_monitores.py`, `test_lembretes.py`, testes de anunciador | Deduplicação/modos/silêncio em S; relevância subjetiva depende do uso |
| T31 | F18/F37 | Testes de autenticação HTTP/ponte/canais | POST sem token e GET privado sem sessão retornam 403; cookie HttpOnly/Strict; câmera e SSE sem token na URL; pairing externo depende da conta |
| T32 | §17 | Aceitação e inspeção dos caminhos de correção/preferência | Sem treino automático por proposta; não valida pipeline de fine-tuning não solicitado |
| T33 | F18/F31/F32 | `test_casa_comunicacao.py`, diagnósticos e aceitação | Capacidade ausente identificada; sem integração/fonte não há simulação oculta |
| T34 | Preservação geral | Suite do modo-show + suites direcionadas OpenJarvis/frontend | Resultado final e falhas precisam constar abaixo; nenhum total antigo substitui esta execução |

## Operação e limites que continuam importantes

- “Memorize meu rosto e minha voz” precisa de Mateus presente, câmera autorizada, microfone operacional e amostras diversas. O código não deve afirmar reconhecer Mateus porque um teste vetorial passou. Desconhecidos e empates continuam desconhecidos.
- “Continue de ontem” recupera tarefa persistida. Em protocolo interrompido durante uma escrita, confira o efeito real antes de confirmar se a etapa foi executada; retomar não repete silenciosamente o passo.
- Edição de peça apresenta prévia; a confirmação vale para a peça e versão apresentadas. Alteração concorrente invalida a prévia. Não é declaração de peça pronta para impressão.
  Exemplo operacional: “aumente a largura em 2 milímetros” gera o STL de prévia; “confirme a alteração da peça” consolida a versão após a conferência. “Qual dimensão?” continua sendo o resultado correto de um pedido ambíguo como “aumente isso”.
- “Qual é a fonte?” deve usar a referência efetivamente recuperada. Arquivo apagado, modificado ou parcialmente indexado precisa ser indicado. Página antiga calculada por proporção fica rotulada aproximada; novos documentos só recebem página quando há offsets reais.
- Conta Google permanece leitura; mensagens permanecem rascunhos. Telegram/contas não conectados não se tornam ativos pela instalação de código.
- Gestos começam inativos e precisam de ativação/calibração. Nenhum movimento no ar é chamado de toque físico na superfície.
- A demonstração do §20 exige um objeto e manual reais escolhidos pelo usuário. Fixtures/STLs de teste comprovam componentes, não substituem essa demonstração.

## Registro final de execução desta entrega

Ambiente dos testes locais: Windows, PowerShell, Python 3.10.11 da `.venv`; dados do HUD isolados por `modo-show/testes/conftest.py`. Ensaios de arquivo/índice/geometria não precisam de Ollama. Ensaios com modelo, câmera, microfone e interface devem indicar o componente real usado.

Revisão adicional: `test_execucao_integrada.py` cobre chamadas de ferramenta malformadas, preservação de resultado anterior, prazo entre passos, comandos que não podem fabricar confirmação/consentimento, falhas SQLite antes/depois do efeito com liberação de lock em outra thread, cancelamento concorrente e propagação de sessão/pedido/ação ao protocolo. `tests/server/test_runtime_bridge.py` verifica que mensagens `system`/`assistant` do cliente não se tornam instruções privilegiadas do runtime: a ponte encaminha somente o pedido literal mais recente do usuário, com contexto do próprio runtime.

### Versão realmente carregada

Em 20/09/2026, 04:34 UTC, o runtime ativo em `127.0.0.1:8765` informou **`68dc34703323caa2`**. O hash calculado do runtime, módulos Python e assets HUD/clássicos no disco confere com o hash do processo; boot concluído. PID do runtime: **28776**. Backend local em `127.0.0.1:8000`, PID **32124**, saúde HTTP 200. Evidência: [instalacao-validada.json](../artifacts/auditoria-2026-09-20/instalacao-validada.json).

Modelo principal preservado: **gemma4:e4b**. O ensaio integrado usou efetivamente a reserva local **qwen3.5:4b**, porque o runtime mediu RAM livre insuficiente para carregar o principal. O modelo usado fica no recibo e no metadado do chat, inclusive em replay; o modelo solicitado fica separado. Comando determinístico sem modelo é rotulado `jarvis-runtime`. Voz preservada: Kokoro `pm_alex`; transcrição Whisper `small`. Câmera e gestos estavam desligados ao concluir.

A primeira tentativa de reinício herdou `OPENJARVIS_HOME` apontando para um diretório temporário. O servidor original continuou ocupando a porta 8000 e o runtime temporário não era a instalação pessoal. Isso foi detectado e corrigido: ambos os processos foram iniciados com o caminho explícito `C:\Users\mateu\.openjarvis`; a instância temporária foi encerrada. A mensagem “iniciando” não foi usada como prova de atualização.

### Testes concluídos

| Escopo | Execução final | Evidência / limite |
|---|---|---|
| HUD/runtime | **725 aprovados, 75 subtestes aprovados**, 128,54s | `python -m pytest modo-show/testes -q`; [JUnit](../artifacts/auditoria-2026-09-20/hud-tests.xml); modelos/dispositivos simulados identificados nos testes |
| Backend/memória/ponte | **122 aprovados**, 82,49s | Rotas, ponte, contexto e integração Mateus; [JUnit](../artifacts/auditoria-2026-09-20/openjarvis-tests.xml). 121 avisos de depreciação existentes, sem falhas |
| Frontend | **6 aprovados**, 1,93s | `npm test -- --run src/lib/sse-runtime.test.ts src/lib/theme.test.ts` |
| Compilação frontend | `npm run build`, código 0 | TypeScript/Vite/PWA concluíram; assets gerados no servidor. Avisos de tamanho de chunk e configuração npm não foram tratados como falha |
| Integração JS da Mesa | Código 0 | `node --experimental-vm-modules modo-show/testes/test_holograma_integracao.mjs`; módulos reais, DOM/canvas/SSE simulados; confirmação depois dos frames, seleção correta e renovação da sessão após 403. Sem captura visual |
| Gestos/modelo | 15 testes S7, incluídos na suíte HUD | Modelo MediaPipe real carregado e imagem vazia inferida; movimentos/calibração por landmarks de teste. Sem mão humana nesta execução |

As primeiras rodadas encontraram duas expectativas antigas nos testes: manchete sem aviso de cobertura e apresentação sem ID. Os testes foram atualizados para exigir os novos contratos. Uma corrida no harness JavaScript criava duas instâncias do módulo cliente; o cache por promessa foi corrigido, com execuções isoladas repetidas. Essas falhas não foram omitidas da contagem final.

### Ensaios reais pela aplicação

- **Pedido composto final:** “calcule 17 vezes 19 e depois calcule 25 por cento de 480” percorreu HTTP 8000 → ponte → runtime 8765 → Qwen3.5:4b → duas chamadas de `executar_comando` → calculadora → revisão. Resposta real: **323 e 120**. Duração **102,219s** na máquina atual. Repetição do mesmo identificador devolveu recibo persistido e não repetiu ferramentas. [Resposta, metadados e eventos](../artifacts/auditoria-2026-09-20/chat-runtime-real.json).
- **Escolha de ferramentas isolada com modelo real:** Qwen3.5:4b selecionou as duas chamadas e recebeu seus resultados reais, em 68,578s. O JSON preserva as trocas HTTP sem dados pessoais: [evidência](../artifacts/auditoria-2026-09-20/modelo-ferramentas-real-reserva.json). O teste usou executor real e dispositivos de fixture. Uma segunda amostra foi interferida pelo reinício e não conta como aprovada. O JSON bruto de um ensaio anterior com Gemma foi sobrescrito durante o trabalho; não foi reconstruído nem usado como evidência final.
- **Falha real descoberta e corrigida:** antes do ajuste, o reserva respondeu ao pedido matemático sem chamar ferramentas e errou. [Registro da falha](../artifacts/auditoria-2026-09-20/chat-runtime-real-falha-inicial.json). O catálogo matemático e o prompt de ferramentas foram corrigidos; não foram criadas chamadas falsas nem respostas numéricas fixas. Resposta do modelo sem executar uma ferramenta deixa uma pendência explícita, sem apresentar um resultado inventado.
- **Cadastro pelo chat:** “Como memorizar meu rosto e minha voz?” respondeu com o procedimento local e as três amostras de voz, sem iniciar captura. A mesma verificação testou autenticação, cancelamento anterior à execução e replay: [HTTP real](../artifacts/auditoria-2026-09-20/chat-cadastro-ajuda-real.json). Este ensaio não equivale a cadastrar ou reconhecer Mateus.
- **SSE:** o caminho de streaming usado pelo frontend entregou resposta e `[DONE]`: [registro](../artifacts/auditoria-2026-09-20/chat-sse-real.json). Um pedido simultâneo recebeu “ocupado” e não executou outra ação: [registro de concorrência](../artifacts/auditoria-2026-09-20/chat-sse-ocupado-real.json).
- **Telas servidas:** HTML/JS/CSS da Mesa e assets compilados do chat retornaram 200 e conferem com o disco. GETs privados sem sessão retornaram 403; cookie da própria tela autorizou a leitura. [HUD](../artifacts/auditoria-2026-09-20/hud-http-real.json), [frontend](../artifacts/auditoria-2026-09-20/frontend-http-real.json). O Browser da ferramenta estava indisponível; isso é evidência HTTP, não visual.
- **Pesquisa pública:** o módulo consultou de verdade “Circuito eletrico” e recuperou resumo da Wikipédia, sem conta privada. A cobertura obtida foi resumo; a comparação de múltiplas fontes e casos de falha também possui testes com fixtures. Nenhum artigo integral foi presumido.

### Arquivos e uso

As alterações principais estão em `modo-show/hud_runtime/{entrada,execucao_modelo,voz,comandos,identidade,projetos,protocolos,pecas,conhecimento,identificacao,rastreador,inventario,gestos,apresentacao,pesquisa,noticias,anunciador,capacidades,reunioes,servidor_http}.py`, no runtime/HUD, na ponte `src/openjarvis/server/runtime_bridge.py` e no encaminhamento do chat em `frontend/src/lib/sse.ts`/`InputArea.tsx`. Os testes acompanham os respectivos módulos.

O [guia de comandos e validação](JARVIS_COMANDOS_E_VALIDACAO.md) explica cadastro, gestos, pesquisa, projetos, prévias e protocolos. O [manifesto](../artifacts/auditoria-2026-09-20/manifesto-arquivos.json) identifica cada arquivo pelo SHA256 e o compara com o checkpoint inicial; inclui alterações preexistentes, sem atribuir toda mudança a esta revisão. [Cópia do código entregue](../artifacts/auditoria-2026-09-20/codigo-entregue.zip), incluindo `modo-show/`, que é ignorado pelo Git. Bibliotecas, modelos pesados e dados pessoais não estão nesse pacote; dependências S7 e hash do modelo estão documentados separadamente.

### Limites finais

A implementação foi integrada e carregada, mas **o prompt inteiro ainda não pode ser declarado 100% validado**. Permanecem a validação humana de rosto/voz/mãos, reconhecimento independente de objetos reais, calibração física, a demonstração completa do §20 com objeto/manual escolhidos e as integrações que dependem de contas/sensores ausentes. A Mesa tem parser/render/confirmação testados com fixtures, sem conferência visual humana nesta sessão. Impressão e propriedades físicas não foram ensaiadas.

O ensaio do chat também mostrou uma limitação prática: 102s para o pedido composto com pouca RAM livre. Essa duração foi registrada, não promovida a experiência instantânea. O trabalho preserva modelos/preferências e não esconde o uso da reserva. Os estados TP/AD/AJ/FE da matriz permanecem explícitos; componentes aprovados em L/S não foram promovidos a uma demonstração humana inexistente.

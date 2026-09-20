# Matriz F01–F44 — o que o filme mostra × o que esta instalação faz

Esta matriz responde ao prompt mestre de 19/09/2026 (§3 e §19). Ela **não substitui**
`INVENTARIO.md`: aquela matriz continua valendo e descreve a origem de cada função. Esta
aqui olha pelos 44 comportamentos pedidos e diz, item por item, o que existe, onde está no
código, qual evidência eu tenho e o que falta.

**Duas mãos trabalharam nesta instalação** com o mesmo prompt: esta sessão (Claude) e a
sessão do Codex/Astra. A coluna **quem** diz de onde veio cada implementação — atribuição
errada também é informação errada. Quando as duas mexeram no mesmo item, está escrito.

## Como ler o estado

| Sigla | Significa | Regra que eu sigo |
|---|---|---|
| **EP** | existente preservado | já existia e continua funcionando; não foi reescrito |
| **IT** | implementado e testado ponta a ponta | teste automatizado **e** execução real registrada nesta instalação |
| **TP** | testes parciais ou simulados | o código existe e tem teste, mas com dublê (mock), fixture ou sem o caminho real completo |
| **AD** | aguardando dado, conta ou permissão | falta algo do Senhor (chave, conta, aparelho, ficar na frente da câmera) |
| **PD** | pendente | não existe ainda; está aqui para ser feito |
| **AJ** | adaptado com justificativa | existe um equivalente útil, diferente do filme, e o porquê está escrito |
| **FE** | fora do escopo operacional | ficção sem equivalente pedido (§3-H do prompt) |

Uma coisa que eu **não** faço nesta matriz: chamar de IT o que só tem teste com dublê.
"O endpoint existe" não é integração funcionando.

Data desta revisão: **20/09/2026, 05h00**. Testes do HUD: **841 passando, 0 pulados**.

---

## A. Conversa, personalidade e colaboração

| ID | Comportamento pedido | Equivalente nesta instalação | Quem | Evidência | Limite honesto | Estado |
|---|---|---|---|---|---|---|
| F01 | Diálogo natural, sem depender de frases fixas | `comandos.py` (regras) + `fala_variantes.py` + modelo local quando nada casa | Claude (+ Codex ajustou) | test_fala_variantes (44 formas) **e** test_variantes_familias: **107 formas em 25 famílias**, 10 pares que não podem se confundir e 6 frases de conversa que não viram comando; 11 buracos reais fechados (clima, "liga a webcam", "põe X na lista", "bota um som", "mais alto", novidades…) | a decisão continua por regra + modelo; sotaque e erro de transcrição não entram nesta conta | IT |
| F02 | "a segunda", "aumente isso", "continue" | `contexto.py` + `ultima_lista` com validade de 10 min + peça ativa em `pecas.py` (sem dimensão, **pergunta**) + `selecao.py` (mouse/voz/gesto no mesmo alvo) | Claude (+ Codex: gesto) | test_pecas, test_selecao, T03/T23; real: "aumente isso" → "Qual dimensão, Senhor?" | "continue" ainda não retoma leitura de texto longo | IT |
| F03 | Continuidade de atividade | `projetos.py`: objetivo, condição de conclusão, etapas, resultados, aprovações, 10 estados; cartão no Painel | Claude (+ Codex: planos do modelo) | test_projetos (20), test_plano_persistente (18), T02/T05/T06; **real**: projeto retomado depois de reiniciar | não há dependência entre tarefas | IT |
| F04 | Perguntar quando há duas leituras possíveis | `ambiguidade.py`: pontua os candidatos e **só age quando um está na frente**; empate vira pergunta citando as opções. Ligado ao inventário e aos documentos | Claude (+ Codex: alvo visual) | test_ambiguidade (13); real: dois carregadores cadastrados → "Qual carregador o senhor quer: carregador da mochila ou carregador da mesa?" e **nada é apagado** | ainda não cobre ambiguidade dentro da própria frase ("aumente a largura e a altura") | IT |
| F05 | Discordar com fundamento | `discordancia.py`: conflito + **alternativa com número** (parede, mesa, dentes, furo, horário da agenda, recurso desligado) | Claude | test_discordancia (18); real: "a parede de 20 mm não cabe… o máximo aqui é 14,9 mm" | cobre engenharia, agenda e recursos; não discute prazo nem custo | IT |
| F06 | Tratamento, personalidade, humor discreto | `preferencias.nome_usuario` + `SISTEMA_NATURAL` | existente | real: trata por "Senhor" em toda resposta | — | EP |

## B. Assistência cotidiana e informações

| ID | Comportamento pedido | Equivalente nesta instalação | Quem | Evidência | Limite honesto | Estado |
|---|---|---|---|---|---|---|
| F07 | Resumo do início do dia | `secretario.py` | existente | test_secretario (22); real: resumo falado no boot | agenda do Google é leitura e depende de conexão | IT |
| F08 | Hora, fuso, cidade, com fonte | `utilidades.py`, `clima.py`, `cotacoes.py` | existente | test_consultas; real: hora mundial e clima com fonte | — | IT |
| F09 | Notícias com fontes e sem repetir | `noticias.py` | existente (+ Codex) | test_novidades (22) | — | IT |
| F10 | Recuperar compromissos, mensagens, decisões | `memoria.py` (+ episódios), `tarefas.py`, `agenda.py`, `rascunhos.py` | existente + Codex | test_memoria, MEMORIA_APRENDIZADO.md | mensagens ficam em rascunho, de propósito | IT |
| F11 | Informação em painel enquanto fala | cartão de contexto + `memoria-painel.js` | existente + Codex | captura real da tela Jarvis | — | IT |
| F12 | Apoio administrativo (reunião, pendências) | `capacidades.py` + `registros.py` (requisitos de tarefa) + `secretario.py` | Codex | test_capacidades_reunioes (14) | preparação de reunião **não** foi exercitada com agenda real conectada | TP |

## C. Visão, percepção e investigação

| ID | Comportamento pedido | Equivalente nesta instalação | Quem | Evidência | Limite honesto | Estado |
|---|---|---|---|---|---|---|
| F13 | Localizar e contar sem duplicar | `deteccao.py` (YOLOX-S int8) + `percepcao.py` | existente (+ Codex) | test_visao_tempo_real, test_percepcao; real: caixas desenhadas na câmera | contagem por quadro estável, não por identidade | IT |
| F14 | Acompanhar movimento, oclusão, reaparição | `rastreador.py`: sobreposição + classe + tamanho, id **temporário**, sumido por 6 s, **na dúvida id novo** | Claude (+ Codex: expiração) | test_rastreador (13), T13; bug real corrigido: o relógio do Windows repetia o horário e o sumiço não era detectado | ids não sobrevivem ao reinício, de propósito | IT |
| F15 | Responder sobre o que se observa | `visao.py` + conversa visual | existente (+ Codex) | test_conversa_visao (9) | — | IT |
| F16 | Reconstruir uma cena consultável | `cena.py`: junta o que o rastreador viu em regiões (esquerda, centro, direita) com hora e estado — **observado**, **última observação** e **não observado**. "descreva a cena", "o que tem no centro?", "o que você não viu?" | Claude | test_cena (17); **real**: câmera desligada → "não tenho cena nenhuma"; câmera ligada sem objeto → "olhei o quadro inteiro e não reconheci nada das categorias que eu conheço" | é um plano de imagem com três regiões, **não** reconstrução 3D; região sem detecção nunca vira "vazia"; sem régua calibrada não sai centímetro | IT |
| F17 | Cruzar ocorrências por período/lugar/atributo | `ocorrencias.py`: junta rastreador, inventário, projetos, peças e registro; entende "hoje à tarde", "ontem", "enquanto eu estava fora" | Claude | test_ocorrencias (14); **real**: "o que aconteceu enquanto eu estava fora?" respondeu com hora e fonte | só o que foi registrado; câmera desligada = período sem observação (e ele diz isso) | IT |
| F18 | Separar o observado do que se pode fazer | `capacidades.py` (componente, efeito, dependência) + texto de capacidades no prompt | Codex + Claude | test_capacidades_reunioes | — | IT |

## D. Engenharia e oficina

| ID | Comportamento pedido | Equivalente nesta instalação | Quem | Evidência | Limite honesto | Estado |
|---|---|---|---|---|---|---|
| F19 | Examinar projetos, versões e parâmetros | `pecas.py`: parâmetros de origem, versões numeradas, arquivo por versão, volume medido | Claude (+ Codex: prévia) | test_pecas; **real**: caixa v1 e v2 no disco | não guarda materiais por peça | IT |
| F20 | Vista explodida / separar componentes | `montagem.py`: componentes conhecidos, malha junta e explodida; **recusa explodir o que não montou** | Claude | test_montagem (11); real: "Separei as 2 peças… de um objeto que eu não montei, não sei o que tem por dentro" | só a montagem "caixa com tampa" por enquanto | IT |
| F21 | Alterar parâmetro com prévia e reversão | `Pecas.alterar()` valida antes, **gera prévia que espera confirmação**, versiona e reverte | Claude + Codex (prévia) | test_pecas, test_continuidade_contratos, T25 | a prévia é o modelo na mesa, não um antes/depois lado a lado | IT |
| F22 | Registrar experimentos, medidas e falhas | `registrar_experimento` (Codex) + extrator de condições do relato falado (Claude): material, temperatura, preenchimento e velocidade saem da própria frase | ambos | test_experimento_dependencia (13); real: "imprimi com PLA a 215 graus" → ensaio com `temperatura 215 graus; material PLA` | condição não dita não é inventada; o resultado fica marcado como **relato**, não medição | IT |
| F23 | Calcular e simular com unidades e hipóteses | `engenharia.py` | existente | test_engenharia; real: contas faladas com unidade | é cálculo analítico e **se apresenta como tal** | IT |
| F24 | Comparar alternativas de material | `engenharia.MATERIAIS` (19) | existente | test_engenharia | massa é teórica e é dita como teórica | IT |
| F25 | Recuperar conhecimento anterior | `conhecimento.py`: índice com trecho, página, **versão e hash**; RAG junto da pergunta; "qual é a fonte?" | Claude + Codex (versão/hash/injeção) | test_conhecimento (19), T20; **real**: manual lido e citado com versão | busca por palavras (sem embeddings), de propósito | IT |
| F26 | Comunicar limites do que foi calculado | campo `validacao` no ensaio (relato × ferramenta) + limite "medida com instrumento" quando ninguém mediu + `capacidades.py` | ambos | test_experimento_dependencia, test_capacidades_reunioes | — | IT |

## E. Diagnóstico, telemetria e assistência operacional

| ID | Comportamento pedido | Equivalente nesta instalação | Quem | Evidência | Limite honesto | Estado |
|---|---|---|---|---|---|---|
| F27 | Energia e disponibilidade | `sistema.py` + `telemetria.py` | existente | test_runtime, test_monitores | consumo por programa é **estimativa** rotulada | IT |
| F28 | Falhas de componentes | `boot.py` + registro + `modelos_ia.py` (modelo reserva) | existente + Claude | test_modelo_reserva (10); real: "Usando o modelo reserva… não cabe na memória livre" | — | IT |
| F29 | Condições anormais com limite | `monitores.py` | existente | test_monitores (10) | só o que o Windows expõe | IT |
| F30 | Diagnóstico contextualizado | `capacidades.py`: componente, situação, **fonte, efeitos e dependências**; "disco tem o modelo" ≠ "modelo responde" | Codex | test_capacidades_reunioes (14) | — | IT |
| F31 | Posição e navegação | — | — | — | sem fonte autorizada; não invento GPS | AD |
| F32 | Dados fisiológicos | — | — | — | **não implemento** diagnóstico médico por webcam | FE |

## F. Computadores, interfaces e comunicação

| ID | Comportamento pedido | Equivalente nesta instalação | Quem | Evidência | Limite honesto | Estado |
|---|---|---|---|---|---|---|
| F33 | Preferências e identidade compartilhadas | `preferencias.py` + `estado.py` por SSE | existente | test_runtime, test_widgets | — | IT |
| F34 | Intermediar comunicações | `telegram.py`, `rascunhos.py`, link do WhatsApp | existente | test_casa_comunicacao (8) | **aguarda o token do bot**; WhatsApp é manual, de propósito | AD |
| F35 | Filtrar interrupções | `notificacoes.py` + `anunciador.py` + revalidação no momento de falar | existente + Codex | test_proatividade_contextual (13) | — | IT |
| F36 | Interfaces consistentes | estado único; telas e chat leem o mesmo SSE | existente | test_widgets (12) | — | IT |
| F37 | Canais com capacidades declaradas | `canais.py`: cada canal declara texto, áudio, arquivo, apresentação e controle; **capacidade não declarada é capacidade ausente** e autenticado ≠ capaz. A ponte do Telegram avisa quando a fala sai no computador | Claude | test_canais (9); real: "o Telegram toca áudio?" → "não faz áudio falado — só texto… e ainda não está autenticado" | as capacidades são as desta instalação, escritas à mão; um conector novo precisa declarar as dele | IT |
| F38 | Transferir a apresentação | `apresentacao.py`: pedido com ID, a Mesa **confirma depois de renderizar**, ack antigo não confirma modelo novo | Codex | test_apresentacao | "carregada" não é validação de engenharia (e está dito) | IT |

## G. Autonomia, paralelismo e protocolos

| ID | Comportamento pedido | Equivalente nesta instalação | Quem | Evidência | Limite honesto | Estado |
|---|---|---|---|---|---|---|
| F39 | Trabalho persistente | `projetos.py` + planos do modelo em disco + `entrada.py` (recibo por pedido) | ambos | test_plano_persistente (18), test_execucao_integrada (18) | reinício **não** inventa worker em execução: a tarefa volta como pausada | IT |
| F40 | Protocolos nomeados | `protocolos.py` (+ comandos proibidos) | existente (+ Codex) | test_automacao (10) | sem parâmetros por execução ainda | IT |
| F41 | Coordenar respeitando dependências | dependência entre etapas por índice ("fechar a caixa depende de soldar os fios"): a etapa travada **não é oferecida** como próxima e aparece no resumo | Codex (executor) + Claude (comando e bloqueio) | test_experimento_dependencia, test_pedidos_compostos, test_execucao_integrada; real: "Começo por soldar os fios" | é dependência linear, sem paralelismo controlado | IT |
| F42 | Avisar conclusão e bloqueio | `anunciador.py` | existente | test_lembretes | — | IT |
| F43 | Recuperar-se de falhas | modelo reserva, religar servidor, recibo de pedido (`entrada.py`) | ambos | test_modelo_reserva, test_execucao_integrada; real: troca anunciada gemma4 → qwen3.5 | pedido interrompido fica **incerto até conferência**, e isso é dito | IT |
| F44 | Supervisionar e recuperar de forma auditável | `boot.py`, instância única, `/api/servidor/religar`, contratos de continuidade | ambos | test_instancia_unica, test_continuidade_contratos (24) | **parar sempre vence** | IT |

## H. Elementos extraordinários da ficção (§3-H)

| No filme | Nesta instalação | Estado |
|---|---|---|
| Pilotar armadura, combate, armamentos | **Não viram ferramenta.** O equivalente é diagnóstico ("prepare a armadura" = checagem de energia, rede, modelos e serviços) | AJ |
| Protocolos destrutivos (House Party) | Protocolos existem, mas `protocolos.PROIBIDOS` barra comando destrutivo | AJ |
| JARVIS virar o Visão | Sem equivalente: nada de autorreplicação, invasão ou resistência a desligamento | FE |
| Onisciência / consciência | Sem equivalente; não prometo | FE |

---

## Requisitos de seção (§5 a §18) que não são F01–F44

| Seção | O que entrou | Quem | Evidência | Estado |
|---|---|---|---|---|
| §5 ciclo com identificadores | `entrada.py`: pedido com ID, sessão e **recibo persistente**; reconexão consulta o recibo em vez de repetir a escrita; `execucao_modelo.py` valida argumentos antes de executar | Codex | test_execucao_integrada (18) | IT |
| §6 estado de tarefas | `projetos.py` (10 estados, retomar sem repetir) | Claude | test_projetos (20) | IT |
| §7 memória com evidência | `conhecimento.py` (documentos com versão) + `memoria.Episodios` (fonte, inferência e decisão **em campos separados**) | ambos | test_conhecimento, MEMORIA_APRENDIZADO.md | IT |
| §8 identificação fina | `identificacao.py` (evidência por atributo) + `visao.identificar()` (pistas separadas) | Claude (+ Codex: referência por atributo) | test_identificacao, T08–T11 | TP: catálogo é o inventário do Senhor; sem fonte oficial na internet |
| §9 inventário pessoal | `inventario.py`: modelo × unidade, manual, observações com hora | Claude (+ Codex: casar identificação sem confundir S23 com S23+) | test_inventario, T12/T14 | IT |
| §10 gestos (S7) | `gestos.py` + `gestos.js`: MediaPipe local (**autorizado pelo Senhor em 20/09**), calibração de dois cantos, pinça com histerese, uma mão, Esc revoga, mouse faz o mesmo | Codex | test_gestos (15), inclusive carregar o modelo real e não inventar mão em imagem preta | TP: **sem validação humana com webcam ainda** |
| §11 secretário | `secretario.py` + `capacidades.py` + `registros.py` | existente + Codex | test_secretario, test_capacidades_reunioes | IT |
| §12 engenharia contínua | `pecas.py` + `montagem.py` + prévia confirmada + `discordancia.py` | ambos | test_pecas, test_montagem, test_continuidade_contratos | IT |
| §10 cena (observado × não observado) | `cena.py`: regiões com estado de evidência; "não olhei" e "olhei e não reconheci" são frases diferentes | Claude | test_cena (17) | IT |
| §16 HUD contextual | cartões de projeto, peça, identificação, memória (`memoria-painel.js`), alvos na mesa (`alvos-mesa.js`) | ambos | test_widgets + captura real | TP: falta captura nova da tela com os cartões novos |
| §17 aprendizado controlado | `correcoes.py` (apelido revisável, **recusa destino que não é comando**) + `aprendizado.py` (coleta opt-in desligada, 3 confirmações, avaliação separada, comparação com reversão) | Claude + Codex | test_correcoes (11), test_aprendizado_controlado | IT — **e nada treina pesos** |
| §18 segurança | trecho de documento marcado como **dado não confiável**; GET de estado exige token; `PROIBIDOS`; quarentena; testes isolados por `conftest.py` | ambos | T21, T31, T32 | IT |

## Cenários de aceitação T01–T34

`testes/test_aceitacao.py` tem um teste por cenário, com o texto do cenário no corpo.
Hoje: **35 de 35 passando, nenhum pulado** (T23 tem dois testes: com e sem lista recente).

---

## Resumo honesto

| Estado | Itens | 19/09 20h30 | 19/09 23h40 | agora |
|---|---|---|---|---|
| IT (testado ponta a ponta) | F01–F03, F05, F07–F11, F13–F30, F33, F35–F44 | 15 | 20 | **39** |
| EP (existente preservado) | F06 | 2 | 2 | **1** |
| TP (parcial ou simulado) | F12 | 15 | 15 | **1** |
| AD (aguarda algo do Senhor) | F31, F34 | 2 | 2 | **2** |
| PD (pendente) | — | 9 | 4 | **0** |
| AJ / FE | armadura, protocolos destrutivos, Visão, onisciência, F32 | 5 | 5 | **5** |

**O que ainda falta — e por que não depende mais de código:**

1. **F12** (preparar reunião) e **F34** (Telegram): dependem de o Senhor conectar a agenda do
   Google e criar o bot. O código está pronto para os dois.
2. **§10 gestos**: o controle existe e passa nos testes, mas **ninguém validou com a mão na
   frente da webcam**. Só o Senhor pode fazer essa parte.
3. **F31** (localização): sem fonte autorizada nesta máquina — não invento GPS.
4. **Cadastro do seu rosto e da sua voz**: os comandos funcionam, a câmera abre — falta o
   Senhor ficar na frente dela e dizer "memorize o meu rosto".
5. **Microfone**: o Windows está com o acesso ao microfone desligado (Configurações →
   Privacidade e segurança → Microfone). O Jarvis detecta e avisa, mas não pode liberar.

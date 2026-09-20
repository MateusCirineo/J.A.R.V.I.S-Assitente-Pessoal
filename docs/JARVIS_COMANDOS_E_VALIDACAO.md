# Usar e conferir as correções do Jarvis

Esta é a instalação em `C:\Linguagem_C\projeto pessoal\Jarvis`. O inventário completo, a comparação antes/depois e os limites de cada requisito estão em [JARVIS_AUDITORIA_2026-09-20.md](JARVIS_AUDITORIA_2026-09-20.md).

## Abrir a versão instalada

- Chat: <http://127.0.0.1:8000>
- Jarvis: <http://127.0.0.1:8765/jarvis>
- Painel: <http://127.0.0.1:8765/painel>
- Mesa: <http://127.0.0.1:8765/holograma>

Recarregue uma aba que já estava aberta durante a atualização. O chat local encaminha comandos ao mesmo runtime da voz e do HUD. Interromper usa o identificador do pedido. Repetir uma requisição de rede com o mesmo identificador consulta o recibo; digitar novamente cria um pedido novo.

## Rosto e voz

Digite ou fale **“Jarvis, memorize meu rosto e minha voz”**, estando diante da câmera e com o microfone disponível. O cadastro conjunto trata as duas modalidades separadamente e informa a pendência de cada uma. Siga as instruções de captura e fale três frases diferentes quando solicitado. Microfone bloqueado, rosto ausente, mais de um rosto, amostra insuficiente ou erro de gravação não contam como sucesso.

**“Como memorizar meu rosto e minha voz?”** explica o procedimento sem iniciar captura. **“Cancele o cadastro da minha voz”** encerra a captura pendente; um cadastro já salvo continua existindo. **“Esqueça meu rosto e minha voz”** pede a exclusão dos próprios cadastros. Reconhecimento não substitui autorização de ações sensíveis.

O ensaio automatizado verifica os contratos e os modelos instalados. O reconhecimento de Mateus requer cadastro e teste com novas amostras humanas; não foi comprovado apenas com vetores de teste.

## Gestos na Mesa

Clique **Ativar gestos**, mostre uma mão e marque os dois cantos da área de controle pelo mouse. Pinça seleciona o alvo; mantendo a pinça, mova para girar ou escolha **Zoom**. **Esc** desativa. O modelo deve estar efetivamente carregado na Mesa. Mouse e teclado continuam disponíveis.

Há instruções completas, dependências e limites em [GESTOS_S7.md](../modo-show/GESTOS_S7.md). O controlador inicia desligado. Desligar a câmera revoga a sessão e exige nova ativação/calibração.

## Projetos, peças e protocolos

- **“Comece o projeto suporte”** abre o contexto do projeto; trocar de projeto invalida a seleção e a prévia anteriores.
- **“Continue de ontem”** recupera a tarefa persistida. Etapa interrompida com efeito incerto exige conferência antes de retomar.
- Com uma peça paramétrica ativa, **“Aumente a largura em 2 milímetros”** gera uma prévia real sem mudar a versão. **“Confirme a alteração da peça”** consolida a alteração daquela peça e versão. “Aumente isso” sem parâmetro suficiente pede esclarecimento.
- Selecionar uma tampa não autoriza alterar silenciosamente a largura de toda a montagem. Declare o parâmetro; dimensões vinculadas precisam ser explicadas.
- **“Registre experimento encaixe: falhou por folga insuficiente”** registra um relato na tarefa ativa; não marca a peça como ensaiada pelo sistema.
- **“Crie o protocolo dobro: calcule {valor} vezes 2”** e **“Execute o protocolo dobro com valor=21”** usam parâmetro simples. Etapas são revalidadas; o protocolo não pode fabricar consentimento ou confirmação.

## Pesquisa e contexto

**“Investigue circuito elétrico”** usa a pesquisa detalhada, limitada a três consultas. **“Qual é a fonte?”** recupera a evidência vinculada à resposta ou seleção. Resumo, manchete e documento indexado têm coberturas diferentes; um resultado de busca não é leitura integral de artigo. Cache antigo mantém seu horário e recebe aviso quando a atualização falha.

**“Prepare minha reunião”** depende de uma agenda conectada e dos documentos autorizados disponíveis. Uma conta desconectada não significa agenda livre. Mensagens continuam sendo rascunhos, sem envio implícito.

**“Modo foco”** reduz as interrupções conforme as preferências. Avisos rechecados na entrega respeitam silêncio, canal, prioridade e deduplicação.

## O que falta conferir com você

O cadastro e a identificação de rosto/voz, a calibração gestual, a precisão visual e a demonstração integrada do prompt precisam de entrada humana. Escolha um objeto e seu manual real para conferir observação → referência → projeto → cálculo → prévia → interrupção → retomada. A matriz registra os componentes comprovados e os passos dependentes dessa demonstração; não declara tudo aprovado por uma compilação.

Contas não conectadas, sensores ausentes, fabricação física e capacidades ficcionais continuam identificados como dependências ou fora do escopo. Nenhuma integração externa foi habilitada silenciosamente.

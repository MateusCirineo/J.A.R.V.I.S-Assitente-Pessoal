# Jarvis HUD — runtime, telas, voz, câmera e ativação por palmas

Esta pasta **não faz parte do OpenJarvis**. É o runtime próprio desta instalação:
estado real do assistente, telas **Jarvis** e **Painel**, conversa por voz pelo servidor
do OpenJarvis, widgets do sistema, câmera com a visão do capacete e ativação por palmas.
Fica fora do controle de versão (`.git/info/exclude`), então `git pull` continua funcionando.

## Ícones da área de trabalho

| Ícone | O que abre |
|---|---|
| **Jarvis** | runtime + tela Jarvis + Painel + Chat (tema HUD) |
| **Jarvis - Modo Show** | espera duas palmas e então abre; sem microfone (bloqueado pelo Windows), diz o motivo e abre direto |
| **OpenJarvis** | o aplicativo original, intocado, com o tema original |

Ao abrir o Jarvis (ícone ou palmas) aparece a tela **Inicializando**: anéis do HUD girando,
a faixa larga enche com o progresso **real** do boot e os pontos no alto são as 10 etapas
(amarelo = ok, laranja = aviso, vermelho = falha, branco pulsando = verificando). Ela fecha
sozinha quando a janela do Jarvis aparece; clique ou Esc fecham antes. No início do Windows
(sem janelas) ela não aparece.

No início do Windows, **Jarvis - escuta de palmas** fica de prontidão. Ela só mede o
pico do som (nada é gravado) e larga o microfone quando o Jarvis abre. Para desativar,
apague o atalho em `shell:startup`. Abrir duas vezes não cria um segundo Jarvis.

## Falar com o Jarvis

- Comece com **"Jarvis"** ("Jarvis, que horas são?"). Depois de cada resposta há
  **30 s** para continuar sem repetir o nome. O que for dito sem o nome não vai ao
  modelo nem ao log; só aparece na tela por 20 s, em âmbar, para você ver o que ele ouviu.
- **Na hora, sem o modelo:** hora, data, clima ("clima em Angatuba"), bateria, agenda
  ("o que tenho hoje / amanhã") e tarefas ("adicione a tarefa…", "quais são minhas tarefas").
- **O resto vai ao modelo da voz** (Preferências → Modelo da voz; hoje **gemma4:e4b**,
  escolha sua) pelo servidor do OpenJarvis, em modo direto (cabeçalho
  `X-OpenJarvis-Direct`: sem o prompt de ferramentas do orquestrador, que custava
  30–110 s nesta CPU). Se demorar, ele diz "Um momento, Senhor.". O gemma4:e4b tem
  9,6 GB e o PC 11,7 GB de RAM: ele usa memória virtual e pode passar de 40 s. Medido
  antes: `qwen3.5:4b` 20–40 s, `qwen3.5:2b` ~4 s, `qwen3.5:0.8b` ~1 s.
- **Reconhecimento da fala:** Whisper **small** com uma dica de vocabulário ("Jarvis,
  cheguei", "que horas são", "quanto está o dólar"…), ~3 s por frase: entende bem melhor
  que o base (que ouviu "Jarvis Shiggy"). Preferências → Precisão do Whisper (small/base)
  e Reconhecimento da fala (Whisper ou VOSK, offline e mais leve, erra mais). A troca vale
  na frase seguinte, sem reiniciar.
- **Pronúncia:** ele fala "Járvis" (não "Jarviz") em todos os motores de voz.
- Com o microfone ligado, o modelo da voz fica carregado no Ollama (sem ~1 min de
  carga depois de uma pausa). Desligável em Preferências.
- Como ele te chama: Preferências → "Como o Jarvis te chama" (hoje: Senhor).
- **Parar na hora:** "Jarvis, pare" / "silêncio", ou **Ctrl+Alt+P** de qualquer janela.
  **Ctrl+Alt+J** abre a conversa sem dizer "Jarvis".
- **Pelo terminal:** `python modo-show\jarvis_cmd.py "notícias de tecnologia"` (ou sem
  texto, para conversar; `--falar` para ele responder em voz alta).

## O que pedir (sem o modelo, na hora; com fontes quando é informação)

| Assunto | Exemplos |
|---|---|
| Resumo do dia | "bom dia", "me atualize", "prepare meu dia" |
| Notícias | "notícias", "notícias de tecnologia / economia / esportes…", "notícias sobre o Corinthians", **"abra a segunda notícia"** |
| Pesquisa com fontes | "quem foi Alan Turing?", "o que é bitcoin?", "pesquise sobre buracos negros" (Wikipédia + notícias; "no google" abre o navegador) |
| Cotações | "quanto está o dólar?", "cotação do bitcoin", "como estão as criptomoedas" (fonte e horário sempre) |
| Lembretes e timers | "me lembre de … às 15h", "todo dia às 8h me lembre do remédio", "timer de 5 minutos", "adie o lembrete em 10 minutos", "mais 5 minutos" (soneca), "mude o lembrete das 15h para as 16h", "cancele o lembrete do Pedro" |
| Memória | "lembre que prefiro café sem açúcar", "o que você sabe sobre mim?", "corrija a memória: …", "esqueça o café", "apague toda a memória" (pede confirmação) |
| Monitores | "me avise quando sair notícia sobre a Nvidia", "me avise quando o dólar passar de 5,50", "monitore o site …", "fique de olho na pasta Downloads", "quais são meus monitores", "pause/remova o monitor …" |
| Falar sozinho | "modo sob demanda" / "modo assistido" / "modo proativo" (também em Preferências) |
| Rotinas | "Jarvis, cheguei" / "Jarvis, vou descansar" (configure no cartão **Rotinas** do Painel) |
| Rascunhos | "escreva um e-mail para o Pedro dizendo que vou atrasar" → tela + área de transferência; **nunca envia**; "abra o rascunho no Gmail" |
| Planilhas | "crie uma planilha de gastos" (11 temas; sem dados inventados; "com exemplo" = aba fictícia) → Documentos\Jarvis\Planilhas |
| Programas | "crie um programa em Python que …" → valida, salva em Documentos\Jarvis\Programas e abre no VS Code; **não executa** |
| Tela e documentos | "olhe minha tela", "explique esse erro", "resuma o último PDF baixado", "resuma o documento aberto" |
| Áudio e vídeo | "transcreva o último áudio baixado", "analise o vídeo da reunião" → Documentos\Jarvis\Transcrições |
| Imagens | "verifique as imagens da pasta Downloads" (só analisa) → "confirmo quarentena" → "restaure a quarentena"; **nunca apaga** |
| Agenda | "o que tenho hoje?", "tenho conflito na agenda amanhã?", "quais horários livres hoje?" |
| Contas e conversões | "quanto é 15% de 230", "raiz quadrada de 144", "2 elevado a 10", "10 milhas em km", "30 graus celsius em fahrenheit", "100 dólares em reais", "meio bitcoin em reais" |
| Datas e sorte | "quantos dias faltam para o Natal?", "que dia da semana cai 25 de dezembro?", "que dia será daqui a 45 dias?", "jogue uma moeda", "sorteie um número de 1 a 10", "escolha entre pizza e hambúrguer" |
| O mundo | "que horas são em Tóquio?", "como está o clima em Paris?", "notícias do mundo" (G1 Mundo + BBC) |
| Listas | "adicione leite e pão à lista de compras", "o que tem na lista de compras?", "tire o leite da lista de compras", "limpe a lista de compras" (sem nome = compras; mercado/feira = compras) |
| Música | "toque Back in Black" (abre e toca o 1º vídeo do YouTube), "toque Legião Urbana no Spotify", "pause", "próxima", "volume 30" |
| Enxergar (câmera ligada) | "o que é isso?" (mostre o objeto), "o que você está vendo?", "onde está meu celular?", "quantas pessoas tem aqui?", "o que mudou?", "ative o olhar automático", "região de visão na mesa" |
| Segurança | "ative o modo vigia" (arma em 20 s; avisa se aparecer alguém), "desative o modo vigia"; "Jarvis, cheguei" desarma |
| Protocolos | "crie o protocolo trabalho: abra o VS Code, abra o Gmail e me dê as notícias de tecnologia", "execute o protocolo trabalho" (ou "Jarvis, protocolo trabalho"), "quais são meus protocolos?", "apague o protocolo trabalho" |
| No horário | "todo dia às 7h me dê o resumo do dia", "dias úteis às 8h30 execute o protocolo trabalho", "toda segunda às 9h quanto está o dólar" (ele executa sozinho) |
| Armadura (o PC) | "prepare a Mark 42", "diagnóstico completo", "o que está consumindo mais energia?" |
| Conversa | "oi", "tchau", "como você está?", "quem é você?", "o que você sabe fazer?", "conte uma piada" |

## Como no vídeo do Copilot (conversa vendo a câmera)

- **Fala enquanto pensa:** cada frase sai assim que o modelo termina de escrevê-la (antes esperava a
  resposta inteira). Estilo "natural" (1 a 5 frases, pode perguntar de volta); "breve" em Preferências.
- **Com a câmera ligada**, perguntas sobre o que ele vê ("o que você acha disso?", "qual a cor?",
  "você vê minha mão?") vão ao gemma4 **daqui** com a imagem. "Me ajude nesse jogo" / "o que tem na
  minha tela?" mandam a janela de trabalho (recusa senha e banco). Preferências → Imagem da câmera na conversa.
- **Régua virtual:** coloque uma folha A4 deitada (lado maior da esquerda para a direita) e diga
  "Jarvis, calibre a régua". Depois: "quanto mede isso?", "qual o tamanho do celular?". Mede no plano
  da mesa (erro de milímetros com o objeto deitado); se a câmera mudar de lugar, calibre de novo.
- **Mesa holográfica:** "Jarvis, abra a mesa holográfica". Com um projetor ligado como segundo monitor
  (como o do vídeo, apontado para a mesa), ela abre nele em tela cheia; fundo preto = só o HUD aparece.
  Mostra a visão ao vivo, a régua, modelos 3D ("mostre o modelo lançador"), gráficos ("mostre o gráfico
  do dólar / bitcoin / da temperatura") e a análise. "Gire o modelo", "aumente o zoom", arrastar e roda do mouse.

## Engenharia, raciocínio, casa e celular

| Assunto | Exemplos |
|---|---|
| Projetar peças (STL) | "projete uma engrenagem de 20 dentes com 40 mm", "crie uma caixa organizadora de 10 por 8 por 5 cm", "faça um tubo de 30 por 26 mm com 40 de altura" → Documentos\Jarvis\Projetos + mesa; "abra no Cura" |
| Contas de engenharia | "qual a corrente com 12 volts e 4 ohms", "quanto gasta um chuveiro de 5500 watts ligado 30 minutos por dia" ("a tarifa de luz é 0,85" para dar em reais), "lançamento a 20 m/s com 45 graus", "quanto tempo leva para cair de 20 metros" |
| Materiais | "compare alumínio e aço", "qual a densidade do titânio", "quanto pesa um cubo de alumínio de 10 cm" (valores típicos) |
| Dados | "analise a planilha de gastos" (CSV/Excel: soma, média, faixa, tendência e gráfico na mesa) |
| Raciocínio | "planeje minha tarde", "priorize minhas tarefas", "por que o PC está lento?" (ele recebe seus dados reais antes de responder) |
| Continuação | "que horas são em Tóquio?" → "e em Londres?"; "quanto está o dólar?" → "e o euro?"; "repita" |
| Casa | "quais aparelhos tem em casa?", "ligue a luz da sala", "volume da TV em 20", "adicione a tomada 192.168.0.50 como ventilador", "destranque a porta" (pede "confirmo destrancar") — cartão **Casa** do Painel (Home Assistant) |
| Celular | cartão **Celular (Telegram)**: crie o bot no @BotFather, cole o token, mande /parear e o código; depois comande pelo celular e receba os avisos. "Avise no meu celular que…", "mande no WhatsApp para 11… dizendo…" (abre pronto; você aperta enviar) |

## Quem é quem (rosto e voz) — autorizado pelo Senhor em 19/09

- **Cadastrar:** "Jarvis, memorize meu rosto" (ou "memore", "cadastre", "grave", "decore":
  o Jarvis entende as variações da fala) (olhe para a câmera ~5 s, sozinho), "memorize o rosto da
  Maria" / "este é o Pedro, memorize o rosto dele" (só com a pessoa de acordo), "memorize minha voz"
  (fale 3 frases de ~3 s, sem dizer Jarvis; "cancelar" desiste).
- **Usar:** o nome aparece sobre o rosto na câmera e na mesa holográfica; "quem está aqui?",
  "quem está falando?", "quem você conhece?". O modo vigia não dispara para quem é cadastrado.
  "Só atenda a minha voz" faz o Jarvis ignorar outras vozes ("atenda qualquer voz" desfaz).
- **Privacidade:** só números (nunca foto nem gravação) em `hud-identidades.json`; nada sai do PC;
  quem não foi cadastrado é "desconhecido" (nunca adivinhado). "Esqueça o rosto da Maria",
  "apague minha voz", "apague todos os rostos". Preferências → Reconhecer rostos e vozes cadastrados.

## Projetos, peças e ensaios — o trabalho continuado (20/09)

O Jarvis passou a guardar **o que estamos fazendo**, não só comandos soltos.

- **Projeto:** "comece o projeto caixa do Arduino", "falta abrir a passagem do cabo",
  "o que falta?", "pause o projeto", "continue de ontem", "terminei", "apague o projeto X".
  Ele guarda objetivo, etapas, resultados e o estado (planejada, em andamento, pausada,
  executada mas **não conferida**, concluída, falha).
- **Dependência entre etapas:** "fechar a caixa depende de soldar os fios". A etapa travada
  não é oferecida como próxima.
- **Peça com versões:** "projete uma caixa de 80 por 50 por 30 com parede de 2", depois
  "aumente a largura em 2 milímetros" → **versão nova**, com o volume medido na peça gerada;
  "quais versões?", "volte para a versão 1". A anterior continua no disco.
  Dizer só "aumente isso" faz ele **perguntar qual dimensão**.
- **Montagem e vista explodida:** "monte uma caixa com tampa de 80 por 50 por 30",
  "quais peças tem isso?", "mostre a vista explodida". De um objeto que ele não montou,
  ele diz que não sabe o que tem por dentro — não inventa.
- **Ensaio:** "registre o experimento primeira impressão: imprimi com PLA a 215 graus e
  ficou boa". Ele tira as condições do relato (material, temperatura, preenchimento,
  velocidade) e marca como **relato seu**, não medição dele.
- **Discordância com alternativa:** peça uma parede de 20 mm numa caixa de 30 e ele responde
  "não cabe: o máximo aqui é 14,9 mm".

## Manuais, objetos e o que aconteceu

- **Manuais:** "leia o manual da impressora" (procura em Documentos, Downloads e Área de
  Trabalho), "o que o manual diz sobre trocar a tinta?", "qual é a fonte?".
  Se o arquivo mudar depois de indexado, ele **não responde pela versão velha**: avisa para
  reindexar. "esqueça o manual X" apaga todas as versões.
- **Seus objetos:** "cadastre esta impressora", "a marca da impressora é Epson",
  "o modelo da impressora é L3250", "o que você sabe sobre a minha impressora?",
  "abra o manual", "esqueça a minha impressora". Ele separa o **modelo do produto** da
  **sua unidade**; com dois parecidos, pergunta qual antes de apagar.
- **O que aconteceu:** "o que aconteceu enquanto eu estava fora?", "o que apareceu hoje à
  tarde?", "quando você viu meu celular?". Só o que foi registrado — com a câmera desligada,
  ele diz que não há observação daquele período.

## A cena: o que ele viu e o que NÃO viu

- "descreva a cena", "o que tem no centro?", "o que está à esquerda?", "o que você não viu?".
- Ele separa três coisas que costumam virar uma só: **estou vendo agora**, **vi antes**
  (com a hora, e sem prometer que ainda está lá) e **não olhei**.
- Região sem objeto detectado **não** é região vazia: se o detector rodou, ele diz "olhei e
  não reconheci nada — pode haver coisa que eu não sei nomear"; se não rodou, diz que não
  observou. E sem a régua calibrada ele não dá centímetro de nada.

## Canais, correções e gestos

- **Canais:** "quais canais você tem?", "o Telegram toca áudio?". Cada canal declara o que
  faz; pelo Telegram vai **texto**, e a fala sai no computador (ele avisa).
- **Correções suas:** "quando eu disser modo oficina, abra o VS Code", "quais são as minhas
  correções?", "esqueça a correção modo oficina". É uma regra revisável, **não treinamento**:
  o destino precisa ser algo que ele já saiba fazer.
- **Gestos na Mesa (autorizado em 20/09):** abra a Mesa, clique **Ativar gestos**, marque os
  dois cantos e use a pinça (indicador + polegar) para selecionar, girar e dar zoom.
  Esc revoga. O mouse faz o mesmo. Gesto no ar **não é** toque na tela, e nada irreversível
  é disparado por movimento.

## Voz do Jarvis dublado (fish.audio)

O motor **fish** já está pronto com a voz pública "Jarvis (UCM) - Português Brasileiro"
(id `a5b93aeddcc948c19ea04f0afe9d178c`). Falta só a sua chave:
1. Entre em fish.audio com a sua conta → **API Keys** → crie uma chave (o cartão tem o
   link **Abrir fish.audio → API Keys** quando o motor fish.audio está escolhido).
2. Painel → cartão **Voz do Jarvis** → Motor: **fish.audio** → cole a chave → **Salvar credencial**.
3. **Ouvir prévia** → **Usar esta voz**.
A chave fica só neste computador (`hud-segredos.json`). O texto que o Jarvis fala vai para a
fish.audio; se ela falhar (chave errada, sem créditos, fora do ar), o cartão mostra o motivo e
ele volta para o Kokoro local. A vidnoz não tem API: não dá para ligar.

## Visão do capacete (câmera)

Ligue a câmera (botão **Câmera**): ao ver seu rosto a tela vira o interior do capacete,
na linguagem dos filmes (HUDs da Cantina Creative / Jayse Hansen): miras presas aos
seus olhos, anéis que crescem da profundidade, horizonte que inclina com a cabeça,
faixa de giro, "prateleira" com a doca de estado, radar da câmera, armadura com as
partes coloridas pelos dados reais (cabeça = CPU, tronco = RAM, braços = GPU e disco,
pernas = bateria, reator = servidor), comunicação com análise de áudio, hora, clima,
diagnóstico e avisos em vermelho quando algo está crítico.

- Câmera em **HD 1280×720** (MJPG), detecção de rosto local (YuNet), ~15 quadros/s.
- **Ocultar rosto**: troca a imagem por um rosto holográfico que acompanha a cabeça.
- Giro, inclinação e distância são **estimativas** geométricas e aparecem marcadas "est.".
- Não identifica quem é a pessoa; nada é gravado nem enviado.
- Preferências → Câmera: automática / sempre / desligada, imagem espelhada.

### Enxergar o mundo (como no vídeo de referência)

- **Olhar automático** (Preferências → "Olhar automático", ligado): com a câmera ligada,
  ele aprende o fundo da **região de visão** (retângulo tracejado: centro, mesa ou quadro
  inteiro). Quando você **mostra um objeto** e o segura parado ~1 s, a tela faz a varredura
  (grade + "ANÁLISE") e ele diz o que é, com marca, modelo ou título quando dá para ler.
  O mesmo objeto não é repetido até sair da região; no máximo uma análise a cada 25 s.
- **Percepção do ambiente:** "o que você está vendo?" descreve os objetos e a cena e marca
  cada um com uma caixa verde na imagem da câmera (3 min). Depois: "onde está meu celular?"
  (esquerda/direita/cima/baixo) e "o que mudou?". Com o modo proativo e a câmera ligada, ele
  dá uma olhada sozinho de vez em quando (só com você parado há 1 min, no máximo a cada 5 min).
- Tudo roda **aqui**, no modelo da voz (hoje gemma4:e4b; cada olhada leva de 30 s a mais de
  1 min nesta máquina). Pessoas aparecem só como "pessoa": ele não identifica quem é nem
  deduz emoção, saúde ou intenção. Nada é gravado. A câmera só liga quando você manda.
- **Visão em tempo real** (Preferências, ligada): com a câmera ligada, um detector local
  (YOLOX, 80 tipos de objeto) marca cada coisa com uma caixa âmbar e o nome, ~4 vezes por
  segundo. "Onde está…?", "quantos…?" e "o que você está vendo?" respondem na hora com ele;
  o modelo de visão continua olhando os detalhes (marca, modelo, título) e fala depois.
- Rastreamento de mãos (MediaPipe) do vídeo **não** foi instalado: o senhor recusou.

## Configurar

- **Clima**: cartão Clima do Painel → buscar → **Principal** ou **+ Adicionar**
  (até 3 cidades extras). Hoje: São Paulo e Angatuba. Fonte Open-Meteo, sem conta.
- **Agenda Google** (só leitura): cartão Agenda → "Credencial do Google" (os 5 passos
  estão no cartão) → **Conectar conta Google**. Dá para ligar mais de uma conta. Pede só
  `calendar.readonly`; tokens ficam em `%USERPROFILE%\.openjarvis\hud-segredos.json`.
  O conector oficial do OpenJarvis não foi usado porque pede Gmail, Drive e Contatos juntos.
  Alternativa: endereço secreto iCal (não o endereço da página do Google Agenda).
- **Avisos no Windows**: ligados por padrão (Preferências). Avisos, alertas,
  compromissos e downloads concluídos aparecem no canto do Windows.

## Temperatura e energia (precisa de administrador, uma vez)

O Windows só libera esses sensores para administrador. O leitor fica em
`sensores\` e **não abre porta de rede**: roda como SYSTEM e grava um JSON em
`%ProgramData%\JarvisSensores`, que o HUD só lê. Com ele o HUD mostra a temperatura
da CPU e a **energia medida de cada resposta** (contador RAPL da CPU).

Para instalar, abra o PowerShell **como administrador** e rode:

```
powershell -ExecutionPolicy Bypass -File "C:\Linguagem_C\projeto pessoal\Jarvis\modo-show\sensores\instalar-sensores.ps1" -Origem "$env:USERPROFILE\.openjarvis\downloads-jarvis\lhm" -PawnIO "$env:USERPROFILE\.openjarvis\downloads-jarvis\PawnIO_setup.exe"
```

Ele instala o driver assinado PawnIO (o mesmo do LibreHardwareMonitor 0.9.6) e cria a
tarefa "Jarvis Sensores". Para desfazer: `sensores\remover-sensores.ps1` (como admin).

## Bibliotecas e APIs usadas

| Recurso | Biblioteca / API |
|---|---|
| Bateria, rede, processos | psutil 7.2 |
| GPU | contador "GPU Engine" do Windows (PDH, sem admin) |
| Música e controles | Windows GSMTC via winrt 3.2 |
| Avisos no Windows | winrt Windows.UI.Notifications (AppUserModelID só do usuário) |
| Volume do sistema | pycaw (Core Audio) |
| Agenda | Google Calendar API (OAuth + PKCE) e icalendar + recurring-ical-events |
| Câmera e rosto | OpenCV 5.0 headless + modelo YuNet (`modelos/`) |
| Clima | Open-Meteo (geocodificação + previsão) |
| Temperatura e energia | LibreHardwareMonitorLib 0.9.6 + PawnIO (opcional, acima) |

Ficam em `_libs\`, **fora do venv**: um `uv sync` apagaria pacotes extras do venv.
Pelo mesmo motivo, depois de um `uv sync` reinstale a extensão de memória do OpenJarvis:
`uv pip install --python .venv\Scripts\python.exe --no-deps "%USERPROFILE%\.openjarvis\downloads-jarvis\wheels\openjarvis_rust-0.1.0-cp310-cp310-win_amd64.whl"`

## Se algo não funcionar

- **Ele não responde**: veja se o texto em âmbar aparece ("Ouvi … sem Jarvis"). Se nada
  aparece, desligue e ligue o microfone (recalibra). Outro microfone: `setx JARVIS_MIC 1`.
- **Demora**: é a RAM. Fechar abas do navegador ajuda; ou use um modelo de voz menor
  (acima). Medido em 19/09 nesta máquina: a CPU lê ~31 tokens de pergunta por segundo e
  escreve ~6 por segundo. A primeira pergunta depois de um tempo parado leva 20-35 s
  (o modelo volta para a memória); as seguintes, 3-14 s, porque o Ollama reaproveita o
  começo da conversa. Por isso o texto fixo do Jarvis é curto de propósito.
- **"Usando o modelo reserva, Senhor…"**: o gemma4:e4b (9,6 GB) não cabe na memória livre
  naquele momento, então o qwen3.5:4b respondeu. Não é troca definitiva: assim que o
  principal couber (ou já estiver carregado), ele volta sozinho. Para escolher outro
  reserva ou desligar isso: Preferências → Modelo reserva (vazio = sem reserva).
- **Palmas não disparam**: `setx JARVIS_CLAP_THRESH 0.15` (mais sensível) ou `0.4`.
- **Servidor fora**: botão "Religar" no cartão Serviços do Painel.
- **Voz some depois de mexer no runtime**: o `winrt` traz uma `msvcp140.dll` antiga que
  quebra o torch se carregar antes. O `jarvis_runtime.py` importa torch e ctranslate2
  primeiro — não mude essa ordem.

## Testes

```
.venv\Scripts\python -m pytest modo-show\testes -p no:faulthandler
.venv\Scripts\python -m pytest tests\server\test_routes.py tests\test_integracao_mateus.py tests\memory\test_fact_store.py
```

Em 20/09/2026: **824 testes do HUD** e 111 do OpenJarvis passando, sem nenhum pulado. A matriz de tudo o que o filme mostra × o que esta instalação faz está em `MATRIZ_FILME.md`; os gestos, em `GESTOS_S7.md`; a memória e o aprendizado, em `MEMORIA_APRENDIZADO.md`.
A situação de cada item dos projetos de referência está em `INVENTARIO.md`.

## Arquivos

- `jarvis_runtime.py` — ponto de entrada (instância única pela porta)
- `escuta_palmas.py` — ativação por palmas (`--uma-vez` / `--continuo`)
- `hud_runtime/` — estado, telemetria, sistema, sensores, clima, mídia, agenda,
  google_agenda, tarefas, notificações, avisos_windows, câmera, áudio, voz, ponte, boot,
  HTTP, janelas, palmas
- `hud/` — telas HUD (`capacete.js/css` é a visão do capacete)
- `sensores/` — leitor de temperatura/energia (instalação manual como admin)
- `modelos/` — detector de rosto YuNet (OpenCV Zoo)
- `testes/` — 63 testes unitários e o teste de integração da voz

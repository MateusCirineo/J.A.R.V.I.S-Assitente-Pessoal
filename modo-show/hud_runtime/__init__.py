"""Runtime do HUD do Jarvis.

Processo unico que guarda o estado real (microfone, inferencia, reproducao,
conexoes, boot), amostra a telemetria, conduz a conversa por voz pelo fluxo
oficial do OpenJarvis e serve as telas Jarvis e Painel em 127.0.0.1.

Nao faz parte do OpenJarvis: fica em modo-show/, fora do controle de versao.
"""

PORTA_PADRAO = 8765
SERVIDOR_OPENJARVIS = "http://127.0.0.1:8000"
OLLAMA = "http://127.0.0.1:11434"

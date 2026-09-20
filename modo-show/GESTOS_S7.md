# S7 e correções de percepção — 20/09/2026

O usuário autorizou instalar MediaPipe e o modelo de mãos nesta sessão.
MediaPipe 1.0.1 e dependências auxiliares estão em `_gestos_libs`, sem substituir
o NumPy 2.2.6 ou OpenCV 5.0.0 existentes. Versões em `requirements-s7.txt`.

Modelo oficial: `modelos/hand_landmarker.task`.
SHA256: `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`.
Fonte: [Hand Landmarker oficial](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker)
e [contrato Python](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python).
Usa landmarks em modo VIDEO com timestamps monotônicos; todos os quadros permanecem locais.

## Usar na Mesa holográfica

1. Abra a Mesa e clique **Ativar gestos**. Isso solicita a câmera compartilhada.
2. Mostre apenas uma mão. Com o indicador no canto superior esquerdo da área
   que deseja controlar, clique **Marcar canto superior esquerdo** pelo mouse.
3. Aponte o indicador para o canto inferior direito e marque o segundo canto.
   São posições da mão no campo da câmera, mapeadas para os cantos da tela.
4. Um cursor indica a posição. Feche indicador e polegar em pinça sobre o modelo
   central para selecioná-lo. Mantenha a pinça e mova para girar, ou selecione
   **Zoom** e mova verticalmente. Solte a pinça para parar a manipulação.
5. **Esc** ou **Desativar gestos** revogam a sessão. Recalibre se mover a câmera.

Mouse seleciona o mesmo alvo e continua girando/ajustando zoom. No canvas,
setas giram e `+`/`-` ajustam zoom. Não há toque físico ou comando irreversível.
O controlador começa desligado em cada boot, usa uma única sessão de tela,
recusa múltiplas mãos, descarta resultados atrasados e para após câmera
desligada ou ausência de heartbeat da tela por 12 segundos. Ocultar a tela
solicita desligamento. Não grava imagens nem cadastra biometria.

## Evidência e limites

`test_gestos.py`: 15 testes, incluindo carregamento real do modelo instalado e
inferência sobre imagem preta sem inventar mão. Os testes de seleção, rotação,
zoom, calibração, ambiguidade, lease, câmera desligada e revogação usam landmarks sintéticos, explicitamente
identificados. Não houve demonstração humana com webcam/calibração neste incremento;
precisão, iluminação, oclusão e ergonomia continuam precisando dessa validação.

`test_percepcao_confiavel.py`: 13 regressões de referência por atributo, recorte
enviado ao modelo, ambiguidade, expiração de rastros, horários de ocorrências,
cena antiga, entrada JSON inválida, cobertura de mídia e homografia inválida.
Outras suítes existentes pertinentes também foram executadas; nenhuma representa
reconhecimento visual independente com produtos reais por si só.

`test_selecao_visual.py`: 8 testes: trilha atual substitui caixa antiga,
seleção perdida exige nova escolha, fonte da mesa não vira imagem da câmera,
região fixa explícita e coordenadas finitas. O endpoint de seleção aceita apenas
mouse/teclado; gesto depende do controlador real e de sua sessão vigente.

F38 recebeu `apresentacao.py`: o pedido de modelo gera um ID; o HTTP entrega
arquivo e ID juntos; a Mesa confirma após interpretar a malha e dois frames de
renderização. Eventos e retries usam o mesmo ID. Ack antigo ou de outro destino
não confirma um modelo novo. `carregada` não significa validação de engenharia.
`test_apresentacao.py` usa Estado real e HTTP local, com artefato isolado;
o POST de confirmação desse teste é simulado e não comprova renderização visual.

O inventário agora distingue leitura de modelo, marca apenas cadastrada e unidade
física. Um manual vinculado não aparece como se tivesse sido consultado. Rastros
ambíguos recebem novos IDs; eventos de sessão são limitados a 500, sem fotos ou
persistência implícita. A régua exige homografia válida com menos de 24 horas e
proporção compatível; não detecta toda movimentação física da câmera, não mede
altura e não fornece incerteza quantitativa validada. Na mídia, frames cuja
descrição falhou não contam como analisados; áudio com duração desconhecida não
vira 'áudio inteiro'.

Comandos de validação, na raiz do projeto:

```powershell
.venv/Scripts/python.exe -m unittest discover -s modo-show/testes -p test_gestos.py
.venv/Scripts/python.exe -m unittest discover -s modo-show/testes -p test_percepcao_confiavel.py
node --check modo-show/hud/gestos.js
node --check modo-show/hud/holograma.js
```

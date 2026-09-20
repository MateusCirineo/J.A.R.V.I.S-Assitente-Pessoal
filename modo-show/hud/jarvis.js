// Tela Jarvis: liga o nucleo, os instrumentos e os controles ao estado real.

import {
  loja, conectar, ouvir, acao, estadoPrincipal, inferenciaAtiva,
  num, comUnidade, haQuanto, el, texto, chip, TRACO, TOKEN_CAMERA, iconeClima, escapar as esc,
} from './cliente.js';
import { criarNucleo } from './nucleo.js';
import { iniciarCapacete, capaceteAtivo, alternarCapacete, prefsCapacete } from './capacete.js';

const nucleo = criarNucleo(el('nucleo'), el('palco'));
let principalAnterior = null;
let arrastandoVolume = false;
let bootFechadoPeloUsuario = null;
// "SISTEMA ONLINE" so aparece se o boot TERMINAR com esta janela aberta
let bootVistoEmAndamento = false;
let anuncioAte = 0;

// ---------------------------------------------------------------------------
// sons de interface (desligados por padrao; so tocam com a preferencia ligada)
let audioCtx = null;
function tique(freq = 880) {
  if (!loja.prefs?.sons_interface) return;
  try {
    audioCtx ??= new AudioContext();
    const o = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    o.frequency.value = freq;
    g.gain.setValueAtTime(0.03, audioCtx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.06);
    o.connect(g).connect(audioCtx.destination);
    o.start();
    o.stop(audioCtx.currentTime + 0.07);
  } catch { /* sem audio: ignora */ }
}

// ---------------------------------------------------------------------------
function renderChips(est) {
  const mic = est.microfone?.estado;
  const micMap = {
    ouvindo: ['ativo', 'Ouvindo'], captando: ['ativo', 'Captando'], calibrando: ['aviso', 'Calibrando'],
    pausado: ['off', 'Mic pausado'], desativado: ['off', 'Mic desligado'], erro: ['erro', 'Mic: erro'],
    bloqueado: ['erro', 'Mic bloqueado (Windows)'],
  };
  const [ms, mt] = micMap[mic] ?? ['off', 'Microfone'];
  chip('c-mic', ms, mt);
  chip('c-mic2', ms, mt);

  const srv = est.conexao?.servidor?.estado;
  if (inferenciaAtiva(est)) chip('c-inf', 'ativo', 'Processando');
  else if (srv && srv !== 'ok' && srv !== 'desconhecido') chip('c-inf', 'erro', 'Inferência indisponível');
  else chip('c-inf', 'off', 'Inferência ociosa');

  const rep = est.reproducao?.estado;
  const repMap = { falando: ['ativo', 'Falando'], preparando: ['aviso', 'Preparando'],
                   erro: ['erro', 'Áudio: erro'], parado: ['off', 'Áudio parado'] };
  const [as, at] = repMap[rep] ?? ['off', 'Áudio'];
  chip('c-aud', as, at);
  chip('c-aud2', as, at);

  chip('c-srv', srv === 'ok' ? 'ok' : srv === 'desconhecido' || !srv ? 'off' : 'erro',
       srv === 'ok' ? 'Servidor' : srv === 'desconhecido' || !srv ? 'Servidor ?' : 'Servidor fora');
  const evt = est.conexao?.eventos?.estado;
  chip('c-evt', evt === 'conectado' ? 'ok' : 'aviso', evt === 'conectado' ? 'Eventos' : 'Eventos offline');
}

function renderBoot(est) {
  const lista = el('etapas');
  const etapas = est.boot?.etapas ?? [];
  const html = etapas.map((e) =>
    `<li data-s="${e.estado}"><span>${e.rotulo}</span>${e.detalhe ? `<small>${escapar(e.detalhe)}</small>` : ''}</li>`,
  ).join('');
  if (lista.dataset.cache !== html) { lista.innerHTML = html; lista.dataset.cache = html; }

  const concluido = est.boot?.concluido;
  const falhas = etapas.filter((e) => e.estado === 'falha');
  const ok = etapas.filter((e) => e.estado === 'ok').length;
  const secao = el('boot');
  const botao = el('b-pular');
  if (concluido) {
    texto('resumo-boot', falhas.length
      ? `${ok} de ${etapas.length} ok · falhou: ${falhas.map((f) => f.rotulo).join(', ')}`
      : `${ok} de ${etapas.length} verificações ok`);
    el('resumo-boot').className = falhas.length ? 'resumo-boot ambar' : 'resumo-boot verde';
    if (bootFechadoPeloUsuario === null) secao.dataset.fechado = falhas.length ? 'false' : 'true';
    botao.textContent = secao.dataset.fechado === 'true' ? 'Detalhes' : 'Recolher';
  } else {
    texto('resumo-boot', `${ok} de ${etapas.length} concluídas…`);
  }
}

function renderInstrumentos(est) {
  const tel = loja.telemetria;
  texto('m-voz', est.modelos?.voz ?? TRACO);
  texto('m-chat', est.modelos?.chat ?? TRACO);
  const oll = tel?.ollama;
  texto('m-carregado', oll?.status === 'ok'
    ? (oll.carregados.length ? oll.carregados.map((m) => m.nome).join(', ') : 'nenhum')
    : TRACO);

  const srv = est.conexao?.servidor?.estado;
  texto('e-srv', srv === 'ok' ? 'no ar · :8000' : srv === 'desconhecido' ? 'verificando' : 'fora do ar');
  texto('e-oll', oll ? (oll.status === 'ok' ? 'no ar · :11434' : 'fora do ar') : TRACO);
  texto('e-evt', est.conexao?.eventos?.estado === 'conectado' ? 'conectado' : 'desconectado');

  const mic = est.microfone ?? {};
  texto('mic-disp', mic.dispositivo ?? TRACO);
  texto('mic-lim', mic.ruido_rms != null ? `${mic.ruido_rms} / ${mic.limiar_rms}` : TRACO);

  const rep = est.reproducao ?? {};
  texto('out-disp', rep.dispositivo ?? TRACO);
  texto('out-vol', typeof rep.volume === 'number' ? `${Math.round(rep.volume * 100)} %` : TRACO);
  if (!arrastandoVolume && typeof rep.volume === 'number') el('vol').value = String(Math.round(rep.volume * 100));

  const u = est.inferencia?.ultima;
  texto('u-mod', u?.modelo ?? TRACO);
  texto('u-lat', comUnidade(u?.latencia_s, 's'));
  texto('u-ttft', comUnidade(u?.ttft_s, 's'));
  texto('u-tok', u?.tokens_saida != null ? String(u.tokens_saida) : TRACO);
  texto('u-em', u ? haQuanto(u.em) : 'nenhuma nesta sessão');
  texto('u-fonte', u?.fonte ? `fonte: ${u.fonte}` : '');

  const c = est.conversa ?? {};
  // fala ignorada (sem "Jarvis"): mostra o que ouviu por 20 s, com a dica
  const ignorada = c.ignorada && c.ignorada_em > (c.em ?? 0) && Date.now() / 1000 - c.ignorada_em < 20;
  texto('t-voce', ignorada ? `Ouvi “${c.ignorada}”, mas sem “Jarvis” no começo não respondo.`
    : c.ultima_fala ?? 'Nada dito ainda.');
  el('t-voce').classList.toggle('ambar', Boolean(ignorada));
  texto('t-jarvis', c.ultima_resposta ?? TRACO);
}

function renderControles(est) {
  const mic = est.microfone?.estado;
  const sttOk = est.boot?.etapas?.find((e) => e.id === 'transcricao')?.estado === 'ok';
  const b = el('b-mic');
  b.disabled = !sttOk;
  const ligado = mic && mic !== 'desativado' && mic !== 'erro';
  b.setAttribute('aria-pressed', String(Boolean(ligado)));
  texto('b-mic-t', !sttOk ? 'Microfone (aguardando)' : mic === 'bloqueado' ? 'Microfone bloqueado (Windows)'
                  : ligado ? 'Microfone ligado' : 'Microfone desligado');
  el('b-parar').disabled = est.reproducao?.estado !== 'falando';
}

// ---------------------------------------------------------------------------
// widgets: agora (relogio + clima), energia, musica, camera, avisos
function renderAgora() {
  const w = loja.prefs?.widgets_jarvis ?? {};
  el('w-agora').classList.toggle('oculto', w.relogio === false && w.clima === false);
  const a = new Date();
  texto('ag-hora', a.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }));
  texto('ag-data', a.toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' }));
  const c = loja.telemetria?.clima;
  const alvo = el('ag-clima');
  let html = '';
  if (w.clima === false) html = '';
  else if (c?.status === 'medido' || c?.status === 'desatualizado') {
    html = `${iconeClima(c.atual.icone, 26)}<span class="temp">${Math.round(c.atual.temperatura)}°</span>`
      + `<span class="desc">${esc(c.atual.descricao)}${c.dias?.[0] ? ` · ${Math.round(c.dias[0].min)}°/${Math.round(c.dias[0].max)}°` : ''}</span>`;
    texto('ag-local', c.local?.nome ?? '');
  } else if (c?.status === 'nao_configurado') {
    html = '<span class="desc">Clima: defina a cidade no Painel</span>';
  } else if (c?.status === 'erro') {
    html = '<span class="desc">Clima indisponível agora</span>';
  }
  if (alvo.dataset.cache !== html) { alvo.innerHTML = html; alvo.dataset.cache = html; }
}

function renderEnergia() {
  el('w-energia').classList.toggle('oculto', loja.prefs?.widgets_jarvis?.energia === false);
  const b = loja.telemetria?.sistema?.bateria;
  if (b?.status !== 'medido') {
    chip('c-bat', 'off', b?.status === 'indisponivel' ? 'Sem bateria' : '—');
    texto('bat-pct', TRACO);
    texto('bat-det', b?.motivo ?? TRACO);
    el('bat-nivel').style.width = '0%';
    return;
  }
  const s = b.na_tomada ? 'ok' : b.percentual <= 20 ? 'erro' : b.percentual <= 40 ? 'aviso' : 'ativo';
  chip('c-bat', s, b.na_tomada ? 'Na tomada' : 'Na bateria');
  texto('bat-pct', `${Math.round(b.percentual)} %`);
  texto('bat-det', b.na_tomada ? 'carregando' : b.restante_min ? `~${b.restante_min} min restantes` : 'descarregando');
  const barra = el('bat-nivel');
  barra.style.width = `${b.percentual}%`;
  barra.style.background = s === 'erro' ? 'var(--vermelho)' : s === 'aviso' ? 'var(--ambar)' : 'var(--verde)';
}

function renderMidia() {
  el('w-midia').classList.toggle('oculto', loja.prefs?.widgets_jarvis?.midia === false);
  const m = loja.telemetria?.midia;
  const tem = m?.status === 'medido' && m.titulo;
  texto('md-titulo', tem ? m.titulo : m?.status === 'erro' ? 'Mídia indisponível' : 'Nada tocando');
  texto('md-artista', tem ? [m.artista, m.album].filter(Boolean).join(' · ') : '');
  texto('md-app', tem ? `${m.app} · ${m.situacao}` : '');
  for (const id of ['md-ant', 'md-play', 'md-prox']) el(id).disabled = !tem;
  if (tem) {
    el('md-prox').disabled = !m.pode_avancar;
    el('md-ant').disabled = !m.pode_voltar;
  }
}

function renderCamera(est) {
  const cam = est.camera ?? {};
  const fig = el('camera');
  const b = el('b-cam');
  b.setAttribute('aria-pressed', String(Boolean(cam.ativa)));
  texto('b-cam-t', cam.ativa ? 'Câmera ligada' : 'Câmera');
  // com o capacete aberto a janelinha some (e fecha o stream dela)
  const mostrar = cam.ativa && !capaceteAtivo() && loja.prefs?.widgets_jarvis?.camera !== false;
  fig.classList.toggle('oculto', !mostrar);
  const img = el('cam-img');
  const src = '/api/camera.mjpg';
  if (mostrar && !img.dataset.ligada) { img.src = src; img.dataset.ligada = '1'; }
  if (!mostrar && img.dataset.ligada) { img.removeAttribute('src'); delete img.dataset.ligada; }
  el('b-capacete').setAttribute('aria-pressed', String(capaceteAtivo()));
  if (cam.resolucao) fig.querySelector('.camera-quadro').style.aspectRatio = cam.resolucao.replace('x', ' / ');
  chip('c-cam', cam.presente ? 'ok' : 'off', cam.presente ? `Presença · ${cam.fps ?? '—'} fps` : 'Ninguém à frente');
  el('c-pres').classList.toggle('oculto', !cam.presente);
  if (cam.detalhe && !cam.ativa) texto('sub', `Câmera: ${cam.detalhe}`);
  const v = est.visao ?? {};
  const emAnalise = v.estado === 'analisando' || (v.estado === 'pronto' && v.em && Date.now() / 1000 - v.em < 20);
  if (emAnalise !== Boolean(fig.dataset.analise)) {
    if (emAnalise) { fig.dataset.analise = '1'; fig.dataset.antes = fig.dataset.ampliada ?? 'false'; fig.dataset.ampliada = 'true'; }
    else { delete fig.dataset.analise; fig.dataset.ampliada = fig.dataset.antes ?? 'false'; }
  }
}

// analise no estilo da mesa do video: grade e varredura enquanto olha; depois,
// painel "ANALISE COMPLETA" com o resultado (o texto e o que o modelo local disse)
function quebrarLinhas(g, texto, largura) {
  const linhas = [];
  let atual = '';
  for (const p of texto.split(/\s+/)) {
    const tentativa = atual ? `${atual} ${p}` : p;
    if (g.measureText(tentativa).width > largura && atual) { linhas.push(atual); atual = p; } else atual = tentativa;
  }
  if (atual) linhas.push(atual);
  return linhas;
}
function desenharAnalise(g, w, h, caixa) {
  const v = loja.estado?.visao ?? {};
  const agoraS = Date.now() / 1000;
  const [rx, ry, rw, rh] = caixa;
  const X = rx * w, Y = ry * h, W = rw * w, H = rh * h;
  if (v.estado === 'analisando' || v.estado === 'olhando') {
    g.save();
    g.strokeStyle = 'rgba(61,139,255,0.35)';
    g.lineWidth = 1;
    for (let i = 1; i < 8; i++) {
      g.beginPath(); g.moveTo(X + (W * i) / 8, Y); g.lineTo(X + (W * i) / 8, Y + H); g.stroke();
      g.beginPath(); g.moveTo(X, Y + (H * i) / 8); g.lineTo(X + W, Y + (H * i) / 8); g.stroke();
    }
    const fase = ((performance.now() / 1400) % 1);
    const yv = Y + H * fase;
    const grad = g.createLinearGradient(0, yv - 18, 0, yv + 2);
    grad.addColorStop(0, 'rgba(95,211,255,0)'); grad.addColorStop(1, 'rgba(95,211,255,0.45)');
    g.fillStyle = grad; g.fillRect(X, yv - 18, W, 20);
    g.strokeStyle = '#5fd3ff'; g.lineWidth = 2; g.shadowColor = '#5fd3ff'; g.shadowBlur = 10;
    g.beginPath(); g.moveTo(X, yv); g.lineTo(X + W, yv); g.stroke();
    g.shadowBlur = 14; g.strokeStyle = '#3d8bff'; g.strokeRect(X, Y, W, H);
    g.restore();
    g.fillStyle = '#5fd3ff'; g.font = '700 11px Bahnschrift, Segoe UI';
    g.fillText('ANALISANDO…', X + 6, Y + H - 8);
  } else if (v.estado === 'pronto' && v.resposta && v.em && agoraS - v.em < 20) {
    const pad = 10;
    g.font = '13px Segoe UI';
    const linhas = quebrarLinhas(g, v.resposta, w - 4 * pad).slice(0, 4);
    const ph = 30 + linhas.length * 17 + pad;
    const py = h - ph - 8;
    g.fillStyle = 'rgba(12,40,110,0.82)';
    g.fillRect(pad, py, w - 2 * pad, ph);
    g.strokeStyle = '#3d8bff'; g.lineWidth = 1.5; g.shadowColor = '#3d8bff'; g.shadowBlur = 12;
    g.strokeRect(pad, py, w - 2 * pad, ph);
    g.shadowBlur = 0;
    g.fillStyle = '#5fd3ff'; g.font = '700 11px Bahnschrift, Segoe UI';
    g.fillText(`ANÁLISE COMPLETA${v.duracao_s ? ` · ${String(v.duracao_s).replace('.', ',')} s` : ''}`, pad * 2, py + 18);
    g.fillStyle = '#e8f4ff'; g.font = '13px Segoe UI';
    linhas.forEach((l, i) => g.fillText(l, pad * 2, py + 36 + i * 17));
  }
}

function renderAvisos(est) {
  const n = est.notificacoes?.nao_lidas ?? 0;
  const ultimo = est.notificacoes?.itens?.[0];
  chip('c-not', n ? (ultimo?.nivel === 'erro' ? 'erro' : 'aviso') : 'off', `${n} aviso${n === 1 ? '' : 's'}`);
  el('c-not').title = ultimo ? `Último: ${ultimo.texto}` : 'Sem avisos';
}

// regua virtual: contorno medido (ou a folha de referencia) com a medida, por 20 s
function desenharMedida(g, w, h) {
  const m = loja.medida;
  if (!m?.cantos || performance.now() - m.recebida > 20000) return;
  const p = m.cantos.map(([x, y]) => [x * w, y * h]);
  g.save();
  g.strokeStyle = '#39ff6a'; g.lineWidth = 2; g.shadowColor = '#39ff6a'; g.shadowBlur = 8;
  g.setLineDash([8, 4]);
  g.beginPath(); p.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.closePath(); g.stroke();
  g.setLineDash([]); g.shadowBlur = 0;
  for (const [x, y] of p) { g.beginPath(); g.arc(x, y, 3.5, 0, Math.PI * 2); g.fillStyle = '#39ff6a'; g.fill(); }
  g.font = '700 12px Bahnschrift, Segoe UI';
  const topo = p.reduce((a, b) => (b[1] < a[1] ? b : a));
  const tw = g.measureText(m.rotulo).width + 10;
  g.fillStyle = 'rgba(0,20,8,0.8)'; g.fillRect(topo[0] - tw / 2, Math.max(0, topo[1] - 24), tw, 17);
  g.fillStyle = '#39ff6a'; g.fillText(m.rotulo, topo[0] - tw / 2 + 5, Math.max(12, topo[1] - 11));
  g.restore();
}

// visao em tempo real: caixas do detector local (ambar; pessoa em vermelho com o vigia armado)
function desenharDeteccoes(g, w, h) {
  const d = loja.deteccoes;
  const viva = d && performance.now() - d.em < 1500;
  if (viva && d.lista.length) {
    g.save();
    g.font = '600 10px Bahnschrift, Segoe UI';
    for (const o of d.lista) {
      const x = o.x * w, y = o.y * h, ow = o.w * w, oh = o.h * h;
      const alerta = d.vigia && o.classe === 0;
      const cor = alerta ? '#ff4d5e' : '#ffc857';
      const k = Math.min(ow, oh) * 0.18;
      g.globalAlpha = 0.45 + 0.55 * Math.min(1, (o.conf - 0.4) / 0.5);
      g.strokeStyle = cor; g.lineWidth = alerta ? 2 : 1.3; g.shadowColor = cor; g.shadowBlur = 5;
      g.beginPath();
      for (const [cx, cy, dx, dy] of [[x, y, 1, 1], [x + ow, y, -1, 1], [x, y + oh, 1, -1], [x + ow, y + oh, -1, -1]]) {
        g.moveTo(cx + dx * k, cy); g.lineTo(cx, cy); g.lineTo(cx, cy + dy * k);
      }
      g.stroke();
      g.shadowBlur = 0;
      const rot = `${o.nome.toUpperCase()} ${Math.round(o.conf * 100)}%`;
      const ly = y + oh + 13 > h ? Math.max(11, y - 4) : y + oh + 12;
      g.fillStyle = 'rgba(20,12,0,0.7)'; g.fillRect(x, ly - 10, g.measureText(rot).width + 8, 13);
      g.fillStyle = cor; g.fillText(rot, x + 4, ly);
    }
    g.restore();
  }
  if (viva || d?.vigia) {
    g.save();
    g.font = '600 10px Bahnschrift, Segoe UI';
    g.textAlign = 'right';
    g.fillStyle = d.vigia ? '#ff4d5e' : 'rgba(255,200,87,0.85)';
    const status = d.vigia ? 'MODO VIGIA ARMADO' : `VISÃO AO VIVO · ${d.lista.length} OBJ · ${d.ms} MS`;
    g.fillText(status, w - 8, h - 8);
    g.restore();
  }
}

// quem e: casa o rosto da camera com o reconhecimento mais recente (so cadastrados tem nome)
function rotuloDoRosto(r) {
  const id = loja.identidades;
  if (!id || performance.now() - id.em > 3000) return null;
  let melhor = null, nota = 0;
  for (const p of id.lista) {
    const ix = Math.max(0, Math.min(r.x + r.w, p.x + p.w) - Math.max(r.x, p.x));
    const iy = Math.max(0, Math.min(r.y + r.h, p.y + p.h) - Math.max(r.y, p.y));
    const inter = ix * iy, uniao = r.w * r.h + p.w * p.h - inter;
    if (uniao > 0 && inter / uniao > nota) { nota = inter / uniao; melhor = p; }
  }
  if (!melhor || nota < 0.2) return null;
  return { texto: String(melhor.rotulo || 'desconhecido').toUpperCase(), conhecido: Boolean(melhor.nome) };
}

// overlay da camera: colchetes de rastreamento nos rostos detectados
const camOverlay = el('cam-overlay');
function desenharRostos() {
  requestAnimationFrame(desenharRostos);
  if (document.hidden || el('camera').classList.contains('oculto')) return;
  const w = camOverlay.clientWidth;
  const h = camOverlay.clientHeight;
  if (camOverlay.width !== w) camOverlay.width = w;
  if (camOverlay.height !== h) camOverlay.height = h;
  const g = camOverlay.getContext('2d');
  g.clearRect(0, 0, w, h);
  if (loja.prefs?.visao_automatica) {                // regiao do olhar automatico
    const [rx, ry, rw, rh] = { centro: [0.22, 0.15, 0.56, 0.70], mesa: [0.12, 0.52, 0.76, 0.46],
                               inteira: [0.005, 0.005, 0.99, 0.99] }[loja.prefs.visao_regiao] ?? [0.22, 0.15, 0.56, 0.70];
    const fase = loja.estado?.visao?.olhar;
    const analisando = loja.estado?.visao?.estado === 'analisando';
    const corR = analisando ? '#ffb547' : '#32e8f3';
    g.strokeStyle = corR;
    g.globalAlpha = 0.8;
    g.setLineDash([6, 5]);
    g.lineWidth = 1.5;
    g.strokeRect(rx * w, ry * h, rw * w, rh * h);
    g.setLineDash([]);
    g.fillStyle = corR;
    g.font = '600 10px Bahnschrift, Segoe UI';
    const rot = analisando ? 'ANALISANDO…' : fase === 'aprendendo' ? 'REGIÃO DE VISÃO · APRENDENDO O FUNDO'
      : fase === 'candidato' ? 'OBJETO? SEGURE PARADO' : 'REGIÃO DE VISÃO';
    g.fillText(rot, rx * w + 4, ry * h + 12);
    g.globalAlpha = 1;
  }
  const caixaVisao = loja.prefs?.visao_automatica
    ? ({ centro: [0.22, 0.15, 0.56, 0.70], mesa: [0.12, 0.52, 0.76, 0.46], inteira: [0.005, 0.005, 0.99, 0.99] }[loja.prefs.visao_regiao]
       ?? [0.22, 0.15, 0.56, 0.70])
    : [0.005, 0.005, 0.99, 0.99];                          // pedido manual ("o que e isso?"): o quadro todo
  desenharAnalise(g, w, h, caixaVisao);
  const pc = loja.estado?.percepcao;
  if (pc?.em && Date.now() / 1000 - pc.em < 180 && loja.estado?.visao?.estado !== 'analisando') {
    g.save();
    g.font = '600 10px Bahnschrift, Segoe UI';
    for (const o of pc.objetos ?? []) {
      const x = o.x * w, y = o.y * h, ow = o.w * w, oh = o.h * h;
      const k = Math.min(ow, oh) * 0.22;
      g.strokeStyle = '#39ff6a'; g.lineWidth = 1.5; g.shadowColor = '#39ff6a'; g.shadowBlur = 6;
      g.beginPath();
      for (const [cx, cy, dx, dy] of [[x, y, 1, 1], [x + ow, y, -1, 1], [x, y + oh, 1, -1], [x + ow, y + oh, -1, -1]]) {
        g.moveTo(cx + dx * k, cy); g.lineTo(cx, cy); g.lineTo(cx, cy + dy * k);
      }
      g.stroke();
      g.shadowBlur = 0;
      const rot = (o.nome + (o.detalhe ? ` · ${o.detalhe}` : '')).toUpperCase().slice(0, 42);
      const tw = g.measureText(rot).width + 8;
      g.fillStyle = 'rgba(2,20,10,0.75)'; g.fillRect(x, Math.max(0, y - 15), tw, 14);
      g.fillStyle = '#39ff6a'; g.fillText(rot, x + 4, Math.max(10, y - 4));
    }
    g.restore();
  }
  desenharDeteccoes(g, w, h);
  desenharMedida(g, w, h);
  const vivo = performance.now() - loja.rostos.em < 800;
  for (const r of vivo ? loja.rostos.lista : []) {
    const x = r.x * w, y = r.y * h, rw = r.w * w, rh = r.h * h;
    const k = Math.min(rw, rh) * 0.25;
    g.strokeStyle = '#32e8f3';
    g.lineWidth = 2;
    g.shadowColor = '#32e8f3';
    g.shadowBlur = 8;
    g.beginPath();
    for (const [cx, cy, dx, dy] of [[x, y, 1, 1], [x + rw, y, -1, 1], [x, y + rh, 1, -1], [x + rw, y + rh, -1, -1]]) {
      g.moveTo(cx + dx * k, cy); g.lineTo(cx, cy); g.lineTo(cx, cy + dy * k);
    }
    g.stroke();
    g.shadowBlur = 0;
    g.beginPath();                                    // retícula no centro
    g.arc(x + rw / 2, y + rh / 2, Math.min(rw, rh) * 0.06, 0, Math.PI * 2);
    g.stroke();
    g.fillStyle = '#32e8f3';
    g.font = '600 11px Bahnschrift, Segoe UI';
    const quem = rotuloDoRosto(r);
    if (quem) { g.fillStyle = quem.conhecido ? '#39ff6a' : '#ffc857'; }
    g.fillText(quem ? quem.texto : `ROSTO${r.confianca != null ? ` ${Math.round(r.confianca * 100)}%` : ''}`, x, Math.max(12, y - 5));
  }
}
requestAnimationFrame(desenharRostos);

// forma de onda: voce (ciano) e Jarvis (ambar); sem sinal, linha reta = silencio
const ondaCanvas = el('onda');
let ultimaOnda = 0;
function desenharOnda(agora) {
  requestAnimationFrame(desenharOnda);
  const oculta = loja.prefs?.widgets_jarvis?.onda === false;
  el('w-onda').classList.toggle('oculto', oculta);
  const fps = { economico: 15, equilibrado: 30, cinematografico: 60 }[loja.prefs?.perfil_grafico] ?? 30;
  if (oculta || document.hidden || agora - ultimaOnda < 1000 / fps - 1) return;
  ultimaOnda = agora;
  const w = ondaCanvas.clientWidth, h = ondaCanvas.clientHeight;
  if (ondaCanvas.width !== w) ondaCanvas.width = w;
  if (ondaCanvas.height !== h) ondaCanvas.height = h;
  const g = ondaCanvas.getContext('2d');
  g.clearRect(0, 0, w, h);
  g.strokeStyle = 'rgba(50,232,243,0.12)';
  g.beginPath(); g.moveTo(0, h / 2); g.lineTo(w, h / 2); g.stroke();
  for (const [fonte, cor, ganho] of [['entrada', '#32e8f3', 3.5], ['saida', '#ffb547', 1.6]]) {
    const n = loja.niveis[fonte];
    const onda = agora - n.em < 250 ? n.onda : null;
    g.strokeStyle = cor;
    g.lineWidth = 1.6;
    g.globalAlpha = onda ? 0.95 : 0.35;
    g.beginPath();
    const pts = onda ?? new Array(48).fill(0);
    pts.forEach((v, i) => {
      const x = (i / (pts.length - 1)) * w;
      const y = h / 2 - Math.max(-1, Math.min(1, v * ganho)) * (h / 2 - 6);
      if (i) g.lineTo(x, y); else g.moveTo(x, y);
    });
    g.stroke();
  }
  g.globalAlpha = 1;
}
requestAnimationFrame(desenharOnda);

function render() {
  chip('c-rt', loja.conectado ? 'ok' : 'erro', loja.conectado ? 'Runtime' : 'Runtime desconectado');
  const est = loja.estado;
  if (!est) return;
  if (!est.boot?.concluido) bootVistoEmAndamento = true;
  else if (bootVistoEmAndamento) {
    bootVistoEmAndamento = false;
    anuncioAte = Date.now() + 4500;                 // anuncia uma vez, por 4,5 s
  }
  let p = loja.conectado ? estadoPrincipal(est) : { id: 'erro', texto: 'Desconectado', sub: 'o runtime não está respondendo' };
  if (loja.conectado && Date.now() < anuncioAte && p.id !== 'falando') {
    const etapas = est.boot?.etapas ?? [];
    const ok = etapas.filter((e) => e.estado === 'ok').length;
    p = est.boot.resultado === 'online'
      ? { id: 'online', texto: 'Sistema online', sub: `${ok} de ${etapas.length} verificações ok` }
      : { id: 'limitado', texto: 'Online com limitações',
          sub: etapas.filter((e) => e.estado !== 'ok').map((e) => e.rotulo).join(', ') };
  }
  const e = el('estado');
  e.dataset.id = p.id;
  texto('estado', p.texto);
  texto('sub', p.sub ?? '');
  if (principalAnterior && principalAnterior !== p.id) tique(p.id === 'falando' ? 660 : 880);
  principalAnterior = p.id;
  renderChips(est);
  renderBoot(est);
  renderInstrumentos(est);
  renderControles(est);
  renderCamera(est);
  renderAvisos(est);
  renderContexto(est);
}

// painel de contexto: o que o Jarvis acabou de listar (noticias, fontes, cotacoes)
let contextoFechado = 0;
function renderContexto(est) {
  const c = est.contexto ?? {};
  const vivo = Boolean(c.em && Date.now() / 1000 - c.em < 90 && c.em !== contextoFechado && (c.itens ?? []).length);
  el('w-contexto').classList.toggle('oculto', !vivo);
  if (!vivo) return;
  const lista = el('ctx-lista');
  if (lista.dataset.cache === String(c.em)) return;
  lista.dataset.cache = String(c.em);
  texto('ctx-titulo', c.titulo ?? '');
  const seguro = (u) => (typeof u === 'string' && /^https:\/\//.test(u) ? u : null);
  lista.innerHTML = c.itens.map((x) => {
    const link = seguro(x.link);
    const t = link ? `<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${esc(x.titulo)}</a>` : esc(x.titulo);
    return `<li>${t}${x.detalhe ? `<small>${esc(x.detalhe)}</small>` : ''}<small>${esc(x.fonte ?? '')}</small></li>`;
  }).join('');
}
el('ctx-fechar').addEventListener('click', () => {
  contextoFechado = loja.estado?.contexto?.em ?? 0;
  el('w-contexto').classList.add('oculto');
});

// manchetes correndo (G1, BBC)
function renderNoticias() {
  const n = loja.telemetria?.noticias;
  const faixa = n?.status === 'medido' ? n.itens.slice(0, 12).map((x) => `${x.fonte} · ${x.titulo}`).join('   ◆   ') : '';
  const p = el('nt-texto');
  if (p.dataset.cache !== faixa) {
    p.dataset.cache = faixa;
    p.textContent = faixa;
    p.style.animationDuration = `${Math.max(40, faixa.length / 9)}s`;
  }
  el('w-noticias').classList.toggle('oculto', !faixa);
}

function renderWidgets() {
  renderNoticias();
  renderAgora();
  renderEnergia();
  renderMidia();
}
setInterval(() => { renderAgora(); if (Date.now() < anuncioAte + 600) render(); }, 1000);

// barras de nivel: 10 Hz, leem os niveis reais sem re-renderizar o resto
function barras() {
  const agora = performance.now();
  for (const [fonte, id] of [['entrada', 'mic-nivel'], ['saida', 'out-nivel']]) {
    const n = loja.niveis[fonte];
    const v = agora - n.em < 300 ? Math.min(1, Math.sqrt(n.rms) * 2.2) : 0;
    el(id).style.width = `${(v * 100).toFixed(0)}%`;
  }
}
setInterval(barras, 100);
setInterval(() => { if (loja.estado) { renderInstrumentos(loja.estado); renderContexto(loja.estado); } }, 1000);   // "ha X s"
setInterval(() => texto('fps', String(nucleo.fps() || TRACO)), 2000);

function escapar(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

// ---------------------------------------------------------------------------
// preferencias
function preencherPrefs() {
  const p = loja.prefs;
  if (!p) return;
  nucleo.definirPerfil(p.perfil_grafico);
  const f = el('f-prefs');
  const sel = el('sel-modelo');
  const instalados = loja.telemetria?.ollama?.instalados?.map((m) => m.nome) ?? [];
  const opcoes = [...new Set([...instalados, p.modelo_voz])];
  const html = opcoes.map((n) => `<option value="${escapar(n)}">${escapar(n)}${instalados.includes(n) ? '' : ' (não instalado)'}</option>`).join('');
  if (sel.dataset.cache !== html) { sel.innerHTML = html; sel.dataset.cache = html; }
  for (const campo of f.elements) {
    if (!campo.name || campo === document.activeElement) continue;
    const [a, b] = campo.name.split('.');
    const v = b ? p[a]?.[b] : p[a];
    if (campo.type === 'checkbox') campo.checked = Boolean(v);
    else if (v !== undefined) campo.value = String(v);
  }
}

el('f-prefs').addEventListener('change', async (ev) => {
  const c = ev.target;
  if (!c.name) return;
  const [a, b] = c.name.split('.');
  let v = c.type === 'checkbox' ? c.checked : c.type === 'range' || c.type === 'number' ? Number(c.value) : c.value;
  const corpo = b ? { [a]: { ...(loja.prefs?.[a] ?? {}), [b]: v } } : { [a]: v };
  try {
    await acao('/api/preferencias', corpo);
    texto('prefs-msg', 'Salvo.');
    if (a === 'tema' && v === 'classico') location.href = '/jarvis';
  } catch (e) {
    texto('prefs-msg', `Não salvou: ${e.message}`);
  }
});
el('f-prefs').addEventListener('submit', (e) => e.preventDefault());

// ---------------------------------------------------------------------------
// controles
el('b-mic').addEventListener('click', async () => {
  const ligado = el('b-mic').getAttribute('aria-pressed') === 'true';
  try { await acao('/api/microfone', { ativo: !ligado }); }
  catch (e) { texto('sub', `Microfone: ${e.message}`); }
});

const vol = el('vol');
let tVol = 0;
vol.addEventListener('pointerdown', () => { arrastandoVolume = true; });
vol.addEventListener('pointerup', () => { arrastandoVolume = false; });
vol.addEventListener('input', () => {
  clearTimeout(tVol);
  tVol = setTimeout(() => acao('/api/audio/volume', { volume: Number(vol.value) / 100 }).catch(() => {}), 150);
});

el('b-parar').addEventListener('click', () => acao('/api/audio/parar').catch(() => {}));

// comando digitado: mesmo caminho da voz (o Jarvis faz e responde falando)
el('f-comando').addEventListener('submit', async (e) => {
  e.preventDefault();
  const campo = el('cmd-texto');
  const txt = campo.value.trim();
  if (!txt) return;
  campo.value = '';
  campo.placeholder = 'Executando…';
  try { await acao('/api/comando', { texto: txt }); }
  catch (err) { texto('sub', `Comando: ${err.message}`); }
  finally { campo.placeholder = 'Fale com o Jarvis… ou digite aqui'; }
});

el('b-cam').addEventListener('click', () => {
  const ligada = el('b-cam').getAttribute('aria-pressed') === 'true';
  acao('/api/camera', { ativa: !ligada }).catch((e) => texto('sub', `Câmera: ${e.message}`));
});
el('b-capacete').addEventListener('click', () =>
  alternarCapacete().catch((e) => texto('sub', `Câmera: ${e.message}`)));
el('b-cam-ampliar').addEventListener('click', () => {
  const fig = el('camera');
  const amp = fig.dataset.ampliada !== 'true';
  fig.dataset.ampliada = String(amp);
  el('b-cam-ampliar').setAttribute('aria-pressed', String(amp));
  texto('b-cam-ampliar', amp ? 'Reduzir' : 'Ampliar');
});
for (const [id, op] of [['md-ant', 'anterior'], ['md-play', 'tocar_pausar'], ['md-prox', 'proxima']]) {
  el(id).addEventListener('click', () => acao('/api/midia', { acao: op }).catch(() => {}));
}
el('c-not').addEventListener('click', () => {
  acao('/api/notificacoes', { acao: 'lidas' }).catch(() => {});
  acao('/api/janela', { nome: 'painel' }).catch(() => {});
});
el('b-chat').addEventListener('click', () => acao('/api/janela', { nome: 'chat' }).catch((e) => texto('sub', e.message)));
el('b-painel').addEventListener('click', () => acao('/api/janela', { nome: 'painel' }).catch((e) => texto('sub', e.message)));

el('b-tela').addEventListener('click', async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  } catch { /* recusado pelo navegador */ }
});
document.addEventListener('fullscreenchange', () =>
  el('b-tela').setAttribute('aria-pressed', String(Boolean(document.fullscreenElement))));

const gaveta = el('gaveta');
function abrirGaveta(abrir) {
  gaveta.dataset.aberta = String(abrir);
  el('b-prefs').setAttribute('aria-expanded', String(abrir));
  if (abrir) { preencherPrefs(); gaveta.querySelector('select, input')?.focus(); }
  else el('b-prefs').focus();
}
el('b-prefs').addEventListener('click', () => abrirGaveta(gaveta.dataset.aberta !== 'true'));
el('b-fechar').addEventListener('click', () => abrirGaveta(false));
addEventListener('keydown', (e) => { if (e.key === 'Escape' && gaveta.dataset.aberta === 'true') abrirGaveta(false); });

el('b-pular').addEventListener('click', () => {
  const secao = el('boot');
  if (loja.estado?.boot?.concluido) {
    secao.dataset.fechado = secao.dataset.fechado === 'true' ? 'false' : 'true';
    bootFechadoPeloUsuario = secao.dataset.fechado === 'true';
    render();
  } else {
    nucleo.pularBoot();                      // so a animacao; a verificacao continua
    el('b-pular').disabled = true;
    el('b-pular').textContent = 'Animação pulada';
  }
});

el('b-desligar').addEventListener('click', async () => {
  if (!confirm('Desligar o Jarvis? A conversa por voz e as telas param. O chat e o servidor continuam.')) return;
  try { await acao('/api/desligar'); } catch { /* ja caindo */ }
  const aviso = document.createElement('p');
  aviso.className = 'titulo desligado';
  aviso.textContent = 'Jarvis desligado · pode fechar esta janela';
  document.body.replaceChildren(aviso);
});

// ---------------------------------------------------------------------------
ouvir((tipo) => {
  if (tipo === 'prefs' || tipo === 'telemetria') preencherPrefs();
  if (tipo === 'prefs' || tipo === 'telemetria') renderWidgets();
  if (tipo === 'prefs') prefsCapacete();
  render();
});
iniciarCapacete(() => { if (loja.estado) renderCamera(loja.estado); });
conectar();

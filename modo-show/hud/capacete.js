// Visao do capacete, na linguagem dos filmes do Homem de Ferro (HUDs da
// Cantina Creative / Jayse Hansen): quando a camera ve um rosto, a tela vira o
// interior do capacete.
//
// - camadas em profundidades diferentes: o que esta preso ao rosto segue a
//   cabeca exatamente; os paineis (camada de perto) seguem pouco e com atraso;
//   a faixa de giro, o aro do visor e a "prateleira" da base quase nao se mexem
// - entrada "de longe" quando o capacete fecha: aneis crescem a partir da
//   profundidade e os paineis chegam escalonados
// - branco com acentos ciano, ambar para destaque, vermelho para alerta
//
// Todo numero vem da telemetria real; aneis, riscos e varreduras sao so
// decoracao. Giro, inclinacao e distancia da cabeca sao estimativas
// geometricas (pontos do YuNet) e aparecem marcadas "est.". Nada e gravado:
// a imagem e o mesmo MJPEG local do preview da camera.

import {
  loja, acao, estadoPrincipal, inferenciaAtiva, el, texto, escapar as esc, iconeClima, TOKEN_CAMERA,
  TRACO, taxa, movimentoReduzido, haQuanto, aoComando,
} from './cliente.js';

const TAU = Math.PI * 2;
const COR = { ciano: '#32e8f3', branco: '#eaf9ff', ambar: '#ffb547', vermelho: '#ff4a57' };
const GRACA_MS = 2500;        // sem rosto por este tempo, o capacete fecha (modo automatico)
const ENTRADA_MS = 1400;      // animacao de "capacete fechando"
const IPD_MM = 63;            // distancia media entre as pupilas de um adulto
const FOV_H = 70;             // campo de visao horizontal tipico de webcam de notebook (graus)
const FPS = { economico: 15, equilibrado: 30, cinematografico: 60 };
const MONO = '"Cascadia Mono", Consolas, monospace';
const TIT = 'Bahnschrift, "Segoe UI", sans-serif';

const raiz = el('capacete');
const img = el('cap-img');
const tela = el('cap-tela');
const g = tela.getContext('2d');
const ondaCv = el('cap-onda');
const og = ondaCv.getContext('2d');
const radarCv = el('cap-radar-cv');
const rg = radarCv.getContext('2d');

// colunas: esquerda (avisos, armadura, hora) e direita (comunicacao, diagnostico, radar)
const PAINEIS = [
  ['cap-alerta', -1], ['cap-armadura', -1], ['cap-hora', -1],
  ['cap-com', 1], ['cap-diag', 1], ['cap-radar', 1],
].map(([id, lado]) => ({ id, lado, e: el(id), w: 250, h: 120, x: 0, y: 0 }));

let ativo = false;
let forcado = false;          // botao "Capacete": mostra mesmo sem rosto
let dispensado = false;       // "Sair": fica fechado ate o rosto sumir e voltar
let pedidoEm = -1e9;          // quando o botao pediu para ligar a camera
let ultimoRosto = -1e9;       // performance.now() da ultima deteccao
let emVisto = 0;
let entradaEm = -1e9;
let ultimoQuadro = 0;
let tAnterior = 0;
let fase = 0;                 // tempo das animacoes (s)
let aoMudar = () => {};
let ultimaPose = null;

// rosto suavizado (coordenadas normalizadas da imagem ja espelhada) e a
// "camada de perto", que segue o rosto devagar
const s = { ok: false, x: 0.4, y: 0.3, w: 0.2, h: 0.3, p: null, conf: null, extras: 0 };
const perto = { x: 0, y: 0, ok: false };

export function capaceteAtivo() { return ativo; }

// ---------------------------------------------------------------------------
// ativacao
function deveMostrar(agora) {
  const cam = loja.estado?.camera;
  const modo = loja.prefs?.capacete ?? 'automatico';
  if (!cam?.ativa) {
    // o botao liga a camera e o estado demora um instante para chegar
    if (agora - pedidoEm > 8000) { forcado = false; dispensado = false; }
    return false;
  }
  if (forcado) return true;
  if (modo === 'desligado') return false;
  if (modo === 'sempre') return !dispensado;
  const visto = agora - ultimoRosto < GRACA_MS;
  if (!visto) dispensado = false;          // rosto sumiu: na proxima vez o capacete volta
  return visto && !dispensado;
}

function entrada() {
  entradaEm = performance.now();
  raiz.dataset.boot = 'false';
  void raiz.offsetWidth;                   // reinicia a animacao CSS
  raiz.dataset.boot = 'true';
  clearTimeout(entrada.t);
  entrada.t = setTimeout(() => { raiz.dataset.boot = 'false'; }, ENTRADA_MS + 400);
}

function definirAtivo(v) {
  if (v === ativo) return;
  ativo = v;
  raiz.dataset.ativo = String(v);
  raiz.setAttribute('aria-hidden', String(!v));
  document.body.dataset.capacete = String(v);
  if (v) { medirPaineis(); atualizarDados(); entrada(); }
  ligarImagem();
  aoMudar(v);
}

function ligarImagem() {
  const comImagem = loja.prefs?.capacete_imagem !== false;
  raiz.dataset.imagem = String(comImagem);
  raiz.dataset.espelho = String(loja.prefs?.espelhar_camera !== false);
  if (ativo && comImagem && !img.dataset.ligada) {
    img.src = '/api/camera.mjpg';
    img.dataset.ligada = '1';
  } else if (!(ativo && comImagem) && img.dataset.ligada) {
    img.removeAttribute('src');           // fecha o stream
    delete img.dataset.ligada;
  }
}

function dispensar() { forcado = false; dispensado = true; definirAtivo(false); }

/** Botao "Capacete" da barra: abre (ligando a camera se preciso) ou fecha. */
export async function alternarCapacete() {
  if (ativo) { dispensar(); return; }
  dispensado = false;
  forcado = true;
  pedidoEm = performance.now();
  if (!loja.estado?.camera?.ativa) await acao('/api/camera', { ativa: true });
}

// ---------------------------------------------------------------------------
// rosto: o maior (o mais perto), suavizado entre as deteccoes (~10 Hz)
function lerRosto(agora) {
  const r = loja.rostos;
  if (r.em !== emVisto) {
    emVisto = r.em;
    if (r.lista.length) {
      if (ativo && agora - ultimoRosto > GRACA_MS) entrada();   // readquiriu
      ultimoRosto = agora;
    }
  }
  if (!r.lista.length || agora - r.em > 700) return null;
  const f = r.lista.reduce((a, b) => (b.w * b.h > a.w * a.h ? b : a));
  const esp = loja.prefs?.espelhar_camera !== false;
  const X = (x) => (esp ? 1 - x : x);
  return {
    x: esp ? 1 - f.x - f.w : f.x, y: f.y, w: f.w, h: f.h, conf: f.confianca,
    p: f.pontos ? f.pontos.map(([x, y]) => [X(x), y]) : null,
    extras: r.lista.length - 1,
  };
}

function suavizar(a, dt) {
  if (!a) return;
  const k = s.ok ? 1 - Math.exp(-dt * 14) : 1;
  for (const c of ['x', 'y', 'w', 'h']) s[c] += (a[c] - s[c]) * k;
  if (a.p) {
    s.p = s.p && s.ok
      ? s.p.map((q, i) => [q[0] + (a.p[i][0] - q[0]) * k, q[1] + (a.p[i][1] - q[1]) * k])
      : a.p.map((q) => [...q]);
  } else s.p = null;
  s.conf = a.conf;
  s.extras = a.extras;
  s.ok = true;
}

// imagem 4:3 em object-fit: cover
function mapa(W, H) {
  const [rw, rh] = (loja.estado?.camera?.resolucao ?? '1280x720').split('x').map(Number);
  const iw = img.naturalWidth || rw || 1280;
  const ih = img.naturalHeight || rh || 720;
  const k = Math.max(W / iw, H / ih);
  const dw = iw * k;
  const dh = ih * k;
  const ox = (W - dw) / 2;
  const oy = (H - dh) / 2;
  return { dw, dh, iw, ih, x: (n) => ox + n * dw, y: (n) => oy + n * dh };
}

function calcularPose(m) {
  if (!s.p) return null;
  const P = s.p.map(([x, y]) => [m.x(x), m.y(y)]);
  let [a, b] = [P[0], P[1]];
  if (a[0] > b[0]) [a, b] = [b, a];                     // a = olho do lado esquerdo da tela
  const olhos = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
  const roll = (Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI;
  const meio = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const ux = (b[0] - a[0]) / olhos;
  const uy = (b[1] - a[1]) / olhos;
  // nariz fora do meio dos olhos ~ cabeca virada (a ponta do nariz fica ~0,6 IPD a frente)
  const desvio = ((P[2][0] - meio[0]) * ux + (P[2][1] - meio[1]) * uy) / olhos;
  const yaw = (Math.atan(desvio / 0.6) * 180) / Math.PI;
  const olhosCam = Math.hypot((s.p[1][0] - s.p[0][0]) * m.iw, (s.p[1][1] - s.p[0][1]) * m.ih);
  const focal = m.iw / 2 / Math.tan(((FOV_H / 2) * Math.PI) / 180);
  const distCm = (focal * IPD_MM) / (olhosCam * Math.cos((yaw * Math.PI) / 180)) / 10;
  return { P, a, b, olhos, roll, yaw, distCm, meio };
}

// ---------------------------------------------------------------------------
// desenho: camada distante (quase fixa no visor)
function aro(W, H, dx, alfa) {
  g.save();
  g.globalAlpha = alfa * 0.55;
  g.strokeStyle = 'rgba(234,249,255,0.5)';
  g.lineWidth = 1;
  const cx = W / 2 + dx;
  const cy = H * 0.9;
  const ry = cy - 30;
  g.beginPath(); g.ellipse(cx, cy, W * 0.75, ry, 0, Math.PI, TAU); g.stroke();
  g.globalAlpha = alfa * 0.3;
  g.beginPath(); g.ellipse(cx, cy + 8, W * 0.74, ry, 0, Math.PI, TAU); g.stroke();
  g.restore();
}

function faixaGiro(cx, y, largura, yaw, alfa) {
  const janela = 60;                                  // graus visiveis
  const pxg = largura / janela;
  g.save();
  g.lineWidth = 1;
  g.strokeStyle = COR.branco;
  g.fillStyle = COR.branco;
  g.font = `10px ${MONO}`;
  g.textAlign = 'center';
  g.globalAlpha = alfa * 0.6;
  g.beginPath(); g.moveTo(cx - largura / 2, y); g.lineTo(cx + largura / 2, y); g.stroke();
  for (let d = Math.ceil((yaw - janela / 2) / 5) * 5; d <= yaw + janela / 2; d += 5) {
    const x = cx + (d - yaw) * pxg;
    const apaga = Math.max(0, 1 - Math.abs(x - cx) / (largura / 2));
    g.globalAlpha = alfa * apaga;
    const grande = d % 15 === 0;
    g.beginPath(); g.moveTo(x, y); g.lineTo(x, y - (grande ? 10 : 5)); g.stroke();
    if (grande) g.fillText(String(((d % 360) + 360) % 360).padStart(3, '0'), x, y - 15);
  }
  g.globalAlpha = alfa;
  g.fillStyle = COR.ciano;
  g.beginPath(); g.moveTo(cx, y + 3); g.lineTo(cx - 6, y + 12); g.lineTo(cx + 6, y + 12); g.closePath(); g.fill();
  g.fillStyle = COR.branco;
  g.font = `600 10px ${TIT}`;
  g.fillText(`GIRO DA CABEÇA ${Math.round(yaw)}° · EST.`, cx, y + 26);
  g.restore();
}

function prateleira(cx, cy, rx, ry, t, alfa) {
  g.save();
  g.globalAlpha = alfa;
  for (const [k, a] of [[1, 0.85], [1.14, 0.45], [1.3, 0.22]]) {
    g.strokeStyle = `rgba(234,249,255,${a})`;
    g.lineWidth = k === 1 ? 1.5 : 1;
    g.beginPath(); g.ellipse(cx, cy, rx * k, ry * k, 0, 0, Math.PI); g.stroke();       // borda da frente
    g.globalAlpha = alfa * 0.3;
    g.beginPath(); g.ellipse(cx, cy, rx * k, ry * k, 0, Math.PI, TAU); g.stroke();     // borda do fundo
    g.globalAlpha = alfa;
  }
  g.strokeStyle = 'rgba(50,232,243,0.85)';
  g.beginPath();
  const desloc = (t * 0.06) % (Math.PI / 36);
  for (let i = 0; i < 36; i++) {                                                      // marcas girando
    const a = (i / 36) * Math.PI + desloc;
    const x = cx + Math.cos(a) * rx * 1.14;
    const y = cy + Math.sin(a) * ry * 1.14;
    g.moveTo(x, y); g.lineTo(x, y + (i % 6 === 0 ? 7 : 3));
  }
  g.stroke();
  g.translate(cx, cy);
  g.scale(1, ry / rx);
  const brilho = g.createRadialGradient(0, 0, 0, 0, 0, rx);
  brilho.addColorStop(0, 'rgba(50,232,243,0.16)');
  brilho.addColorStop(1, 'rgba(50,232,243,0)');
  g.fillStyle = brilho;
  g.beginPath(); g.arc(0, 0, rx, 0, TAU); g.fill();
  g.restore();
}

// camada do rosto -------------------------------------------------------------
function horizonte(cx, cy, R, roll, alfa) {
  g.save();
  g.translate(cx, cy);
  g.rotate((roll * Math.PI) / 180);
  g.globalAlpha = alfa;
  g.strokeStyle = 'rgba(234,249,255,0.8)';
  g.fillStyle = COR.branco;
  g.lineWidth = 1.2;
  const a = R * 1.32;
  const b = R * 1.95;
  g.beginPath();
  g.moveTo(-b, 0); g.lineTo(-a, 0); g.lineTo(-a, 7);
  g.moveTo(b, 0); g.lineTo(a, 0); g.lineTo(a, 7);
  g.stroke();
  g.lineWidth = 0.8;
  g.strokeStyle = 'rgba(234,249,255,0.38)';
  g.font = `9px ${MONO}`;
  g.textAlign = 'center';
  for (const k of [-2, -1, 1, 2]) {                   // escada: tracejada abaixo do horizonte
    const y = k * R * 0.42;
    const a2 = a + Math.abs(k) * 6;
    const b2 = a2 + R * 0.3;
    const ponta = k < 0 ? 6 : -6;
    g.setLineDash(k > 0 ? [4, 4] : []);
    g.beginPath();
    g.moveTo(-b2, y); g.lineTo(-a2, y); g.lineTo(-a2, y + ponta);
    g.moveTo(b2, y); g.lineTo(a2, y); g.lineTo(a2, y + ponta);
    g.stroke();
    g.globalAlpha = alfa * 0.5;
    g.fillText(String(Math.abs(k) * 10), -b2 - 11, y + 3);
    g.fillText(String(Math.abs(k) * 10), b2 + 11, y + 3);
    g.globalAlpha = alfa;
  }
  g.setLineDash([]);
  g.font = `600 10px ${TIT}`;
  g.textAlign = 'left';
  g.fillText(`INCL ${Math.round(roll)}° EST.`, b + 8, 3);
  g.restore();
}

function aneis(cx, cy, R, t, alfa, alerta) {
  g.save();
  g.translate(cx, cy);
  g.lineCap = 'round';
  g.globalAlpha = alfa * 0.7;
  g.strokeStyle = COR.branco;
  g.lineWidth = 1;
  g.beginPath(); g.arc(0, 0, R, 0, TAU); g.stroke();

  g.save();                                          // regua de marcas
  g.rotate(t * 0.12);
  g.globalAlpha = alfa * 0.6;
  g.beginPath();
  for (let i = 0; i < 120; i++) {
    const a = (i / 120) * TAU;
    const lon = i % 10 === 0 ? 10 : i % 5 === 0 ? 6 : 3;
    g.moveTo(Math.cos(a) * R * 1.08, Math.sin(a) * R * 1.08);
    g.lineTo(Math.cos(a) * (R * 1.08 + lon), Math.sin(a) * (R * 1.08 + lon));
  }
  g.stroke();
  g.restore();

  g.save();                                          // segmentos grossos
  g.rotate(-t * 0.25);
  g.strokeStyle = COR.ciano;
  g.lineWidth = 4;
  g.globalAlpha = alfa * 0.75;
  for (const [a0, len] of [[0, 0.9], [2.2, 0.5], [3.6, 1.3]]) {
    g.beginPath(); g.arc(0, 0, R * 1.2, a0, a0 + len); g.stroke();
  }
  g.restore();

  g.save();                                          // tracejado interno
  g.rotate(t * 0.4);
  g.setLineDash([2, 7]);
  g.lineWidth = 1.5;
  g.globalAlpha = alfa * 0.55;
  g.strokeStyle = COR.ciano;
  g.beginPath(); g.arc(0, 0, R * 0.9, 0, TAU); g.stroke();
  g.restore();

  g.save();                                          // motivo ambar
  g.rotate(-t * 0.08);
  g.strokeStyle = COR.ambar;
  g.fillStyle = COR.ambar;
  g.lineWidth = 2;
  g.globalAlpha = alfa * 0.85;
  g.beginPath(); g.arc(0, 0, R * 1.3, -0.35, 0.35); g.stroke();
  for (const a of [-0.5, 0.5, 0.62]) {
    g.beginPath(); g.arc(Math.cos(a) * R * 1.3, Math.sin(a) * R * 1.3, 2.4, 0, TAU); g.fill();
  }
  g.restore();

  if (alerta) {                                      // aviso nao lido: arco vermelho pulsando
    g.strokeStyle = COR.vermelho;
    g.lineWidth = 3;
    g.globalAlpha = alfa * (0.55 + 0.45 * Math.sin(t * 4));
    g.beginPath(); g.arc(0, 0, R * 1.38, Math.PI * 0.8, Math.PI * 1.15); g.stroke();
  }
  g.restore();
}

function mira(x, y, r, t, grande, alfa) {
  g.save();
  g.translate(x, y);
  g.globalAlpha = alfa;
  g.strokeStyle = COR.branco;
  g.lineWidth = 1.3;
  g.beginPath(); g.arc(0, 0, r, 0, TAU); g.stroke();
  g.fillStyle = COR.ciano;
  g.beginPath(); g.arc(0, 0, 1.8, 0, TAU); g.fill();
  g.save();
  g.rotate(t * (grande ? 0.9 : -0.7));
  g.setLineDash([r * 0.35, r * 0.25]);
  g.strokeStyle = COR.ciano;
  g.lineWidth = 2;
  g.beginPath(); g.arc(0, 0, r * 1.6, 0, TAU); g.stroke();
  g.restore();
  g.beginPath();
  for (const a of [0, Math.PI / 2, Math.PI, Math.PI * 1.5]) {
    g.moveTo(Math.cos(a) * r * 1.85, Math.sin(a) * r * 1.85);
    g.lineTo(Math.cos(a) * r * 2.25, Math.sin(a) * r * 2.25);
  }
  g.stroke();
  if (grande) {                                      // "scanner" do olho
    g.save();
    g.rotate(-t * 0.35);
    g.lineWidth = 2.5;
    g.strokeStyle = 'rgba(50,232,243,0.8)';
    g.beginPath(); g.arc(0, 0, r * 2.6, -0.6, 1.1); g.stroke();
    g.beginPath(); g.arc(0, 0, r * 2.6, 2.2, 3.0); g.stroke();
    g.lineWidth = 1;
    g.beginPath(); g.arc(0, 0, r * 3.0, 0.2, 2.6); g.stroke();
    g.restore();
  }
  g.restore();
}

// linhas angulares brancas sobre os olhos, como na referencia do filme
function angulares(pose, alfa) {
  const d = pose.olhos;
  const r = d * 0.15;
  g.save();
  g.translate(pose.meio[0], pose.meio[1]);
  g.rotate((pose.roll * Math.PI) / 180);
  g.globalAlpha = alfa * 0.85;
  g.strokeStyle = COR.branco;
  g.lineWidth = 1.3;
  const e = -d / 2;
  const dd = d / 2;
  g.beginPath();
  // faixa sobre as sobrancelhas, com o degrau no meio
  g.moveTo(e - r * 3.2, -r * 2.8); g.lineTo(-r * 1.2, -r * 2.8); g.lineTo(-r * 0.4, -r * 3.7);
  g.lineTo(r * 0.4, -r * 3.7); g.lineTo(r * 1.2, -r * 2.8); g.lineTo(dd + r * 2.4, -r * 2.8);
  // saidas para a direita (olho de fora)
  g.moveTo(dd + r * 2.4, -r * 2.8); g.lineTo(dd + r * 7, -r * 2.8); g.lineTo(dd + r * 9, -r * 1);
  g.moveTo(dd + r * 2.6, r * 2.5); g.lineTo(dd + r * 6, r * 2.5); g.lineTo(dd + r * 7.2, r * 3.7); g.lineTo(dd + r * 11, r * 3.7);
  // cantoneira do olho da esquerda
  g.moveTo(e - r * 3.2, -r * 1.2); g.lineTo(e - r * 3.2, r * 1.6); g.lineTo(e - r * 2.2, r * 2.6);
  g.stroke();
  g.fillStyle = COR.branco;
  for (const [x, y] of [[dd + r * 9, -r], [dd + r * 11, r * 3.7]]) { g.beginPath(); g.arc(x, y, 2, 0, TAU); g.fill(); }
  g.restore();
}

// "rosto holografico", para quando a imagem da camera esta oculta
function holograma(cx, cy, rx, ry, pose, alfa, brilho) {
  g.save();
  g.globalAlpha = alfa;
  g.strokeStyle = 'rgba(50,232,243,0.9)';
  g.lineWidth = 1.5;
  g.shadowColor = COR.ciano;
  g.shadowBlur = brilho ? 10 : 0;
  g.beginPath(); g.ellipse(cx, cy, rx, ry, 0, 0, TAU); g.stroke();
  g.shadowBlur = 0;
  g.lineWidth = 0.8;
  g.strokeStyle = 'rgba(50,232,243,0.35)';
  const giro = pose ? (pose.yaw * Math.PI) / 180 : 0;
  for (let i = -3; i <= 3; i++) {                    // meridianos (giram com a cabeca)
    const f = (i / 4) * (Math.PI / 2) + giro;
    if (Math.abs(f) >= Math.PI / 2) continue;
    g.beginPath();
    for (let k = 0; k <= 24; k++) {
      const tt = -1 + (k / 24) * 2;
      const x = cx + rx * Math.sin(f) * Math.sqrt(1 - tt * tt);
      const y = cy + ry * tt;
      if (k) g.lineTo(x, y); else g.moveTo(x, y);
    }
    g.stroke();
  }
  for (let j = -4; j <= 4; j++) {                    // paralelos
    const l = (j / 5) * (Math.PI / 2);
    const hw = rx * Math.cos(l);
    g.beginPath(); g.ellipse(cx, cy + ry * Math.sin(l), hw, hw * 0.12, 0, 0, Math.PI); g.stroke();
  }
  if (pose) {                                        // olhos, nariz e boca pelos pontos reais
    const { P, a, b, olhos, roll } = pose;
    g.strokeStyle = COR.branco;
    g.lineWidth = 1.2;
    for (const o of [a, b]) {
      g.beginPath(); g.ellipse(o[0], o[1], olhos * 0.2, olhos * 0.085, (roll * Math.PI) / 180, 0, TAU); g.stroke();
    }
    g.beginPath();
    g.moveTo(pose.meio[0], pose.meio[1]); g.lineTo(P[2][0], P[2][1]);
    const mx = (P[3][0] + P[4][0]) / 2;
    const my = (P[3][1] + P[4][1]) / 2;
    g.moveTo(P[3][0], P[3][1]); g.quadraticCurveTo(mx, my + olhos * 0.08, P[4][0], P[4][1]);
    g.stroke();
    g.fillStyle = COR.ciano;
    for (const q of P) { g.beginPath(); g.arc(q[0], q[1], 2.2, 0, TAU); g.fill(); }
  }
  g.restore();
}

function colchetes(x, y, w, h, cor, alfa, k = 0.22) {
  const d = Math.min(w, h) * k;
  g.save();
  g.globalAlpha = alfa;
  g.strokeStyle = cor;
  g.lineWidth = 1.6;
  g.beginPath();
  for (const [cx, cy, dx, dy] of [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]]) {
    g.moveTo(cx + dx * d, cy); g.lineTo(cx, cy); g.lineTo(cx, cy + dy * d);
  }
  g.stroke();
  g.restore();
}

function varredura(x, y, w, h, prog, alfa) {
  const yy = y + h * prog;
  const grad = g.createLinearGradient(0, yy - 34, 0, yy);
  grad.addColorStop(0, 'rgba(50,232,243,0)');
  grad.addColorStop(1, 'rgba(50,232,243,0.28)');
  g.save();
  g.globalAlpha = alfa;
  g.fillStyle = grad;
  g.fillRect(x, yy - 34, w, 34);
  g.strokeStyle = 'rgba(234,249,255,0.85)';
  g.lineWidth = 1;
  g.beginPath(); g.moveTo(x, yy); g.lineTo(x + w, yy); g.stroke();
  g.restore();
}

function conectores(cx, cy, R, alfa) {
  g.save();
  g.globalAlpha = alfa * 0.45;
  g.strokeStyle = COR.branco;
  g.fillStyle = COR.branco;
  g.lineWidth = 0.9;
  for (const p of PAINEIS) {
    if (p.e.offsetParent === null) continue;          // painel oculto (tela estreita)
    const ax = p.lado < 0 ? p.x + p.w * 0.95 : p.x + p.w * 0.05;
    const ay = p.y + Math.min(24, p.h / 2);
    const ang = Math.atan2(ay - cy, ax - cx);
    const sx = cx + Math.cos(ang) * R * 1.24;
    const sy = cy + Math.sin(ang) * R * 1.24;
    if ((p.lado < 0 && sx < ax + 30) || (p.lado > 0 && sx > ax - 30)) continue;   // rosto colado no painel
    const jx = ax - p.lado * 40;
    g.beginPath(); g.moveTo(sx, sy); g.lineTo(jx, ay); g.lineTo(ax, ay); g.stroke();
    g.beginPath(); g.arc(sx, sy, 1.8, 0, TAU); g.fill();
    g.beginPath(); g.arc(ax, ay, 2.4, 0, TAU); g.fill();
  }
  g.restore();
}

function procurando(cx, cy, R, t, alfa) {
  g.save();
  g.globalAlpha = alfa * (0.45 + 0.35 * Math.sin(t * 3));
  g.strokeStyle = COR.ciano;
  g.setLineDash([6, 10]);
  g.lineWidth = 1.5;
  g.beginPath(); g.arc(cx, cy, R, 0, TAU); g.stroke();
  g.setLineDash([]);
  g.fillStyle = COR.branco;
  g.font = `600 13px ${TIT}`;
  g.textAlign = 'center';
  g.fillText('PROCURANDO ROSTO…', cx, cy + R + 26);
  g.restore();
}

// "capacete fechando": linhas que se abrem do centro + clarao
function fechamento(W, H, prog) {
  if (prog >= 0.45) return;
  const e = prog / 0.45;
  g.save();
  g.globalAlpha = (1 - e) * 0.18;
  g.fillStyle = '#bff8ff';
  g.fillRect(0, 0, W, H);
  g.globalAlpha = 1 - e;
  g.strokeStyle = COR.branco;
  g.lineWidth = 1.5;
  const dy = (H / 2) * e;
  g.beginPath();
  g.moveTo(0, H / 2 - dy); g.lineTo(W, H / 2 - dy);
  g.moveTo(0, H / 2 + dy); g.lineTo(W, H / 2 + dy);
  g.stroke();
  g.restore();
}

function desenhar(agora, dt) {
  const dpr = loja.prefs?.perfil_grafico === 'economico' ? 1 : Math.min(devicePixelRatio || 1, 1.5);
  const W = tela.clientWidth;
  const H = tela.clientHeight;
  if (tela.width !== Math.round(W * dpr)) tela.width = Math.round(W * dpr);
  if (tela.height !== Math.round(H * dpr)) tela.height = Math.round(H * dpr);
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, W, H);

  const reduzido = movimentoReduzido();
  if (!reduzido) fase += dt;
  const t = fase;
  const m = mapa(W, H);
  const visto = agora - ultimoRosto < 900;
  const brilho = loja.prefs?.perfil_grafico !== 'economico';
  const prog = reduzido ? 1 : Math.min(1, (agora - entradaEm) / ENTRADA_MS);
  const e = 1 - (1 - prog) ** 3;

  // centro do rosto (ou do visor, sem rosto) e a camada de perto, que segue devagar
  let cx = W / 2;
  let cy = H * 0.45;
  let bx = 0; let by = 0; let bw = 0; let bh = 0;
  if (s.ok) {
    bx = m.x(s.x); by = m.y(s.y); bw = s.w * m.dw; bh = s.h * m.dh;
    cx = bx + bw / 2; cy = by + bh / 2;
  }
  const kp = perto.ok ? 1 - Math.exp(-dt * 3) : 1;
  perto.x += (cx - perto.x) * kp;
  perto.y += (cy - perto.y) * kp;
  perto.ok = true;
  const ox = reduzido ? 0 : perto.x - W / 2;
  const oy = reduzido ? 0 : perto.y - H * 0.45;
  raiz.style.setProperty('--lx', `${((cx / W) * 100).toFixed(1)}%`);
  raiz.style.setProperty('--ly', `${((cy / H) * 100).toFixed(1)}%`);

  // camada distante
  aro(W, H, ox * 0.05, e);
  faixaGiro(W / 2 + ox * 0.05, 64, Math.min(W * 0.4, 560), ultimaPose?.yaw ?? 0, e);
  prateleira(W / 2 + ox * 0.06, H - 118, Math.min(W * 0.2, 300), 20, t, e);

  posicionar(W, H, ox, oy, ultimaPose?.yaw ?? 0, reduzido);

  if (!s.ok) {
    procurando(W / 2, H * 0.45, Math.min(W, H) * 0.18, t, 1);
    fechamento(W, H, prog);
    return;
  }

  const R = Math.max(bw, bh) * 0.52;
  const pose = calcularPose(m);
  ultimaPose = pose;
  const alfa = visto ? 1 : 0.35;
  const nl = loja.estado?.notificacoes;
  const alerta = (nl?.nao_lidas ?? 0) > 0 && nl?.itens?.[0]?.nivel === 'erro';

  if (loja.prefs?.capacete_imagem === false) holograma(cx, cy + bh * 0.03, bw * 0.5, bh * 0.62, pose, alfa, brilho);
  if (pose) horizonte(pose.meio[0], pose.meio[1], R, pose.roll, alfa * 0.8 * e);
  aneis(cx, cy, R * (1 + (1 - e) * 1.5), t, alfa * e, alerta);     // cresce a partir da profundidade

  if (pose && visto) {
    const r = pose.olhos * 0.15;
    const ep = Math.min(1, Math.max(0, (prog - 0.25) / 0.5));
    mira(pose.a[0], pose.a[1], r * (1 + (1 - ep) * 2), t, false, alfa * ep);
    mira(pose.b[0], pose.b[1], r * (1 + (1 - ep) * 2), t, true, alfa * ep);
    angulares(pose, alfa * ep);
  }
  colchetes(bx, by, bw, bh, COR.branco, alfa * 0.8);
  if (!visto) procurando(cx, cy, R * 1.05, t, 1);

  if (prog < 1) {
    const L = (a0, a1) => a0 + (a1 - a0) * e;
    colchetes(L(0, bx), L(0, by), L(W, bw), L(H, bh), COR.ciano, 1 - prog * 0.6, 0.12);
    varredura(bx - bw * 0.2, by, bw * 1.4, bh, prog, 1 - prog * 0.5);
    const b = loja.estado?.boot;
    const msg = !b?.concluido ? 'INICIALIZANDO' : b.resultado === 'online' ? 'SISTEMAS ONLINE' : 'ONLINE COM LIMITAÇÕES';
    g.save();
    g.globalAlpha = Math.min(1, prog * 3) * (1 - Math.max(0, prog - 0.8) * 5);
    g.fillStyle = COR.branco;
    g.font = `600 13px ${TIT}`;
    g.textAlign = 'center';
    g.fillText(`J.A.R.V.I.S. · ${msg}`, cx, by - 20);
    g.restore();
  } else if (!reduzido) {                            // varredura periodica
    const ciclo = (t % 7) / 0.9;
    if (ciclo < 1) varredura(bx - bw * 0.2, by, bw * 1.4, bh, ciclo, 0.6);
  }

  conectores(cx, cy, R, alfa * e);
  posicionarAlvo(W, H, cx, cy, R);
  varreduraObjeto(W, H, t);
  fechamento(W, H, prog);
}

// "o que e isso?": mira quadrada no centro (onde se mostra o objeto) enquanto analisa
function varreduraObjeto(W, H, t) {
  const v = loja.estado?.visao;
  if (!v || !['olhando', 'analisando'].includes(v.estado)) return;
  const cx = W / 2;
  const cy = H * 0.52;
  const L = Math.min(W, H) * 0.3;
  g.save();
  g.translate(cx, cy);
  g.strokeStyle = COR.ambar;
  g.lineWidth = 2;
  const d = L * 0.18;
  g.save();
  g.rotate(Math.sin(t * 2) * 0.05);
  g.beginPath();
  for (const [sx, sy] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
    const x = sx * L / 2;
    const y = sy * L / 2;
    g.moveTo(x, y - sy * d); g.lineTo(x, y); g.lineTo(x - sx * d, y);
  }
  g.stroke();
  g.restore();
  const yy = ((t * 0.8) % 1) * L - L / 2;                   // linha de varredura
  g.globalAlpha = 0.8;
  g.beginPath(); g.moveTo(-L / 2, yy); g.lineTo(L / 2, yy); g.stroke();
  g.globalAlpha = 1;
  g.fillStyle = COR.ambar;
  g.font = `600 13px ${TIT}`;
  g.textAlign = 'center';
  g.fillText(v.estado === 'olhando' ? 'CAPTURANDO…' : 'ANALISANDO OBJETO…', 0, L / 2 + 22);
  g.restore();
}

// ---------------------------------------------------------------------------
// paineis: colunas curvas nas laterais, na camada de perto (seguem pouco e com atraso)
function medirPaineis() { for (const p of PAINEIS) { p.w = p.e.offsetWidth; p.h = p.e.offsetHeight; } }

function posicionar(W, H, ox, oy, yaw, reduzido) {
  const topo = 128;                                  // abaixo da faixa de giro e do ticker
  const base = H - 100;                              // acima da barra de controles
  const margem = Math.max(14, W * 0.025);
  const px = ox * 0.14;
  const py = oy * 0.08;
  for (const lado of [-1, 1]) {
    const col = PAINEIS.filter((p) => p.lado === lado && p.e.offsetParent !== null);
    const vao = 16;
    const total = col.reduce((a, p) => a + p.h, 0) + vao * Math.max(0, col.length - 1);
    let y = Math.max(topo, topo + (base - topo - total) / 2);
    for (const p of col) {
      const x = lado < 0 ? margem + px : W - margem - p.w + px;
      const rot = -lado * 22 + (reduzido ? 0 : yaw * 0.25);
      p.x = x;
      p.y = y + py;
      p.e.style.transform = `translate3d(${x.toFixed(1)}px, ${p.y.toFixed(1)}px, 0) rotateY(${rot.toFixed(2)}deg)`;
      y += p.h + vao;
    }
  }
  el('cap-base').style.transform = `translateX(calc(-50% + ${(ox * 0.06).toFixed(1)}px))`;
}

// etiqueta do rosto: ao lado dele, sem entrar nas colunas de paineis
function posicionarAlvo(W, H, cx, cy, R) {
  const a = el('cap-alvo');
  const w = a.offsetWidth;
  const h = a.offsetHeight;
  const visiveis = PAINEIS.filter((p) => p.e.offsetParent !== null);
  // a perspectiva puxa a borda interna dos paineis para o centro: folga de 40 px
  const esq = Math.max(8, ...visiveis.filter((p) => p.lado < 0).map((p) => p.x + p.w)) + 40;
  const dir = Math.min(W - 8, ...visiveis.filter((p) => p.lado > 0).map((p) => p.x)) - 40;
  let x = cx - R * 1.6 - w;                          // a direita ficam as linhas do olho
  if (x < esq) x = cx + R * 1.6;
  x = Math.max(esq, Math.min(dir - w, x));
  const y = Math.max(128, Math.min(H - h - 150, cy + R * 0.35));
  a.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
}

// forma de onda: voce (ciano) e Jarvis (ambar)
function desenharOnda(agora) {
  const w = ondaCv.clientWidth;
  const h = ondaCv.clientHeight;
  if (!w || !h) return;
  if (ondaCv.width !== w) ondaCv.width = w;
  if (ondaCv.height !== h) ondaCv.height = h;
  og.clearRect(0, 0, w, h);
  og.strokeStyle = 'rgba(234,249,255,0.15)';
  og.beginPath(); og.moveTo(0, h / 2); og.lineTo(w, h / 2); og.stroke();
  for (const [fonte, cor, ganho] of [['entrada', COR.ciano, 3.5], ['saida', COR.ambar, 1.6]]) {
    const n = loja.niveis[fonte];
    const onda = agora - n.em < 250 ? n.onda : null;
    og.strokeStyle = cor;
    og.lineWidth = 1.4;
    og.globalAlpha = onda ? 0.95 : 0.3;
    og.beginPath();
    const pts = onda ?? new Array(48).fill(0);
    pts.forEach((v, i) => {
      const x = (i / (pts.length - 1)) * w;
      const y = h / 2 - Math.max(-1, Math.min(1, v * ganho)) * (h / 2 - 4);
      if (i) og.lineTo(x, y); else og.moveTo(x, y);
    });
    og.stroke();
  }
  og.globalAlpha = 1;
}

// radar do campo de visao da camera: cada rosto vira um ponto (angulo e distancia estimada)
function desenharRadar(agora) {
  const w = radarCv.clientWidth;
  const h = radarCv.clientHeight;
  if (!w || !h) return;
  if (radarCv.width !== w) radarCv.width = w;
  if (radarCv.height !== h) radarCv.height = h;
  rg.clearRect(0, 0, w, h);
  const cx = w / 2;
  const cy = h - 4;
  const R = Math.min(w / 2, h) - 6;
  const meia = ((FOV_H / 2) * Math.PI) / 180;
  rg.save();
  rg.strokeStyle = 'rgba(234,249,255,0.35)';
  rg.lineWidth = 1;
  for (const k of [1, 0.66, 0.33]) { rg.beginPath(); rg.arc(cx, cy, R * k, Math.PI, TAU); rg.stroke(); }
  rg.strokeStyle = 'rgba(234,249,255,0.2)';
  for (const a of [-60, -30, 0, 30, 60]) {
    const r = (a * Math.PI) / 180 - Math.PI / 2;
    rg.beginPath(); rg.moveTo(cx, cy); rg.lineTo(cx + Math.cos(r) * R, cy + Math.sin(r) * R); rg.stroke();
  }
  rg.fillStyle = 'rgba(50,232,243,0.08)';                         // campo de visao da camera
  rg.beginPath(); rg.moveTo(cx, cy); rg.arc(cx, cy, R, -Math.PI / 2 - meia, -Math.PI / 2 + meia); rg.closePath(); rg.fill();
  const varre = movimentoReduzido() ? 0 : Math.sin(fase * 1.2) * meia;
  const grad = rg.createLinearGradient(cx, cy, cx + Math.cos(varre - Math.PI / 2) * R, cy + Math.sin(varre - Math.PI / 2) * R);
  grad.addColorStop(0, 'rgba(50,232,243,0)');
  grad.addColorStop(1, 'rgba(50,232,243,0.9)');
  rg.strokeStyle = grad;
  rg.lineWidth = 2;
  rg.beginPath(); rg.moveTo(cx, cy); rg.lineTo(cx + Math.cos(varre - Math.PI / 2) * R, cy + Math.sin(varre - Math.PI / 2) * R); rg.stroke();
  const r = loja.rostos;
  const esp = loja.prefs?.espelhar_camera !== false;
  if (agora - r.em < 900) {
    for (const f of r.lista) {
      const nx = f.x + f.w / 2;
      const a = ((esp ? 1 - nx : nx) - 0.5) * 2 * meia - Math.PI / 2;
      const dist = 0.16 / Math.max(0.04, f.w);                    // rosto maior = mais perto
      const rr = Math.min(0.95, dist / 1.6) * R;
      const x = cx + Math.cos(a) * rr;
      const y = cy + Math.sin(a) * rr;
      rg.fillStyle = COR.branco;
      rg.shadowColor = COR.ciano;
      rg.shadowBlur = 8;
      rg.beginPath(); rg.arc(x, y, 3.5, 0, TAU); rg.fill();
      rg.shadowBlur = 0;
      rg.strokeStyle = 'rgba(234,249,255,0.6)';
      rg.beginPath(); rg.arc(x, y, 7, 0, TAU); rg.stroke();
    }
  }
  rg.restore();
}

// ---------------------------------------------------------------------------
// dados reais dos paineis (2x por segundo)
function setHtml(id, html) { const e = el(id); if (e.dataset.cache !== html) { e.innerHTML = html; e.dataset.cache = html; } }

function nivelUso(v, invertido = false) {
  if (typeof v !== 'number') return 'sem';
  const x = invertido ? 100 - v : v;
  return x >= 90 ? 'critico' : x >= 70 ? 'atencao' : 'ok';
}

function atualizarArmadura(t, est) {
  const si = t.sistema ?? {};
  const val = (o, campo) => (o?.status === 'medido' ? o[campo] : null);
  const partes = [
    ['cabeca', 'Cabeça · CPU', val(si.cpu, 'uso_pct'), false],
    ['tronco', 'Tronco · RAM', val(si.memoria, 'uso_pct'), false],
    ['braco-e', 'Braço E · GPU', val(si.gpu, 'uso_pct'), false],
    ['braco-d', 'Braço D · disco', val(si.disco, 'uso_pct'), false],
    ['pernas', 'Pernas · bateria', val(si.bateria, 'percentual'), true],
  ];
  for (const [k, , v, inv] of partes) {
    // bateria na tomada nao e problema, mesmo baixa
    const n = k === 'pernas' && si.bateria?.na_tomada ? (typeof v === 'number' ? 'ok' : 'sem') : nivelUso(v, inv);
    for (const p of raiz.querySelectorAll(`[data-parte="${k}"]`)) p.dataset.n = n;
  }
  const srv = est.conexao?.servidor?.estado;
  raiz.querySelector('[data-parte="reator"]').dataset.n = srv === 'ok' ? 'ok' : srv ? 'critico' : 'sem';
  setHtml('cap-legenda', partes.map(([k, rot, v, inv]) => {
    const n = k === 'pernas' && si.bateria?.na_tomada ? 'ok' : nivelUso(v, inv);
    return `<li data-n="${n === 'critico' ? 'erro' : n === 'atencao' ? 'aviso' : ''}"><span>${esc(rot)}</span><span>${typeof v === 'number' ? `${Math.round(v)}%` : TRACO}</span></li>`;
  }).join('') + `<li data-n="${srv && srv !== 'ok' ? 'erro' : ''}"><span>Reator · servidor</span><span>${srv === 'ok' ? 'no ar' : srv ? 'fora' : TRACO}</span></li>`);
}

function atualizarDados() {
  if (!ativo) return;
  const agora = new Date();
  texto('cap-hh', agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }));
  texto('cap-ss', String(agora.getSeconds()).padStart(2, '0'));
  texto('cap-dia', String(agora.getDate()).padStart(2, '0'));
  texto('cap-semana', agora.toLocaleDateString('pt-BR', { weekday: 'long' }));
  texto('cap-mes', agora.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' }));

  const t = loja.telemetria ?? {};
  const est = loja.estado ?? {};
  const si = t.sistema ?? {};

  const c = t.clima ?? {};
  if (c.status === 'medido' || c.status === 'desatualizado') {
    const d0 = c.dias?.[0];
    setHtml('cap-clima', `<div class="cap-clima">${iconeClima(c.atual.icone, 30)}
      <span class="cap-temp num">${Math.round(c.atual.temperatura)}°</span>
      <span>${esc(c.local?.nome ?? '')} · ${esc(c.atual.descricao)}${d0 ? `<br><small>${Math.round(d0.min)}° / ${Math.round(d0.max)}° · chuva ${d0.chuva_pct ?? TRACO}%</small>` : ''}</span></div>`
      + (c.outros ?? []).filter((o) => o.status === 'medido').map((o) =>
        `<div class="cap-outros">${esc(o.local.nome)} · ${Math.round(o.atual.temperatura)}° · ${esc(o.atual.descricao)}</div>`).join(''));
  } else {
    setHtml('cap-clima', `<p class="cap-fraco">${c.status === 'nao_configurado' ? 'Cidade não definida (Painel → Clima).' : 'Clima sem leitura agora.'}</p>`);
  }

  atualizarArmadura(t, est);

  const conv = est.conversa ?? {};
  const ignorada = conv.ignorada && conv.ignorada_em > (conv.em ?? 0) && Date.now() / 1000 - conv.ignorada_em < 20;
  texto('cap-voce', ignorada ? `(sem “Jarvis”) ${conv.ignorada}` : conv.ultima_fala ?? 'nada dito ainda');
  texto('cap-jarvis', conv.ultima_resposta ?? TRACO);
  texto('cap-audio-est', `mic ${est.microfone?.estado ?? TRACO} · voz ${est.reproducao?.estado ?? TRACO}`);

  // diagnostico: cabecalho vermelho quando algo esta critico
  const r = si.rede ?? {};
  const d = si.disco ?? {};
  const m = si.memoria ?? {};
  const srv = est.conexao?.servidor?.estado;
  const oll = t.ollama?.status;
  const cam = est.camera ?? {};
  const md = t.midia;
  const tp = si.temperatura;
  const linhas = [
    ['Memória', m.status === 'medido' ? `${Math.round(m.uso_pct)}% · ${m.livre_gb.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} GB livres` : TRACO,
      m.uso_pct >= 92 ? 'erro' : m.uso_pct >= 80 ? 'aviso' : ''],
    ['Disco livre', d.status === 'medido' ? `${d.livre_gb.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} GB` : TRACO,
      d.livre_gb < 10 ? 'erro' : d.livre_gb < 25 ? 'aviso' : ''],
    ['Temperatura', tp?.status === 'medido' ? `${Math.round(tp.celsius)} °C` : 'sem sensor', tp?.celsius >= 90 ? 'erro' : ''],
    ['Energia', est.inferencia?.energia_ultima ? `${Math.round(est.inferencia.energia_ultima.joules)} J última resp.`
      : si.energia_cpu?.status === 'medido' ? `CPU ${si.energia_cpu.potencia_w.toFixed(1)} W` : 'sem medidor', ''],
    ['Rede ↓ / ↑', r.status === 'medido' ? `${taxa(r.recebimento_bps)} / ${taxa(r.envio_bps)}` : TRACO, ''],
    ['Servidor', srv === 'ok' ? 'no ar' : srv ? 'fora do ar' : TRACO, srv && srv !== 'ok' && srv !== 'desconhecido' ? 'erro' : ''],
    ['Ollama', oll === 'ok' ? 'no ar' : oll ? 'fora do ar' : TRACO, oll && oll !== 'ok' ? 'erro' : ''],
    ['Modelo da voz', est.modelos?.voz ?? TRACO, ''],
  ];
  if (md?.status === 'medido' && md.titulo) linhas.push(['Tocando', md.titulo, '']);
  const pior = linhas.some((l) => l[2] === 'erro') ? 'erro' : linhas.some((l) => l[2] === 'aviso') ? 'aviso' : '';
  el('cap-diag').dataset.alerta = pior;
  texto('cap-diag-rot', pior === 'erro' ? 'Sistema · crítico' : pior === 'aviso' ? 'Sistema · atenção' : 'Diagnóstico');
  setHtml('cap-diag-lista', linhas.map(([k, v, n]) => `<li data-n="${n}"><span>${esc(k)}</span><span>${esc(v)}</span></li>`).join(''));

  // avisos > proximo compromisso > tarefas
  const nt = est.notificacoes ?? {};
  const itens = (nt.itens ?? []).slice(0, 3);
  let nivel = '';
  let html = '';
  if ((nt.nao_lidas ?? 0) > 0 && itens.length) {
    nivel = itens.some((i) => i.nivel === 'erro') ? 'erro' : 'aviso';
    texto('cap-alerta-rot', nivel === 'erro' ? 'Alerta' : `${nt.nao_lidas} aviso${nt.nao_lidas === 1 ? '' : 's'}`);
    html = itens.map((i) => `<li data-n="${i.nivel === 'erro' ? 'erro' : ''}"><span>${esc(i.texto)}</span><span>${new Date(i.em * 1000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</span></li>`).join('');
  } else {
    const ag = t.agenda;
    const seg = Date.now() / 1000;
    const prox = ag?.status === 'medido' ? ag.eventos.find((ev) => ev.fim >= seg) : null;
    const pend = (est.tarefas?.itens ?? []).filter((x) => !x.feita);
    texto('cap-alerta-rot', prox ? 'Agenda' : 'Tarefas');
    if (prox) {
      const dt = new Date(prox.inicio * 1000);
      html += `<li><span>${esc(prox.titulo)}</span><span>${prox.dia_inteiro ? 'dia inteiro' : dt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</span></li>`;
    }
    html += pend.slice(0, prox ? 2 : 3).map((x) => `<li><span>${esc(x.texto)}</span><span>pendente</span></li>`).join('');
    if (!html) html = `<li><span>${ag?.status === 'medido' ? 'Nada na agenda' : 'Agenda não conectada'}</span><span>0 tarefas</span></li>`;
  }
  el('cap-alerta').dataset.alerta = nivel;
  setHtml('cap-alerta-lista', html);

  // doca sobre a prateleira
  const mic = est.microfone?.estado;
  const rep = est.reproducao?.estado;
  const inter = t.dispositivos?.internet;
  const doca = {
    mic: [{ ouvindo: 'ativo', captando: 'ativo', calibrando: 'aviso', erro: 'erro', bloqueado: 'erro' }[mic] ?? 'off', mic ?? TRACO],
    voz: [{ falando: 'ativo', preparando: 'aviso', erro: 'erro' }[rep] ?? 'ok', rep === 'falando' ? 'falando' : rep === 'erro' ? 'erro' : 'pronta'],
    ia: inferenciaAtiva(est) ? ['ativo', 'processando'] : srv && srv !== 'ok' && srv !== 'desconhecido' ? ['erro', 'fora'] : ['ok', 'ociosa'],
    cam: cam.ativa ? ['ok', `${cam.fps ?? TRACO} fps`] : ['off', 'desligada'],
    rede: inter === true ? ['ok', 'online'] : inter === false ? ['erro', 'sem internet'] : ['off', TRACO],
  };
  for (const li of raiz.querySelectorAll('.cap-dock li')) {
    const [sv, tv] = doca[li.dataset.k];
    li.dataset.s = sv;
    const sp = li.querySelector('span');
    if (sp.textContent !== tv) sp.textContent = tv;
  }

  const p = estadoPrincipal(est);
  texto('cap-estado', p.texto);
  texto('cap-sub', p.sub ?? '');

  const ev = (est.eventos ?? []).at(-1);
  texto('cap-ticker', ev ? `${new Date(ev.em * 1000).toLocaleTimeString('pt-BR')} · ${ev.tipo} · ${ev.texto}` : '');

  // noticias correndo embaixo, como o noticiario que o Jarvis poe na tela
  const nt2 = t.noticias;
  const faixa = nt2?.status === 'medido' ? nt2.itens.slice(0, 12).map((n) => `${n.fonte} · ${n.titulo}`).join('   ◆   ') : '';
  const alvoN = el('cap-noticias-txt');
  if (alvoN.dataset.cache !== faixa) {
    alvoN.dataset.cache = faixa;
    alvoN.textContent = faixa;
    alvoN.style.animationDuration = `${Math.max(40, faixa.length / 9)}s`;
  }
  el('cap-noticias').classList.toggle('oculto', !faixa);

  // contexto: a lista que o Jarvis acabou de falar (numerada, para "abra a segunda")
  const cx = est.contexto ?? {};
  const cxVivo = Boolean(cx.em && Date.now() / 1000 - cx.em < 90 && (cx.itens ?? []).length);
  el('cap-contexto').classList.toggle('oculto', !cxVivo);
  if (cxVivo && el('cap-ctx-lista').dataset.cache !== String(cx.em)) {
    el('cap-ctx-lista').dataset.cache = String(cx.em);
    texto('cap-ctx-titulo', cx.titulo ?? '');
    el('cap-ctx-lista').innerHTML = cx.itens.slice(0, 5).map((x) =>
      `<li>${esc(x.titulo)}${x.detalhe ? ` — ${esc(x.detalhe)}` : ''}<small>${esc(x.fonte ?? '')}</small></li>`).join('');
  }

  // analise visual ("o que e isso?")
  const v = est.visao ?? {};
  const recente = v.em && Date.now() / 1000 - v.em < 30;
  const mostrar = ['olhando', 'analisando'].includes(v.estado) || (recente && ['pronto', 'erro'].includes(v.estado));
  el('cap-analise').classList.toggle('oculto', !mostrar);
  if (mostrar) {
    el('cap-analise').dataset.s = v.estado;
    texto('cap-analise-rot', v.estado === 'pronto' ? `Análise visual · ${v.duracao_s ?? TRACO} s`
      : v.estado === 'erro' ? 'Análise visual · falhou' : 'Analisando…');
    texto('cap-analise-txt', v.estado === 'pronto' || v.estado === 'erro' ? (v.resposta ?? '') : (v.pergunta || 'o que está na frente da câmera'));
    const im = el('cap-analise-img');
    if (v.miniatura && im.getAttribute('src') !== v.miniatura) im.src = v.miniatura;
    im.classList.toggle('oculto', !v.miniatura);
  }

  const pose = ultimaPose;
  const visto = performance.now() - ultimoRosto < 900;
  const lista = performance.now() - loja.rostos.em < 900 ? loja.rostos.lista.length : 0;
  texto('cap-pessoas', cam.ativa ? String(lista) : TRACO);
  texto('cap-alvo-rot', visto ? 'Usuário presente' : 'Procurando');
  const det = [];
  if (visto) {
    if (s.conf != null) det.push(`confiança ${Math.round(s.conf * 100)}%`);
    if (cam.desde) det.push(`presente ${haQuanto(cam.desde)}`);
    if (pose) det.push(`distância ~${Math.round(pose.distCm / 5) * 5} cm (est.)`);
    if (s.extras) det.push(`+${s.extras} pessoa${s.extras === 1 ? '' : 's'} na imagem`);
  } else det.push('nenhum rosto na imagem');
  setHtml('cap-alvo-det', det.map((x) => `<div>${esc(x)}</div>`).join(''));
  texto('cap-b-imagem', loja.prefs?.capacete_imagem === false ? 'Mostrar rosto' : 'Ocultar rosto');
  el('cap-b-imagem').setAttribute('aria-pressed', String(loja.prefs?.capacete_imagem !== false));
}

// ---------------------------------------------------------------------------
function quadro(agora) {
  requestAnimationFrame(quadro);
  const dt = Math.min(0.1, (agora - (tAnterior || agora)) / 1000);
  tAnterior = agora;
  suavizar(lerRosto(agora), dt);
  definirAtivo(deveMostrar(agora));
  if (!ativo || document.hidden) return;
  const fps = FPS[loja.prefs?.perfil_grafico] ?? 30;
  if (agora - ultimoQuadro < 1000 / fps - 1) return;
  const passo = (agora - (ultimoQuadro || agora)) / 1000;
  ultimoQuadro = agora;
  desenhar(agora, Math.min(0.1, passo));
  desenharOnda(agora);
  desenharRadar(agora);
}

export function iniciarCapacete(callback) {
  aoMudar = callback ?? aoMudar;
  // "Jarvis, modo capacete" / "feche o capacete"
  aoComando((c) => {
    if (c.acao !== 'capacete') return;
    if (c.ligado) { dispensado = false; forcado = true; pedidoEm = performance.now(); } else dispensar();
  });
  el('cap-b-analisar').addEventListener('click', () => acao('/api/visao', {}).catch(() => {}));
  el('cap-b-sair').addEventListener('click', dispensar);
  el('cap-b-imagem').addEventListener('click', () =>
    acao('/api/preferencias', { capacete_imagem: loja.prefs?.capacete_imagem === false }).catch(() => {}));
  addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && ativo && el('gaveta').dataset.aberta !== 'true') dispensar();
  });
  addEventListener('resize', () => { if (ativo) medirPaineis(); });
  setInterval(() => { atualizarDados(); if (ativo) medirPaineis(); }, 500);
  requestAnimationFrame(quadro);
}

/** Chamado quando as preferencias mudam (imagem, espelho). */
export function prefsCapacete() { ligarImagem(); atualizarDados(); }

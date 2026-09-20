// Mesa holografica (como a do video de referencia: projetor apontado para a mesa +
// webcam). Fundo preto = o projetor nao acende; so o HUD brilha sobre a mesa.
// Esquerda: o que a camera ve agora (detector local) e a regua. Centro: modelo 3D
// (STL/OBJ) em arame holografico, ou o reator girando. Direita: graficos e a
// ultima analise. Embaixo: a conversa. Tudo num canvas, sem bibliotecas (CSP).

import { loja, conectar, aoComando, ouvir, acao, TOKEN_CAMERA, estadoPrincipal } from './cliente.js';
import { iniciarGestos } from './gestos.js';
import { alvoDaMesa, corDaMesa } from './alvos-mesa.js';

const cv = document.getElementById('holo');
const g = cv.getContext('2d');
let W = 0, H = 0;
function medir() {
  const dpr = Math.min(2, devicePixelRatio || 1);
  W = innerWidth; H = innerHeight;
  cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
}
addEventListener('resize', medir);
medir();

const CIANO = '95,211,255', CLARO = '#d9f7ff', AMBAR = '#ffc857', VERDE = '#39ff6a', VERMELHO = '#ff4d5e';
const rgba = (c, a) => `rgba(${c},${a})`;

// ---------------------------------------------------------------- modelo 3D
const vista = { yaw: 0.6, pitch: -0.42, zoom: 1, auto: true, pausaAte: 0 };
let modelo = null;          // {nome, pos: Float32Array (xyz), arestas: Uint32Array (pares)}

function lerSTL(buf) {
  const dv = new DataView(buf);
  if (buf.byteLength >= 84) {
    const n = dv.getUint32(80, true);
    if (84 + n * 50 === buf.byteLength) {                 // binario
      const v = new Float32Array(n * 9);
      for (let i = 0; i < n; i++) {
        const o = 84 + i * 50 + 12;
        for (let k = 0; k < 9; k++) v[i * 9 + k] = dv.getFloat32(o + k * 4, true);
      }
      return v;
    }
  }
  const txt = new TextDecoder().decode(buf);             // ASCII
  const nums = [];
  for (const m of txt.matchAll(/vertex\s+(\S+)\s+(\S+)\s+(\S+)/g)) nums.push(+m[1], +m[2], +m[3]);
  return new Float32Array(nums);
}

function lerOBJ(txt) {
  const vs = [], tris = [];
  for (const linha of txt.split(/\r?\n/)) {
    const p = linha.trim().split(/\s+/);
    if (p[0] === 'v') vs.push([+p[1], +p[2], +p[3]]);
    else if (p[0] === 'f') {
      const idx = p.slice(1).map((s) => { const i = parseInt(s.split('/')[0], 10); return i < 0 ? vs.length + i : i - 1; });
      for (let k = 1; k + 1 < idx.length; k++) for (const i of [idx[0], idx[k], idx[k + 1]]) tris.push(...(vs[i] ?? [0, 0, 0]));
    }
  }
  return new Float32Array(tris);
}

// Arestas "de forma": borda aberta ou dobra > 25 graus (arame limpo, sem a malha toda)
function arestasDe(tris) {
  const nTri = tris.length / 9;
  let min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < tris.length; i += 3) for (let k = 0; k < 3; k++) {
    min[k] = Math.min(min[k], tris[i + k]); max[k] = Math.max(max[k], tris[i + k]);
  }
  const diag = Math.hypot(max[0] - min[0], max[1] - min[1], max[2] - min[2]) || 1;
  const q = diag * 1e-5;
  const mapa = new Map(), pos = [], idx = new Uint32Array(nTri * 3);
  for (let v = 0; v < nTri * 3; v++) {
    const x = tris[v * 3], y = tris[v * 3 + 1], z = tris[v * 3 + 2];
    const chave = `${Math.round(x / q)},${Math.round(y / q)},${Math.round(z / q)}`;
    let i = mapa.get(chave);
    if (i === undefined) { i = pos.length / 3; mapa.set(chave, i); pos.push(x, y, z); }
    idx[v] = i;
  }
  const normais = new Float32Array(nTri * 3);
  for (let t = 0; t < nTri; t++) {
    const [a, b, c] = [idx[t * 3], idx[t * 3 + 1], idx[t * 3 + 2]];
    const ux = pos[b * 3] - pos[a * 3], uy = pos[b * 3 + 1] - pos[a * 3 + 1], uz = pos[b * 3 + 2] - pos[a * 3 + 2];
    const vx = pos[c * 3] - pos[a * 3], vy = pos[c * 3 + 1] - pos[a * 3 + 1], vz = pos[c * 3 + 2] - pos[a * 3 + 2];
    let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    const l = Math.hypot(nx, ny, nz) || 1;
    normais[t * 3] = nx / l; normais[t * 3 + 1] = ny / l; normais[t * 3 + 2] = nz / l;
  }
  const N = pos.length / 3, faces = new Map();
  for (let t = 0; t < nTri; t++) for (let k = 0; k < 3; k++) {
    const a = idx[t * 3 + k], b = idx[t * 3 + (k + 1) % 3];
    if (a === b) continue;
    const chave = a < b ? a * N + b : b * N + a;
    const f = faces.get(chave);
    if (f) f.push(t); else faces.set(chave, [t]);
  }
  let escolhidas = [];
  for (const [chave, f] of faces) {
    let dobra = 1;
    if (f.length === 2) {
      const [t1, t2] = f;
      dobra = normais[t1 * 3] * normais[t2 * 3] + normais[t1 * 3 + 1] * normais[t2 * 3 + 1] + normais[t1 * 3 + 2] * normais[t2 * 3 + 2];
    } else dobra = -1;                                     // borda aberta ou malha nao manifold
    if (dobra < 0.906) escolhidas.push([chave, dobra]);
  }
  if (escolhidas.length > 40000) escolhidas = escolhidas.sort((a, b) => a[1] - b[1]).slice(0, 40000);
  const arestas = new Uint32Array(escolhidas.length * 2);
  escolhidas.forEach(([chave], i) => { arestas[i * 2] = Math.floor(chave / N); arestas[i * 2 + 1] = chave % N; });
  const cx = (min[0] + max[0]) / 2, cy = (min[1] + max[1]) / 2, cz = (min[2] + max[2]) / 2;
  let r = 0;
  for (let i = 0; i < pos.length; i += 3) r = Math.max(r, Math.hypot(pos[i] - cx, pos[i + 1] - cy, pos[i + 2] - cz));
  const p = new Float32Array(pos.length);
  for (let i = 0; i < pos.length; i += 3) {                // STL vem com Z para cima: vira Y para cima
    p[i] = (pos[i] - cx) / r; p[i + 1] = (pos[i + 2] - cz) / r; p[i + 2] = -(pos[i + 1] - cy) / r;
  }
  return { pos: p, arestas, tamanho: [max[0] - min[0], max[1] - min[1], max[2] - min[2]], triangulos: nTri };
}

// reator em arame: o que gira quando nao ha modelo
function reator() {
  const pos = [], arestas = [];
  const anel = (r, y, n = 64) => {
    const base = pos.length / 3;
    for (let i = 0; i < n; i++) { const a = (i / n) * Math.PI * 2; pos.push(Math.cos(a) * r, y, Math.sin(a) * r); }
    for (let i = 0; i < n; i++) arestas.push(base + i, base + (i + 1) % n);
  };
  for (const [r, y] of [[1, 0.08], [1, -0.08], [0.82, 0.1], [0.5, 0.12], [0.5, -0.12], [0.26, 0.16], [0.26, -0.16]]) anel(r, y);
  for (let i = 0; i < 10; i++) {                           // 10 bobinas
    const a1 = (i / 10) * Math.PI * 2 + 0.12, a2 = a1 + 0.38, base = pos.length / 3;
    for (const [r, a] of [[0.55, a1], [0.78, a1], [0.78, a2], [0.55, a2]]) pos.push(Math.cos(a) * r, 0.06, Math.sin(a) * r);
    arestas.push(base, base + 1, base + 1, base + 2, base + 2, base + 3, base + 3, base);
  }
  return { pos: new Float32Array(pos), arestas: new Uint32Array(arestas) };
}
const REATOR = reator();
ouvir(() => {
  const a = loja.estado?.apresentacao;
  const elemento = document.getElementById('apresentacao-status');
  if (!a?.id) return;
  elemento.textContent = a.estado === 'carregada' ? `${a.nome} · carregamento confirmado pela mesa` :
    `${a.nome} · aguardando confirmação da mesa`;
});

function desenhar3D(cx, cy, raio, dt) {
  const m = modelo ?? REATOR;
  const corModelo = corDaMesa(modelo, loja.estado?.peca, loja.estado?.previa, loja.estado?.apresentacao) || CIANO;
  if (vista.auto && performance.now() > vista.pausaAte) vista.yaw += dt * 0.35;
  const cyw = Math.cos(vista.yaw), syw = Math.sin(vista.yaw), cp = Math.cos(vista.pitch), sp = Math.sin(vista.pitch);
  const d = 3.2, f = raio * 2.6 * vista.zoom, n = m.pos.length / 3;
  const px = new Float32Array(n), py = new Float32Array(n), pz = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const x = m.pos[i * 3], y = m.pos[i * 3 + 1], z = m.pos[i * 3 + 2];
    const x1 = x * cyw - z * syw, z1 = x * syw + z * cyw;
    const y2 = y * cp - z1 * sp, z2 = y * sp + z1 * cp;
    const k = f / (z2 + d);
    px[i] = cx + x1 * k; py[i] = cy - y2 * k; pz[i] = z2;
  }
  g.save();
  g.globalCompositeOperation = 'lighter';
  const faixas = [[-9, -0.33, 0.95], [-0.33, 0.33, 0.6], [0.33, 9, 0.3]];    // perto brilha mais
  for (const [a, b, alfa] of faixas) {
    g.beginPath();
    for (let e = 0; e < m.arestas.length; e += 2) {
      const i = m.arestas[e], j = m.arestas[e + 1], z = (pz[i] + pz[j]) / 2;
      if (z < a || z >= b) continue;
      g.moveTo(px[i], py[i]); g.lineTo(px[j], py[j]);
    }
    g.strokeStyle = rgba(corModelo, alfa); g.lineWidth = 1.1; g.shadowColor = rgba(corModelo, 0.9); g.shadowBlur = 6;
    g.stroke();
  }
  g.restore();
  // base do "holograma": aneis na mesa e linha de varredura
  g.save();
  g.strokeStyle = rgba(CIANO, 0.35); g.lineWidth = 1;
  for (const k of [1, 0.8]) { g.beginPath(); g.ellipse(cx, cy + raio * 1.02, raio * 1.1 * k, raio * 0.22 * k, 0, 0, Math.PI * 2); g.stroke(); }
  const t = (performance.now() / 2600) % 1;
  g.strokeStyle = rgba(CIANO, 0.18 * (1 - t)); g.beginPath();
  g.ellipse(cx, cy + raio * 1.02, raio * 1.1 * (0.3 + t), raio * 0.22 * (0.3 + t), 0, 0, Math.PI * 2); g.stroke();
  g.restore();
}

let carregamentoSeq = 0;
function confirmarApresentacao(apresentacaoId, pedido) {
  // Dois frames permitem que o loop da mesa desenhe a nova malha antes do ack.
  requestAnimationFrame(() => requestAnimationFrame(async () => {
    if (!apresentacaoId || pedido !== carregamentoSeq || modelo?.apresentacaoId !== apresentacaoId) return;
    try { await acao('/api/apresentacao/confirmar', { id: apresentacaoId, destino: 'holograma' }); }
    catch (e) { console.error('Não consegui confirmar a apresentação na mesa.', e); }
  }));
}
async function carregarModelo(esperado = null) {
  const pedido = ++carregamentoSeq;
  try {
    const r = await fetch('/api/holograma/modelo', { headers: { 'X-Jarvis-Token': TOKEN_CAMERA } });
    if (!r.ok) return;
    const apresentacaoId = r.headers.get('X-Apresentacao-Id');
    if ((esperado && esperado !== apresentacaoId) || pedido !== carregamentoSeq) return;
    if (apresentacaoId && modelo?.apresentacaoId === apresentacaoId) {
      confirmarApresentacao(apresentacaoId, pedido);
      return;
    }
    const nome = decodeURIComponent(r.headers.get('X-Modelo-Nome') || 'modelo');
    const buf = await r.arrayBuffer();
    const tris = /\.obj$/i.test(nome) ? lerOBJ(new TextDecoder().decode(buf)) : lerSTL(buf);
    if (pedido !== carregamentoSeq || !tris.length || tris.length % 9 || !tris.every(Number.isFinite)) return;
    const malha = arestasDe(tris);
    if (!malha.pos.length || !malha.arestas.length || !malha.pos.every(Number.isFinite)) return;
    modelo = { nome, apresentacaoId, ...malha };
    vista.zoom = 1; vista.auto = true;
    confirmarApresentacao(apresentacaoId, pedido);
  } catch (e) { console.error(e); }
}

// ------------------------------------------------------------------ graficos
let grafico = null;                                        // {titulo, unidade, series:[{nome, pontos:[[x,y]]}], em}
const historico = { cpu: [], ram: [], em: 0 };

function registrarTelemetria() {
  const t = loja.telemetria;
  if (!t || t.em === historico.em) return;
  historico.em = t.em;
  const s = t.sistema ?? {};
  if (s.cpu?.status === 'medido') historico.cpu.push([t.em, s.cpu.uso_pct]);
  if (s.memoria?.status === 'medido') historico.ram.push([t.em, s.memoria.uso_pct]);
  for (const k of ['cpu', 'ram']) if (historico[k].length > 120) historico[k].shift();
}

function desenharGrafico(x, y, w, h, titulo, series, unidade) {
  const todos = series.flatMap((s) => s.pontos);
  if (todos.length < 2) { texto(x, y + 30, 'Sem dados ainda…', 13, rgba(CIANO, 0.5)); return; }
  let x0 = Math.min(...todos.map((p) => p[0])), x1 = Math.max(...todos.map((p) => p[0]));
  let y0 = Math.min(...todos.map((p) => p[1])), y1 = Math.max(...todos.map((p) => p[1]));
  if (y1 - y0 < 1e-9) { y0 -= 1; y1 += 1; }
  if (x1 - x0 < 1e-9) x1 = x0 + 1;
  const pad = (y1 - y0) * 0.12; y0 -= pad; y1 += pad;
  const top = y + 26, alt = h - 44;
  texto(x, y + 12, titulo.toUpperCase(), 12, CLARO, 700);
  g.save();
  g.strokeStyle = rgba(CIANO, 0.15); g.lineWidth = 1;
  for (let i = 0; i <= 3; i++) { const yy = top + (alt * i) / 3; g.beginPath(); g.moveTo(x, yy); g.lineTo(x + w, yy); g.stroke(); }
  const cores = [CIANO, '255,200,87', '57,255,106'];
  series.forEach((s, k) => {
    g.beginPath();
    s.pontos.forEach(([px, py], i) => {
      const xx = x + ((px - x0) / (x1 - x0)) * w, yy = top + alt - ((py - y0) / (y1 - y0)) * alt;
      if (i) g.lineTo(xx, yy); else g.moveTo(xx, yy);
    });
    g.strokeStyle = rgba(cores[k % 3], 0.95); g.lineWidth = 2; g.shadowColor = rgba(cores[k % 3], 0.8); g.shadowBlur = 8;
    g.stroke();
    const ult = s.pontos[s.pontos.length - 1];
    g.shadowBlur = 0;
    texto(x + w - 4, top + 14 + k * 16, `${s.nome ? s.nome + ': ' : ''}${fmt(ult[1])}${unidade ? ' ' + unidade : ''}`, 12,
          rgba(cores[k % 3], 1), 600, 'right');
  });
  g.restore();
  texto(x, top + alt + 14, `mín ${fmt(y0 + pad)} · máx ${fmt(y1 - pad)}${unidade ? ' ' + unidade : ''}`, 11, rgba(CIANO, 0.55));
}

const fmt = (v) => (Math.abs(v) >= 1000 ? Math.round(v).toLocaleString('pt-BR')
  : v.toLocaleString('pt-BR', { maximumFractionDigits: Math.abs(v) < 10 ? 2 : 1 }));

// --------------------------------------------------------------- utilitarios
function texto(x, y, s, tam = 13, cor = CLARO, peso = 500, alinhar = 'left') {
  g.font = `${peso} ${tam}px Bahnschrift, "Segoe UI", sans-serif`;
  g.fillStyle = cor; g.textAlign = alinhar; g.fillText(s, x, y); g.textAlign = 'left';
}

function quebrar(s, largura, tam) {
  g.font = `500 ${tam}px Bahnschrift, "Segoe UI", sans-serif`;
  const linhas = [];
  let atual = '';
  for (const p of String(s).split(/\s+/)) {
    const tentativa = atual ? `${atual} ${p}` : p;
    if (g.measureText(tentativa).width > largura && atual) { linhas.push(atual); atual = p; } else atual = tentativa;
  }
  if (atual) linhas.push(atual);
  return linhas;
}

function moldura(x, y, w, h, titulo) {
  g.save();
  g.strokeStyle = rgba(CIANO, 0.3); g.lineWidth = 1;
  g.strokeRect(x + 0.5, y + 0.5, w, h);
  g.strokeStyle = rgba(CIANO, 0.95); g.lineWidth = 2;
  const c = 14;
  for (const [cx, cy, dx, dy] of [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]]) {
    g.beginPath(); g.moveTo(cx + dx * c, cy); g.lineTo(cx, cy); g.lineTo(cx, cy + dy * c); g.stroke();
  }
  g.restore();
  if (titulo) texto(x + 12, y + 20, titulo, 12, rgba(CIANO, 0.95), 700);
}

// ------------------------------------------------------------------- paineis
function painelVisao(x, y, w, h) {
  moldura(x, y, w, h, 'VISÃO AO VIVO');
  const d = loja.deteccoes;
  const viva = d && performance.now() - d.em < 1500;
  const cam = loja.estado?.camera;
  let yy = y + 44;
  if (!cam?.ativa) {
    texto(x + 12, yy, 'Câmera desligada', 14, rgba(CIANO, 0.55));
    texto(x + 12, yy + 20, 'Diga: “Jarvis, ligue a câmera”', 12, rgba(CIANO, 0.4));
    yy += 44;
  } else {
    const mapaH = Math.min(h * 0.38, w * 0.56);             // mapa da mesa: onde cada objeto esta
    g.save();
    g.strokeStyle = rgba(CIANO, 0.25); g.strokeRect(x + 12, yy, w - 24, mapaH);
    for (const o of viva ? d.lista : []) {
      const bx = x + 12 + o.x * (w - 24), by = yy + o.y * mapaH, bw = o.w * (w - 24), bh = o.h * mapaH;
      g.strokeStyle = d.vigia && o.classe === 0 ? VERMELHO : AMBAR; g.lineWidth = 1.4;
      g.shadowColor = g.strokeStyle; g.shadowBlur = 6; g.strokeRect(bx, by, bw, bh); g.shadowBlur = 0;
    }
    g.restore();
    yy += mapaH + 22;
    const lista = viva ? [...d.lista].sort((a, b) => b.conf - a.conf).slice(0, 7) : [];
    if (!lista.length) texto(x + 12, yy, 'Nada reconhecido agora', 13, rgba(CIANO, 0.5));
    for (const o of lista) {
      texto(x + 12, yy, o.nome.toUpperCase(), 13, CLARO, 600);
      const bw = (w - 24) * 0.4;
      g.fillStyle = rgba(CIANO, 0.15); g.fillRect(x + w - 12 - bw, yy - 10, bw, 8);
      g.fillStyle = AMBAR; g.fillRect(x + w - 12 - bw, yy - 10, bw * o.conf, 8);
      yy += 21;
    }
    if (viva) texto(x + 12, yy + 4, `${d.lista.length} objeto(s) · ${d.ms} ms por análise`, 11, rgba(CIANO, 0.45));
    yy += 26;
  }
  const m = loja.medida;
  if (m?.rotulo && performance.now() - m.recebida < 120000) {
    texto(x + 12, yy, 'RÉGUA VIRTUAL', 11, rgba(CIANO, 0.8), 700);
    texto(x + 12, yy + 20, m.rotulo, 15, VERDE, 700);
    yy += 44;
  }
  const ids = loja.identidades;
  if (ids?.lista?.length && performance.now() - ids.em < 3000) {
    texto(x + 12, yy, 'PESSOAS', 11, rgba(CIANO, 0.8), 700);
    yy += 20;
    for (const p of ids.lista.slice(0, 4)) {
      texto(x + 12, yy, String(p.rotulo || 'desconhecido').toUpperCase(), 14, p.nome ? VERDE : AMBAR, 700);
      yy += 19;
    }
    yy += 8;
  }
  if (d?.vigia) texto(x + 12, Math.min(yy, y + h - 14), 'MODO VIGIA ARMADO', 14, VERMELHO, 700);
}

function painelDados(x, y, w, h) {
  moldura(x, y, w, h, 'DADOS');
  const gh = h * 0.5;
  if (grafico && Date.now() / 1000 - grafico.em < 900) {
    desenharGrafico(x + 12, y + 32, w - 24, gh, grafico.titulo, grafico.series, grafico.unidade);
  } else {
    desenharGrafico(x + 12, y + 32, w - 24, gh, 'Computador · uso agora',
                    [{ nome: 'CPU', pontos: historico.cpu }, { nome: 'RAM', pontos: historico.ram }], '%');
  }
  let yy = y + 32 + gh + 30;
  const ctx = loja.estado?.contexto;
  const conv = loja.estado?.conversa;
  let titulo = 'ANÁLISE', linhas = [];
  if (ctx?.titulo && (!conv?.em || (ctx.em ?? 0) >= conv.em - 5)) {
    titulo = ctx.titulo.toUpperCase();
    linhas = (ctx.itens ?? []).slice(0, 8).map((i) => [i.titulo, i.detalhe, i.fonte].filter(Boolean).join(' · '));
  } else if (conv?.ultima_resposta) {
    linhas = quebrar(conv.ultima_resposta, w - 24, 14);
  }
  texto(x + 12, yy, titulo, 11, rgba(CIANO, 0.8), 700);
  yy += 22;
  for (const l of linhas.flatMap((s) => quebrar(s, w - 24, 14)).slice(0, Math.max(1, Math.floor((y + h - yy) / 19)))) {
    texto(x + 12, yy, l, 14, CLARO); yy += 19;
  }
}

function barraConversa(x, y, w) {
  const conv = loja.estado?.conversa ?? {};
  const st = estadoPrincipal(loja.estado);
  const cor = { falando: AMBAR, processando: AMBAR, ouvindo: VERDE, erro: VERMELHO }[st.id] ?? rgba(CIANO, 0.9);
  const pulso = 0.5 + 0.5 * Math.sin(performance.now() / 300);
  g.save();
  g.beginPath(); g.arc(x + 10, y - 4, 6 + (st.id === 'ouvindo' || st.id === 'falando' ? 2 * pulso : 0), 0, Math.PI * 2);
  g.fillStyle = cor; g.shadowColor = cor; g.shadowBlur = 12; g.fill();
  g.restore();
  texto(x + 26, y, st.texto.toUpperCase(), 13, cor, 700);
  if (conv.ultima_fala) {
    const l = quebrar(`VOCÊ: ${conv.ultima_fala}`, w - 200, 13)[0];
    texto(x + 170, y, l, 13, rgba(CIANO, 0.6));
  }
}

// ---------------------------------------------------------------- quadro
let antes = performance.now();
function quadro(agora) {
  requestAnimationFrame(quadro);
  const dt = Math.min(0.1, (agora - antes) / 1000);
  antes = agora;
  registrarTelemetria();
  g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
  const m = Math.max(14, W * 0.012);
  texto(m, m + 16, 'J.A.R.V.I.S.', 20, CLARO, 700);
  texto(m + 150, m + 16, 'MESA HOLOGRÁFICA', 12, rgba(CIANO, 0.8), 600);
  texto(W - m, m + 16, new Date().toLocaleTimeString('pt-BR'), 18, CLARO, 600, 'right');
  const topo = m + 34, baixo = H - m - 34, alt = baixo - topo;
  const lado = Math.max(260, W * 0.24);
  painelVisao(m, topo, lado, alt);
  painelDados(W - m - lado, topo, lado, alt);
  const cx = W / 2, cy = topo + alt * 0.46, raio = Math.min((W - 2 * lado - 4 * m) * 0.36, alt * 0.34);
  desenhar3D(cx, cy, raio, dt);
  const nome = modelo ? `${modelo.nome}` : 'Nenhum modelo · diga “mostre o modelo…” ou “projete…”';
  texto(cx, topo + alt - 36, nome, 14, modelo ? CLARO : rgba(CIANO, 0.5), 600, 'center');
  if (modelo) {
    const [a, b, c] = modelo.tamanho.map((v) => fmt(v));
    texto(cx, topo + alt - 16, `${a} × ${b} × ${c} (unidades do arquivo, em geral mm) · ${modelo.triangulos.toLocaleString('pt-BR')} triângulos`,
          11, rgba(CIANO, 0.5), 500, 'center');
  }
  barraConversa(m, H - m - 6, W - 2 * m);
}

// ----------------------------------------------------------- interacao
let arrasto = null;
function alvoMesa() {
  return alvoDaMesa(modelo, loja.estado?.peca, loja.estado?.apresentacao);
}
const gestos = iniciarGestos({ alvos: () => [alvoMesa()], manipular: (a) => {
  if (a.id !== alvoMesa().id) return;
  if (a.tipo === 'girar') {
    vista.yaw += a.dx * 5;
    vista.pitch = Math.max(-1.5, Math.min(1.5, vista.pitch + a.dy * 5));
  } else if (a.tipo === 'zoom') vista.zoom = Math.max(0.3, Math.min(4, vista.zoom * Math.exp(-a.dy * 4)));
  vista.pausaAte = performance.now() + 5000;
} });
cv.addEventListener('pointerdown', (e) => {
  const alvo = alvoMesa(), [x, y, w, h] = alvo.caixa;
  if (e.clientX / W >= x && e.clientX / W <= x + w && e.clientY / H >= y && e.clientY / H <= y + h)
    gestos.selecionarMouse(alvo);
  arrasto = [e.clientX, e.clientY]; cv.setPointerCapture(e.pointerId);
});
cv.addEventListener('pointermove', (e) => {
  if (!arrasto) return;
  vista.yaw += (e.clientX - arrasto[0]) * 0.01;
  vista.pitch = Math.max(-1.5, Math.min(1.5, vista.pitch + (e.clientY - arrasto[1]) * 0.01));
  vista.pausaAte = performance.now() + 5000;
  arrasto = [e.clientX, e.clientY];
});
cv.addEventListener('pointerup', () => { arrasto = null; });
cv.tabIndex = 0;
cv.addEventListener('keydown', (e) => {
  if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', '+', '-'].includes(e.key)) {
    e.preventDefault();
    if (e.key === 'ArrowLeft') vista.yaw -= .1;
    if (e.key === 'ArrowRight') vista.yaw += .1;
    if (e.key === 'ArrowUp') vista.pitch = Math.max(-1.5, vista.pitch - .1);
    if (e.key === 'ArrowDown') vista.pitch = Math.min(1.5, vista.pitch + .1);
    if (e.key === '+') vista.zoom = Math.min(4, vista.zoom * 1.1);
    if (e.key === '-') vista.zoom = Math.max(.3, vista.zoom / 1.1);
    vista.pausaAte = performance.now() + 5000;
  }
});
cv.addEventListener('wheel', (e) => {
  vista.zoom = Math.max(0.3, Math.min(4, vista.zoom * Math.exp(-e.deltaY * 0.001)));
  e.preventDefault();
}, { passive: false });
cv.addEventListener('dblclick', () => (document.fullscreenElement ? document.exitFullscreen() : cv.requestFullscreen()).catch(() => {}));
setTimeout(() => document.getElementById('dica').classList.add('sumir'), 8000);

// "Jarvis, mostre o modelo…", "gire", "aumente o zoom", "mostre o gráfico do dólar"
aoComando((c) => {
  if (c.acao !== 'holograma') return;
  if (c.tipo === 'modelo') carregarModelo(c.apresentacao_id || null);
  else if (c.tipo === 'limpar') modelo = null;
  else if (c.tipo === 'girar') { vista.auto = c.ligado !== false; vista.pausaAte = 0; }
  else if (c.tipo === 'zoom') vista.zoom = Math.max(0.3, Math.min(4, vista.zoom * (c.fator || 1)));
  else if (c.tipo === 'vista') { vista.yaw = c.yaw ?? vista.yaw; vista.pitch = c.pitch ?? vista.pitch; vista.pausaAte = performance.now() + 8000; }
  else if (c.tipo === 'grafico') grafico = { ...c.grafico, em: Date.now() / 1000 };
});

async function carregarGrafico() {
  try {
    const r = await fetch('/api/holograma/grafico', { headers: { 'X-Jarvis-Token': TOKEN_CAMERA } });
    const d = r.ok ? await r.json() : null;
    if (d?.grafico?.series?.length) grafico = { ...d.grafico, em: d.grafico.em ?? Date.now() / 1000 };
  } catch (e) { console.error(e); }
}

conectar();
carregarModelo();
carregarGrafico();
requestAnimationFrame(quadro);

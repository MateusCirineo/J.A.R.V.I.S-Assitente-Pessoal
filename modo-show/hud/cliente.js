// Cliente compartilhado das telas HUD: estado (SSE), acoes (POST com token),
// preferencias e formatacao. Uma unica conexao por janela.

const TOKEN = document.querySelector('meta[name="jarvis-token"]')?.content ?? '';

export const loja = {
  estado: null,
  telemetria: null,
  prefs: null,
  conectado: false,
  // niveis reais de audio; o renderizador le a cada quadro
  niveis: {
    entrada: { rms: 0, bandas: null, onda: null, em: 0 },
    saida: { rms: 0, bandas: null, onda: null, em: 0 },
  },
  // posicoes de rostos da camera (normalizadas 0..1), atualizadas ~10x/s
  rostos: { lista: [], em: 0 },
  deteccoes: { lista: [], em: 0, ms: 0, vigia: false },
  medida: null,
  identidades: { lista: [], em: 0 },
};

export const TOKEN_CAMERA = TOKEN;

const ouvintes = new Set();
// comandos que o runtime manda para a tela executar (ex.: abrir o capacete por voz)
const comandos = new Set();
export function aoComando(fn) { comandos.add(fn); }
export function ouvir(fn) { ouvintes.add(fn); return () => ouvintes.delete(fn); }
function avisar(tipo) { for (const fn of ouvintes) { try { fn(tipo); } catch (e) { console.error(e); } } }

let fonte = null;
let sessaoInicial = null;
let conferindoSessao = false;
export function conectar() {
  if (fonte) return;
  fonte = new EventSource('/api/eventos');
  fonte.onopen = () => { loja.conectado = true; avisar('conexao'); };
  fonte.onerror = async () => {
    loja.conectado = false; avisar('conexao');
    if (conferindoSessao) return;
    conferindoSessao = true;
    try {
      const resposta = await fetch('/api/estado', { headers: { 'X-Jarvis-Token': TOKEN } });
      // Após reinício, o cookie antigo não pode receber o estado privado novo.
      if (resposta.status === 403) location.reload();
    } catch { /* O EventSource tenta novamente quando o serviço voltar. */ }
    finally { conferindoSessao = false; }
  };
  fonte.addEventListener('estado', (e) => {
    const novo = JSON.parse(e.data);
    // runtime reiniciou (o EventSource reconecta sozinho): o token desta pagina
    // ficou velho, entao recarrega para pegar o novo
    if (sessaoInicial && novo.sessao && novo.sessao !== sessaoInicial) { location.reload(); return; }
    sessaoInicial ??= novo.sessao;
    loja.estado = novo;
    avisar('estado');
  });
  fonte.addEventListener('canal', (e) => {
    const { canal, valor, versao } = JSON.parse(e.data);
    if (!loja.estado || versao <= (loja.estado.versao ?? -1)) return;   // descarta velho
    loja.estado[canal] = valor;
    loja.estado.versao = versao;
    avisar('estado');
  });
  fonte.addEventListener('log', (e) => {
    if (!loja.estado) return;
    loja.estado.eventos = [...(loja.estado.eventos ?? []), JSON.parse(e.data)].slice(-60);
    avisar('log');
  });
  fonte.addEventListener('telemetria', (e) => { loja.telemetria = JSON.parse(e.data); avisar('telemetria'); });
  fonte.addEventListener('preferencias', (e) => {
    loja.prefs = JSON.parse(e.data);
    aplicarPrefs(loja.prefs);
    avisar('prefs');
  });
  fonte.addEventListener('nivel', (e) => {
    const n = JSON.parse(e.data);
    const alvo = loja.niveis[n.fonte];
    if (alvo) { alvo.rms = n.rms; alvo.bandas = n.bandas; alvo.onda = n.onda; alvo.em = performance.now(); }
  });
  fonte.addEventListener('rostos', (e) => {
    loja.rostos = { lista: JSON.parse(e.data).rostos || [], em: performance.now() };
  });
  fonte.addEventListener('identidades', (e) => { loja.identidades = { lista: JSON.parse(e.data).pessoas || [], em: performance.now() }; });
  fonte.addEventListener('medida', (e) => { loja.medida = { ...JSON.parse(e.data), recebida: performance.now() }; });
  fonte.addEventListener('deteccoes', (e) => {
    const d = JSON.parse(e.data);
    loja.deteccoes = { lista: d.objetos || [], em: performance.now(), ms: d.ms || 0, vigia: Boolean(d.vigia) };
  });
  fonte.addEventListener('comando', (e) => {
    const c = JSON.parse(e.data);
    for (const fn of comandos) { try { fn(c); } catch (err) { console.error(err); } }
  });
  addEventListener('pagehide', () => { fonte?.close(); fonte = null; });
}

export async function acao(rota, corpo = {}) {
  if (rota === '/api/comando') {
    corpo = { sessao_id: 'hud-local', pedido_id: crypto.randomUUID(), ...corpo };
  }
  const r = await fetch(rota, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Jarvis-Token': TOKEN },
    body: JSON.stringify(corpo),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.erro || `HTTP ${r.status}`);
  return j;
}

export function aplicarPrefs(p) {
  const h = document.documentElement;
  h.dataset.perfil = p.perfil_grafico;
  h.dataset.nucleo = p.estilo_nucleo;
  if (h.dataset.cor !== (p.cor_tema || 'ciano')) {
    h.dataset.cor = p.cor_tema || 'ciano';
    window.dispatchEvent(new Event('hud-cores'));      // o nucleo (canvas) rele as cores
  }
  const reduzido = p.movimento === 'reduzido' || matchMedia('(prefers-reduced-motion: reduce)').matches;
  h.dataset.movimento = reduzido ? 'reduzido' : 'normal';
  h.style.setProperty('--brilho', String(p.brilho));
}

export function movimentoReduzido() {
  return document.documentElement.dataset.movimento === 'reduzido';
}

// Estados derivados ---------------------------------------------------------

export function inferenciaAtiva(est) {
  const i = est?.inferencia;
  return Boolean(i && (i.ativas_servidor > 0 || i.voz_em_andamento));
}

/** Rotulo principal. Reproducao > inferencia > escuta > pronto. */
export function estadoPrincipal(est) {
  if (!est) return { id: 'desconectado', texto: 'Conectando…' };
  if (!est.boot?.concluido) return { id: 'boot', texto: 'Inicializando' };
  const mic = est.microfone?.estado;
  if (est.reproducao?.estado === 'falando') return { id: 'falando', texto: 'Falando' };
  if (inferenciaAtiva(est)) return { id: 'processando', texto: 'Processando' };
  // sem servidor ele escuta mas nao responde: "Ouvindo" aqui enganaria
  const srv = est.conexao?.servidor?.estado;
  if (srv && srv !== 'ok' && srv !== 'desconhecido')
    return { id: 'erro', texto: 'Servidor desconectado',
             sub: mic === 'ouvindo' || mic === 'captando' ? 'o microfone escuta, mas sem respostas até ele voltar' : 'religue pelo Painel' };
  if (mic === 'captando') return { id: 'ouvindo', texto: 'Ouvindo', sub: 'captando fala' };
  if (mic === 'ouvindo') {
    const conversa = (est.conversa?.janela_ate ?? 0) > Date.now() / 1000;
    return { id: 'ouvindo', texto: 'Ouvindo',
             sub: conversa ? 'pode continuar falando, sem dizer “Jarvis”' : 'comece a frase com “Jarvis”' };
  }
  if (mic === 'calibrando') return { id: 'pronto', texto: 'Calibrando', sub: 'medindo o ruído do ambiente' };
  if (mic === 'erro') return { id: 'erro', texto: 'Erro no microfone', sub: est.microfone.detalhe };
  if (mic === 'bloqueado') return { id: 'erro', texto: 'Microfone bloqueado pelo Windows',
                                    sub: `${est.microfone.detalhe ?? ''}. Volta sozinho ao liberar; enquanto isso, digite o comando.` };
  if (mic === 'desativado') return { id: 'mic-off', texto: 'Microfone desativado' };
  return { id: 'pronto', texto: 'Pronto' };
}

// Formatacao: ausencia de dado nunca vira zero ------------------------------

export const TRACO = '—';
export function num(v, casas = 1) {
  return typeof v === 'number' && Number.isFinite(v)
    ? v.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas })
    : TRACO;
}
export function comUnidade(v, unidade, casas = 1) {
  const s = num(v, casas);
  return s === TRACO ? s : `${s} ${unidade}`;
}
export function haQuanto(ts) {
  if (!ts) return TRACO;
  const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (s < 60) return `há ${s} s`;
  if (s < 3600) return `há ${Math.floor(s / 60)} min`;
  return `há ${Math.floor(s / 3600)} h`;
}
export function hora(ts) {
  return ts ? new Date(ts * 1000).toLocaleTimeString('pt-BR') : TRACO;
}
export function desatualizada(t) {
  return !t?.em || Date.now() / 1000 - t.em > (t.intervalo_s ?? 3) * 3;
}

export function escapar(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

export function bytes(n) {
  if (typeof n !== 'number') return TRACO;
  const u = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toLocaleString('pt-BR', { maximumFractionDigits: i ? 1 : 0 })} ${u[i]}`;
}

export function taxa(bps) {
  return typeof bps === 'number' ? `${bytes(bps)}/s` : TRACO;
}

// Icones do clima, desenhados em SVG (sem imagens externas)
const ICONES_CLIMA = {
  sol: '<circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/>',
  parcial: '<circle cx="9" cy="9" r="3.5"/><path d="M9 2.5v1.5M2.5 9H4M4.4 4.4l1 1M13.6 4.4l-1 1"/><path d="M8 19h9a4 4 0 0 0 0-8 5 5 0 0 0-9.6 1.6A3.2 3.2 0 0 0 8 19z"/>',
  nuvem: '<path d="M7 19h10a4.5 4.5 0 0 0 .4-9 6 6 0 0 0-11.6 1.8A3.7 3.7 0 0 0 7 19z"/>',
  chuva: '<path d="M7 15h10a4 4 0 0 0 .4-8 5.5 5.5 0 0 0-10.6 1.6A3.3 3.3 0 0 0 7 15z"/><path d="M8 18l-1 3M12 18l-1 3M16 18l-1 3"/>',
  garoa: '<path d="M7 15h10a4 4 0 0 0 .4-8 5.5 5.5 0 0 0-10.6 1.6A3.3 3.3 0 0 0 7 15z"/><path d="M9 18v1.5M13 18v1.5M17 18v1.5"/>',
  trovoada: '<path d="M7 14h10a4 4 0 0 0 .4-8 5.5 5.5 0 0 0-10.6 1.6A3.3 3.3 0 0 0 7 14z"/><path d="M12 15l-2 4h3l-1.5 3.5"/>',
  neve: '<path d="M7 14h10a4 4 0 0 0 .4-8 5.5 5.5 0 0 0-10.6 1.6A3.3 3.3 0 0 0 7 14z"/><path d="M9 18h.01M13 19h.01M17 18h.01M11 21h.01M15 21h.01"/>',
  neblina: '<path d="M4 9h16M3 13h18M5 17h14"/>',
};
export function iconeClima(chave, tam = 22) {
  return `<svg viewBox="0 0 24 24" width="${tam}" height="${tam}" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONES_CLIMA[chave] || ICONES_CLIMA.nuvem}</svg>`;
}

export function el(id) { return document.getElementById(id); }
export function texto(id, v) { const e = el(id); if (e && e.textContent !== String(v)) e.textContent = v; }
export function chip(id, s, t) {
  const e = el(id);
  if (!e) return;
  e.dataset.s = s;
  if (t !== undefined && e.textContent !== t) e.textContent = t;
}

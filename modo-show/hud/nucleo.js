// Nucleo HUD em Canvas 2D.
//
// Camadas (de fora para dentro) e o que as dirige:
//   0 escala radial ............ decorativa, gira devagar
//   1 arco ambar ............... decorativo (acento)
//   2 faixa segmentada ......... decorativa, sentido oposto
//   3 anel de ENTRADA .......... espectro REAL do microfone (so com ele aberto)
//   4 circulos finos ........... decorativo
//   5 anel de SAIDA ............ espectro REAL do audio sendo reproduzido
//   6 anel de PROCESSAMENTO .... varredura enquanto ha inferencia (sem %)
//   7 arcos internos ........... decorativos
//   8 nucleo ................... pulso: nivel real da fala; em repouso, respiracao
//
// Estilo "orbe" (alternativa do projeto C): esfera de particulas 3D. O raio
// pulsa com o nivel REAL da fala dele e a superficie ondula com o espectro REAL
// do microfone; a rotacao acelera enquanto ha inferencia (efeito decorativo, sem
// numero: nao e medida de nada).
//
// No boot, cada camada acende quando a etapa correspondente e resolvida.
// Niveis que param de chegar decaem a zero: nada fica congelado fingindo sinal.

import { loja, movimentoReduzido, inferenciaAtiva } from './cliente.js';

export const PERFIS = {
  economico:       { fps: 15, dpr: 1,   barrasIn: 48, barrasOut: 48, tiques: 90,  brilho: 0,  particulas: 260 },
  equilibrado:     { fps: 30, dpr: 1.5, barrasIn: 72, barrasOut: 64, tiques: 180, brilho: 6,  particulas: 520 },
  cinematografico: { fps: 60, dpr: 2,   barrasIn: 96, barrasOut: 96, tiques: 180, brilho: 12, particulas: 900 },
};

const GRAU = Math.PI / 180;
const NB = 32;

export function criarNucleo(canvas, palco) {
  const ctx = canvas.getContext('2d', { alpha: true });
  let perfil = PERFIS.equilibrado;
  let tam = 0;
  let raf = 0;
  let ultimo = 0;
  let pularBoot = false;
  let cor = {};
  const t0 = performance.now();
  const suave = {
    entrada: new Float32Array(NB), saida: new Float32Array(NB),
    rmsSaida: 0, varredura: 0, ativacao: new Float32Array(9), olho: 0,
  };
  const medidas = { quadros: 0, inicio: performance.now(), fps: 0 };

  function lerCores() {
    const s = getComputedStyle(document.documentElement);
    const v = (n) => s.getPropertyValue(n).trim();
    cor = { ciano: v('--ciano'), azul: v('--azul'), ambar: v('--ambar'), vermelho: v('--vermelho'),
            verde: v('--verde'), fundo0: v('--fundo-0'), fundo1: v('--fundo-1') };
  }

  function redimensionar() {
    const w = palco.clientWidth;
    const h = palco.clientHeight;
    tam = Math.max(160, Math.floor(Math.min(w, h)));          // sempre quadrado: nunca elipse
    const dpr = Math.min(window.devicePixelRatio || 1, perfil.dpr);
    canvas.style.width = `${tam}px`;
    canvas.style.height = `${tam}px`;
    canvas.width = Math.round(tam * dpr);
    canvas.height = Math.round(tam * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    palco.style.setProperty('--tam-nucleo', `${tam}px`);
  }

  const obs = new ResizeObserver(redimensionar);
  obs.observe(palco);

  function rgba(hex, a) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${Math.max(0, Math.min(1, a))})`;
  }

  function nivelReal(fonte, agora, alvo, dt) {
    const n = loja.niveis[fonte];
    const vivo = n.bandas && agora - n.em < 300;
    for (let i = 0; i < NB; i++) {
      const x = vivo ? n.bandas[i] ?? 0 : 0;
      const a = alvo[i];
      alvo[i] = x > a ? a + (x - a) * 0.6 : a + (x - a) * Math.min(1, dt * 6);
    }
    return vivo ? n.rms : 0;
  }

  function anel(r, largura, alpha, cores = cor.ciano) {
    ctx.beginPath();
    ctx.arc(tam / 2, tam / 2, r, 0, Math.PI * 2);
    ctx.lineWidth = largura;
    ctx.strokeStyle = rgba(cores, alpha);
    ctx.stroke();
  }

  function arco(r, ini, fim, largura, estilo) {
    ctx.beginPath();
    ctx.arc(tam / 2, tam / 2, r, ini, fim);
    ctx.lineWidth = largura;
    ctx.strokeStyle = estilo;
    ctx.stroke();
  }

  // barras radiais espelhadas a partir de r0, comprimento pelas bandas
  function espectroRadial(r0, compMax, n, bandas, alpha, hex, rot) {
    const c = tam / 2;
    ctx.lineWidth = Math.max(1.2, (2 * Math.PI * r0) / n * 0.45);
    ctx.strokeStyle = rgba(hex, alpha);
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const f = i / n;
      const dobra = f < 0.5 ? f * 2 : (1 - f) * 2;           // simetrico
      const b = bandas[Math.min(NB - 1, Math.floor(dobra * NB))];
      const len = 1 + Math.pow(b, 1.6) * compMax;
      const ang = rot + f * Math.PI * 2 - Math.PI / 2;
      const cs = Math.cos(ang);
      const sn = Math.sin(ang);
      ctx.moveTo(c + cs * r0, c + sn * r0);
      ctx.lineTo(c + cs * (r0 + len), c + sn * (r0 + len));
    }
    ctx.stroke();
  }

  function desenhar(agora, dt) {
    const est = loja.estado;
    const prefs = loja.prefs;
    const R = tam / 2;
    const c = R;
    const reduzido = movimentoReduzido();
    const t = reduzido ? 0 : (agora - t0) / 1000;
    const brilhoPref = prefs?.brilho ?? 0.8;
    ctx.clearRect(0, 0, tam, tam);

    const falando = est?.reproducao?.estado === 'falando';
    const processando = inferenciaAtiva(est);
    const mic = est?.microfone?.estado;
    const micAberto = mic === 'ouvindo' || mic === 'captando' || mic === 'calibrando';
    const servidorOk = est?.conexao?.servidor?.estado === 'ok' || !est?.boot?.concluido;

    // Janela aberta (ou reaberta) depois do boot: mostra o estado atual, sem
    // repetir a animacao de abertura.
    if (!suave.lido && est) {
      suave.lido = true;
      if (est.boot?.concluido) suave.ativacao.fill(1);
    }

    // ativacao das camadas pelas etapas reais do boot
    const etapas = est?.boot?.etapas ?? [];
    const semAnimacao = pularBoot || reduzido || prefs?.boot_animado === false || est?.boot?.concluido;
    for (let i = 0; i < 9; i++) {
      const e = etapas[i]?.estado;
      const alvo = semAnimacao || e === 'ok' || e === 'falha' ? 1 : e === 'verificando' ? 0.35 : 0.06;
      suave.ativacao[i] = reduzido ? alvo : suave.ativacao[i] + (alvo - suave.ativacao[i]) * Math.min(1, dt * 3);
    }
    const A = suave.ativacao;

    const rmsIn = nivelReal('entrada', agora, suave.entrada, dt);
    const rmsOut = nivelReal('saida', agora, suave.saida, dt);
    suave.rmsSaida += (rmsOut - suave.rmsSaida) * Math.min(1, dt * 10);

    ctx.shadowBlur = 0;
    const glow = (on) => {
      ctx.shadowBlur = on && perfil.brilho ? perfil.brilho * brilhoPref : 0;
      ctx.shadowColor = cor.ciano;
    };

    if (document.documentElement.dataset.nucleo === 'reator') {
      reator({ R, c, t, A, falando, processando, mic, micAberto, servidorOk, reduzido, dt, glow });
      contarQuadro(agora);
      return;
    }
    if (document.documentElement.dataset.nucleo === 'orbe') {
      orbe({ R, c, t, A, falando, processando, micAberto, reduzido, dt });
      contarQuadro(agora);
      return;
    }

    // 0 - escala radial
    {
      const r = R * 0.965;
      const rot = t * 0.6 * GRAU;
      ctx.lineWidth = 1;
      ctx.strokeStyle = rgba(cor.ciano, 0.32 * A[0]);
      ctx.beginPath();
      for (let i = 0; i < perfil.tiques; i++) {
        const ang = rot + (i / perfil.tiques) * Math.PI * 2;
        const longo = i % (perfil.tiques / 36) === 0;
        const r2 = r - (longo ? R * 0.035 : R * 0.014);
        ctx.moveTo(c + Math.cos(ang) * r, c + Math.sin(ang) * r);
        ctx.lineTo(c + Math.cos(ang) * r2, c + Math.sin(ang) * r2);
      }
      ctx.stroke();
    }

    // 1 - circulo + arco ambar
    anel(R * 0.905, 1, 0.22 * A[1]);
    {
      const ini = t * 4 * GRAU - Math.PI / 2;
      glow(true);
      arco(R * 0.905, ini, ini + 38 * GRAU, 2.5, rgba(cor.ambar, 0.85 * A[1]));
      glow(false);
    }

    // 2 - faixa segmentada (sentido oposto)
    {
      const r = R * 0.845;
      const segs = 48;
      const rot = -t * 3 * GRAU;
      for (let i = 0; i < segs; i++) {
        const forte = i % 7 === 0 || i % 11 === 3;
        const ini = rot + (i / segs) * Math.PI * 2;
        arco(r, ini, ini + (Math.PI * 2 / segs) * 0.62, R * 0.028,
             rgba(cor.azul, (forte ? 0.55 : 0.2) * A[2]));
      }
    }

    // 3 - anel de ENTRADA (microfone)
    {
      const r = R * 0.745;
      if (mic === 'erro') {
        ctx.setLineDash([4, 6]);
        anel(r, 1.5, 0.8 * A[3], cor.vermelho);
        ctx.setLineDash([]);
      } else if (!micAberto) {
        // desativado ou pausado: tracejado parado, nenhuma animacao de escuta
        ctx.setLineDash([2, 7]);
        anel(r, 1, 0.3 * A[3], mic === 'pausado' ? cor.azul : cor.ciano);
        ctx.setLineDash([]);
      } else {
        anel(r, 1, (mic === 'captando' ? 0.8 : 0.4) * A[3]);
        glow(mic === 'captando');
        espectroRadial(r + 2, R * 0.06, perfil.barrasIn, suave.entrada,
                       (mic === 'captando' ? 0.95 : 0.55) * A[3], cor.ciano, t * 2 * GRAU);
        glow(false);
      }
    }

    // 4 - circulos finos com marcas a cada 30 graus
    anel(R * 0.695, 1, 0.28 * A[4]);
    anel(R * 0.683, 1, 0.14 * A[4]);
    {
      ctx.strokeStyle = rgba(cor.ciano, 0.5 * A[4]);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (let i = 0; i < 12; i++) {
        const ang = i * 30 * GRAU;
        ctx.moveTo(c + Math.cos(ang) * R * 0.683, c + Math.sin(ang) * R * 0.683);
        ctx.lineTo(c + Math.cos(ang) * R * 0.71, c + Math.sin(ang) * R * 0.71);
      }
      ctx.stroke();
    }

    // 5 - anel de SAIDA (audio reproduzido de fato)
    {
      const r = R * 0.6;
      if (falando || suave.rmsSaida > 0.002) {
        glow(true);
        espectroRadial(r, R * 0.075, perfil.barrasOut, suave.saida, 0.9 * A[5], cor.ciano, 0);
        glow(false);
      } else {
        ctx.fillStyle = rgba(cor.ciano, 0.3 * A[5]);
        for (let i = 0; i < 72; i++) {
          const ang = (i / 72) * Math.PI * 2;
          ctx.fillRect(c + Math.cos(ang) * r - 0.75, c + Math.sin(ang) * r - 0.75, 1.5, 1.5);
        }
      }
    }

    // 6 - anel de PROCESSAMENTO: varredura enquanto ha inferencia (nao e porcentagem)
    {
      const r = R * 0.535;
      const segs = 24;
      const passo = (Math.PI * 2) / segs;
      if (processando && !reduzido) suave.varredura = (suave.varredura + dt * 220 * GRAU) % (Math.PI * 2);
      for (let i = 0; i < segs; i++) {
        const ini = i * passo - Math.PI / 2;
        let a = 0.12;
        if (!servidorOk) a = 0.1;
        if (processando) {
          const d = ((suave.varredura - ini) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
          a = reduzido ? 0.55 : Math.max(0.12, 1 - d / (passo * 5));
        }
        arco(r, ini + 0.02, ini + passo - 0.02, R * 0.022,
             rgba(servidorOk ? cor.ciano : cor.vermelho, a * A[6]));
      }
    }

    // 7 - arcos internos, sentidos opostos, com um acento ambar
    {
      const r1 = R * 0.47;
      const r2 = R * 0.452;
      const a1 = t * 8 * GRAU;
      const a2 = -t * 5 * GRAU;
      arco(r1, a1, a1 + 200 * GRAU, 1.5, rgba(cor.ciano, 0.55 * A[7]));
      arco(r2, a2, a2 + 120 * GRAU, 1, rgba(cor.azul, 0.6 * A[7]));
      arco(r2, a2 + 170 * GRAU, a2 + 188 * GRAU, 2, rgba(cor.ambar, 0.7 * A[7]));
    }

    // 8 - nucleo escuro com pulso
    {
      const r = R * 0.42;
      const g = ctx.createRadialGradient(c, c, r * 0.2, c, c, r);
      g.addColorStop(0, rgba(cor.fundo1, 0.95));
      g.addColorStop(1, rgba(cor.fundo0, 0.98));
      ctx.beginPath();
      ctx.arc(c, c, r, 0, Math.PI * 2);
      ctx.fillStyle = g;
      ctx.fill();
      // pulso: nivel real da fala; em repouso, respiracao lenta (decorativa)
      const pulso = falando ? Math.min(1, suave.rmsSaida * 6) : 0.18 + 0.08 * Math.sin(t * 1.2);
      glow(true);
      anel(r, 1.5 + pulso * 2.5, (0.25 + pulso * 0.6) * A[8]);
      glow(false);

      if (document.documentElement.dataset.nucleo === 'olhos') {
        suave.olho = (t % 5.5) > 5.35 ? 0.1 : 1;              // piscada decorativa
        ctx.fillStyle = rgba('#f0fbff', 0.95 * A[8]);
        glow(true);
        for (const lado of [-1, 1]) {
          ctx.beginPath();
          ctx.ellipse(c + lado * R * 0.13, c - R * 0.04, R * 0.05, R * 0.05 * suave.olho, 0, 0, Math.PI * 2);
          ctx.fill();
        }
        glow(false);
      }
    }

    contarQuadro(agora);
  }

  // ---- estilo "orbe": esfera de Fibonacci girando em 3D ---------------------
  const esfera = { n: 0, pts: null, ang: 0 };
  function pontosEsfera(n) {
    if (esfera.n === n) return esfera.pts;
    const pts = new Float32Array(n * 3);
    const passo = Math.PI * (3 - Math.sqrt(5));              // angulo dourado: pontos bem espalhados
    for (let i = 0; i < n; i++) {
      const y = 1 - (i / (n - 1)) * 2;
      const r = Math.sqrt(1 - y * y);
      pts[i * 3] = Math.cos(passo * i) * r;
      pts[i * 3 + 1] = y;
      pts[i * 3 + 2] = Math.sin(passo * i) * r;
    }
    esfera.n = n;
    esfera.pts = pts;
    return pts;
  }

  function orbe({ R, c, t, A, falando, processando, micAberto, reduzido, dt }) {
    const n = perfil.particulas;
    const pts = pontosEsfera(n);
    if (!reduzido) esfera.ang += dt * (processando ? 1.6 : falando ? 0.9 : 0.3);
    const ay = esfera.ang;
    const ax = 0.35 + (reduzido ? 0 : Math.sin(t * 0.2) * 0.15);
    const cy = Math.cos(ay), sy = Math.sin(ay), cx = Math.cos(ax), sx = Math.sin(ax);
    const nivel = Math.min(1, Math.sqrt(suave.rmsSaida) * 2.2);       // fala REAL dele
    const base = R * 0.66 * (0.92 + nivel * 0.2) * (0.55 + 0.45 * A[8]);

    const halo = ctx.createRadialGradient(c, c, base * 0.1, c, c, base * 1.35);
    halo.addColorStop(0, rgba(cor.ciano, (0.14 + nivel * 0.28) * A[8]));
    halo.addColorStop(1, rgba(cor.ciano, 0));
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(c, c, base * 1.35, 0, Math.PI * 2);
    ctx.fill();

    ctx.globalCompositeOperation = 'lighter';                     // brilho somado, sem shadowBlur caro
    const escala = tam / 700;
    for (let i = 0; i < n; i++) {
      let x = pts[i * 3], y = pts[i * 3 + 1], z = pts[i * 3 + 2];
      const k = 1 + (micAberto ? suave.entrada[i % NB] * 0.22 : 0) + (falando ? Math.sin(t * 6 + i) * nivel * 0.04 : 0);
      x *= k; y *= k; z *= k;
      const x1 = x * cy + z * sy;
      const z1 = -x * sy + z * cy;
      const y2 = y * cx - z1 * sx;
      const z2 = y * sx + z1 * cx;
      const persp = 1.2 / (1.9 - z2 * 0.6);
      const prof = (z2 + 1) / 2;                                   // 0 = fundo, 1 = frente
      ctx.fillStyle = rgba(prof > 0.55 ? cor.ciano : cor.azul, (0.16 + prof * 0.8) * A[8]);
      const s = (0.7 + prof * 1.7) * escala;
      ctx.fillRect(c + x1 * base * persp - s / 2, c + y2 * base * persp - s / 2, s, s);
    }
    ctx.globalCompositeOperation = 'source-over';

    // orbitas finas: a externa acende com o microfone aberto (estado real)
    anel(R * 0.82, 1, 0.22 * A[4]);
    anel(R * 0.86, 1, (micAberto ? 0.55 : 0.15) * A[3], micAberto ? cor.ciano : cor.azul);
    if (processando) arco(R * 0.9, t * 2, t * 2 + 0.9, 2, rgba(cor.ambar, 0.7));
  }

  function contarQuadro(agora) {
    medidas.quadros++;
    if (agora - medidas.inicio > 2000) {
      medidas.fps = Math.round((medidas.quadros * 1000) / (agora - medidas.inicio));
      medidas.quadros = 0;
      medidas.inicio = agora;
    }
  }

  // ------------------------------------------------------------------------
  // Estilo "reator": a composicao classica do J.A.R.V.I.S. do filme -- faixa
  // azul grossa e translucida, pontos amarelos no topo, colchete ambar a
  // esquerda, anel de marcacoes e moldura externa com segmentos.
  //   marcacoes ........ crescem com o espectro REAL da fala dele
  //   faixa ............ pulsa com o volume REAL da fala; brilho que percorre a
  //                      faixa enquanto ha inferencia (sem porcentagem)
  //   anel interno ..... espectro REAL do microfone; tracejado parado se desligado
  // ------------------------------------------------------------------------
  function reator({ R, c, t, A, falando, processando, mic, micAberto, servidorOk, reduzido, dt, glow }) {
    const AZUL_FAIXA = document.documentElement.dataset.cor === 'dourado' ? '#f2b95c' : '#5ec8f0';

    // moldura externa: circulo fino + segmentos grossos que giram bem devagar
    anel(R * 0.975, 1, 0.3 * A[0]);
    {
      const rot = t * 1.5 * GRAU;
      glow(true);
      for (const [a0, a1] of [[20, 46], [108, 124], [200, 232], [298, 314], [338, 346]]) {
        arco(R * 0.975, rot + a0 * GRAU, rot + a1 * GRAU, R * 0.02, rgba(cor.ciano, 0.75 * A[0]));
      }
      glow(false);
      anel(R * 0.945, 1, 0.18 * A[0]);
    }

    // anel de marcacoes: o comprimento segue o espectro real da fala dele
    {
      const n = perfil.tiques === 90 ? 90 : 120;
      const r0 = R * 0.875;
      ctx.lineWidth = Math.max(1.2, R * 0.006);
      ctx.strokeStyle = rgba(cor.ciano, 0.8 * A[1]);
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const f = i / n;
        const dobra = f < 0.5 ? f * 2 : (1 - f) * 2;
        const b = suave.saida[Math.min(NB - 1, Math.floor(dobra * NB))];
        const len = R * 0.045 + (falando ? Math.pow(b, 1.5) * R * 0.05 : 0);
        const ang = f * Math.PI * 2 - Math.PI / 2;
        ctx.moveTo(c + Math.cos(ang) * r0, c + Math.sin(ang) * r0);
        ctx.lineTo(c + Math.cos(ang) * (r0 + len), c + Math.sin(ang) * (r0 + len));
      }
      ctx.stroke();
    }

    // faixa principal: 300 graus, com a abertura embaixo
    const ini = 160 * GRAU;
    const fim = ini + 300 * GRAU;
    const rMeio = R * 0.73;
    const espessura = R * 0.14;
    {
      const pulso = falando ? Math.min(1, suave.rmsSaida * 5) : 0.08 + 0.05 * Math.sin(t * 1.3);
      arco(rMeio, ini, fim, espessura, rgba(AZUL_FAIXA, (0.42 + pulso * 0.3) * A[2]));
      // divisoes da faixa a cada 10 graus
      ctx.strokeStyle = rgba(cor.fundo0, 0.35 * A[2]);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (let g = 160; g <= 460; g += 10) {
        const a = g * GRAU;
        ctx.moveTo(c + Math.cos(a) * (rMeio - espessura / 2), c + Math.sin(a) * (rMeio - espessura / 2));
        ctx.lineTo(c + Math.cos(a) * (rMeio + espessura / 2), c + Math.sin(a) * (rMeio + espessura / 2));
      }
      ctx.stroke();
      glow(true);
      arco(rMeio - espessura / 2, ini, fim, 2, rgba(cor.ciano, 0.85 * A[2]));
      arco(rMeio + espessura / 2, ini, fim, 1.5, rgba(cor.ciano, 0.6 * A[2]));
      glow(false);
      // inferencia: um brilho percorre a faixa (nao e porcentagem)
      if (processando || !servidorOk) {
        if (processando && !reduzido) suave.varredura = (suave.varredura + dt * 150 * GRAU) % (300 * GRAU);
        const a0 = ini + (reduzido ? 0 : suave.varredura);
        const largura = reduzido ? 300 * GRAU : 34 * GRAU;
        arco(rMeio, a0, Math.min(fim, a0 + largura), espessura * 0.92,
             servidorOk ? rgba('#ffffff', 0.28 * A[2]) : rgba(cor.vermelho, 0.35 * A[2]));
      }
    }

    // pontos amarelos no topo da faixa
    {
      arco(R * 0.745, -118 * GRAU, -62 * GRAU, 1, rgba(cor.ambar, 0.45 * A[3]));
      ctx.fillStyle = rgba(cor.ambar, 0.95 * A[3]);
      glow(true);
      ctx.shadowColor = cor.ambar;
      for (const g of [-112, -100, -90, -80, -68]) {
        ctx.beginPath();
        ctx.arc(c + Math.cos(g * GRAU) * R * 0.745, c + Math.sin(g * GRAU) * R * 0.745, R * 0.012, 0, Math.PI * 2);
        ctx.fill();
      }
      glow(false);
    }

    // colchete ambar a esquerda (dentro da faixa)
    {
      arco(R * 0.64, 150 * GRAU, 208 * GRAU, R * 0.011, rgba(cor.ambar, 0.9 * A[4]));
      ctx.lineCap = 'round';
      arco(R * 0.64, 140 * GRAU, 153 * GRAU, R * 0.032, rgba(cor.ambar, 0.9 * A[4]));
      ctx.lineCap = 'butt';
    }

    // anel interno: microfone
    {
      const r = R * 0.6;
      if (mic === 'erro') {
        ctx.setLineDash([4, 6]);
        anel(r, 1.5, 0.8 * A[5], cor.vermelho);
        ctx.setLineDash([]);
      } else if (!micAberto) {
        ctx.setLineDash([2, 7]);
        anel(r, 1, 0.35 * A[5], mic === 'pausado' ? cor.azul : cor.ciano);
        ctx.setLineDash([]);
      } else {
        const n = perfil.barrasIn;
        ctx.lineWidth = Math.max(1.2, (2 * Math.PI * r) / n * 0.4);
        ctx.strokeStyle = rgba(cor.ciano, (mic === 'captando' ? 0.95 : 0.55) * A[5]);
        ctx.beginPath();
        for (let i = 0; i < n; i++) {
          const f = i / n;
          const dobra = f < 0.5 ? f * 2 : (1 - f) * 2;
          const b = suave.entrada[Math.min(NB - 1, Math.floor(dobra * NB))];
          const len = 1 + Math.pow(b, 1.6) * R * 0.05;
          const ang = f * Math.PI * 2 - Math.PI / 2;
          ctx.moveTo(c + Math.cos(ang) * r, c + Math.sin(ang) * r);
          ctx.lineTo(c + Math.cos(ang) * (r - len), c + Math.sin(ang) * (r - len));
        }
        ctx.stroke();
      }
    }

    // circulos internos brilhantes
    glow(true);
    anel(R * 0.575, 2, 0.9 * A[6]);
    glow(false);
    anel(R * 0.545, 1, 0.35 * A[6]);

    // nucleo escuro com tracado tecnico discreto
    {
      const r = R * 0.54;
      const g = ctx.createRadialGradient(c, c, r * 0.1, c, c, r);
      g.addColorStop(0, rgba(cor.fundo1, 0.96));
      g.addColorStop(1, rgba(cor.fundo0, 0.98));
      ctx.beginPath();
      ctx.arc(c, c, r, 0, Math.PI * 2);
      ctx.fillStyle = g;
      ctx.fill();
      ctx.strokeStyle = rgba(cor.ciano, 0.08 * A[7]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(c - r * 0.9, c); ctx.lineTo(c + r * 0.9, c);
      ctx.moveTo(c, c - r * 0.9); ctx.lineTo(c, c + r * 0.9);
      ctx.stroke();
      anel(r * 0.66, 1, 0.1 * A[7]);
      anel(r * 0.4, 1, 0.08 * A[7]);
      ctx.strokeStyle = rgba(cor.ciano, 0.14 * A[7]);
      ctx.beginPath();
      for (let i = 0; i < 12; i++) {
        const a = i * 30 * GRAU;
        ctx.moveTo(c + Math.cos(a) * r * 0.62, c + Math.sin(a) * r * 0.62);
        ctx.lineTo(c + Math.cos(a) * r * 0.7, c + Math.sin(a) * r * 0.7);
      }
      ctx.stroke();
    }
  }

  function quadro(agora) {
    raf = requestAnimationFrame(quadro);
    if (agora - ultimo < 1000 / perfil.fps - 1) return;
    const dt = ultimo ? Math.min(0.1, (agora - ultimo) / 1000) : 0.016;
    ultimo = agora;
    desenhar(agora, dt);
  }

  // janela oculta/minimizada: para de desenhar
  function visibilidade() {
    if (document.hidden) { cancelAnimationFrame(raf); raf = 0; }
    else if (!raf) { ultimo = 0; raf = requestAnimationFrame(quadro); }
  }
  document.addEventListener('visibilitychange', visibilidade);

  lerCores();
  window.addEventListener('hud-cores', lerCores);
  redimensionar();
  raf = requestAnimationFrame(quadro);

  return {
    definirPerfil(nome) { perfil = PERFIS[nome] ?? PERFIS.equilibrado; redimensionar(); },
    pularBoot() { pularBoot = true; },
    fps() { return medidas.fps; },
    destruir() {
      cancelAnimationFrame(raf);
      obs.disconnect();
      document.removeEventListener('visibilitychange', visibilidade);
      window.removeEventListener('hud-cores', lerCores);
    },
  };
}

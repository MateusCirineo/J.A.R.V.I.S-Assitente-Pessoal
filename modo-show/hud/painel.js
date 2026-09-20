// Painel: telemetria real, com ausencia de dado sempre explicita.

import {
  loja, conectar, ouvir, acao, inferenciaAtiva, num, comUnidade, haQuanto, hora,
  desatualizada, el, texto, chip, TRACO, escapar, bytes, taxa, iconeClima,
} from './cliente.js';

const NS = 'http://www.w3.org/2000/svg';
const C = 2 * Math.PI * 40;

// ---------------------------------------------------------------------------
// medidores circulares
function criarMedidor(fig) {
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 100 100');
  svg.setAttribute('aria-hidden', 'true');
  const add = (tag, attrs) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    svg.appendChild(e);
    return e;
  };
  for (let i = 0; i < 36; i++) {
    const a = (i / 36) * Math.PI * 2;
    const r1 = i % 9 === 0 ? 44 : 46;
    add('line', { x1: 50 + Math.cos(a) * r1, y1: 50 + Math.sin(a) * r1,
                  x2: 50 + Math.cos(a) * 48, y2: 50 + Math.sin(a) * 48,
                  stroke: 'rgba(50,232,243,0.35)', 'stroke-width': 0.8 });
  }
  add('circle', { cx: 50, cy: 50, r: 40, fill: 'none', stroke: 'rgba(50,232,243,0.12)', 'stroke-width': 6 });
  const arco = add('circle', { cx: 50, cy: 50, r: 40, fill: 'none', stroke: '#32e8f3', 'stroke-width': 6,
                               'stroke-dasharray': `0 ${C}`, transform: 'rotate(-90 50 50)' });
  add('circle', { cx: 50, cy: 50, r: 31, fill: 'none', stroke: 'rgba(50,232,243,0.2)', 'stroke-width': 0.8 });
  const valor = add('text', { x: 50, y: 53, 'text-anchor': 'middle', fill: '#e5f8ff',
                              'font-family': 'Cascadia Mono, Consolas, monospace', 'font-size': 17 });
  const unidade = add('text', { x: 50, y: 66, 'text-anchor': 'middle', fill: '#8fb5c5',
                                'font-family': 'Bahnschrift, Segoe UI', 'font-size': 7, 'letter-spacing': 1 });
  fig.querySelector('.svg').appendChild(svg);
  return {
    // pct 0..100; cor: funcao pct -> cor; rotulo: texto sob o numero
    definir(pct, status, { rotulo = '% EM USO', cor, mostrado } = {}) {
      if (status === 'medido' && typeof pct === 'number') {
        const c = cor ? cor(pct) : pct >= 88 ? '#ff5964' : pct >= 70 ? '#ffb547' : '#32e8f3';
        arco.setAttribute('stroke', c);
        arco.setAttribute('stroke-dasharray', `${(Math.max(0, Math.min(100, pct)) / 100) * C} ${C}`);
        valor.textContent = mostrado ?? Math.round(pct);
        unidade.textContent = rotulo;
      } else {
        arco.setAttribute('stroke-dasharray', `0 ${C}`);
        valor.textContent = status === 'aguardando' ? '…' : TRACO;
        unidade.textContent = status === 'erro' ? 'ERRO' : status === 'aguardando' ? 'AGUARDANDO' : 'SEM DADO';
      }
    },
  };
}

const medidores = Object.fromEntries(
  ['mem', 'cpu', 'gpu', 'dsk', 'bat', 'tmp'].map((k) => [k, criarMedidor(el(`g-${k}`))]),
);

function setHtml(id, html) { const e = el(id); if (e.dataset.cache !== html) { e.innerHTML = html; e.dataset.cache = html; } }
function gb(v) { return comUnidade(v, 'GB', 1); }
function vazio(txt) { return `<li class="vazio"><span class="t">${escapar(txt)}</span></li>`; }

// ---------------------------------------------------------------------------
function renderSistema(t) {
  const s = t.sistema ?? {};
  const m = s.memoria ?? {};
  medidores.mem.definir(m.uso_pct, m.status);
  texto('g-mem-d', m.status === 'medido' ? `${gb(m.livre_gb)} livres de ${gb(m.total_gb)}` : TRACO);

  const c = s.cpu ?? {};
  medidores.cpu.definir(c.uso_pct, c.status);
  texto('g-cpu-d', c.status === 'aguardando' ? 'precisa de 2 amostras' : c.status === 'medido' ? 'uso médio no intervalo' : TRACO);

  const g = s.gpu ?? {};
  medidores.gpu.definir(g.uso_pct, g.status);
  texto('g-gpu-d', g.status === 'medido' ? (g.nome ?? 'GPU') : g.motivo ?? TRACO);

  const d = s.disco ?? {};
  medidores.dsk.definir(d.uso_pct, d.status);
  texto('g-dsk-d', d.status === 'medido' ? `${gb(d.livre_gb)} livres de ${gb(d.total_gb)} (${d.unidade})` : TRACO);

  const b = s.bateria ?? {};
  // bateria: pouca carga e que e ruim (cor invertida)
  medidores.bat.definir(b.percentual, b.status, {
    rotulo: '% CARGA', cor: (p) => (b.na_tomada ? '#3de6b0' : p <= 20 ? '#ff5964' : p <= 40 ? '#ffb547' : '#32e8f3'),
  });
  texto('g-bat-d', b.status === 'medido'
    ? (b.na_tomada ? 'na tomada · carregando' : b.restante_min ? `na bateria · ~${b.restante_min} min` : 'na bateria')
    : b.motivo ?? TRACO);

  const tp = s.temperatura ?? {};
  const temTemp = tp.status === 'medido';
  el('g-tmp').classList.toggle('oculto', !temTemp);
  if (temTemp) {
    medidores.tmp.definir(Math.min(100, Math.max(0, (tp.celsius - 30) / 70 * 100)), 'medido',
                          { rotulo: '°C', mostrado: Math.round(tp.celsius) });
    texto('g-tmp-d', tp.sensor ?? 'CPU');
  }
  const notas = [];
  if (!temTemp) notas.push(`Temperatura: ${tp.motivo ?? 'sem leitura'}.`);
  texto('a-notas', notas.join(' '));
}

function renderAgora() {
  const est = loja.estado;
  if (!est) return;
  const inf = est.inferencia ?? {};
  texto('a-inf', inferenciaAtiva(est) ? `processando · ${inf.modelo ?? TRACO}${inf.voz_em_andamento ? ' (voz)' : ''}` : 'ociosa');
  texto('a-mic', est.microfone?.estado ?? TRACO);
  texto('a-voz', est.reproducao?.estado ?? TRACO);
  const cam = est.camera ?? {};
  texto('a-cam', cam.ativa ? `ligada · ${cam.presente ? 'presença detectada' : 'ninguém à frente'}` : 'desligada');
  texto('a-pres', cam.presente && cam.desde ? `presente ${haQuanto(cam.desde)}` : '');
}

// ---------------------------------------------------------------------------
function renderClima(t) {
  const c = t.clima ?? {};
  texto('cl-local', c.local ? [c.local.nome, c.local.regiao].filter(Boolean).join(' · ') : 'cidade não definida');
  if (c.status === 'medido' || c.status === 'desatualizado') {
    const a = c.atual;
    const fmtDia = (iso, i) => (i === 0 ? 'hoje' : new Date(`${iso}T12:00`).toLocaleDateString('pt-BR', { weekday: 'short' }));
    setHtml('cl-corpo', `
      <div class="clima-atual">${iconeClima(a.icone, 46)}
        <div><div><span class="temp">${Math.round(a.temperatura)}°</span></div>
        <div class="desc">${escapar(a.descricao)}</div></div>
        <div class="fraco pequeno">sensação ${Math.round(a.sensacao)}° · umidade ${a.umidade}%<br>
        vento ${Math.round(a.vento_kmh)} km/h · chuva ${num(a.chuva_mm, 1)} mm${c.status === 'desatualizado' ? '<br><span class="ambar">dado antigo</span>' : ''}</div>
      </div>
      <div class="clima-dias">${c.dias.map((d, i) => `<div><span class="dia">${fmtDia(d.data, i)}</span>
        ${iconeClima(d.icone, 22)}<span class="mm">${Math.round(d.min)}° / ${Math.round(d.max)}°</span>
        <span class="chuva">${d.chuva_pct ?? TRACO}%</span></div>`).join('')}</div>`);
  } else if (c.status === 'nao_configurado') {
    setHtml('cl-corpo', '<p class="fraco">Digite sua cidade abaixo para ativar o clima e a previsão.</p>');
  } else if (c.status === 'erro') {
    setHtml('cl-corpo', `<p class="vermelho">Não consegui consultar o clima (${escapar(c.detalhe)}).</p>`);
  } else {
    setHtml('cl-corpo', '<p class="fraco">Carregando…</p>');
  }
  // outras cidades: resumo de cada uma, com trocar para principal e remover
  const extras = loja.prefs?.climas_extras ?? [];
  const leituras = c.outros ?? [];
  setHtml('cl-extras', extras.map((lc, i) => {
    const o = leituras.find((x) => x.local?.lat === lc.lat && x.local?.lon === lc.lon);
    const agora = o && (o.status === 'medido' || o.status === 'desatualizado')
      ? `${iconeClima(o.atual.icone, 18)} ${Math.round(o.atual.temperatura)}° · ${escapar(o.atual.descricao)}`
      : o?.status === 'erro' ? 'sem leitura' : '…';
    return `<li><span class="t">${escapar(lc.nome)}${lc.regiao ? `, ${escapar(lc.regiao)}` : ''}</span>
      <span class="mono">${agora}</span>
      <button type="button" class="botao mini" data-i="${i}" data-op="principal">Principal</button>
      <button type="button" class="remover" data-i="${i}" data-op="remover" aria-label="Remover ${escapar(lc.nome)}">✕</button></li>`;
  }).join(''));
}

function renderAgenda(t) {
  const ag = t.agenda ?? {};
  const conf = loja.prefs?.agenda_configurada;
  const gg = loja.prefs?.agenda_google ?? { cliente: false, contas: [] };
  texto('ag-estado', ag.status === 'medido' ? `via ${ag.fonte}` : conf ? 'configurada' : 'não configurada');
  el('ag-remover').disabled = !loja.prefs?.agenda_ics;
  setHtml('ag-contas', gg.contas.map((c) => `<li><span class="t">${escapar(c.email)}</span>
    <span class="${c.reconectar ? 'ambar' : 'verde'}">${c.reconectar ? 'reconectar' : 'conectada'}</span>
    <button type="button" class="remover" data-email="${escapar(c.email)}" aria-label="Desconectar ${escapar(c.email)}">✕</button></li>`).join(''));
  el('ag-conectar').disabled = !gg.cliente;
  texto('ag-conectar', gg.contas.length ? 'Conectar outra conta Google' : 'Conectar conta Google');
  if (!gg.cliente && !el('ag-cliente').dataset.visto) { el('ag-cliente').open = true; el('ag-cliente').dataset.visto = '1'; }
  texto('ag-avisos', (ag.avisos ?? []).join(' · '));
  if (ag.status === 'medido') {
    const agora = Date.now() / 1000;
    setHtml('ag-lista', ag.eventos.length ? ag.eventos.map((e) => {
      const d = new Date(e.inicio * 1000);
      const quando = e.dia_inteiro
        ? `${d.toLocaleDateString('pt-BR', { weekday: 'short', day: 'numeric' })} · dia inteiro`
        : `${d.toLocaleDateString('pt-BR', { weekday: 'short', day: 'numeric' })} ${d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
      const agoraMesmo = !e.dia_inteiro && e.inicio <= agora && e.fim >= agora;
      const extra = [e.agenda, e.local].filter(Boolean).map(escapar).join(' · ');
      return `<li data-n="${agoraMesmo ? 'aviso' : ''}"><span class="t">${escapar(e.titulo)}</span><span class="mono">${quando}</span>${extra ? `<small>${extra}</small>` : ''}</li>`;
    }).join('') : vazio('Nada nos próximos dias.'));
  } else if (ag.status === 'erro') {
    setHtml('ag-lista', vazio(`Não consegui ler a agenda: ${ag.detalhe}.`));
  } else {
    setHtml('ag-lista', vazio(ag.motivo ?? 'Carregando…'));
  }
}

const REPETE = { diario: 'todos os dias', dias_uteis: 'dias úteis', semanal: 'toda semana' };
function renderMonitores() {
  const itens = loja.estado?.monitores?.itens ?? [];
  texto('sc-mon-resumo', itens.length ? `${itens.filter((m) => m.ativo).length} ativo(s)` : 'nenhum');
  setHtml('sc-monitores', itens.length ? itens.map((m) => `<li data-n="${m.ativo ? 'info' : 'off'}"><span class="t">${escapar(m.descricao)}</span>
      <span class="mono fraco">${m.ativo ? (m.verificado_em ? `visto ${hora(m.verificado_em)}` : 'aguardando') : 'pausado'}</span>
      <small>${m.disparos} aviso${m.disparos === 1 ? '' : 's'}</small></li>`).join('')
    : vazio('Nenhum monitor. Crie por voz.'));
}

function renderSecretario() {
  renderMonitores();
  const s = loja.estado?.secretario ?? {};
  const lemb = s.lembretes ?? [];
  const notas = s.notas ?? [];
  texto('sc-resumo', `${lemb.length} lembrete${lemb.length === 1 ? '' : 's'} · ${notas.length} nota${notas.length === 1 ? '' : 's'}`);
  const quando = (ts) => {
    const d = new Date(ts * 1000);
    const hoje = new Date().toDateString() === d.toDateString();
    return `${hoje ? 'hoje' : d.toLocaleDateString('pt-BR', { weekday: 'short', day: 'numeric' })} ${d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
  };
  setHtml('sc-lembretes', lemb.length ? lemb.map((x) => `<li><span class="t">${x.tipo === 'timer' ? '⏱ ' : x.tipo === 'alarme' ? '⏰ ' : ''}${escapar(x.texto)}</span>
      <span class="mono">${x.repetir ? `<span title="${REPETE[x.repetir] ?? ''}" aria-label="${REPETE[x.repetir] ?? ''}">↻ </span>` : ''}${quando(x.quando)}</span>
      <button type="button" class="remover" data-lembrete="${x.id}" aria-label="Cancelar ${escapar(x.texto)}">✕</button></li>`).join('')
    : vazio('Sem lembretes. Diga “Jarvis, me lembre de … às 15h”.'));
  setHtml('sc-notas', notas.length ? notas.slice(0, 8).map((x) => `<li><span class="t">${escapar(x.texto)}</span>
      <span class="mono fraco">${hora(x.em)}</span>
      <button type="button" class="remover" data-nota="${x.id}" aria-label="Apagar nota">✕</button></li>`).join('')
    : vazio('Sem notas.'));
}

// ---- OpenJarvis: agentes, canais, persona (so leitura) --------------------------
function renderOpenJarvis(t) {
  const o = t.openjarvis;
  if (!o) return;
  if (o.status !== 'medido') { texto('oj-resumo', o.detalhe ?? 'aguardando'); return; }
  const p = o.persona ?? {};
  const tem = Object.entries(p).filter(([, v]) => v).map(([k]) => k);
  texto('oj-persona', tem.length ? tem.join(', ') : 'nenhum arquivo (prompt padrão)');
  el('oj-criar-persona').classList.toggle('oculto', Boolean(p['SOUL.md'] && p['USER.md']));
  texto('oj-ponte', o.ponte_canais === 'not_configured' ? `${(o.canais ?? []).length} disponíveis · nenhum conectado` : o.ponte_canais);
  texto('oj-canais', (o.canais ?? []).join(' · '));
  texto('oj-agentes-n', `${o.agentes.length} registrados · ${o.agentes_rodando} rodando · ${o.skills} skills`);
  texto('oj-agentes', o.agentes.map((a) => a.chave + (a.ferramentas ? ' (ferramentas)' : '')).join(' · '));
  texto('oj-resumo', 'instalado');
}

// ---- rotinas (chegada / descanso) ---------------------------------------------
const listaDe = (s, sep = /[,;\n]/) => s.split(sep).map((x) => x.trim()).filter(Boolean);
// ---- casa e celular ---------------------------------------------------------
function renderProjeto() {
  // a tela mostra a MESMA tarefa de que a voz fala: tudo vem do canal "projeto"
  const p = loja.estado?.projeto;
  const t = p?.tarefa;
  texto('pj-estado', t ? `${t.estado_falado}${p.abertas > 1 ? ` · ${p.abertas} em andamento` : ''}`
    : (p?.abertas ? `${p.abertas} em andamento` : '—'));
  if (!t) {
    texto('pj-objetivo', 'Nenhum projeto aberto.');
    setHtml('pj-etapas', '');
    texto('pj-resultados', '');
    return;
  }
  texto('pj-objetivo', `${p.projeto && p.projeto !== t.objetivo ? p.projeto + ' — ' : ''}${t.objetivo}`
    + (t.versao > 1 ? ` (versão ${t.versao})` : ''));
  const marca = { concluida: '✔', falha: '✕', planejada: '·', cancelada: '–' };
  setHtml('pj-etapas', t.etapas?.length ? t.etapas.map((e) => `<li data-feita="${e.estado === 'concluida'}">
      <span class="t">${marca[e.estado] ?? '·'} ${escapar(e.descricao)}</span>
      ${e.resultado ? `<small class="fraco">${escapar(e.resultado)}</small>` : ''}</li>`).join('')
    : vazio('Nenhuma etapa anotada. Diga: falta …'));
  texto('pj-resultados', t.conclusao_quando ? `Termina quando ${t.conclusao_quando}` : '');
}

function renderPeca() {
  // parametros e versoes da peca aberta: o Senhor volta a evidencia sem refazer a conversa
  const p = loja.estado?.peca;
  const bloco = el('pj-peca');
  if (!bloco) return;
  bloco.classList.toggle('oculto', !p?.nome);
  if (!p?.nome) return;
  texto('pc-versao', `${p.nome} · versão ${p.versao}${p.volume_cm3 != null ? ` · ${p.volume_cm3} cm³ medidos` : ''}`);
  texto('pc-parametros', (p.parametros ?? []).map((d) => `${d.nome} ${d.valor}`).join(' · '));
  setHtml('pc-historico', (p.historico ?? []).slice().reverse().map((v) => `<li>
      <span class="t">v${v.versao}</span><small class="fraco">${escapar(v.motivo ?? '')}</small></li>`).join(''));
}

function renderCasa() {
  const c = loja.prefs?.casa;
  if (!c) return;
  texto('cs-resumo', `${c.aparelhos.length} aparelho${c.aparelhos.length === 1 ? '' : 's'}${c.ha ? ' · Home Assistant' : ''}`);
  setHtml('cs-lista', c.aparelhos.length ? c.aparelhos.map((a) => `<li><span class="t">${escapar(a.nome)}</span>
      <span class="mono fraco">${escapar(a.ip ?? '')}</span><small>${escapar(a.tipo)}</small></li>`).join('')
    : vazio(c.descoberto_em ? 'Nenhum aparelho respondeu na rede.' : 'Clique em Procurar aparelhos.'));
  if (document.activeElement !== el('cs-ha-url') && c.ha_url) el('cs-ha-url').value = c.ha_url;
  el('cs-ha-token').placeholder = c.ha ? 'Token salvo (digite para trocar)' : 'Token de acesso de longa duração';
}
function renderCelular() {
  const tg = loja.prefs?.telegram;
  if (!tg) return;
  texto('tg-resumo', tg.pareado ? `pareado${tg.bot ? ' · @' + tg.bot : ''}` : tg.configurado ? 'aguardando pareamento' : 'não configurado');
  texto('tg-codigo', tg.configurado && !tg.pareado && tg.codigo ? `No seu bot, mande: /parear ${tg.codigo}` : (tg.erro ? `Último erro: ${tg.erro}` : ''));
  el('tg-token').placeholder = tg.configurado ? 'Token salvo (digite para trocar)' : 'Token do bot (123456:ABC...)';
  el('tg-avisos').checked = loja.prefs.avisos_no_celular !== false;
}

function renderRotinas() {
  const p = loja.prefs;
  if (!p?.rotina_chegada || el('f-rotinas').contains(document.activeElement)) return;
  el('rt-frases-c').value = p.rotina_chegada.frases.join(', ');
  el('rt-apps').value = p.rotina_chegada.apps.join(', ');
  el('rt-sites').value = p.rotina_chegada.sites.join(' ');
  el('rt-resumo').checked = Boolean(p.rotina_chegada.resumo);
  el('rt-frases-d').value = p.rotina_descanso.frases.join(', ');
  el('rt-fechar').checked = Boolean(p.rotina_descanso.fechar_apps);
  el('rt-acao').value = p.rotina_descanso.acao_final;
  el('rt-inicio').checked = Boolean(p.inicio_com_windows);
}

// ---- catalogo de vozes -------------------------------------------------------
const CAMPOS_CRED = { azure: ['vc-chave', 'vc-regiao'], google: ['vc-chave'], elevenlabs: ['vc-chave', 'vc-vozid', 'vc-modelo'],
                      fish: ['vc-chave', 'vc-modelo'], piper: ['vc-exe', 'vc-modelo'] };
function provedorEscolhido() { return el('vc-provedor').value || loja.prefs?.voz_provedor || 'kokoro'; }
function renderVozes() {
  const p = loja.prefs;
  if (!p?.vozes_catalogo) return;
  const sel = el('vc-provedor');
  const html = p.vozes_catalogo.map((v) => `<option value="${v.id}">${escapar(v.nome)} · ${v.remoto ? 'remoto' : 'local'}${v.pronto ? '' : ' (falta configurar)'}</option>`).join('');
  if (sel.dataset.cache !== html) { sel.innerHTML = html; sel.dataset.cache = html; sel.value = p.voz_provedor || 'kokoro'; }
  const prov = p.vozes_catalogo.find((v) => v.id === provedorEscolhido()) ?? p.vozes_catalogo[0];
  setHtml('vc-vozes', prov.vozes.map((v) => `<option value="${escapar(v)}">`).join(''));
  const campo = el('vc-voz');
  if (document.activeElement !== campo && !campo.dataset.editado) {
    campo.value = prov.id === 'kokoro' ? (p.voz_tts || 'pm_alex') : prov.id === p.voz_provedor ? (p.voz_remota || prov.vozes[0] || '') : (prov.vozes[0] || '');
  }
  const campos = CAMPOS_CRED[prov.id] ?? [];
  el('f-vc-cred').classList.toggle('oculto', !campos.length);
  for (const id of ['vc-chave', 'vc-regiao', 'vc-modelo', 'vc-vozid', 'vc-exe']) el(id).classList.toggle('oculto', !campos.includes(id));
  el('vc-chave').placeholder = prov.configurado.chave ? 'Chave salva (digite para trocar)' : 'Chave da API';
  el('vc-modelo').placeholder = prov.id === 'piper' ? 'Caminho do modelo .onnx' : prov.id === 'fish' ? 'Modelo (s2.1-pro-free, s2.1-pro, s2-pro, s1, drama-3-preview)' : 'Modelo (opcional)';
  const aviso = [];
  if (prov.remoto) aviso.push(`Remoto: o texto que o Jarvis fala vai para ${prov.nome}.`);
  if (!prov.pronto) aviso.push(`Falta: ${prov.falta.join(', ')}.`);
  if (prov.id === 'fish') aviso.push('Voz padrão: “Jarvis (UCM) - Português Brasileiro” da fish.audio; crie a chave em fish.audio → API Keys.');
  if (p.voz_ultimo?.erro && p.voz_ultimo.provedor === prov.id) aviso.push(`Último erro: ${p.voz_ultimo.erro}. Usei o Kokoro no lugar.`);
  texto('vc-aviso', aviso.join(' '));
  el('vc-fish-link').classList.toggle('oculto', prov.id !== 'fish' || Boolean(prov.configurado.chave));
  const u = p.voz_ultimo ?? {};
  texto('vc-atual', u.erro ? `falhou: ${u.provedor}` : u.provedor ? `em uso: ${u.provedor}${u.s != null ? ` · ${u.s} s` : ''}` : (p.voz_provedor || 'kokoro'));
  el('vc-muda').checked = Boolean(p.voz_muda);
  if (p.atalhos?.length) texto('vc-atalhos', p.atalhos.join(' · '));
}

function renderEmail(t) {
  const e = t.email ?? {};
  if (e.status === 'medido') {
    texto('em-resumo', `${e.nao_lidos} não lido${e.nao_lidos === 1 ? '' : 's'}`);
    const itens = e.contas.flatMap((c) => c.recentes.map((r) => ({ ...r, conta: c.email })));
    setHtml('em-lista', itens.length ? itens.map((r) => `<li><span class="t">${escapar(r.de)}</span>
        <span class="mono fraco">${hora(r.em)}</span><small>${escapar(r.assunto)}${e.contas.length > 1 ? ` · ${escapar(r.conta)}` : ''}</small></li>`).join('')
      : vazio('Caixa de entrada em dia.'));
  } else {
    texto('em-resumo', e.status === 'erro' ? 'erro' : 'não conectado');
    setHtml('em-lista', vazio(e.status === 'erro' ? `Não consegui ler: ${e.detalhe}` : (e.motivo ?? 'Conecte sua conta Google no cartão Agenda.')));
  }
}

function renderNoticias(t) {
  const n = t.noticias ?? {};
  texto('nw-fontes', n.status === 'medido' ? n.fontes.join(' · ') : n.status === 'erro' ? 'fora do ar' : '…');
  const seguro = (u) => (typeof u === 'string' && /^https?:\/\//.test(u) ? u : null);
  setHtml('nw-lista', n.status === 'medido' ? n.itens.slice(0, 10).map((x) => {
    const link = seguro(x.link);
    const titulo = link ? `<a href="${escapar(link)}" target="_blank" rel="noopener noreferrer">${escapar(x.titulo)}</a>` : escapar(x.titulo);
    return `<li><span class="t">${titulo}</span><span class="mono fraco">${x.em ? hora(x.em) : ''}</span><small>${escapar(x.fonte)}</small></li>`;
  }).join('') : vazio(n.status === 'erro' ? `Sem notícias agora (${n.detalhe})` : 'Carregando…'));
}

function renderTarefas() {
  const itens = loja.estado?.tarefas?.itens ?? [];
  const pend = itens.filter((t) => !t.feita).length;
  texto('tf-resumo', `${pend} pendente${pend === 1 ? '' : 's'} · ${itens.length - pend} feita${itens.length - pend === 1 ? '' : 's'}`);
  setHtml('tf-lista', itens.length ? itens.map((t) => `<li data-feita="${t.feita}">
      <input type="checkbox" data-id="${t.id}" ${t.feita ? 'checked' : ''} aria-label="Concluir ${escapar(t.texto)}">
      <span class="t">${escapar(t.texto)}</span>
      <button class="remover" data-id="${t.id}" type="button" aria-label="Remover ${escapar(t.texto)}">✕</button></li>`).join('')
    : vazio('Nenhuma tarefa. Adicione acima ou por voz.'));
}

function renderNotificacoes() {
  const n = loja.estado?.notificacoes ?? {};
  setHtml('nt-lista', (n.itens ?? []).length ? n.itens.map((i) =>
    `<li data-n="${i.nivel}"><span class="t">${escapar(i.texto)}</span><span class="mono fraco">${hora(i.em)}</span></li>`).join('')
    : vazio('Sem notificações.'));
}

function renderMidia(t) {
  const m = t.midia ?? {};
  const tem = m.status === 'medido' && m.titulo;
  texto('md-titulo', tem ? m.titulo : m.status === 'erro' ? 'Mídia indisponível' : 'Nada tocando');
  texto('md-artista', tem ? [m.artista, m.album].filter(Boolean).join(' · ') : '');
  texto('md-app', tem ? `${m.app} · ${m.situacao}` : '');
  el('md-prog').style.width = tem && m.duracao_s ? `${Math.min(100, (m.posicao_s / m.duracao_s) * 100)}%` : '0%';
  el('md-ant').disabled = !tem || !m.pode_voltar;
  el('md-prox').disabled = !tem || !m.pode_avancar;
  el('md-play').disabled = !tem;
  const v = t.volume ?? {};
  if (v.status === 'medido') {
    if (document.activeElement !== el('vs-vol')) el('vs-vol').value = String(Math.round(v.volume * 100));
    texto('vs-num', `${Math.round(v.volume * 100)}%`);
    el('vs-mudo').setAttribute('aria-pressed', String(v.mudo));
    texto('vs-mudo', v.mudo ? 'Sem som' : 'Mudo');
  } else {
    texto('vs-num', TRACO);
  }
}

function renderRede(t) {
  const r = t.sistema?.rede ?? {};
  texto('rd-rec', r.status === 'medido' ? taxa(r.recebimento_bps) : TRACO);
  texto('rd-env', r.status === 'medido' ? taxa(r.envio_bps) : TRACO);
  texto('rd-if', r.nome ? `${r.nome} · ${r.ipv4}` : TRACO);
  const dv = t.dispositivos ?? {};
  const rede = (dv.redes ?? [])[0];
  texto('rd-ssid', rede ? `${rede.nome} (${rede.ipv4})` : TRACO);
  chip('rd-net', dv.internet ? 'ok' : dv.status === 'medido' ? 'erro' : 'off',
       dv.internet ? 'Internet' : dv.status === 'medido' ? 'Sem internet' : '—');
  const h = r.historico ?? [];
  if (h.length > 1) {
    const max = Math.max(1, ...h.flat());
    const pts = (i) => h.map((p, x) => `${(x / (h.length - 1)) * 300},${58 - (p[i] / max) * 54}`).join(' ');
    el('rd-l-rec').setAttribute('points', pts(1));
    el('rd-l-env').setAttribute('points', pts(0));
  }
}

function renderModelos(t) {
  const est = loja.estado ?? {};
  const o = t.ollama ?? {};
  if (o.status !== 'ok') {
    texto('mod-resumo', 'Ollama fora do ar');
    setHtml('mod-linhas', `<tr><td colspan="3" class="vermelho">Ollama não respondeu: ${escapar(o.detalhe)}</td></tr>`);
    return;
  }
  const chat = est.modelos?.chat;
  const voz = est.modelos?.voz;
  const carregados = new Map((o.carregados ?? []).map((m) => [m.nome, m]));
  const nomes = new Set(o.instalados.map((m) => m.nome));
  const linhas = o.instalados.map((m) => {
    const chips = [];
    if (m.nome === chat) chips.push('<span class="chip" data-s="ativo">chat</span>');
    if (m.nome === voz) chips.push('<span class="chip" data-s="ativo">voz</span>');
    const c = carregados.get(m.nome);
    if (c) chips.push(`<span class="chip" data-s="ok">em memória${c.expira ? ` · até ${new Date(c.expira).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}` : ''}</span>`);
    return `<tr><td>${escapar(m.nome)}</td><td class="num">${num(m.tamanho_gb, 1)} GB</td><td>${chips.join('') || '<span class="fraco">instalado</span>'}</td></tr>`;
  });
  for (const [papel, nome] of [['chat', chat], ['voz', voz]]) {
    if (nome && !nomes.has(nome)) linhas.push(`<tr><td>${escapar(nome)}</td><td class="num">${TRACO}</td><td><span class="chip" data-s="erro">${papel}: não instalado</span></td></tr>`);
  }
  setHtml('mod-linhas', linhas.join('') || '<tr><td colspan="3" class="fraco">nenhum modelo instalado</td></tr>');
  texto('mod-resumo', `${o.instalados.length} instalados · ${carregados.size} em memória`);
}

function renderInferencia(t) {
  const srv = t.servidor ?? {};
  const ids = ['s-req', 's-tok', 's-lat', 's-vaz'];
  if (srv.status !== 'ok') {
    ids.forEach((i) => texto(i, TRACO));
    texto('s-ene', TRACO);
    texto('inf-escopo', 'servidor fora do ar');
  } else {
    const s = srv.estatisticas ?? {};
    const req = s.total_requests;
    const tem = typeof req === 'number' && req > 0;         // sem requisicao, zero = sem dado
    texto('inf-escopo', 'desde o início do servidor');
    texto('s-req', typeof req === 'number' ? String(req) : TRACO);
    texto('s-tok', tem ? String(s.total_tokens) : TRACO);
    texto('s-lat', tem ? comUnidade(s.total_latency / req, 's') : TRACO);
    texto('s-vaz', tem ? comUnidade(s.avg_throughput_tok_per_sec, 'tok/s', 2) : TRACO);
    const e = srv.energia ?? {};
    // 1) medidor do proprio OpenJarvis; 2) leitor de sensores do HUD (CPU, por resposta)
    const eu = loja.estado?.inferencia?.energia_ultima;
    const cpu = t.sistema?.energia_cpu;
    texto('s-ene', s.total_energy_joules > 0 ? `${num(s.total_energy_joules, 1)} J · ${num(e.avg_power_w, 1)} W (medido)`
      : eu ? `última resposta: ${num(eu.joules, 0)} J (${num(eu.wh, 3)} Wh) em ${num(eu.segundos, 0)} s · CPU medida`
        : cpu?.status === 'medido' ? `CPU agora: ${num(cpu.potencia_w, 1)} W · aguardando uma resposta`
          : !tem ? `${TRACO} sem inferências ainda`
            : 'Indisponível · instale o leitor de sensores (ver LEIA-ME)');
  }
  const u = loja.estado?.inferencia?.ultima;
  texto('u-mod', u?.modelo ?? TRACO);
  texto('u-lat', u ? `${comUnidade(u.latencia_s, 's')} · ${comUnidade(u.ttft_s, 's')}` : TRACO);
  texto('u-tok', u ? `${u.tokens_entrada ?? TRACO} · ${u.tokens_saida ?? TRACO}` : TRACO);
  texto('u-em', u ? `${hora(u.em)} (${haQuanto(u.em)})` : 'nenhuma nesta sessão do runtime');
  texto('u-fonte', u?.fonte ? `fonte: ${u.fonte}` : '');
}

function renderCustos(t) {
  const c = t.servidor_extra?.custos;
  if (!c) { setHtml('cu-lista', vazio('Sem dados de custo (servidor fora ou sem uso).')); texto('cu-nota', ''); return; }
  const usd = (v) => (typeof v === 'number' ? `US$ ${v.toFixed(4)}` : TRACO);
  setHtml('cu-lista', `<li><span class="t verde">Local (Ollama)</span><span class="mono">${usd(c.custo_local)}</span>
      <small>sem taxa de API; a energia deste computador não está incluída (sem medidor)</small></li>`
    + c.provedores.map((p) => `<li><span class="t">${escapar(p.nome)}</span><span class="mono">${usd(p.custo)}</span>
      <small>mesmo volume na nuvem${p.energia_wh ? ` · ~${num(p.energia_wh, 2)} Wh estimados no datacenter` : ''}</small></li>`).join(''));
  texto('cu-nota', `${c.chamadas ?? TRACO} chamadas · ${c.tokens_entrada ?? TRACO} tokens de entrada · ${c.tokens_saida ?? TRACO} de saída. Preços de tabela configurados no OpenJarvis; não são preços em tempo real.`);
}

function renderHistorico(t) {
  const h = t.servidor_extra?.historico;
  if (!h) { setHtml('hs-lista', vazio('Sem histórico (servidor fora?).')); return; }
  setHtml('hs-lista', h.length ? h.map((i) => `<li><span class="t">${escapar(i.consulta || '(vazia)')}</span>
      <span class="mono fraco">${i.em ? hora(i.em) : TRACO}</span>
      <small>${escapar(i.modelo ?? TRACO)} · ${i.duracao_s} s${i.agente ? ` · ${escapar(i.agente)}` : ''}</small></li>`).join('')
    : vazio('Nenhuma pergunta registrada ainda.'));
}

function renderAutomacoes(t) {
  const x = t.servidor_extra ?? {};
  const itens = (x.automacoes ?? []).map((a) => `<li><span class="t">${escapar(a.nome)}</span>
      <span class="chip" data-s="${a.situacao === 'running' ? 'ativo' : 'off'}">${escapar(a.situacao ?? TRACO)}</span>
      <small>${escapar(a.tipo)} · agenda: ${escapar(a.agenda === 'manual' ? 'manual' : `${a.agenda} ${a.valor || ''}`)}</small></li>`);
  if (x.resumo_diario) {
    itens.push(`<li><span class="t">Resumo diário (digest)</span>
      <span class="chip" data-s="${x.resumo_diario.ativo ? 'ok' : 'off'}">${x.resumo_diario.ativo ? 'ativo' : 'desligado'}</span>
      <small>cron ${escapar(x.resumo_diario.cron ?? TRACO)}</small></li>`);
  }
  setHtml('au-lista', itens.join('') || vazio('Nenhuma automação (servidor fora?).'));
}

function renderServicos(t) {
  const est = loja.estado ?? {};
  const o = t.ollama ?? {};
  const s = t.servidor ?? {};
  const x = t.servidor_extra ?? {};
  const etapa = (id) => est.boot?.etapas?.find((e) => e.id === id);
  const item = (nome, st, rot, det) =>
    `<li><span>${nome}</span><span class="chip" data-s="${st}">${rot}</span>${det ? `<small>${escapar(det)}</small>` : ''}</li>`;
  const stt = etapa('transcricao');
  const tts = etapa('sintese');
  const mem = x.memoria ?? {};
  const conectados = (x.conectores ?? []).filter((c) => c.conectado).map((c) => c.nome);
  const religar = s.status !== 'ok'
    ? '<li><span class="vermelho">O servidor OpenJarvis está fora do ar.</span><button class="botao mini" type="button" id="b-religar">Religar</button></li>'
    : '';
  setHtml('servicos', religar + [
    item('Ollama', o.status === 'ok' ? 'ok' : 'erro', o.status === 'ok' ? 'no ar' : 'fora',
         `${o.endpoint ?? ''}${o.status === 'ok' ? ` · ${o.carregados?.length ?? 0} modelo(s) em memória` : ` · ${o.detalhe ?? ''}`}`),
    item('Servidor OpenJarvis', s.status === 'ok' ? 'ok' : 'erro', s.status === 'ok' ? 'no ar' : 'fora',
         s.status === 'ok' ? `${s.endpoint} · agente ${s.info?.agent ?? TRACO} · modelo ${s.info?.model ?? TRACO}` : s.detalhe),
    item('Memória do OpenJarvis', mem.status === 'medido' ? 'ok' : 'aviso', mem.status === 'medido' ? 'ok' : 'indisponível',
         mem.motivo ?? null),
    item('Conectores', conectados.length ? 'ok' : 'off', `${conectados.length} conectado(s)`,
         conectados.join(', ') || 'nenhum conectado (Google, Spotify etc. via jarvis connect)'),
    item('Transcrição do servidor', s.fala?.available ? 'ok' : 'off', s.fala?.available ? 'disponível' : 'indisponível',
         s.fala?.backend ? `backend ${s.fala.backend} (botão de voz do chat)` : null),
    item('Eventos (WebSocket)', est.conexao?.eventos?.estado === 'conectado' ? 'ok' : 'aviso',
         est.conexao?.eventos?.estado ?? TRACO, '/v1/agents/events'),
    item('Runtime do HUD', loja.conectado ? 'ok' : 'erro', loja.conectado ? 'conectado' : 'desconectado',
         'telas, voz, câmera e telemetria deste painel'),
    item('Voz do runtime', tts?.estado === 'ok' && stt?.estado === 'ok' ? 'ok' : tts?.estado === 'falha' || stt?.estado === 'falha' ? 'erro' : 'aviso',
         tts?.estado === 'ok' && stt?.estado === 'ok' ? 'pronta' : tts?.estado ?? TRACO,
         `síntese: ${tts?.detalhe ?? TRACO} · transcrição: ${stt?.detalhe ?? TRACO}`),
  ].join(''));
}

function renderVozRota(t) {
  const est = loja.estado ?? {};
  const cfg = t.config ?? {};
  texto('v-tts', cfg.tts ? `${cfg.tts} · ${cfg.voz ?? TRACO}` : TRACO);
  texto('v-stt', `faster-whisper base · ${cfg.idioma ?? TRACO} · ${cfg.stt_dispositivo ?? TRACO}`);
  const mic = est.microfone ?? {};
  texto('v-in', mic.dispositivo ? `${mic.dispositivo} · ${mic.estado}` : mic.estado ?? TRACO);
  const rep = est.reproducao ?? {};
  texto('v-out', `${rep.dispositivo ?? TRACO} · ${typeof rep.volume === 'number' ? `${Math.round(rep.volume * 100)} %` : TRACO}`);
  texto('r-pref', cfg.motor_preferido ? `${cfg.motor_preferido} (padrão ${cfg.motor_padrao ?? TRACO})` : TRACO);
  texto('r-rot', t.servidor?.info?.engine ?? TRACO);
  const canais = t.servidor?.canais;
  texto('r-canais', canais?.status === 'not_configured' ? 'nenhum configurado' : canais?.status ?? TRACO);
  texto('r-nota', cfg.motor_preferido === 'ollama'
    ? 'A configuração prefere o Ollama em 127.0.0.1. O roteador do servidor pode usar outros motores se forem configurados; isto não é garantia de que tudo fica local. Clima e agenda (se configurados) consultam a internet.'
    : '');
}

function renderApps(t) {
  const a = t.apps ?? {};
  texto('ap-total', a.status === 'medido' ? `${a.total} app(s)` : TRACO);
  setHtml('ap-lista', a.status === 'medido' && a.apps.length ? a.apps.map((x) =>
    `<li><span class="t">${escapar(x.app)}</span><span class="mono fraco">${x.janelas} jan.</span><small>${escapar(x.titulo)}</small></li>`).join('')
    : vazio(a.status === 'medido' ? 'Nenhuma janela aberta.' : 'Carregando…'));
}

function renderDownloads(t) {
  const d = t.arquivos?.downloads ?? {};
  texto('dl-pasta', d.pasta ? d.pasta.split('\\').pop() : TRACO);
  if (d.status !== 'medido') { setHtml('dl-lista', vazio(d.motivo ?? 'Carregando…')); return; }
  const and = d.em_andamento.map((i) => `<li data-n="aviso"><span class="t">⬇ ${escapar(i.nome)}</span><span class="mono">${bytes(i.bytes)}</span><small>baixando…</small></li>`);
  const rec = d.recentes.map((i) => `<li><span class="t">${escapar(i.nome)}</span><span class="mono fraco">${i.pasta ? 'pasta' : bytes(i.bytes)}</span><small>${haQuanto(i.modificado)}</small></li>`);
  setHtml('dl-lista', [...and, ...rec].join('') || vazio('Pasta vazia.'));
}

function renderPastas(t) {
  const p = t.arquivos?.pastas ?? {};
  if (p.status !== 'medido') { setHtml('ps-corpo', '<p class="fraco">Carregando…</p>'); return; }
  setHtml('ps-corpo', p.pastas.map((x) => {
    if (x.status !== 'medido') return `<div class="grupo"><span class="rotulo">${escapar(x.caminho)}</span><div class="vermelho">não encontrada</div></div>`;
    const alt = x.alterados_recentes.length
      ? x.alterados_recentes.map((i) => `${escapar(i.nome)} (${haQuanto(i.modificado)})`).join(' · ')
      : `sem alterações nos últimos 15 min · último: ${escapar(x.ultimos[0]?.nome ?? TRACO)}`;
    return `<div class="grupo"><span class="rotulo">${escapar(x.caminho.split('\\').pop())} · ${x.total} itens</span><div>${alt}</div></div>`;
  }).join(''));
  const campo = el('ps-lista');
  if (document.activeElement !== campo && !campo.dataset.editado) campo.value = (loja.prefs?.pastas_monitoradas ?? []).join('\n');
}

function renderDispositivos(t) {
  const d = t.dispositivos ?? {};
  if (d.status !== 'medido') { setHtml('dv-corpo', `<p class="fraco">${d.status === 'erro' ? `Erro: ${escapar(d.detalhe)}` : 'Carregando… (atualiza a cada 60 s)'}</p>`); return; }
  setHtml('dv-corpo', Object.entries(d.grupos).map(([g, nomes]) =>
    `<div class="grupo"><span class="rotulo">${escapar(g)}</span><div>${nomes.map(escapar).join(' · ')}</div></div>`).join('')
    || '<p class="fraco">Nenhum dispositivo listado.</p>');
}

function renderEventos() {
  const evs = (loja.estado?.eventos ?? []).slice(-16).reverse();
  setHtml('eventos', evs.map((e) =>
    `<li data-n="${e.nivel}"><span>${hora(e.em)}</span><span>${escapar(e.tipo)}</span><span>${escapar(e.texto)}</span></li>`,
  ).join('') || '<li><span></span><span></span><span class="fraco">sem eventos</span></li>');
}

function renderWidgets() {
  const w = loja.prefs?.widgets_painel ?? {};
  for (const k of ['projeto', 'clima', 'agenda', 'vozcat', 'rotinas', 'openjarvis', 'secretario', 'email', 'noticias', 'tarefas', 'notificacoes', 'midia', 'rede', 'modelos', 'inferencia',
                   'custos', 'historico', 'automacoes', 'servicos', 'voz', 'apps', 'downloads', 'pastas',
                   'dispositivos', 'eventos']) {
    el(`w-${k}`).classList.toggle('oculto', w[k] === false);
  }
}

function renderTelemetria() {
  const t = loja.telemetria;
  if (!t?.em) return;
  const velho = desatualizada(t);
  const at = el('atualizado');
  at.textContent = `${velho ? 'desatualizado · ' : ''}amostra ${haQuanto(t.em)}`;
  at.dataset.velho = String(velho);
  for (const id of ['g-mem', 'g-cpu', 'g-gpu', 'g-dsk', 'g-bat', 'w-modelos', 'w-inferencia', 'w-servicos', 'w-rede']) {
    el(id).classList.toggle('velho', velho);
  }
  const passos = [renderOpenJarvis, renderSistema, renderClima, renderAgenda, renderMidia, renderRede, renderModelos,
                  renderInferencia, renderCustos, renderHistorico, renderAutomacoes, renderServicos,
                  renderVozRota, renderApps, renderDownloads, renderPastas, renderDispositivos,
                  renderEmail, renderNoticias];
  for (const f of passos) {
    try { f(t); } catch (e) { console.error(f.name, e); }         // um cartao quebrado nao derruba os outros
  }
}

// ---------------------------------------------------------------------------
// formularios e controles
el('f-cidade').addEventListener('submit', async (e) => {
  e.preventDefault();
  const nome = el('cl-busca').value.trim();
  if (!nome) return;
  setHtml('cl-opcoes', '<li class="fraco">Buscando…</li>');
  try {
    const r = await acao('/api/clima/buscar', { nome });
    const temPrincipal = Boolean(loja.prefs?.local_clima);
    setHtml('cl-opcoes', r.cidades.length ? r.cidades.map((c, i) =>
      `<li><span>${escapar([c.nome, c.regiao, c.pais].filter(Boolean).join(', '))}</span>
        <button type="button" class="botao mini" data-i="${i}" data-op="principal">Principal</button>
        ${temPrincipal ? `<button type="button" class="botao mini" data-i="${i}" data-op="adicionar">+ Adicionar</button>` : ''}</li>`).join('')
      : '<li class="fraco">Nenhuma cidade encontrada.</li>');
    el('cl-opcoes').onclick = async (ev) => {
      const { i, op } = ev.target.dataset ?? {};
      if (i === undefined) return;
      try {
        if (op === 'adicionar') await acao('/api/clima/extras', { acao: 'adicionar', local: r.cidades[Number(i)] });
        else await acao('/api/clima/local', { local: r.cidades[Number(i)] });
      } catch (err) {
        setHtml('cl-opcoes', `<li class="vermelho">${escapar(err.message)}</li>`);
        return;
      }
      setHtml('cl-opcoes', '');
      el('cl-busca').value = '';
      if (op !== 'adicionar') setHtml('cl-corpo', '<p class="fraco">Carregando previsão…</p>');
    };
  } catch (err) {
    setHtml('cl-opcoes', `<li class="vermelho">${escapar(err.message)}</li>`);
  }
});

el('f-google').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    await acao('/api/agenda/google/cliente', { id: el('gg-id').value, chave: el('gg-chave').value });
    el('gg-id').value = '';
    el('gg-chave').value = '';
    el('ag-cliente').open = false;
    texto('ag-avisos', 'Credencial salva. Agora clique em Conectar conta Google.');
  } catch (err) {
    texto('ag-avisos', `Credencial: ${err.message}`);
  }
});
el('ag-conectar').addEventListener('click', async () => {
  try {
    const r = await acao('/api/agenda/google/conectar');
    texto('ag-avisos', `${r.observacao}. Escolha a conta e permita "ver suas agendas".`);
  } catch (err) {
    texto('ag-avisos', err.message);
  }
});
el('ag-contas').addEventListener('click', (ev) => {
  const email = ev.target.dataset?.email;
  if (!email || !confirm(`Desconectar ${email} do Jarvis? O acesso é revogado no Google.`)) return;
  acao('/api/agenda/google/desconectar', { email }).catch((err) => texto('ag-avisos', err.message));
});

el('vc-provedor').addEventListener('change', () => { delete el('vc-voz').dataset.editado; renderVozes(); });
el('vc-voz').addEventListener('input', () => { el('vc-voz').dataset.editado = '1'; });
el('vc-previa').addEventListener('click', () =>
  acao('/api/voz/previa', { provedor: provedorEscolhido(), voz: el('vc-voz').value.trim() || null }).catch((e) => texto('vc-aviso', e.message)));
el('vc-usar').addEventListener('click', async () => {
  const prov = provedorEscolhido();
  const voz = el('vc-voz').value.trim();
  try {
    await acao('/api/preferencias', { voz_provedor: prov, ...(prov === 'kokoro' ? { voz_tts: voz || 'pm_alex' } : voz ? { voz_remota: voz } : {}) });
    delete el('vc-voz').dataset.editado;
  } catch (e) { texto('vc-aviso', e.message); }
});
el('f-vc-cred').addEventListener('submit', async (e) => {
  e.preventDefault();
  const prov = provedorEscolhido();
  const dados = { provedor: prov, chave: el('vc-chave').value, regiao: el('vc-regiao').value, modelo: el('vc-modelo').value,
                  voz: el('vc-vozid').value, exe: el('vc-exe').value };
  try {
    await acao('/api/voz/credenciais', dados);
    for (const id of ['vc-chave', 'vc-regiao', 'vc-modelo', 'vc-vozid', 'vc-exe']) el(id).value = '';
    texto('vc-aviso', 'Credencial salva só neste computador. Agora: Ouvir prévia.');
  } catch (err) { texto('vc-aviso', err.message); }
});
el('vc-remover').addEventListener('click', () => acao('/api/voz/remover', { provedor: provedorEscolhido() }).catch(() => {}));
el('vc-muda').addEventListener('change', () => acao('/api/preferencias', { voz_muda: el('vc-muda').checked }).catch(() => {}));

el('cs-procurar').addEventListener('click', async () => {
  texto('cs-resumo', 'procurando…');
  try { const r = await acao('/api/casa/descobrir', {}); texto('cs-resumo', `${r.total} aparelho(s)`); }
  catch (e) { texto('cs-resumo', e.message); }
});
el('cs-holo').addEventListener('click', () => acao('/api/janela', { nome: 'holograma' }).catch((e) => texto('cs-nota', e.message)));
el('f-cs-ha').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    const r = await acao('/api/casa/ha', { url: el('cs-ha-url').value, token: el('cs-ha-token').value });
    el('cs-ha-token').value = '';
    texto('cs-nota', `Home Assistant conectado: ${r.entidades} entidades.`);
  } catch (err) { texto('cs-nota', err.message); }
});
el('cs-ha-remover').addEventListener('click', () => acao('/api/casa/ha', { url: '', token: '' })
  .then(() => { el('cs-ha-url').value = ''; texto('cs-nota', 'Home Assistant removido.'); }).catch(() => {}));
el('f-tg').addEventListener('submit', async (e) => {
  e.preventDefault();
  try { const r = await acao('/api/telegram/token', { token: el('tg-token').value }); el('tg-token').value = ''; texto('tg-resumo', `@${r.bot}: aguardando pareamento`); }
  catch (err) { texto('tg-codigo', err.message); }
});
el('tg-desparear').addEventListener('click', () => acao('/api/telegram/desparear', {}).catch(() => {}));
el('tg-avisos').addEventListener('change', () => acao('/api/preferencias', { avisos_no_celular: el('tg-avisos').checked }).catch(() => {}));

el('f-rotinas').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    await acao('/api/preferencias', {
      rotina_chegada: { frases: listaDe(el('rt-frases-c').value), apps: listaDe(el('rt-apps').value),
                        sites: listaDe(el('rt-sites').value, /[\s,;]+/), resumo: el('rt-resumo').checked },
      rotina_descanso: { frases: listaDe(el('rt-frases-d').value), fechar_apps: el('rt-fechar').checked,
                         acao_final: el('rt-acao').value },
    });
    document.activeElement?.blur();
    texto('rt-nota', 'Rotinas salvas. Só sites https são aceitos.');
  } catch (err) { texto('rt-nota', err.message); }
});
el('oj-criar-persona').addEventListener('click', () =>
  acao('/api/openjarvis/persona', {}).then((r) => texto('oj-persona', `criado: ${r.criados.join(', ') || 'nada (já existiam)'}`))
    .catch((err) => texto('oj-persona', err.message)));
el('rt-inicio').addEventListener('change', () =>
  acao('/api/rotinas/inicio', { ligar: el('rt-inicio').checked }).catch((err) => texto('rt-nota', err.message)));

el('f-lembrete').addEventListener('submit', async (e) => {
  e.preventDefault();
  const frase = el('sc-lembrete').value.trim();
  if (!frase) return;
  try {
    await acao('/api/secretario', { acao: 'lembrar', frase });
    el('sc-lembrete').value = '';
  } catch (err) { texto('sc-resumo', err.message); }
});
el('f-nota').addEventListener('submit', async (e) => {
  e.preventDefault();
  const txt = el('sc-nota').value.trim();
  if (!txt) return;
  await acao('/api/secretario', { acao: 'anotar', texto: txt }).catch(() => {});
  el('sc-nota').value = '';
});
el('sc-lembretes').addEventListener('click', (ev) => {
  const id = Number(ev.target.dataset?.lembrete);
  if (id) acao('/api/secretario', { acao: 'cancelar', id }).catch(() => {});
});
el('sc-notas').addEventListener('click', (ev) => {
  const id = Number(ev.target.dataset?.nota);
  if (id) acao('/api/secretario', { acao: 'apagar_nota', id }).catch(() => {});
});

el('cl-extras').addEventListener('click', (ev) => {
  const { i, op } = ev.target.dataset ?? {};
  if (i === undefined) return;
  acao('/api/clima/extras', { acao: op, indice: Number(i) }).catch(() => {});
});

el('f-agenda').addEventListener('submit', async (e) => {
  e.preventDefault();
  const url = el('ag-url').value.trim();
  if (!url) return;
  try {
    await acao('/api/agenda', { ics: url });
    el('ag-url').value = '';
    setHtml('ag-lista', vazio('Lendo a agenda…'));
  } catch (err) {
    setHtml('ag-lista', vazio(err.message));
  }
});
el('ag-remover').addEventListener('click', () => acao('/api/agenda', { ics: '' }).catch(() => {}));

el('f-tarefa').addEventListener('submit', async (e) => {
  e.preventDefault();
  const txt = el('tf-texto').value.trim();
  if (!txt) return;
  await acao('/api/tarefas', { acao: 'adicionar', texto: txt }).catch(() => {});
  el('tf-texto').value = '';
});
el('tf-lista').addEventListener('click', (e) => {
  const id = e.target.dataset?.id;
  if (!id) return;
  const op = e.target.classList.contains('remover') ? 'remover' : 'alternar';
  acao('/api/tarefas', { acao: op, id }).catch(() => {});
});
el('tf-limpar').addEventListener('click', () => acao('/api/tarefas', { acao: 'limpar_feitas' }).catch(() => {}));

el('servicos').addEventListener('click', (e) => {
  if (e.target.id !== 'b-religar') return;
  e.target.disabled = true;
  e.target.textContent = 'Religando…';
  acao('/api/servidor/religar').catch(() => { e.target.disabled = false; e.target.textContent = 'Religar'; });
});
el('nt-lidas').addEventListener('click', () => acao('/api/notificacoes', { acao: 'lidas' }).catch(() => {}));
el('nt-limpar').addEventListener('click', () => acao('/api/notificacoes', { acao: 'limpar' }).catch(() => {}));

for (const [id, op] of [['md-ant', 'anterior'], ['md-play', 'tocar_pausar'], ['md-prox', 'proxima']]) {
  el(id).addEventListener('click', () => acao('/api/midia', { acao: op }).catch(() => {}));
}
let tVol = 0;
el('vs-vol').addEventListener('input', () => {
  clearTimeout(tVol);
  texto('vs-num', `${el('vs-vol').value}%`);
  tVol = setTimeout(() => acao('/api/volume-sistema', { volume: Number(el('vs-vol').value) / 100 }).catch(() => {}), 120);
});
el('vs-mudo').addEventListener('click', () => {
  const mudo = el('vs-mudo').getAttribute('aria-pressed') !== 'true';
  acao('/api/volume-sistema', { mudo }).catch(() => {});
});

el('ps-lista').addEventListener('input', () => { el('ps-lista').dataset.editado = '1'; });
el('f-pastas').addEventListener('submit', async (e) => {
  e.preventDefault();
  const linhas = el('ps-lista').value.split('\n').map((l) => l.trim()).filter(Boolean);
  await acao('/api/preferencias', { pastas_monitoradas: linhas.length ? linhas : null }).catch(() => {});
  delete el('ps-lista').dataset.editado;
});

// ---------------------------------------------------------------------------
function relogio() {
  const a = new Date();
  texto('hora', a.toLocaleTimeString('pt-BR'));
  texto('data', a.toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }));
  chip('c-rt', loja.conectado ? 'ok' : 'erro', loja.conectado ? 'Runtime conectado' : 'Runtime desconectado');
  renderTelemetria();                 // atualiza "ha X s" e o selo de desatualizado
  renderAgora();
}
setInterval(relogio, 1000);
relogio();

ouvir((tipo) => {
  if (tipo === 'telemetria') renderTelemetria();
  if (tipo === 'prefs') { renderWidgets(); renderVozes(); renderRotinas(); renderCasa(); renderCelular(); if (loja.telemetria) { renderAgenda(loja.telemetria); renderPastas(loja.telemetria); } }
  if (tipo === 'estado' || tipo === 'log') {
    renderAgora(); renderTarefas(); renderNotificacoes(); renderEventos(); renderSecretario(); renderProjeto(); renderPeca();
    if (loja.telemetria) { renderServicos(loja.telemetria); renderModelos(loja.telemetria); renderInferencia(loja.telemetria); }
  }
  if (tipo === 'conexao') relogio();
});
conectar();

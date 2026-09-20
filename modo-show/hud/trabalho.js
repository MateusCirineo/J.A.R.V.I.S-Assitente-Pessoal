import { loja, ouvir, conectar, acao } from './cliente.js';
import { HistoricoTrabalho, renderTrabalho, escapar, caixaValida } from './trabalho-dados.js';

export function iniciarTrabalho(painel = document.getElementById('trabalho-painel')) {
  if (!painel) return;
  const el = id => document.getElementById(id), historico = new HistoricoTrabalho();
  let fixado = false, cache = '', novidade = false, abertoAutomaticamente = false;
  const status = mensagem => { el('tr-status').textContent = mensagem; };
  const selecionandoTexto = () => {
    const s = document.getSelection?.();
    return s && !s.isCollapsed && painel.contains(s.anchorNode);
  };
  function render() {
    const est = loja.estado || {};
    historico.receber(est);
    const opcoes = '<option value="">Estado atual</option>' + historico.registros.map(r => `<option value="${r.id}">${escapar(r.titulo)} · ${new Date(r.em * 1000).toLocaleTimeString('pt-BR')}</option>`).join('');
    const seletor = el('tr-historico');
    if (seletor.dataset.opcoes !== opcoes && document.activeElement !== seletor) {
      const anterior = seletor.value;
      seletor.innerHTML = opcoes; seletor.value = anterior;
      seletor.dataset.opcoes = opcoes;
    }
    const registro = historico.registros.find(r => r.id === seletor.value);
    const html = (registro ? '<p class="tr-aviso">Registro anterior desta sessão. Capturas não são guardadas no histórico.</p>' : '') + renderTrabalho(registro?.dados || est);
    if ((fixado || selecionandoTexto()) && html !== cache) { novidade = true; status('Há atualização disponível. Retome quando terminar a leitura.'); }
    else if (html !== cache) { el('tr-corpo').innerHTML = html; cache = html; }
    if (!abertoAutomaticamente && historico.registros.length) { painel.open = true; abertoAutomaticamente = true; }
    // Só mostra controles de leitura quando existe uma sessão no backend.
    const leitura = est.leitura;
    el('tr-leitura').hidden = !leitura || leitura.estado === 'inativo';
    if (leitura) {
      el('tr-leitura-estado').textContent = `${leitura.titulo || 'Leitura'} · ${leitura.estado}${Number.isInteger(leitura.indice) && Number.isInteger(leitura.total) ? ` · trecho ${leitura.indice} de ${leitura.total}` : ''}${leitura.erro ? ` · ${leitura.erro}` : ''}`;
      el('tr-leitura-pausar').disabled = leitura.estado !== 'lendo';
      el('tr-leitura-retomar').disabled = leitura.estado !== 'pausada';
      el('tr-leitura-parar').disabled = !['lendo', 'pausada'].includes(leitura.estado);
    }
  }
  el('tr-fixar').addEventListener('click', () => {
    fixado = !fixado; el('tr-fixar').textContent = fixado ? 'Retomar atualizações' : 'Fixar leitura';
    el('tr-fixar').setAttribute('aria-pressed', String(fixado));
    status(fixado ? 'Leitura fixada nesta tela; o trabalho continua no backend.' : 'Exibindo estado atual.');
    if (!fixado) { novidade = false; render(); }
  });
  el('tr-foco').addEventListener('click', () => {
    const foco = painel.classList.toggle('tr-foco');
    el('tr-foco').setAttribute('aria-pressed', String(foco));
  });
  el('tr-historico').addEventListener('change', () => { fixado = false; el('tr-fixar').textContent = 'Fixar leitura'; el('tr-fixar').setAttribute('aria-pressed', 'false'); render(); });
  el('tr-limpar').addEventListener('click', () => { historico.limpar(); el('tr-historico').value = ''; status('Histórico desta tela apagado; registros do projeto permanecem no backend.'); render(); });
  el('tr-parar').addEventListener('click', async () => {
    try { await acao('/api/parar'); status('Interrupção solicitada. Confira o estado da execução.'); }
    catch (e) { status(e.message); }
  });
  for (const nome of ['pausar', 'retomar', 'parar']) el(`tr-leitura-${nome}`).addEventListener('click', async () => {
    try { await acao('/api/leitura', { acao: nome }); }
    catch (e) { status(e.message); }
  });
  let entradaRegiao = 'teclado';
  el('tr-regiao-form').addEventListener('pointerdown', () => { entradaRegiao = 'mouse'; });
  el('tr-regiao-form').addEventListener('keydown', () => { entradaRegiao = 'teclado'; });
  el('tr-regiao-form').addEventListener('submit', async e => {
    e.preventDefault();
    const caixa = ['x', 'y', 'w', 'h'].map(k => Number(el(`tr-regiao-${k}`).value) / 100);
    if (!caixaValida(caixa)) { status('A região precisa caber no quadro e ter largura e altura maiores que zero.'); return; }
    try {
      await acao('/api/selecao', { alvo: { tipo: 'regiao', id: 'regiao-camera-painel', rotulo: 'Área fixa escolhida no painel', por: entradaRegiao, extra: { fonte: 'camera', caixa } } });
      status('Área fixa selecionada. Peça a análise do objeto; a região não acompanha movimentos.');
    } catch (e) { status(e.message); }
  });
  painel.addEventListener('keydown', e => {
    if (e.key === 'Escape') { painel.open = false; el('tr-resumo').focus(); }
  });
  document.addEventListener('selectionchange', () => { if (novidade && !fixado && !selecionandoTexto()) { novidade = false; render(); } });
  ouvir(tipo => { if (tipo === 'estado') render(); });
  conectar(); render();
  return { historico, render };
}
iniciarTrabalho();

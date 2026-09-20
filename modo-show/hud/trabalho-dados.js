// Projeções textuais dos canais reais. Não inferem progresso nem identidade.
const lista = (v) => Array.isArray(v) ? v : [];
export const escapar = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const txt = (v) => escapar(v == null || v === '' ? 'não informado' : v);
const data = (v) => typeof v === 'number' && Number.isFinite(v) && v > 0 ? new Date(v * 1000).toLocaleString('pt-BR') : 'instante não informado';
const estado = (v) => String(v || 'não informado').replaceAll('_', ' ');
const itens = (valores) => lista(valores).length ? `<ul>${valores.map(v => `<li>${txt(v)}</li>`).join('')}</ul>` : '<p class="tr-fraco">Nenhum registro.</p>';
const campo = (nome, valor) => `<p><strong>${escapar(nome)}:</strong> ${txt(valor)}</p>`;
const secao = (titulo, corpo) => `<section class="tr-secao"><h3>${escapar(titulo)}</h3>${corpo}</section>`;
const linkSeguro = (v) => {
  try { const url = new URL(v); return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : null; }
  catch { return null; }
};
export function caixaValida(c) {
  return Array.isArray(c) && c.length === 4 && c.every(v => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1)
    && c[2] > 0 && c[3] > 0 && c[0] + c[2] <= 1 && c[1] + c[3] <= 1;
}
export function imagemDaAnalise(i, visao) {
  // Nunca ligar uma análise anterior à miniatura de outra captura.
  return i?.captura_id && i.captura_id === visao?.captura_id &&
    /^data:image\/jpeg;base64,[A-Za-z0-9+/=]+$/.test(visao?.miniatura || '') ? visao.miniatura : null;
}
function regiao(i, visao) {
  const imagem = imagemDaAnalise(i, visao), c = i.regiao;
  const caixa = caixaValida(c) ? `<svg viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Região analisada"><rect x="${c[0] * 1000}" y="${c[1] * 1000}" width="${c[2] * 1000}" height="${c[3] * 1000}" /></svg>` : '';
  return `<figure class="tr-regiao${imagem ? '' : ' tr-sem-imagem'}">${imagem ? `<img src="${imagem}" alt="Captura usada nesta análise, sem gravação em disco">` : ''}${caixa}</figure>` +
    `<p class="tr-fraco">${imagem ? 'Captura desta análise disponível em memória; não é câmera ao vivo.' : 'Captura não disponível neste registro; a imagem não foi retida aqui.'}${caixa ? ' Contorno: região analisada.' : ''}</p>`;
}
function objeto(est) {
  const i = est.identificacao, alvo = est.selecao?.alvo;
  let s = alvo ? campo('Seleção registrada', `${alvo.rotulo || alvo.id} · ${alvo.tipo} · ${alvo.extra?.fonte || 'fonte não informada'}`) +
    `<p class="tr-fraco">Por ${txt(alvo.por)} em ${data(alvo.em)}. A posição pode ter mudado desde a seleção.</p>` : '';
  if (!i?.em) return s ? secao('Alvo', s) : '';
  s += campo('Categoria', i.categoria) + campo('Fonte e instante', `${i.fonte || 'não informada'} · ${data(i.capturado_em || i.em)}`) +
    (i.pergunta ? campo('Pergunta desta análise', i.pergunta) : '') + regiao(i, est.visao);
  if (lista(i.qualidade?.problemas).length) s += campo('Limites da imagem', i.qualidade.problemas.join('; '));
  s += '<h4>Atributos e origem</h4>' + (lista(i.atributos).length ? `<table><thead><tr><th>Atributo</th><th>Valor e evidência</th></tr></thead><tbody>${i.atributos.map(a => `<tr><th scope="row">${txt(a.nome)}</th><td>${txt(a.valor)} · ${txt(a.estado_falado || estado(a.estado))}<small>${txt(a.fonte)} · ${data(a.em)}</small></td></tr>`).join('')}</tbody></table>` : '<p>Marca, modelo e versão não determinados.</p>');
  s += '<h4>Candidatos comparados</h4>' + (lista(i.candidatos).length ? `<ul>${i.candidatos.map(c => `<li><strong>${txt(c.nome)}</strong>${campo('Concorda', lista(c.concordam).join('; '))}${campo('Conflita', lista(c.conflitam).join('; ') || 'nenhum conflito registrado')}${campo('Referência', c.fonte)}</li>`).join('')}</ul>` : '<p>Nenhum candidato fundamentado registrado.</p>');
  s += '<h4>Evidências consultadas e pistas</h4>' + itens(i.evidencias) + (i.metodo ? campo('Método', i.metodo) : '');
  s += campo('Próximo passo / informação pendente', i.proximo_passo || 'Nenhum pedido adicional registrado; isso não valida atributos ausentes.');
  return secao('Análise do objeto', s);
}
function pesquisa(est) {
  const c = est.contexto;
  if (!lista(c?.itens).length) return '';
  return secao(c.titulo || 'Fontes e contexto', `<p class="tr-fraco">${txt(c.tipo)} · ${data(c.em)}</p><ol>${c.itens.map(f => {
    const url = linkSeguro(f.link);
    return `<li>${url ? `<a href="${escapar(url)}" target="_blank" rel="noopener noreferrer">${txt(f.titulo)}</a>` : `<strong>${txt(f.titulo)}</strong>`}` +
      (f.detalhe ? `<p>${txt(f.detalhe)}</p>` : '') + `<small>${txt(f.fonte)}${f.em ? ` · consulta ${data(f.em)}` : ''}</small>` +
      (f.cobertura ? campo('Cobertura', f.cobertura) : '') + (f.publicado_em ? campo('Publicado', f.publicado_em) : '') + '</li>';
  }).join('')}</ol>`);
}
function observacao(est) {
  const v = est.visao;
  if (!v?.estado || (v.captura_id && v.captura_id === est.identificacao?.captura_id)) return '';
  return secao('Observação visual', campo('Estado', v.estado) + campo('Fonte e escopo', `${v.fonte || 'não informada'} · ${v.escopo || 'não informado'}`) +
    campo('Captura', data(v.capturado_em)) + campo('Pergunta', v.pergunta) + (v.resposta ? campo('Resposta', v.resposta) : '') +
    '<p class="tr-fraco">Análise de uma captura; não representa observação contínua ao vivo.</p>');
}
function projeto(est) {
  const t = est.projeto?.tarefa;
  if (!t) return '';
  let s = campo('Projeto', est.projeto.projeto || t.projeto) + campo('Objetivo', t.objetivo) + campo('Estado', t.estado_falado || estado(t.estado));
  if (t.motivo) s += campo('Motivo / erro / pendência', t.motivo);
  if (t.conclusao_quando) s += campo('Condição de conclusão', t.conclusao_quando);
  s += '<h4>Etapas registradas</h4>' + (lista(t.etapas).length ? `<ol>${t.etapas.map(e => `<li><strong>${txt(e.descricao)}</strong> · ${txt(estado(e.estado))}${e.resultado ? `<p>${txt(e.resultado)}</p>` : ''}${e.em ? `<small>${data(e.em)}</small>` : ''}</li>`).join('')}</ol>` : '<p>Nenhuma etapa registrada.</p>');
  if (t.total_etapas > lista(t.etapas).length) s += `<p>Exibindo ${t.etapas.length} de ${t.total_etapas} etapas registradas.</p>`;
  s += '<h4>Restrições</h4>' + itens(t.restricoes) + '<h4>Resultados</h4>' + itens(t.resultados);
  if (t.aprovacao_pendente) s += campo('Aprovação pendente', typeof t.aprovacao_pendente === 'string' ? t.aprovacao_pendente : JSON.stringify(t.aprovacao_pendente));
  s += '<h4>Aprovações registradas</h4>' + (lista(t.aprovacoes).length ? itens(t.aprovacoes.map(a => `${a.operacao} · ${a.parametros || 'sem parâmetros adicionais'} · ${data(a.em)}`)) : '<p>Nenhuma aprovação registrada para esta tarefa.</p>');
  if (lista(t.pendencias).length) s += '<h4>Pendências</h4>' + itens(t.pendencias);
  if (lista(t.experimentos).length) s += '<h4>Experimentos registrados</h4>' + itens(t.experimentos.map(e => `${e.nome}: ${e.resultado}. ${e.condicoes || ''} ${e.unidades || ''} ${e.falha ? `Falha: ${e.falha}` : ''} · fonte ${e.fonte} · ${data(e.em)}`));
  return secao('Tarefa e verificação', s);
}
function peca(est) {
  const p = est.peca;
  if (!p?.nome) return '';
  let s = campo('Componente ativo', p.nome) + campo('Versão', p.versao) + campo('Material', p.material) + campo('Cor', p.cor);
  s += '<h4>Parâmetros</h4>' + itens(lista(p.parametros).map(v => `${v.nome}: ${v.valor}${v.unidade ? ` ${v.unidade}` : ''}`));
  if (p.volume_cm3 != null) s += campo('Volume da geometria', `${p.volume_cm3} cm³ · calculado no modelo, não medição física`);
  s += '<h4>Restrições</h4>' + itens(p.restricoes);
  if (est.previa?.arquivo) s += campo('Prévia', `${est.previa.motivo || est.previa.estado || 'aguardando confirmação'} · versão base ${est.previa.versao_base ?? 'não informada'}`) +
    (est.previa.material ? campo('Material proposto', est.previa.material) : '') + (est.previa.cor ? campo('Cor proposta', est.previa.cor) : '');
  if (est.apresentacao?.id) s += campo('Apresentação na Mesa', `${estado(est.apresentacao.estado)} · ${est.apresentacao.nome || ''}. Carregamento não é validação de engenharia.`);
  s += '<h4>Versões</h4>' + itens(lista(p.historico).map(v => `v${v.versao ?? v.numero}: ${v.motivo || ''}${v.material ? ` · material ${v.material}` : ''}${v.cor ? ` · cor ${v.cor}` : ''}`));
  return secao('Projeto de peça', s);
}
export function renderTrabalho(est = {}) {
  const pedido = est.pedido?.estado && est.pedido.estado !== 'inativo' ? secao('Execução do pedido', campo('Estado', estado(est.pedido.estado)) + (est.pedido.erro ? campo('Erro', est.pedido.erro) : '')) : '';
  const conteudo = objeto(est) + observacao(est) + pesquisa(est) + projeto(est) + peca(est) + pedido;
  return conteudo || '<p class="tr-fraco">Ainda não há análise, pesquisa ou projeto nesta sessão.</p>';
}
export class HistoricoTrabalho {
  constructor(limite = 20) { this.limite = limite; this.registros = []; this.chaves = new Map(); this.sessao = null; this.seq = 0; }
  receber(est) {
    if (est.sessao && this.sessao && est.sessao !== this.sessao) this.limpar(true);
    this.sessao = est.sessao || this.sessao;
    const blocos = [
      ['identificacao', est.identificacao?.em && { identificacao: est.identificacao, selecao: est.selecao }, `Objeto: ${est.identificacao?.categoria || 'análise'}`],
      ['contexto', lista(est.contexto?.itens).length && { contexto: est.contexto }, est.contexto?.titulo || 'Contexto'],
      ['projeto', est.projeto?.tarefa && { projeto: est.projeto }, est.projeto?.tarefa?.objetivo || 'Tarefa'],
      ['peca', est.peca?.nome && { peca: est.peca, previa: est.previa, apresentacao: est.apresentacao }, `Peça: ${est.peca?.nome}`],
    ];
    for (const [tipo, valor, titulo] of blocos) {
      if (!valor) continue;
      // em global do canal pode ser atualizado sem mudança substantiva.
      const chave = JSON.stringify(valor, (k, v) => k === 'em' && tipo === 'projeto' ? undefined : v);
      if (this.chaves.get(tipo) === chave) continue;
      this.chaves.set(tipo, chave);
      const dados = JSON.parse(JSON.stringify(valor)); // nunca inclui visao/miniatura
      this.registros.unshift({ id: String(++this.seq), titulo, em: Date.now() / 1000, dados });
    }
    this.registros.length = Math.min(this.registros.length, this.limite);
  }
  limpar(reiniciar = false) { this.registros = []; if (reiniciar) this.chaves.clear(); }
}

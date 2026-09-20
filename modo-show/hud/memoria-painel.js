// Só formulários enviados pelo usuário. Nunca copia a conversa para exemplos.
import { loja, acao } from './cliente.js';
import { escapar } from './trabalho-dados.js';
const linhas = texto => texto.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
export function iniciarRegistros(raiz = document.getElementById('w-registros')) {
  if (!raiz) return;
  const el = id => document.getElementById(id), valor = id => el(id).value.trim();
  let episodios = [], exemplos = [], tarefaEditada = null, colecaoAtiva = false;
  const status = texto => { el('rg-status').textContent = texto; };
  const opcoes = (id, itens, rotulo) => {
    const s = el(id), anterior = s.value;
    s.innerHTML = '<option value="">Selecione um registro</option>' + itens.map(i => `<option value="${escapar(i.id)}">${escapar(rotulo(i))}</option>`).join('');
    s.value = itens.some(i => i.id === anterior) ? anterior : '';
  };
  const executar = async fn => {
    try { await fn(); }
    catch (e) { status(e.message || String(e)); }
  };
  async function listarEpisodios() {
    const r = await acao('/api/memoria/episodios', { acao: 'listar' });
    episodios = r.episodios || [];
    opcoes('ep-lista', episodios, e => `${e.atividade} · ${e.escopo}`);
    mostrarEpisodio();
  }
  function mostrarEpisodio() {
    const e = episodios.find(x => x.id === el('ep-lista').value);
    el('ep-detalhes').textContent = e ? JSON.stringify(e, null, 2) : 'Nenhum episódio selecionado.';
    el('ep-correcao').value = e?.resultado || '';
    el('ep-corrigir').disabled = el('ep-apagar').disabled = !e;
  }
  function estadoColecao(estado) {
    colecaoAtiva = estado?.coleta_ativa === true;
    el('ap-optar').checked = colecaoAtiva;
    el('ap-estado').textContent = `${colecaoAtiva ? 'Registro manual autorizado' : 'Registro de exemplos desativado'} · adaptação: ${estado?.adaptacao ?? 0} · avaliação reservada: ${estado?.avaliacao ?? 0}. Coleta automática e treinamento desativados.`;
  }
  async function listarExemplos() {
    const r = await acao('/api/aprendizado', { acao: 'listar' });
    estadoColecao(r.estado); exemplos = r.exemplos || [];
    opcoes('ap-lista', exemplos, e => `${e.destino} · ${e.pedido} · ${e.id}`);
    mostrarExemplo();
    el('ap-avaliacoes').textContent = r.avaliacoes?.length ? JSON.stringify(r.avaliacoes, null, 2) : 'Nenhuma comparação registrada.';
  }
  function mostrarExemplo() {
    const e = exemplos.find(x => x.id === el('ap-lista').value);
    el('ap-detalhes').textContent = e ? JSON.stringify(e, null, 2) : 'Nenhum exemplo selecionado.';
    el('ap-apagar').disabled = !e;
  }
  el('ep-consultar').addEventListener('click', () => executar(async () => { await listarEpisodios(); status('Episódios locais carregados.'); }));
  el('ep-lista').addEventListener('change', mostrarEpisodio);
  el('ep-form').addEventListener('submit', e => {
    e.preventDefault(); return executar(async () => {
      const atividade = valor('ep-atividade'), resultado = valor('ep-resultado');
      if (!atividade || !resultado) throw new Error('Preencha atividade e resultado observado.');
      await acao('/api/memoria/episodios', { acao: 'registrar', atividade, resultado, escopo: valor('ep-escopo') || 'pessoal', origem: 'usuario' });
      el('ep-form').reset(); await listarEpisodios(); status('Episódio registrado como declaração do usuário.');
    });
  });
  el('ep-corrigir').addEventListener('click', () => executar(async () => {
    const id = valor('ep-lista');
    if (!id || !valor('ep-correcao')) throw new Error('Selecione o episódio e escreva o resultado corrigido.');
    await acao('/api/memoria/episodios', { acao: 'corrigir', id, resultado: valor('ep-correcao') });
    await listarEpisodios(); status('Resultado corrigido.');
  }));
  el('ep-apagar').addEventListener('click', () => executar(async () => {
    const id = valor('ep-lista'); if (!id) return;
    const r = await acao('/api/memoria/episodios', { acao: 'esquecer', id });
    await listarEpisodios(); status(r.apagado ? 'Episódio apagado.' : 'O episódio já não estava disponível.');
  }));
  el('ap-consultar').addEventListener('click', () => executar(async () => { await listarExemplos(); status('Coleções locais carregadas.'); }));
  el('ap-lista').addEventListener('change', mostrarExemplo);
  el('ap-opcao-salvar').addEventListener('click', () => executar(async () => {
    const r = await acao('/api/aprendizado', { acao: 'optar', ativo: el('ap-optar').checked });
    estadoColecao(r.estado); status('Opção salva. Nenhuma conversa foi coletada.');
  }));
  el('ap-form').addEventListener('submit', e => {
    e.preventDefault(); return executar(async () => {
      if (!colecaoAtiva) throw new Error('Consulte o estado ou autorize o registro manual antes de enviar.');
      const verificado = el('ap-verificado').checked, aprovado = el('ap-aprovado').checked, sucesso = el('ap-sucesso').checked;
      if (![verificado, aprovado, sucesso].every(v => v === true)) throw new Error('Confirme explicitamente resultado conferido, sucesso e correção aprovada.');
      const corpo = { acao: 'registrar', pedido: valor('ap-pedido'), contexto: valor('ap-contexto'), acao_executada: valor('ap-acao'), resultado: valor('ap-resultado'), correcao: valor('ap-correcao'), destino: valor('ap-destino'), verificado, aprovado, sucesso };
      if (['pedido', 'contexto', 'acao_executada', 'resultado', 'correcao'].some(k => !corpo[k])) throw new Error('Preencha os cinco textos revisados.');
      await acao('/api/aprendizado', corpo);
      el('ap-form').reset();
      for (const id of ['ap-verificado', 'ap-aprovado', 'ap-sucesso']) el(id).checked = false;
      await listarExemplos(); status('Exemplo revisado guardado; nenhum modelo foi treinado.');
    });
  });
  el('ap-apagar').addEventListener('click', () => executar(async () => {
    const id = valor('ap-lista'); if (!id) return;
    const r = await acao('/api/aprendizado', { acao: 'esquecer', id });
    await listarExemplos(); status(r.apagado ? 'Exemplo e comparações derivadas apagados.' : 'O exemplo já não estava disponível.');
  }));
  el('av-arquivo').addEventListener('change', () => executar(async () => {
    const arquivo = el('av-arquivo').files?.[0]; if (!arquivo) return;
    if (arquivo.size > 14000) throw new Error('O JSON deve ter até 14 KB para caber no limite da API local.');
    const texto = await arquivo.text(); JSON.parse(texto);
    el('av-json').value = texto; status('JSON carregado localmente. Confira antes de comparar.');
  }));
  el('av-form').addEventListener('submit', e => {
    e.preventDefault(); return executar(async () => {
      const texto = valor('av-json');
      if (new TextEncoder().encode(texto).length > 14000) throw new Error('O JSON deve ter até 14 KB.');
      const dados = JSON.parse(texto);
      const campos = ['referencia', 'candidato', 'resultados_referencia', 'resultados_candidato', 'politica_referencia', 'politica_candidato', 'reversao'];
      if (!dados || Array.isArray(dados) || typeof dados !== 'object' || Object.keys(dados).some(k => !campos.includes(k)) || campos.some(k => !(k in dados))) throw new Error('O JSON precisa conter exatamente os sete campos descritos.');
      const r = await acao('/api/aprendizado', { acao: 'comparar', ...dados });
      el('av-resultado').textContent = JSON.stringify(r.comparacao, null, 2);
      status('Relatório registrado com os resultados enviados. Nenhum candidato foi executado ou promovido.');
    });
  });
  el('rq-carregar').addEventListener('click', () => {
    const t = loja.estado?.projeto?.tarefa;
    if (!t?.id) { status('Abra uma tarefa antes de editar os requisitos.'); return; }
    tarefaEditada = t.id;
    el('rq-tarefa').textContent = `${t.objetivo} · id ${t.id}`;
    el('rq-conclusao').value = t.conclusao_quando || '';
    for (const [id, campo] of [['rq-restricoes', 'restricoes'], ['rq-recursos', 'recursos'], ['rq-dependencias', 'depende_de']]) el(id).value = Array.isArray(t[campo]) ? t[campo].join('\n') : '';
    el('rq-salvar').disabled = false; status('Requisitos da tarefa ativa carregados para edição.');
  });
  el('rq-form').addEventListener('submit', e => {
    e.preventDefault(); return executar(async () => {
      if (!tarefaEditada || tarefaEditada !== loja.estado?.projeto?.tarefa?.id) throw new Error('A tarefa ativa mudou; carregue os requisitos dela antes de salvar.');
      await acao('/api/projetos/requisitos', { id: tarefaEditada, conclusao_quando: valor('rq-conclusao'), restricoes: linhas(valor('rq-restricoes')), recursos: linhas(valor('rq-recursos')), depende_de: linhas(valor('rq-dependencias')) });
      status('Requisitos registrados como declaração do usuário; a tarefa não foi executada.');
    });
  });
  // Não consulta nem grava coleções ao inicializar a página.
  return { listarEpisodios, listarExemplos };
}
iniciarRegistros();

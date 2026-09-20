// Formulários reais com HTTP/DOM simulados; não escreve na memória do usuário.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';
const hud = resolve(dirname(fileURLToPath(import.meta.url)), '../hud');
const elements = new Map(), requests = [];
class Element {
  constructor() { this.value = ''; this.checked = false; this.listeners = new Map(); }
  addEventListener(name, fn) { this.listeners.set(name, fn); }
  emit(name, args = { preventDefault() {} }) { return this.listeners.get(name)?.(args); }
  reset() { this.resetado = true; }
}
for (const name of ['jarvis', 'painel', 'holograma']) {
  const html = await readFile(resolve(hud, `${name}.html`), 'utf8');
  const ids = [...html.matchAll(/id="([^"]+)"/g)].map(x => x[1]);
  assert.equal(new Set(ids).size, ids.length, `IDs únicos em ${name}`);
  assert.ok(html.includes('/hud/trabalho.js') && html.includes('/hud/trabalho.css'));
  assert.equal(html.includes('/hud/memoria-painel.js'), name === 'painel');
  assert.ok(html.includes('Trabalho e evidências'), 'Acentos preservados em UTF-8');
  if (name === 'painel') for (const id of ids) elements.set(id, new Element());
}
const document = { getElementById: id => elements.get(id), querySelector: () => ({ content: 'fixture-token' }) };
let ativa = false, failNext = false;
const episodio = { id: 'ep1', atividade: '<img src=x onerror=alert(1)>', resultado: 'Resultado explicitamente informado', escopo: 'Fixture' };
const exemplo = { id: 'ex1', pedido: 'Pedido revisado', contexto: 'Contexto', acao: 'Ação', resultado: 'Resultado', correcao: 'Correção', destino: 'avaliacao' };
const context = vm.createContext({ document, URL, TextEncoder, crypto: webcrypto,
  fetch: async (url, options) => {
    const body = JSON.parse(options.body); requests.push({ url, body, options });
    if (failNext) { failNext = false; return new Response('{"erro":"Ocupado com outro pedido"}', { status: 400 }); }
    let result = { ok: true };
    if (url === '/api/memoria/episodios') result = body.acao === 'listar' ? { episodios: [episodio] } : body.acao === 'esquecer' ? { apagado: true } : { episodio };
    if (url === '/api/aprendizado') {
      if (body.acao === 'optar') ativa = body.ativo;
      result = { estado: { coleta_ativa: ativa, adaptacao: 0, avaliacao: 1 }, exemplos: [exemplo], avaliacoes: [], comparacao: { promovido: false, limite: 'Resultados enviados' }, apagado: true };
    }
    return new Response(JSON.stringify({ ok: true, ...result }));
  },
});
const modules = new Map();
async function load(path) {
  if (!modules.has(path)) modules.set(path, (async () => {
    const m = new vm.SourceTextModule(await readFile(path, 'utf8'), { context, identifier: path });
    await m.link((spec, parent) => load(resolve(dirname(parent.identifier), spec)));
    return m;
  })());
  return modules.get(path);
}
await (await load(resolve(hud, 'memoria-painel.js'))).evaluate();
const el = id => elements.get(id);
assert.equal(requests.length, 0, 'Abrir a página não consulta nem coleta episódios/exemplos');
assert.equal(el('ap-optar').checked, false);
for (const id of ['ap-verificado', 'ap-aprovado', 'ap-sucesso']) assert.equal(el(id).checked, false);
await el('ap-form').emit('submit'); assert.equal(requests.length, 0);
el('ep-atividade').value = 'Teste do componente'; el('ep-resultado').value = 'Medida informada'; el('ep-escopo').value = 'projeto teste';
await el('ep-form').emit('submit');
assert.deepEqual(requests[0].body, { acao: 'registrar', atividade: 'Teste do componente', resultado: 'Medida informada', escopo: 'projeto teste', origem: 'usuario' });
assert.ok(el('ep-lista').innerHTML.includes('&lt;img')); assert.ok(!el('ep-lista').innerHTML.includes('<img'));
el('ep-lista').value = 'ep1'; el('ep-lista').emit('change'); el('ep-correcao').value = 'Resultado corrigido';
await el('ep-corrigir').emit('click');
assert.ok(requests.some(r => r.body.acao === 'corrigir' && r.body.id === 'ep1' && r.body.resultado === 'Resultado corrigido'));
await el('ep-apagar').emit('click'); assert.ok(requests.some(r => r.url === '/api/memoria/episodios' && r.body.acao === 'esquecer' && r.body.id === 'ep1'));

el('ap-optar').checked = true; await el('ap-opcao-salvar').emit('click');
const countBeforeUnapproved = requests.length;
await el('ap-form').emit('submit'); assert.equal(requests.length, countBeforeUnapproved);
for (const id of ['ap-pedido', 'ap-contexto', 'ap-acao', 'ap-resultado', 'ap-correcao']) el(id).value = `Texto revisado ${id}`;
for (const id of ['ap-verificado', 'ap-aprovado', 'ap-sucesso']) el(id).checked = true;
el('ap-destino').value = 'avaliacao'; await el('ap-form').emit('submit');
const sent = requests.find(r => r.url === '/api/aprendizado' && r.body.acao === 'registrar').body;
assert.equal(sent.acao_executada, 'Texto revisado ap-acao'); assert.equal(sent.destino, 'avaliacao');
assert.equal(sent.verificado, true); assert.equal(sent.aprovado, true); assert.equal(sent.sucesso, true);
assert.equal(el('ap-form').resetado, true);
for (const id of ['ap-verificado', 'ap-aprovado', 'ap-sucesso']) assert.equal(el(id).checked, false, 'Novo exemplo exige novas confirmações');
el('ap-lista').value = 'ex1'; el('ap-lista').emit('change'); await el('ap-apagar').emit('click');
assert.ok(requests.some(r => r.url === '/api/aprendizado' && r.body.acao === 'esquecer' && r.body.id === 'ex1'));

const comparison = { referencia: 'base', candidato: 'candidato', resultados_referencia: {}, resultados_candidato: {}, politica_referencia: 'mesma', politica_candidato: 'mesma', reversao: 'Restaurar base' };
el('av-arquivo').files = [{ size: 100, text: async () => JSON.stringify(comparison) }];
const beforeImport = requests.length; await el('av-arquivo').emit('change'); assert.equal(requests.length, beforeImport);
await el('av-form').emit('submit'); assert.deepEqual(requests.at(-1).body, { acao: 'comparar', ...comparison });
assert.ok(el('av-resultado').textContent.includes('"promovido": false'));
el('av-json').value = '{"acao":"optar","ativo":true}';
const beforeInvalid = requests.length; await el('av-form').emit('submit'); assert.equal(requests.length, beforeInvalid);

const { loja } = (await load(resolve(hud, 'cliente.js'))).namespace;
loja.estado = { projeto: { tarefa: { id: 't1', objetivo: 'Fixture', restricoes: ['sem publicação'], recursos: [], depende_de: [] } } };
await el('rq-carregar').emit('click');
el('rq-conclusao').value = 'Quando conferir'; el('rq-recursos').value = 'arquivo A\n\narquivo B';
await el('rq-form').emit('submit');
assert.deepEqual(requests.at(-1).body, { id: 't1', conclusao_quando: 'Quando conferir', restricoes: ['sem publicação'], recursos: ['arquivo A', 'arquivo B'], depende_de: [] });
loja.estado.projeto.tarefa.id = 't2';
const beforeChanged = requests.length; await el('rq-form').emit('submit'); assert.equal(requests.length, beforeChanged, 'Não salvar parâmetros na tarefa que substituiu a editada');
await el('rq-carregar').emit('click'); failNext = true;
el('rq-conclusao').value = 'Preservar edição'; await el('rq-form').emit('submit');
assert.equal(el('rq-conclusao').value, 'Preservar edição'); assert.ok(el('rg-status').textContent.includes('Ocupado'));
assert.ok(requests.every(r => r.options.headers['X-Jarvis-Token'] === 'fixture-token'));
console.log('PASS: formulários reais de episódio, correção/remoção, opt-in explícito, exemplos revisados, comparação manual e requisitos sem troca de tarefa. HTTP/DOM são fixtures; sem registros pessoais escritos.');

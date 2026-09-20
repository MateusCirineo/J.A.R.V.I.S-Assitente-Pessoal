// Módulos reais + fixtures de DOM/SSE/HTTP. Não substitui inspeção visual humana.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';
const hud = resolve(dirname(fileURLToPath(import.meta.url)), '../hud');
const requests = [], errors = [], elements = new Map(), documentListeners = new Map();
class Element {
  constructor(id) { this.id = id; this.value = ''; this.dataset = {}; this.innerHTML = ''; this.textContent = ''; this.listeners = new Map(); this.classes = new Set(); this.classList = { toggle: c => { this.classes.has(c) ? this.classes.delete(c) : this.classes.add(c); return this.classes.has(c); } }; }
  addEventListener(event, fn) { this.listeners.set(event, fn); }
  emit(event, args = {}) { return this.listeners.get(event)?.(args); }
  setAttribute(k, v) { this[k] = v; }
  contains(node) { return node?.inside === true; }
  focus() { document.activeElement = this; }
}
const markup = await readFile(resolve(hud, 'holograma.html'), 'utf8');
for (const match of markup.matchAll(/id="([^"]+)"/g)) elements.set(match[1], new Element(match[1]));
for (const [key, value] of Object.entries({ x: 25, y: 25, w: 50, h: 50 })) elements.get(`tr-regiao-${key}`).value = value;
let selection = null, source;
const document = {
  activeElement: null, getElementById: id => elements.get(id),
  querySelector: () => ({ content: 'token-fixture' }), getSelection: () => selection,
  addEventListener: (event, fn) => documentListeners.set(event, fn),
};
class Source {
  constructor() { source = this; this.listeners = new Map(); }
  addEventListener(event, fn) { this.listeners.set(event, fn); }
  emit(event, data) { this.listeners.get(event)?.({ data: JSON.stringify(data) }); }
  close() {}
}
const context = vm.createContext({ document, URL, crypto: webcrypto, EventSource: Source,
  console: { error: (...args) => errors.push(args) }, addEventListener() {},
  fetch: async (url, options) => { requests.push({ url, options, body: JSON.parse(options.body) }); return new Response('{"ok":true}'); },
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
await (await load(resolve(hud, 'trabalho.js'))).evaluate();
const { renderTrabalho, imagemDaAnalise, HistoricoTrabalho, caixaValida } = (await load(resolve(hud, 'trabalho-dados.js'))).namespace;
// alvos-mesa não é importado pelo painel; avaliar explicitamente.
const alvos = await load(resolve(hud, 'alvos-mesa.js')); await alvos.evaluate();
const color = alvos.namespace.corDaMesa;
assert.equal(color({ apresentacaoId: 'm' }, { arquivo: 'C:\\caixa.stl', cor: '#26c6da' }, null, { id: 'm', arquivo: 'c:/caixa.stl' }), '38,198,218');
assert.equal(color({ apresentacaoId: 'm' }, { arquivo: 'c:/caixa.stl', cor: '#26c6da' }, { arquivo: 'c:/previa.stl', cor: '#ff0000' }, { id: 'm', arquivo: 'c:/previa.stl' }), '255,0,0');
assert.equal(color({ apresentacaoId: 'antigo' }, { arquivo: 'c:/caixa.stl', cor: '#26c6da' }, null, { id: 'novo', arquivo: 'c:/caixa.stl' }), null);
assert.equal(color({ apresentacaoId: 'm' }, { arquivo: 'c:/outra.stl', cor: '#26c6da' }, null, { id: 'm', arquivo: 'c:/caixa.stl' }), null);
assert.equal(color({ apresentacaoId: 'm' }, { arquivo: 'c:/caixa.stl', cor: 'red;script' }, null, { id: 'm', arquivo: 'c:/caixa.stl' }), null);

const fixtureImage = 'data:image/jpeg;base64,YWJj';
const state = {
  sessao: 'fixture', identificacao: { em: 1700000000, categoria: 'carregador', captura_id: 'captura-a', fonte: 'camera', capturado_em: 1700000000, regiao: [.2, .2, .3, .4],
    atributos: [{ nome: 'marca', valor: 'Acme', estado: 'provavel', fonte: 'logotipo parcialmente visível', em: 1700000000 }],
    candidatos: [{ nome: 'Modelo A', concordam: ['texto 65W'], conflitam: [], fonte: 'inventário' }, { nome: 'Modelo B', concordam: ['formato'], conflitam: ['potência'], fonte: 'cadastro' }],
    evidencias: ['Texto legível: 65W', 'manual vinculado, não consultado'], proximo_passo: 'mostre a etiqueta', qualidade: { problemas: ['ângulo limitado'] } },
  visao: { captura_id: 'captura-a', miniatura: fixtureImage },
  contexto: { titulo: 'Pesquisa fixture', tipo: 'pesquisa', em: 1700000000, itens: [
    { titulo: 'Fonte oficial', detalhe: 'Trecho pertinente', fonte: 'Fonte A', link: 'https://example.org/ref?a=1&b=2', cobertura: 'trecho consultado' },
    { titulo: '<script>não executar</script>', detalhe: 'Divergência ainda não resolvida', link: 'javascript:alert(1)' }] },
  projeto: { projeto: 'Fixture', tarefa: { objetivo: 'Comparar', estado: 'aguardando_autorizacao', motivo: 'Erro na etapa anterior', restricoes: ['Não publicar'], etapas: [{ descricao: 'Busca', estado: 'falha', resultado: 'Sem rede' }], resultados: ['rascunho'], aprovacoes: [], aprovacao_pendente: 'publicar' } },
  peca: { nome: 'Caixa', versao: 2, material: 'PLA', cor: '#26c6da', volume_cm3: 2, parametros: [{ nome: 'altura', valor: '20 mm' }], historico: [] },
};
const rendered = renderTrabalho(state);
for (const phrase of ['provavel', 'logotipo parcialmente visível', 'Modelo A', 'Modelo B', 'potência', 'manual vinculado, não consultado', 'mostre a etiqueta', 'Trecho pertinente', 'Divergência ainda não resolvida', 'Não publicar', 'Sem rede', 'Aprovação pendente', 'não medição física']) assert.ok(rendered.includes(phrase), phrase);
assert.ok(rendered.includes('&lt;script&gt;')); assert.ok(!rendered.includes('href="javascript:'));
assert.ok(rendered.includes(fixtureImage));
assert.equal(imagemDaAnalise(state.identificacao, { captura_id: 'outra', miniatura: fixtureImage }), null);
assert.ok(renderTrabalho({ identificacao: state.identificacao }).includes('Captura não disponível'));
assert.equal(caixaValida([0, 0, Infinity, 1]), false);
assert.equal(caixaValida([.9, .2, .2, .4]), false);
const history = new HistoricoTrabalho(3);
history.receber(state);
assert.equal(history.registros.length, 3); assert.ok(!JSON.stringify(history.registros).includes('base64'));
history.limpar(); history.receber(state); assert.equal(history.registros.length, 0);
history.receber({ ...state, sessao: 'outra-sessao' }); assert.equal(history.registros.length, 3);

source.emit('estado', state);
assert.equal(elements.get('trabalho-painel').open, true);
const before = elements.get('tr-corpo').innerHTML;
await elements.get('tr-fixar').emit('click');
state.identificacao.proximo_passo = 'mostre a traseira'; source.emit('estado', state);
assert.equal(elements.get('tr-corpo').innerHTML, before);
assert.ok(elements.get('tr-status').textContent.includes('atualização'));
await elements.get('tr-fixar').emit('click');
assert.ok(elements.get('tr-corpo').innerHTML.includes('mostre a traseira'));
selection = { isCollapsed: false, anchorNode: { inside: true } };
state.identificacao.proximo_passo = 'mostre o código'; source.emit('estado', state);
assert.ok(!elements.get('tr-corpo').innerHTML.includes('mostre o código'));
selection = null; documentListeners.get('selectionchange')();
assert.ok(elements.get('tr-corpo').innerHTML.includes('mostre o código'));
await elements.get('tr-regiao-form').emit('submit', { preventDefault() {} });
assert.equal(requests.at(-1).url, '/api/selecao');
assert.equal(requests.at(-1).body.alvo.por, 'teclado');
assert.deepEqual(requests.at(-1).body.alvo.extra, { fonte: 'camera', caixa: [.25, .25, .5, .5] });
const count = requests.length;
elements.get('tr-regiao-w').value = 'Infinity';
await elements.get('tr-regiao-form').emit('submit', { preventDefault() {} });
assert.equal(requests.length, count);
assert.ok(!requests.some(r => r.url === '/api/camera'));
await elements.get('tr-parar').emit('click'); assert.equal(requests.at(-1).url, '/api/parar');
state.leitura = { estado: 'pausada', titulo: 'Documento', indice: 2, total: 5 }; source.emit('estado', state);
assert.equal(elements.get('tr-leitura').hidden, false);
assert.equal(elements.get('tr-leitura-retomar').disabled, false);
await elements.get('tr-leitura-retomar').emit('click'); assert.deepEqual(requests.at(-1).body, { acao: 'retomar' });
assert.ok(requests.every(r => r.options.headers['X-Jarvis-Token'] === 'token-fixture'));
assert.equal(errors.length, 0, String(errors));
console.log('PASS: evidências/candidatos/limites, captura correta, histórico sem imagens, fixar/selecionar texto, seleção teclado sem câmera, leitura, cor por artefato. DOM/SSE/HTTP são fixtures.');

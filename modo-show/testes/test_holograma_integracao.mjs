// Executa os módulos reais da Mesa com DOM/canvas/SSE/HTTP simulados em Node.
// É teste de integração JS, não captura de navegador ou validação visual humana.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';

const hud = resolve(dirname(fileURLToPath(import.meta.url)), '../hud');
const raf = [], requests = [], errors = [], elements = new Map(), authRequests = [], strokeStyles = [];
let reloads = 0, authResponse = async () => new Response('{}', { status: 200 });
const context2d = new Proxy({}, { get: (_, key) => {
  if (key === 'measureText') return (t) => ({ width: String(t).length * 7 });
  if (key === 'createLinearGradient' || key === 'createRadialGradient') return () => ({ addColorStop() {} });
  return () => {};
}, set: (target, key, value) => { if (key === 'strokeStyle') strokeStyles.push(value); target[key] = value; return true; } });
class Element {
  constructor() { this.listeners = new Map(); this.style = {}; this.dataset = {}; this.classList = { add() {} }; }
  addEventListener(name, callback) { this.listeners.set(name, callback); }
  async emit(name, value = {}) { return this.listeners.get(name)?.(value); }
  getContext() { return context2d; }
  setPointerCapture() {}
  requestFullscreen() { return Promise.resolve(); }
}
const document = {
  hidden: false, documentElement: new Element(),
  querySelector: () => ({ content: 'fixture-token' }),
  getElementById(id) { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); },
  addEventListener() {}, exitFullscreen: () => Promise.resolve(),
};
let source;
class Source {
  constructor() { this.listeners = new Map(); source = this; }
  addEventListener(name, callback) { this.listeners.set(name, callback); }
  emit(name, data) { this.listeners.get(name)?.({ data: JSON.stringify(data) }); }
  close() {}
}
let presentacaoId = 'a1';
const fixtureObj = 'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n';
const context = vm.createContext({
  document, innerWidth: 1440, innerHeight: 900, devicePixelRatio: 1, crypto: webcrypto,
  location: { reload: () => reloads++ },
  performance, TextDecoder, console: { log: console.log, error: (...args) => errors.push(args) },
  EventSource: Source, requestAnimationFrame: (callback) => raf.push(callback),
  setTimeout: () => 1, setInterval: () => 1, clearInterval() {}, addEventListener() {},
  fetch: async (url, options = {}) => {
    if (options.method === 'POST') {
      requests.push({ url, options, body: JSON.parse(options.body) });
      return new Response('{"ok":true,"confirmado":true}', { status: 200 });
    }
    if (url === '/api/holograma/modelo') return new Response(fixtureObj, {
      status: 200, headers: { 'X-Apresentacao-Id': presentacaoId, 'X-Modelo-Nome': 'caixa.obj' },
    });
    if (url === '/api/holograma/grafico') return new Response('{"grafico":null}', { status: 200 });
    if (url === '/api/estado') {
      authRequests.push({ url, options });
      return authResponse();
    }
    throw new Error(`HTTP inesperado: ${url}`);
  },
});
const modules = new Map();
async function load(path) {
  if (modules.has(path)) return modules.get(path);
  // Imports irmãos compartilham a promessa desde antes do primeiro I/O. Sem isso,
  // gestos.js e holograma.js podem criar duas lojas cliente.js, algo que o cache
  // de módulos do navegador impede, tornando este harness intermitente.
  const pending = (async () => {
    const module = new vm.SourceTextModule(await readFile(path, 'utf8'), { context, identifier: path });
    await module.link((spec, parent) => load(resolve(dirname(parent.identifier), spec)));
    return module;
  })();
  modules.set(path, pending);
  return pending;
}
await (await load(resolve(hud, 'holograma.js'))).evaluate();
const settle = async () => { for (let i = 0; i < 4; i++) await new Promise(setImmediate); };
const frame = async () => { const callbacks = raf.splice(0); for (const callback of callbacks) callback(performance.now()); await settle(); };
const state = {
  sessao: 'fixture', versao: 1, boot: { concluido: true }, camera: { ativa: false },
  gestos: { ativo: false, fase: 'desativado' },
  peca: { nome: 'Peça errada', arquivo: 'C:/fixture/outro.obj' },
  apresentacao: { id: 'a1', arquivo: 'C:/fixture/caixa.obj', nome: 'caixa.obj', estado: 'solicitada' },
};
source.emit('estado', state);
await settle();
assert.equal(requests.filter(r => r.url === '/api/apresentacao/confirmar').length, 0);
await frame(); await frame();
assert.deepEqual(requests.filter(r => r.url === '/api/apresentacao/confirmar').map(r => r.body.id), ['a1']);
assert.equal(errors.length, 0, String(errors));

const canvas = document.getElementById('holo');
await canvas.emit('pointerdown', { clientX: 720, clientY: 360, pointerId: 1 });
assert.equal(requests.at(-1).body.alvo.tipo, 'regiao');
assert.equal(requests.at(-1).body.alvo.extra.fonte, 'mesa');
state.versao++;
state.peca = { nome: 'Caixa correta', arquivo: 'C:\\fixture\\caixa.obj', cor: '#26c6da' };
source.emit('estado', state);
await canvas.emit('pointerdown', { clientX: 720, clientY: 360, pointerId: 1 });
assert.equal(requests.at(-1).body.alvo.id, 'Caixa correta');
assert.equal(requests.at(-1).body.alvo.tipo, 'peca');
await frame();
assert.ok(strokeStyles.some(c => c.startsWith('rgba(38,198,218,')), 'A cor da versão deve chegar ao canvas real da Mesa');

// Carregamento C superado por D antes de qualquer frame: não confirma C.
presentacaoId = 'c';
source.emit('comando', { acao: 'holograma', tipo: 'modelo', apresentacao_id: 'c' });
await settle();
presentacaoId = 'd';
source.emit('comando', { acao: 'holograma', tipo: 'modelo', apresentacao_id: 'd' });
await settle(); await frame(); await frame();
assert.deepEqual(requests.filter(r => r.url === '/api/apresentacao/confirmar').map(r => r.body.id), ['a1', 'd']);

await document.getElementById('gestos-ligar').emit('click');
const client = requests.findLast(r => r.url === '/api/gestos' && r.body.acao === 'ativar')?.body.cliente;
assert.ok(client, 'A ativação precisa enviar o identificador da tela dona dos gestos');
state.versao++;
state.gestos = { ativo: true, cliente: client, fase: 'rastreando', calibrado: true, modo: 'zoom', em: Date.now()/1000 };
source.emit('estado', state);
await settle();
assert.equal(document.getElementById('gestos-modo').value, 'zoom');
assert.ok(requests.some(r => r.url === '/api/gestos' && r.body.acao === 'alvos'));
assert.ok(requests.every(r => r.options.headers['X-Jarvis-Token'] === 'fixture-token'));
assert.equal(errors.length, 0, String(errors));

// Cookie/token da página anterior ao reinício: o SSE falha, o GET autenticado
// retorna 403 e a própria tela recarrega para receber a sessão atual.
const { loja } = (await load(resolve(hud, 'cliente.js'))).namespace;
source.onopen();
assert.equal(loja.conectado, true);
let finishAuth;
authResponse = () => new Promise(resolveAuth => { finishAuth = resolveAuth; });
const firstError = source.onerror();
const duplicateError = source.onerror();
assert.equal(loja.conectado, false);
assert.equal(authRequests.length, 1, 'Erros SSE simultâneos fazem uma única consulta de sessão');
finishAuth(new Response('{}', { status: 403 }));
await Promise.all([firstError, duplicateError]);
assert.equal(reloads, 1, 'Sessão expirada deve recarregar a página');
assert.equal(authRequests[0].options.headers['X-Jarvis-Token'], 'fixture-token');
authResponse = async () => new Response('{}', { status: 200 });
await source.onerror();
assert.equal(reloads, 1, 'Sessão válida deve deixar o EventSource reconectar');
authResponse = async () => { throw new Error('Serviço temporariamente fora do ar'); };
await source.onerror();
assert.equal(reloads, 1, 'Queda de rede deve deixar o EventSource reconectar');
assert.equal(errors.length, 0, String(errors));
console.log('PASS: boot dos módulos reais, token HTTP, alvo correto, ack após frames, ack obsoleto descartado, modo de gesto sincronizado e SSE com sessão expirada/erro transitório. DOM/canvas/SSE são fixtures.');

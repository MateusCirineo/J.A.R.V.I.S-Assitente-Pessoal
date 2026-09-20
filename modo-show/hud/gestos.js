// Gestos locais na câmera compartilhada. Cada sessão pertence a uma única tela.
import { acao, ouvir, loja } from './cliente.js';

export function iniciarGestos({ alvos, manipular }) {
  const cliente = crypto.randomUUID();
  const ligar = document.getElementById('gestos-ligar');
  const calibrar = document.getElementById('gestos-calibrar');
  const status = document.getElementById('gestos-status');
  const cursor = document.getElementById('gestos-cursor');
  let seq = 0, chave = '', ocupado = false;
  const enviar = (acaoNome, extra = {}) => acao('/api/gestos', { acao: acaoNome, cliente, ...extra });
  const meu = () => loja.estado?.gestos?.cliente === cliente && loja.estado.gestos.ativo;
  function erro(e) { status.textContent = e.message; }
  async function atualizarAlvos() {
    const lista = alvos();
    const atual = JSON.stringify(lista);
    if (meu() && chave !== atual) {
      chave = atual;
      try { await enviar('alvos', { alvos: lista }); }
      catch (e) { chave = ''; throw e; }
    }
  }
  ligar.addEventListener('click', async () => {
    if (ocupado) return;
    ocupado = true;
    try {
      await enviar(meu() ? 'desativar' : 'ativar');
      chave = '';
      seq = loja.estado?.gestos?.acao?.seq || 0;
    } catch (e) { erro(e); }
    finally { ocupado = false; }
  });
  calibrar.addEventListener('click', () => enviar('calibrar').catch(erro));
  document.getElementById('gestos-modo').addEventListener('change', (e) =>
    enviar('modo', { modo: e.target.value }).catch(erro));
  addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && meu()) enviar('desativar').catch(erro);
  });
  const interval = setInterval(async () => {
    if (!meu() || document.hidden) return;
    try { await enviar('heartbeat'); await atualizarAlvos(); }
    catch (e) { erro(e); }
  }, 2500);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && meu()) enviar('desativar').catch(erro);
  });
  addEventListener('pagehide', () => clearInterval(interval));
  ouvir(() => {
    const s = loja.estado?.gestos;
    if (!s) return;
    const ativo = meu();
    ligar.textContent = ativo ? 'Desativar gestos (Esc)' : 'Ativar gestos';
    calibrar.disabled = !ativo;
    document.getElementById('gestos-modo').disabled = !ativo;
    if (ativo) document.getElementById('gestos-modo').value = s.modo || 'girar';
    calibrar.textContent = s.calibrado ? 'Recalibrar: canto superior esquerdo' :
      s.pontos_calibrados === 1 ? 'Marcar canto inferior direito' : 'Marcar canto superior esquerdo';
    status.textContent = s.ativo && !ativo ? 'Gestos em uso por outra tela.' :
      `${s.fase || 'desativado'} · ${s.detalhe || (s.calibrado ? 'Pinça seleciona; mantenha fechada para mover.' : 'Aponte o indicador para os dois cantos e marque cada um.')}`;
    const p = ativo && s.calibrado && Date.now() / 1000 - s.em < 1 ? s.ponteiro : null;
    cursor.hidden = !p;
    if (p) {
      cursor.style.left = `${p.x * 100}%`;
      cursor.style.top = `${p.y * 100}%`;
      cursor.dataset.pinca = String(p.pinca);
    }
    if (ativo && s.acao && s.acao.seq > seq) {
      seq = s.acao.seq;
      manipular(s.acao);
    }
    if (ativo) atualizarAlvos().catch(erro);
  });
  // Mouse continua disponível durante calibração e em qualquer falha.
  return { selecionarMouse: async (alvo) => {
    try { await acao('/api/selecao', { alvo: { ...alvo, por: 'mouse' } }); }
    catch (e) { erro(e); }
  } };
}

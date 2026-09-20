// A peça ativa só é o alvo se for também o artefato exibido nesta tela.
const caminho = (valor) => typeof valor === 'string' ? valor.replace(/\\/g, '/').toLowerCase() : '';
export function alvoDaMesa(modelo, peca, apresentacao) {
  const mesmaPeca = Boolean(modelo && peca?.nome && peca.arquivo && apresentacao?.id &&
    apresentacao.id === modelo.apresentacaoId && caminho(peca.arquivo) === caminho(apresentacao.arquivo));
  return { tipo: mesmaPeca ? 'peca' : 'regiao', id: mesmaPeca ? peca.nome : 'mesa-3d',
    rotulo: mesmaPeca ? peca.nome : modelo?.nome || 'Visualização 3D',
    caixa: [0.27, 0.1, 0.46, 0.65], extra: { fonte: 'mesa' } };
}

// STL não guarda cor. O estilo vem da versão/prévia cujo arquivo está exibido.
export function corDaMesa(modelo, peca, previa, apresentacao) {
  if (!modelo || !apresentacao?.id || modelo.apresentacaoId !== apresentacao.id) return null;
  const exibido = caminho(apresentacao.arquivo);
  if (!exibido) return null;
  const estilo = exibido === caminho(previa?.arquivo) ? previa : exibido === caminho(peca?.arquivo) ? peca : null;
  if (!/^#[0-9a-f]{6}$/i.test(estilo?.cor || '')) return null;
  return [1, 3, 5].map(i => parseInt(estilo.cor.slice(i, i + 2), 16)).join(',');
}

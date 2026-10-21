// Posição pra nó que chegou sem `position` (fluxo montado por script ou importado à
// mão). Sem isso o canvas quebrava ao abrir (position.x de undefined) e continuava
// mostrando o fluxo anterior. Mesmo layout do servidor (api.posicionar): da esquerda
// pra direita, coluna = distância a partir da entrada seguindo as arestas. Nó que
// já tem posição fica onde está. Função pura: devolve nós novos.

const temPosicao = (n) => Number.isFinite(n?.position?.x) && Number.isFinite(n?.position?.y)

export function posicionar(nodes = [], edges = [], entrada = '') {
  if (nodes.every(temPosicao)) return nodes
  const ids = nodes.map((n) => n.id)
  const saidas = {}
  for (const e of edges) (saidas[e.source] ||= []).push(e.target)
  const alvos = new Set(edges.map((e) => e.target))
  const raizes = [...(ids.includes(entrada) ? [entrada] : []), ...ids.filter((i) => !alvos.has(i))]
  const coluna = new Map()
  const fila = raizes.map((r) => [r, 0])
  while (fila.length) {
    const [id, c] = fila.shift()
    if (coluna.has(id) || !ids.includes(id)) continue
    coluna.set(id, c)
    for (const alvo of saidas[id] || []) fila.push([alvo, c + 1])
  }
  const proxima = Math.max(-1, ...coluna.values()) + 1
  const linhas = {}
  return nodes.map((n) => {
    if (!coluna.has(n.id)) coluna.set(n.id, proxima)   // solto: vai pro fim
    const c = coluna.get(n.id)
    const linha = linhas[c] || 0
    linhas[c] = linha + 1
    if (temPosicao(n)) return n
    return { ...n, position: { x: 380 + c * 300, y: 160 + linha * 180 } }
  })
}

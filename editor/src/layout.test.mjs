// node --test editor/src/layout.test.mjs  (rodado também pelo pytest, se houver node)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { posicionar } from './layout.js'

test('nó sem position ganha posição da esquerda pra direita', () => {
  const nodes = [{ id: 'b', type: 'text' }, { id: 'a', type: 'text' }, { id: 'c', type: 'text', position: { x: 5, y: 6 } }]
  const edges = [{ source: 'a', target: 'b' }, { source: 'b', target: 'c' }]
  const saida = posicionar(nodes, edges, 'a')
  const pos = Object.fromEntries(saida.map((n) => [n.id, n.position]))
  assert.deepEqual(pos.a, { x: 380, y: 160 })
  assert.deepEqual(pos.b, { x: 680, y: 160 })
  assert.deepEqual(pos.c, { x: 5, y: 6 })   // quem tinha posição fica
})

test('position inválida e nó solto também ganham posição', () => {
  const saida = posicionar([{ id: 'x', position: { x: 'a' } }, { id: 'y' }], [], '')
  for (const n of saida) assert.ok(Number.isFinite(n.position.x) && Number.isFinite(n.position.y))
  assert.notDeepEqual(saida[0].position, saida[1].position)
})

test('ciclo não trava', () => {
  const saida = posicionar([{ id: 'a' }, { id: 'b' }], [{ source: 'a', target: 'b' }, { source: 'b', target: 'a' }], 'a')
  assert.equal(saida.length, 2)
})

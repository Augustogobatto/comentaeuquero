<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import CeqEdge from './CeqEdge.vue'
import CeqNode from './CeqNode.vue'
import Funil from './Funil.vue'
import Icone from './Icone.vue'
import NodePanel from './NodePanel.vue'
import { NOMES_GATILHO, gatilhosDisponiveis, paleta } from './tipos'

const { onConnect, addEdges, project, vueFlowRef, fitView, onNodesInitialized,
        updateNodeData, getSelectedEdges } = useVueFlow()

// enquadra quando o Vue Flow JA MEDIU os nos. Fazer isso antes (no nextTick) nao
// funciona: sem tamanho conhecido, o calculo do enquadramento sai errado e o fluxo
// nasce encostado no canto. O teto de 1:1 evita que um fluxo de um passo so
// apareca com o card ocupando meia tela.
onNodesInitialized(() => fitView({ maxZoom: 1, padding: 0.25 }))

const fluxos = ref([])
const fluxoAtual = ref(null)
const nodes = ref([])
const edges = ref([])
const selecionado = ref(null)
const avisos = ref([])
const tags = ref([])
const medias = ref([])
const salvando = ref(false)
const sujo = ref(false)
const erro = ref('')
// enquanto um fluxo está sendo carregado, trocar nós e arestas não conta como edição
const carregando = ref(false)
const waAtivo = ref(false)
// a paleta depende do WhatsApp estar ligado (waAtivo, logo abaixo)
const familias = computed(() => paleta({ wa: waAtivo.value }))

async function api(caminho, opcoes = {}) {
  const r = await fetch(`/api${caminho}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opcoes,
    body: opcoes.body ? JSON.stringify(opcoes.body) : undefined,
  })
  if (r.status === 401) { window.location.href = '/login'; return null }
  if (!r.ok) { erro.value = `${r.status}: ${(await r.text()).slice(0, 200)}`; return null }
  return r.json()
}

async function carregarLista() {
  fluxos.value = (await api('/flows')) || []
  tags.value = (await api('/tags')) || []
}

// WhatsApp ligado na conta? Sem número (ou instância antiga, que nem tem a rota e
// responde 404), o editor esconde tudo que é de WhatsApp. Fetch direto, sem o api():
// 404 aqui é resposta esperada, não erro pra mostrar na tela.
async function carregarEstadoWa() {
  try {
    const r = await fetch('/api/wa/estado')
    waAtivo.value = r.ok ? !!(await r.json()).configurado : false
  } catch { waAtivo.value = false }
}
const gatilhosDoSeletor = computed(() => gatilhosDisponiveis(waAtivo.value))

// O gatilho abre o fluxo no canvas, mas não é um nó do grafo: ele vive na tabela de
// gatilhos, que é quem o motor consulta. Aqui ele é desenhado a partir dela e some de
// novo na hora de salvar. Assim a leitura fica na ordem em que a coisa acontece
// (alguém comenta, aí o fluxo responde) sem duplicar a fonte da verdade.
const ID_GATILHO = '__gatilho__'
const LARGURA_GATILHO = 300

function noDoGatilho(f, entrada) {
  const alvo = f.graph.nodes?.find((n) => n.id === entrada)
  const pos = alvo
    ? { x: alvo.position.x - LARGURA_GATILHO, y: alvo.position.y }
    : { x: 80, y: 160 }
  return { id: ID_GATILHO, type: 'gatilho', position: pos,
           data: { triggers: f.triggers || [] }, deletable: false }
}

function entradaSalva(f) {
  if (f.entry_node && f.graph.nodes?.some((n) => n.id === f.entry_node)) return f.entry_node
  const alvos = new Set((f.graph.edges || []).map((e) => e.target))
  const raiz = (f.graph.nodes || []).find((n) => !alvos.has(n.id))
  return raiz?.id || f.graph.nodes?.[0]?.id || ''
}

async function abrir(id) {
  if (sujo.value && !confirm('Tem alteração não salva. Descartar?')) return
  const f = await api(`/flows/${id}`)
  if (!f) return
  carregando.value = true
  fluxoAtual.value = f
  const entrada = entradaSalva(f)
  nodes.value = [noDoGatilho(f, entrada), ...(f.graph.nodes || []).map((n) => ({ ...n }))]
  edges.value = (f.graph.edges || []).map((e, i) => ({ id: e.id || `e${i}`, ...e, type: 'ceq' }))
  if (entrada) {
    edges.value.push({ id: 'e-gatilho', source: ID_GATILHO, target: entrada, type: 'ceq' })
  }
  avisos.value = f.avisos || []
  selecionado.value = null
  vista.value = 'fluxo'   // trocar de fluxo volta pro canvas
  // os watchers rodam depois desta função; o sujo volta a false no fim da fila
  setTimeout(() => { sujo.value = false; carregando.value = false }, 0)
}

async function novoFluxo() {
  const nome = prompt('Nome do fluxo:')
  if (!nome) return
  const r = await api('/flows', { method: 'POST', body: { name: nome } })
  if (r) { await carregarLista(); await abrir(r.id) }
}

async function apagarFluxo() {
  if (!fluxoAtual.value) return
  const f = fluxoAtual.value
  // o título editável pode carregar um nome que nunca foi salvo; o aviso mostra
  // o nome que o servidor conhece
  const nome = fluxos.value.find((x) => x.id === f.id)?.name || f.name
  // o banco apaga em cascata: passos, gatilhos e as sessões de quem estava no
  // meio do fluxo. O aviso soletra o estrago porque não tem lixeira nem desfazer.
  if (!confirm(`Apagar o fluxo "${nome}"?\n\nSome com os passos, os gatilhos e as conversas em andamento dele. Não tem volta.`)) return
  // a condição do 404 abaixo lê o erro global; um "404:" velho pendurado na
  // faixa faria até uma recusa do servidor passar como sucesso
  erro.value = ''
  const r = await api(`/flows/${f.id}`, { method: 'DELETE' })
  // 404 = outra aba já apagou; o objetivo está cumprido, segue a limpeza —
  // senão o fluxo fantasma ficava aberto no canvas sem cura
  if (!r && !erro.value.startsWith('404:')) return
  erro.value = ''
  mostrarGatilhos.value = false
  // zerar nós e arestas acorda os watchers de edição; sem a flag de carga o
  // "sujo" voltava a true e o abrir() seguinte pedia pra descartar uma
  // alteração que não existe. O finally garante que a flag não fica presa
  // se a rede cair no meio — presa, ela emudece os watchers pra sempre.
  carregando.value = true
  try {
    fluxoAtual.value = null
    nodes.value = []
    edges.value = []
    selecionado.value = null
    avisos.value = []
    metrica.value = null
    sujo.value = false
    await carregarLista()
  } finally {
    // os watchers rodam no microtask; quando a lista voltou da rede, já passaram
    carregando.value = false
  }
  if (fluxos.value.length) await abrir(fluxos.value[0].id)
}

async function salvar() {
  if (!fluxoAtual.value) return
  salvando.value = true
  // o nó de gatilho e a aresta dele não vão pro banco: viram o entry_node
  const ligacaoDoGatilho = edges.value.find((e) => e.source === ID_GATILHO)
  const graph = {
    nodes: nodes.value.filter((n) => n.id !== ID_GATILHO).map((n) => ({
      id: n.id, type: n.type, position: n.position, data: n.data,
    })),
    edges: edges.value.filter((e) => e.source !== ID_GATILHO && e.target !== ID_GATILHO)
      .map((e) => ({
        id: e.id, source: e.source, target: e.target,
        sourceHandle: e.sourceHandle || null,
      })),
  }
  const entrada = graph.nodes.some((n) => n.id === ligacaoDoGatilho?.target)
    ? ligacaoDoGatilho.target
    : entradaDoGrafo(graph)
  const r = await api(`/flows/${fluxoAtual.value.id}`, {
    method: 'PUT',
    body: { graph, entry_node: entrada, name: fluxoAtual.value.name,
            active: fluxoAtual.value.active },
  })
  salvando.value = false
  if (r) { avisos.value = r.avisos || []; sujo.value = false; await carregarLista() }
}

// o nó de entrada é o único sem ninguém apontando pra ele
function entradaDoGrafo(graph) {
  const alvos = new Set(graph.edges.map((e) => e.target))
  const raiz = graph.nodes.find((n) => !alvos.has(n.id))
  return raiz ? raiz.id : (graph.nodes[0]?.id || '')
}

const PADROES = {
  text: { text: '' },
  buttons: { text: '', buttons: [] },
  quick_replies: { text: '', options: [] },
  media: { kind: 'image', url: '' },
  ai: { prompt: '', fallback: '' },
  delay: { minutes: 5 },
  schedule: { run_at: '' },
  wait_input: { expects: 'texto', save_as: '', retry_text: '' },
  condition: { check: 'tem_tag', value: '' },
  split: { percent_a: 50 },
  action: { actions: [] },
  webhook: { url: '' },
  pedir_whatsapp: { text: '', consentimento: '', retry_text: '' },
  template_wa: { template: '', idioma: 'pt_BR', variaveis: {}, botoes: [] },
}

function addNo(tipo) {
  const id = `n${Date.now().toString(36)}`
  const caixa = vueFlowRef.value?.getBoundingClientRect()
  const gatilho = nodes.value.find((n) => n.id === ID_GATILHO)
  const primeiro = !nodes.value.some((n) => n.id !== ID_GATILHO)
  // no fluxo vazio o centro da tela é onde o gatilho está: o passo novo nasceria em
  // cima dele. O primeiro passo vai ao lado do gatilho, na ordem de leitura.
  const pos = primeiro && gatilho
    ? { x: gatilho.position.x + LARGURA_GATILHO, y: gatilho.position.y }
    : (caixa
      ? project({ x: caixa.width / 2 - 110, y: caixa.height / 2 - 70 })
      : { x: 120, y: 120 })
  nodes.value.push({ id, type: tipo, position: pos, data: { ...(PADROES[tipo] || {}) } })
  // primeiro passo do fluxo já sai ligado ao gatilho: é o que a pessoa faria em
  // seguida de qualquer jeito, e sem a ligação o fluxo não teria por onde começar
  if (!edges.value.some((e) => e.source === ID_GATILHO)) {
    edges.value.push({ id: 'e-gatilho', source: ID_GATILHO, target: id, type: 'ceq' })
  }
  selecionado.value = id
  sujo.value = true
}

// ---- ligações ----
// qual ligação está com o mouse em cima; é o que acende o botão de apagar. O
// botão fica numa camada HTML separada do SVG da linha, então ele também avisa
// quando o mouse entra nele — senão o botão sumia no caminho até o clique.
const ligacaoSobMouse = ref(null)

// a ligação do gatilho não é apagável: ela não existe no banco, é o entry_node
// desenhado. Trocar a entrada se faz arrastando do gatilho pro outro passo.
const fixa = (id) => id === 'e-gatilho'

function apagarLigacao(id) {
  if (fixa(id)) return
  edges.value = edges.value.filter((e) => e.id !== id)
  ligacaoSobMouse.value = null
  sujo.value = true
}

// Delete/Backspace com ligação selecionada. O atalho nativo do Vue Flow ficou
// desligado de propósito (delete-key-code=null): ele apagaria PASSO junto, e
// apagar passo tem confirmação no painel. A guarda do campo de texto existe
// porque Backspace dentro de um input é edição de texto, não comando.
function teclaApaga(ev) {
  if (ev.key !== 'Delete' && ev.key !== 'Backspace') return
  const alvo = ev.target
  if (alvo && (alvo.isContentEditable ||
               ['INPUT', 'TEXTAREA', 'SELECT'].includes(alvo.tagName))) return
  const ids = getSelectedEdges.value.map((e) => e.id).filter((id) => !fixa(id))
  if (!ids.length) return
  ev.preventDefault()
  edges.value = edges.value.filter((e) => !ids.includes(e.id))
  sujo.value = true
}
onMounted(() => window.addEventListener('keydown', teclaApaga))
onUnmounted(() => window.removeEventListener('keydown', teclaApaga))

function apagarNo(id) {
  nodes.value = nodes.value.filter((n) => n.id !== id)
  edges.value = edges.value.filter((e) => e.source !== id && e.target !== id)
  selecionado.value = null
  sujo.value = true
}

onConnect((params) => {
  // uma saída leva a um lugar só: ligar de novo troca o destino em vez de empilhar
  edges.value = edges.value.filter(
    (e) => !(e.source === params.source &&
             (e.sourceHandle || null) === (params.sourceHandle || null)))
  addEdges([{ ...params, id: `e${Date.now().toString(36)}`, type: 'ceq' }])
  sujo.value = true
})

// vista do fluxo aberto: o canvas de edição ou o funil de métricas dele, como o
// "Editar / Visualização" do ManyChat — as métricas moram no fluxo, não numa aba solta
const vista = ref('fluxo')
const metrica = ref(null)
const periodoMetrica = ref('tudo')

async function verMetricas() {
  vista.value = 'metricas'
  selecionado.value = null
  await carregarMetricas()
}

async function carregarMetricas() {
  if (!fluxoAtual.value) return
  metrica.value = await api(`/flows/${fluxoAtual.value.id}/metricas?periodo=${periodoMetrica.value}`)
}

async function trocaPeriodo(p) {
  periodoMetrica.value = p
  await carregarMetricas()
}

// o gatilho não abre o painel de passo: ele tem janela própria
const noSelecionado = computed(() =>
  nodes.value.find((n) => n.id === selecionado.value && n.id !== ID_GATILHO))

function clicouNoNo(id) {
  if (id === ID_GATILHO) {
    selecionado.value = null
    abrirGatilhos()
    return
  }
  selecionado.value = id
}

// Marca alteração só pelo CONTEÚDO dos nós e pelas ligações. Observar o nó inteiro
// em profundidade era armadilha: o Vue Flow escreve dimensões e limites de conector
// dentro de cada nó ao medi-los, então só de abrir um fluxo ele já aparecia como
// editado, e trocar de fluxo pedia confirmação sem ninguém ter mexido em nada.
// Compara o CONTEÚDO em texto, não a lista. Com deep sobre um getter que devolve
// array novo a cada leitura, qualquer mexida no array de nós já disparava — inclusive
// atualizar o card do gatilho depois de abrir a janela, que acendia o "Salvar" sem
// ninguém ter editado o fluxo. O gatilho fica de fora porque ele salva sozinho.
watch(() => JSON.stringify(nodes.value.filter((n) => n.id !== ID_GATILHO)
                            .map((n) => [n.type, n.data])),
      () => { if (!carregando.value) sujo.value = true })
watch(() => edges.value.map((e) => [e.source, e.target, e.sourceHandle].join('>')),
      () => { if (!carregando.value) sujo.value = true })

// ---- gatilhos ----
const mostrarGatilhos = ref(false)
const GATILHO_VAZIO = () => ({ type: 'comment', keywords: '', media_ids: [], public_replies: [] })
const novoGatilho = ref(GATILHO_VAZIO())

async function addGatilho() {
  const g = novoGatilho.value
  const r = await api(`/flows/${fluxoAtual.value.id}/triggers`, {
    method: 'POST',
    body: {
      type: g.type,
      keywords: g.keywords.split(',').map((k) => k.trim()).filter(Boolean),
      media_ids: g.media_ids,
      public_replies: g.public_replies.map((t) => t.trim()).filter(Boolean),
    },
  })
  if (r) {
    await recarregarGatilhos()
    novoGatilho.value = GATILHO_VAZIO()
  }
}

async function alternarGatilho(t) {
  // desligar é diferente de apagar: o gatilho some do ar mas guarda palavras-chave,
  // posts escolhidos e respostas públicas pra quando religar
  const novo = t.active ? 0 : 1
  const r = await api(`/triggers/${t.id}`, { method: 'PATCH', body: { active: novo } })
  if (r) { t.active = novo; await recarregarGatilhos() }
}

async function apagarGatilho(id) {
  await api(`/triggers/${id}`, { method: 'DELETE' })
  await recarregarGatilhos()
}

async function recarregarGatilhos() {
  const f = await api(`/flows/${fluxoAtual.value.id}`)
  if (f) {
    fluxoAtual.value.triggers = f.triggers
    // o card no canvas mostra os gatilhos, inclusive quais estão desligados, então
    // precisa acompanhar a janela. Trocar o objeto dentro do array não bastava: o
    // Vue Flow mantém o próprio estado dos nós, e só o updateNodeData dele redesenha.
    if (nodes.value.some((n) => n.id === ID_GATILHO)) {
      updateNodeData(ID_GATILHO, { triggers: f.triggers || [] })
    }
  }
  await carregarLista()
}

async function abrirGatilhos() {
  mostrarGatilhos.value = true
  if (!medias.value.length) medias.value = (await api('/medias')) || []
  await recarregarGatilhos()
}

async function exportar() {
  const j = await api(`/flows/${fluxoAtual.value.id}/export`)
  if (!j) return
  const blob = new Blob([JSON.stringify(j, null, 2)], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${(j.name || 'fluxo').replace(/\s+/g, '-').toLowerCase()}.json`
  a.click()
}

async function importar(ev) {
  const arquivo = ev.target.files[0]
  if (!arquivo) return
  const r = await api('/flows/import', { method: 'POST', body: JSON.parse(await arquivo.text()) })
  if (r) { await carregarLista(); await abrir(r.id) }
  ev.target.value = ''
}

onMounted(async () => {
  await carregarLista()
  carregarEstadoWa()
  // a lista em /fluxos manda o id na URL; sem ele, abre o primeiro
  const params = new URLSearchParams(location.search)
  if (params.get('novo')) {
    await novoFluxo()
    return
  }
  const pedido = Number(params.get('f'))
  const alvo = fluxos.value.find((f) => f.id === pedido) || fluxos.value[0]
  if (alvo) await abrir(alvo.id)
})

</script>

<template>
  <!-- barra do produto: a mesma do painel, pra ficar claro que é a mesma casa -->
  <header class="topo">
    <a class="marca" href="/painel"><span class="marca-q" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span class="marca-txt">comenta EU QUERO</span></a>
    <nav>
      <a href="/painel">Painel</a>
      <a href="/fluxos" class="aqui">Fluxos</a>
      <a href="/leads">Leads</a>
      <a href="/logout">Sair</a>
    </nav>
  </header>

  <div class="tela">
    <aside class="lateral">
      <section class="bloco">
        <div class="bloco-cab">
          <a class="voltar" href="/fluxos" title="ver todos os fluxos">
            <Icone nome="voltar" :tamanho="13" /> todos
          </a>
          <button class="quieto mini" @click="novoFluxo">novo</button>
        </div>
        <ul class="lista">
          <li v-for="f in fluxos" :key="f.id" :class="{ ativo: f.id === fluxoAtual?.id }"
              @click="abrir(f.id)">
            <span class="dot" :class="f.active ? 'ok' : 'mut'"></span>
            <span class="nome">{{ f.name }}</span>
            <span class="num">{{ f.nos }}</span>
          </li>
          <li v-if="!fluxos.length" class="nada">nenhum fluxo ainda</li>
        </ul>
        <div class="io">
          <button class="quieto mini" @click="exportar" :disabled="!fluxoAtual">exportar</button>
          <label class="quieto mini arquivo">importar
            <input type="file" accept="application/json" @change="importar" hidden />
          </label>
        </div>
        <button class="quieto mini apagar-fluxo" @click="apagarFluxo" :disabled="!fluxoAtual"
                title="apagar o fluxo aberto">apagar fluxo</button>
      </section>

      <section class="bloco" v-if="fluxoAtual">
        <h2>Adicionar passo</h2>
        <div v-for="fam in familias" :key="fam.chave" class="familia">
          <span class="fam-rot" :style="{ color: fam.cor }">{{ fam.rotulo }}</span>
          <button v-for="t in fam.itens" :key="t.tipo" class="peca" @click="addNo(t.tipo)"
                  :style="{ '--c': fam.cor, '--s': fam.suave }">
            <span class="peca-ico" :style="{ background: fam.suave, color: fam.cor }">
              <Icone :nome="t.tipo" :tamanho="13" />
            </span>
            {{ t.rotulo }}
          </button>
        </div>
      </section>
    </aside>

    <main class="centro">
      <div class="barra" v-if="fluxoAtual">
        <input class="titulo" v-model="fluxoAtual.name" @input="sujo = true"
               placeholder="Nome do fluxo" />

        <div class="vistas">
          <button :class="{ on: vista === 'fluxo' }" @click="vista = 'fluxo'">Fluxo</button>
          <button :class="{ on: vista === 'metricas' }" @click="verMetricas">Métricas</button>
        </div>

        <template v-if="vista === 'fluxo'">
          <button class="liga" :class="{ on: fluxoAtual.active }"
                  @click="fluxoAtual.active = fluxoAtual.active ? 0 : 1; sujo = true">
            <span class="dot" :class="fluxoAtual.active ? 'ok' : 'mut'"></span>
            {{ fluxoAtual.active ? 'ligado' : 'desligado' }}
          </button>
          <button class="quieto" @click="abrirGatilhos">
            Gatilhos <span class="cont">{{ fluxoAtual.triggers?.length || 0 }}</span>
          </button>
          <button class="salvar" @click="salvar" :disabled="salvando || !sujo">
            {{ salvando ? 'salvando' : (sujo ? 'Salvar' : 'Salvo') }}
          </button>
        </template>
      </div>

      <div v-if="erro" class="faixa erro" @click="erro = ''">{{ erro }}</div>

      <div v-if="avisos.length" class="faixa aviso">
        <h2>Vale conferir</h2>
        <ul><li v-for="(a, i) in avisos" :key="i">{{ a }}</li></ul>
      </div>

      <!-- métricas do fluxo aberto -->
      <Funil v-if="fluxoAtual && vista === 'metricas'" :dados="metrica"
             :periodo="periodoMetrica" @periodo="trocaPeriodo" />

      <!-- bezier em vez de smoothstep: com nós próximos, o degrau vira zigue-zague e
           cruza por cima dos cards. A curva passa por fora e fica legível. -->
      <VueFlow v-if="fluxoAtual && vista === 'fluxo'" v-model:nodes="nodes" v-model:edges="edges"
               :min-zoom="0.2" :max-zoom="1.8"
               :default-edge-options="{ type: 'ceq', animated: false }"
               :delete-key-code="null"
               @node-click="clicouNoNo($event.node.id)"
               @node-drag-stop="sujo = true"
               @edge-mouse-enter="ligacaoSobMouse = $event.edge.id"
               @edge-mouse-leave="ligacaoSobMouse = null"
               @pane-click="selecionado = null">
        <template #edge-ceq="p">
          <CeqEdge v-bind="p" :fixa="fixa(p.id)"
                   :destaque="ligacaoSobMouse === p.id"
                   @entrou="ligacaoSobMouse = p.id" @saiu="ligacaoSobMouse = null"
                   @apagar="apagarLigacao(p.id)" />
        </template>
        <template v-for="t in [...Object.keys(PADROES), 'gatilho']" :key="t" #[`node-${t}`]="p">
          <CeqNode v-bind="p" />
        </template>
        <Background :gap="15" :size="1.4" pattern-color="var(--linha)" />
        <Controls :show-interactive="false" />
      </VueFlow>

      <div v-if="!fluxoAtual" class="vazio">
        <p class="vazio-t">Nenhum fluxo por aqui</p>
        <p class="vazio-s">Um fluxo é o caminho que a pessoa percorre depois de comentar.</p>
        <button class="salvar" @click="novoFluxo">Criar o primeiro</button>
      </div>
    </main>

    <NodePanel v-if="noSelecionado" :key="noSelecionado.id" :node="noSelecionado" :tags="tags"
               @fechar="selecionado = null" @apagar="apagarNo" />
  </div>

  <!-- gatilhos -->
  <!-- o fluxoAtual na guarda: apagar o fluxo com esta janela aberta (dá pelo
       teclado) derrubava o render inteiro no null -->
  <div v-if="mostrarGatilhos && fluxoAtual" class="cortina" @click.self="mostrarGatilhos = false">
    <div class="janela">
      <header>
        <h1>Quando este fluxo começa</h1>
        <button class="x" @click="mostrarGatilhos = false" aria-label="fechar"><Icone nome="fechar" :tamanho="16" /></button>
      </header>

      <ul class="gatilhos">
        <li v-for="t in fluxoAtual.triggers || []" :key="t.id" :class="{ off: !t.active }">
          <button class="chave" :class="{ on: t.active }" @click="alternarGatilho(t)"
                  :title="t.active ? 'desligar este gatilho' : 'ligar este gatilho'"
                  :aria-label="t.active ? 'desligar' : 'ligar'" role="switch"
                  :aria-checked="!!t.active">
            <span class="bolinha"></span>
          </button>
          <div>
            <b>{{ NOMES_GATILHO[t.type] || t.type }}</b>
            <template v-if="t.keywords.length">
              <span class="pill" v-for="k in t.keywords" :key="k">{{ k }}</span>
            </template>
            <span v-else class="obs">qualquer texto</span>
            <div v-if="t.media_ids.length" class="obs">
              só em {{ t.media_ids.length }} post{{ t.media_ids.length > 1 ? 's' : '' }}
            </div>
            <div v-for="(r, i) in t.public_replies || []" :key="i" class="obs">
              responde no comentário: “{{ r }}”
            </div>
          </div>
          <button class="perigo" @click="apagarGatilho(t.id)">remover</button>
        </li>
        <li v-if="!(fluxoAtual.triggers || []).length" class="nada">
          Sem gatilho, este fluxo não começa sozinho.
        </li>
      </ul>

      <div class="novo">
        <label>Acontece quando
          <select v-model="novoGatilho.type">
            <option v-for="(nome, k) in gatilhosDoSeletor" :key="k" :value="k">{{ nome }}</option>
          </select>
        </label>

        <label v-if="novoGatilho.type === 'wa_template_reply'">Texto do botão
          <span class="sub">o texto exato do botão do template, separado por vírgula se for mais de um</span>
          <input v-model="novoGatilho.keywords" placeholder="texto do botão" />
        </label>
        <label v-else>Palavras-chave <span class="sub">separadas por vírgula; vazio vale pra qualquer texto</span>
          <input v-model="novoGatilho.keywords" placeholder="aurora, quero aurora" />
        </label>

        <template v-if="['comment', 'live_comment'].includes(novoGatilho.type)">
          <label>Responder no próprio comentário <span class="sub">opcional</span></label>
          <div v-for="(r, i) in novoGatilho.public_replies" :key="i" class="resposta">
            <input v-model="novoGatilho.public_replies[i]"
                   :placeholder="i ? 'Outro jeito de dizer a mesma coisa' : 'Te mandei no direct'" />
            <button class="perigo" @click="novoGatilho.public_replies.splice(i, 1)">remover</button>
          </div>
          <button class="add" @click="novoGatilho.public_replies.push('')">
            {{ novoGatilho.public_replies.length ? 'adicionar outra resposta' : 'adicionar resposta pública' }}
          </button>
          <p class="obs" v-if="novoGatilho.public_replies.length > 1">
            As respostas entram em rodízio, uma a cada comentário. É o que evita a mesma
            frase repetida embaixo de dez comentários seguidos.
          </p>

          <label>Só nestes posts <span class="sub">nenhum marcado vale pra todos</span></label>
          <div class="posts">
            <label v-for="m in medias" :key="m.id" class="post"
                   :class="{ marcado: novoGatilho.media_ids.includes(m.id) }"
                   :title="m.caption">
              <input type="checkbox" :value="m.id" v-model="novoGatilho.media_ids" hidden />
              <img v-if="m.thumb" :src="m.thumb" :alt="m.caption" />
              <span v-else class="sem-thumb">{{ m.type }}</span>
            </label>
            <p v-if="!medias.length" class="obs">Nenhum post encontrado na conta.</p>
          </div>
        </template>

        <button class="salvar" @click="addGatilho">Adicionar gatilho</button>
      </div>
    </div>
  </div>
</template>

<style>
@import '@vue-flow/core/dist/style.css';
@import '@vue-flow/core/dist/theme-default.css';
@import '@vue-flow/controls/dist/style.css';

/* Tokens: espelho de blocos/app/globals.css — manter em sincronia
   (os mesmos de app/static/ceq.css; editor e painel são o mesmo produto). */
:root {
  --fundo: #ffffff;
  --texto: #0a0a0a;
  --suave: #6b6b6b;
  --linha: #e6e6e6;
  --acento: #F0561D;
  --painel: #fafafa;
  --erro: #b91c1c;
  --reserva: #2563eb;
  --aviso: #b45309;
  --ok: #1F7A4D;
  color-scheme: light;
}
.dark {
  --fundo: #0a0a0a;
  --texto: #f2f2f2;
  --suave: #9a9a9a;
  --linha: #262626;
  --acento: #F0561D;
  --painel: #141414;
  --erro: #f87171;
  --reserva: #60a5fa;
  --aviso: #fbbf24;
  --ok: #4CC28A;
  color-scheme: dark;
}
:root {
  --texto-4: color-mix(in srgb, var(--texto) 4%, transparent);
  --texto-6: color-mix(in srgb, var(--texto) 6%, transparent);
  --acento-10: color-mix(in srgb, var(--acento) 10%, transparent);
  --acento-25: color-mix(in srgb, var(--acento) 25%, transparent);
  /* nomes antigos do editor apontando pros tokens do Blocos */
  --bg: var(--texto-4);
  --panel: var(--fundo);
  --ink: var(--texto);
  --mut: var(--suave);
  --line: var(--linha);
  --accent: var(--acento);
  --accent-soft: var(--acento-10);
  --err: var(--erro);
  --sans: "Instrument Sans", ui-sans-serif, system-ui, sans-serif;
  --mono: ui-monospace, "SF Mono", "Cascadia Code", Menlo, monospace;
}
* { box-sizing: border-box; }
body {
  font-family: var(--sans); background: var(--fundo); color: var(--ink); margin: 0;
  font-size: 14px; line-height: 1.45; -webkit-font-smoothing: antialiased;
}
h1 { font-size: 16px; font-weight: 600; letter-spacing: -.01em; margin: 0; }
h2 { font-size: 13px; font-weight: 500; color: var(--suave); margin: 0; }
.sub { color: var(--mut); font-weight: 400; }
.num { font-family: var(--mono); font-variant-numeric: tabular-nums; }
.dot {
  display: inline-block; width: 7px; height: 7px; border-radius: 50%; flex: none;
}
.dot.ok { background: var(--ok); }
.dot.mut { background: var(--suave); opacity: .5; }
.obs { font-size: 12px; color: var(--mut); }
.nada { color: var(--mut); font-size: 13px; font-style: italic; }
.pill {
  display: inline-flex; align-items: center; height: 20px; background: var(--texto-6); color: var(--texto);
  border-radius: 999px; padding: 0 8px; font-size: 12px;
  font-weight: 500; margin: 0 4px 2px 0;
}

/* topo do produto: mesma marca e mesmos itens do painel */
.topo {
  background: var(--painel); border-bottom: 1px solid var(--line); padding: 0 16px;
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  height: 56px;
}
.marca {
  display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: 15px;
  letter-spacing: -.01em; color: var(--texto); text-decoration: none; white-space: nowrap;
}
.marca-q { display: inline-grid; width: 22px; height: 22px; grid-template-columns: 1fr 1fr; gap: 2px; flex: none; }
.marca-q i { background: var(--texto); border-radius: 2px; }
.marca-q i:last-child { background: var(--acento); }
.topo nav { display: flex; gap: 2px; }
.topo nav a {
  display: flex; align-items: center; height: 32px; color: var(--suave); text-decoration: none;
  font-size: 14px; padding: 0 12px; border-radius: 6px; transition: background .15s, color .15s;
}
.topo nav a:hover { color: var(--ink); background: var(--texto-4); }
.topo nav a.aqui { color: var(--ink); background: var(--texto-6); font-weight: 500; }

.tela { display: flex; height: calc(100vh - 56px); }

/* botões, no dialeto do painel */
button, .btn {
  border: 1px solid transparent; border-radius: 6px; height: 34px; padding: 0 14px; font: inherit; font-size: 14px;
  font-weight: 500; cursor: pointer; background: var(--ink); color: var(--fundo);
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  transition: opacity .15s, background .15s;
}
button:hover { opacity: .9; }
/* pointer-events: sem isso o :hover pinta botão desabilitado como se estivesse
   armado — no "apagar fluxo" isso acendia o vermelho com o botão morto */
button:disabled { opacity: .45; cursor: default; pointer-events: none; }
.quieto {
  background: var(--panel); color: var(--ink); border: 1px solid var(--line);
}
.quieto:hover { background: var(--texto-4); opacity: 1; }
.mini { height: 28px; padding: 0 10px; font-size: 13px; font-weight: 500; }
.perigo { background: none; color: var(--err); font-weight: 500; height: auto; padding: 2px 4px; font-size: 13px; }
.salvar { background: var(--ink); color: var(--fundo); }
button:focus-visible, a:focus-visible, input:focus-visible {
  outline: 2px solid var(--accent); outline-offset: 2px;
}

/* lateral */
.lateral {
  width: 232px; background: var(--painel); border-right: 1px solid var(--line);
  overflow-y: auto; flex: none;
}
.bloco { padding: 16px; border-bottom: 1px solid var(--line); }
.bloco-cab { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.voltar {
  display: inline-flex; align-items: center; gap: 6px; color: var(--mut);
  text-decoration: none; font-size: 13px; font-weight: 500;
}
.voltar:hover { color: var(--ink); text-decoration: none; }
.bloco h2 { margin-bottom: 10px; }
.bloco-cab h2 { margin-bottom: 0; }
/* com muitos fluxos a lista rola sozinha; sem o teto ela empurrava o
   "Adicionar passo" pra fora da tela. A ul cresce 8px pra cada lado (padding
   espelhado no margin) pra rolagem não cortar o li, que continua sangrando
   até a borda do bloco como antes. */
.lista {
  list-style: none; padding: 0 8px; margin: 0 -8px;
  max-height: 32vh; overflow-y: auto;
}
.lista li {
  display: flex; align-items: center; gap: 8px; height: 34px; padding: 0 8px; margin: 0 -8px;
  border-radius: 6px; cursor: pointer; font-size: 14px; color: var(--suave);
}
.lista li:hover { color: var(--texto); }
.lista li:hover { background: var(--texto-4); }
.lista li.ativo { background: var(--texto-6); color: var(--texto); font-weight: 500; }
.nome { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lista .num { font-size: 11px; color: var(--mut); }
.lista li.nada { cursor: default; }
.lista li.nada:hover { background: none; }
.io { display: flex; gap: 6px; margin-top: 12px; }
.io > * { flex: 1; text-align: center; }
.apagar-fluxo { display: block; width: 100%; margin-top: 12px; color: var(--err); }
.apagar-fluxo:hover { background: color-mix(in srgb, var(--erro) 8%, transparent);
  border-color: color-mix(in srgb, var(--erro) 35%, transparent); opacity: 1; }
.arquivo { cursor: pointer; display: inline-flex; align-items: center; justify-content: center;
  border-radius: 6px; font-size: 13px; }
/* os pontos do fundo: o pattern-color não aceita var(), então a cor vem por aqui */
.vue-flow__background circle, .vue-flow__background pattern * { fill: color-mix(in srgb, var(--texto) 16%, transparent); }
.tela { overflow: hidden; }
@media (max-width: 640px) {
  .marca-txt { display: none; }
  .topo nav { overflow-x: auto; }
  .topo nav a { padding: 0 10px; }
  .lateral { width: 196px; }
}

.familia { margin-bottom: 14px; }
.familia:last-child { margin-bottom: 0; }
.fam-rot {
  display: block; font-size: 12px; font-weight: 500; color: var(--suave) !important; margin-bottom: 4px;
}
.peca {
  display: flex; align-items: center; justify-content: flex-start; gap: 10px; width: 100%; text-align: left;
  background: none; border: 1px solid transparent; color: var(--ink);
  font-size: 14px; font-weight: 400; height: 32px; padding: 0 8px; margin: 0 -8px 1px;
  width: calc(100% + 16px); border-radius: 6px;
}
.peca:hover { background: var(--texto-4); opacity: 1; }
.peca-ico {
  width: 22px; height: 22px; border-radius: 6px; display: grid; place-items: center;
  font-size: 11px; flex: none;
}

/* centro */
.centro { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.barra {
  display: flex; align-items: center; gap: 8px; padding: 10px 16px;
  background: var(--fundo); border-bottom: 1px solid var(--line);
}
.titulo {
  flex: 1; min-width: 0; font: inherit; font-size: 18px; font-weight: 500;
  letter-spacing: -.02em; border: 1px solid transparent; background: none;
  height: 34px; padding: 0 8px; border-radius: 6px; color: var(--ink);
}
.titulo:hover { border-color: var(--line); }
.titulo:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--acento-25); }
.vistas { display: inline-flex; background: var(--texto-4); border: 1px solid var(--line);
          border-radius: 6px; padding: 2px; gap: 2px; flex: none; }
.vistas button { height: 28px; font-size: 13px; font-weight: 500; color: var(--mut); background: none;
                 border: none; cursor: pointer; padding: 0 12px; border-radius: 4px; margin: 0; }
.vistas button:hover { color: var(--ink); }
.vistas button.on { background: var(--fundo); color: var(--ink);
                    box-shadow: 0 1px 2px rgba(10,10,10,.08); }
.liga {
  display: flex; align-items: center; gap: 6px; background: none;
  border: 1px solid var(--line); color: var(--mut); font-weight: 500; font-size: 13px;
}
.liga:hover { background: var(--texto-4); opacity: 1; }
.liga.on { color: var(--ok); }
.cont {
  font-variant-numeric: tabular-nums; font-size: 12px;
  background: var(--texto-6); color: var(--mut); border-radius: 999px; padding: 0 7px;
  margin-left: 2px;
}

.faixa { padding: 10px 16px; font-size: 13px; border-bottom: 1px solid; }
.faixa.aviso { background: color-mix(in srgb, var(--aviso) 6%, var(--fundo));
  border-color: color-mix(in srgb, var(--aviso) 30%, var(--linha)); color: var(--texto); }
.faixa.aviso h2 { color: var(--aviso); margin-bottom: 5px; }
.faixa.aviso ul { margin: 0; padding-left: 18px; }
.faixa.aviso li { margin-bottom: 2px; }
.faixa.erro { background: color-mix(in srgb, var(--erro) 6%, var(--fundo));
  border-color: color-mix(in srgb, var(--erro) 30%, var(--linha)); color: var(--err); cursor: pointer; }

.vazio { flex: 1; display: grid; place-content: center; justify-items: center; gap: 6px; }
.vazio-t { font-size: 16px; font-weight: 600; margin: 0; }
.vazio-s { color: var(--mut); font-size: 13px; margin: 0 0 10px; max-width: 320px; text-align: center; }

/* canvas — o fundo fica só no container: pintar o pane também cobre a textura */
.vue-flow { background: var(--painel); }
.vue-flow__edge-path { stroke: color-mix(in srgb, var(--texto) 30%, transparent); stroke-width: 1.5; }
.vue-flow__edge.selected .vue-flow__edge-path,
.vue-flow__edge:hover .vue-flow__edge-path { stroke: var(--accent); }
.vue-flow__connection-path { stroke: var(--accent); stroke-width: 1.5; }
.vue-flow__controls {
  box-shadow: none; border: 1px solid var(--linha); border-radius: 6px; overflow: hidden;
}
.vue-flow__controls-button {
  background: var(--fundo); border-bottom: 1px solid var(--line); fill: var(--mut);
  width: 28px; height: 28px; margin: 0; padding: 6px; border-radius: 0;
}
.vue-flow__controls-button svg { fill: var(--suave); }
.vue-flow__controls-button:hover { background: var(--painel); opacity: 1; }

/* janela de gatilhos */
.resposta { display: flex; gap: 8px; align-items: center; margin-top: 8px; }
.resposta input { flex: 1; margin-top: 0; }
.cortina {
  position: fixed; inset: 0; background: rgba(0, 0, 0, .3);
  backdrop-filter: blur(2px); display: grid; place-items: center; z-index: 60;
  animation: surge .14s ease;
}
@keyframes surge { from { opacity: 0 } to { opacity: 1 } }
.janela {
  background: var(--fundo); border: 1px solid var(--linha); border-radius: 8px; width: min(540px, 92vw);
  max-height: 86vh; overflow-y: auto; box-shadow: 0 4px 16px rgba(10, 10, 10, .08);
}
.janela header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid var(--line);
  position: sticky; top: 0; background: var(--panel);
}
.x { background: none; color: var(--mut); font-size: 15px; height: 30px; width: 30px; padding: 0; }
.x:hover { background: var(--texto-4); color: var(--texto); opacity: 1; }
.gatilhos { list-style: none; margin: 0; padding: 6px 20px; }
.gatilhos li.off { opacity: .5; }
.chave {
  flex: none; width: 34px; height: 20px; border-radius: 999px; padding: 0;
  background: var(--line); border: none; cursor: pointer; margin: 0;
  transition: background .15s ease;
}
.chave .bolinha {
  display: block; width: 16px; height: 16px; border-radius: 50%; background: var(--fundo);
  margin-left: 2px; transition: transform .15s ease;
  box-shadow: 0 1px 2px rgba(17, 17, 19, .25);
}
.chave.on { background: var(--ok); }
.chave.on .bolinha { transform: translateX(14px); }
.chave:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

.gatilhos li {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;
  padding: 12px 0; border-bottom: 1px solid var(--line); font-size: 13px;
}
.gatilhos li:last-child { border-bottom: none; }
.novo { padding: 4px 20px 20px; }
.novo label { display: block; font-size: 13px; font-weight: 500; margin-top: 16px; }
.novo input, .novo select {
  width: 100%; height: 36px; padding: 0 12px; border: 1px solid var(--line); border-radius: 6px;
  font: inherit; font-size: 14px; margin-top: 6px; background: var(--fundo); color: var(--ink);
}
.novo input:focus, .novo select:focus {
  outline: none; border-color: var(--acento); box-shadow: 0 0 0 3px var(--acento-25);
}
.novo .salvar { margin-top: 20px; width: 100%; height: 36px; }
.posts { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 7px; }
.post {
  width: 56px; height: 56px; border-radius: 8px; overflow: hidden; cursor: pointer;
  border: 2px solid var(--line); transition: border-color .12s ease;
}
.post:hover { border-color: var(--mut); }
.post.marcado { border-color: var(--accent); }
.post img { width: 100%; height: 100%; object-fit: cover; display: block; }
.sem-thumb {
  display: grid; place-items: center; width: 100%; height: 100%;
  background: var(--texto-4); font-family: var(--mono); font-size: 8px; color: var(--mut);
}
</style>

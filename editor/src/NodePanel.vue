<script setup>
// Painel que abre ao clicar num nó. Cada tipo mostra só os campos que fazem sentido
// pra ele: um nó de espera não pede texto, um nó de texto não pede condição.
import { computed, nextTick, onMounted, ref } from 'vue'
import Icone from './Icone.vue'
import { NOS_COM_JANELA, TIPOS, corDe, suaveDe } from './tipos'

const props = defineProps({ node: Object, tags: Array })
const emit = defineEmits(['fechar', 'apagar'])

const d = computed(() => props.node.data)

// Limites da Meta que aparecem na tela. O do botão é recomendação: passando disso o
// app corta na hora de desenhar, e quem escreveu não fica sabendo.
const MAX_BOTAO = 20
const MAX_BOTOES = 3
const LIMITE_TEXTO = 640      // mensagem com botões
const LIMITE_TEXTO_SIMPLES = 1000

// Caixa de texto que acompanha o que foi escrito. Sem isso, mensagem de dez linhas
// fica espiando por uma janelinha de quatro, que é como o Aurora estava sendo editado.
function ajustaAltura(el) {
  if (!el) return
  el.style.overflowY = 'hidden'   // sem barra: a caixa acompanha o texto
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight + 2}px`
}
const vCresce = {
  mounted(el) {
    const ajusta = () => ajustaAltura(el)
    ajusta()
    // de novo no quadro seguinte: no mounted o painel ainda está abrindo e a caixa
    // não tem a largura final, então o texto reflui depois e a conta muda
    requestAnimationFrame(ajusta)
    // e de novo quando a fonte da interface termina de carregar: com a fonte de
    // sistema o texto ocupa menos linhas, e a caixa nascia curta pro texto real
    document.fonts?.ready.then(ajusta)
    setTimeout(ajusta, 150)
    el.addEventListener('input', ajusta)
    // o pai, não a própria caixa: observar o elemento que estamos redimensionando
    // seria um laço. O que importa aqui é mudança de largura do painel.
    if (el.parentElement) {
      el._observador = new ResizeObserver(ajusta)
      el._observador.observe(el.parentElement)
    }
  },
  updated(el) { ajustaAltura(el) },
  unmounted(el) { el._observador?.disconnect() },
}

// o fluxo guarda o prazo em segundos, mas quem edita pensa em minutos. Sem isso o
// campo abre vazio num nó que TEM prazo configurado, e parece que não tem.
onMounted(() => {
  if (props.node.type === 'wait_input' && d.value.timeout_minutes === undefined) {
    d.value.timeout_minutes = Math.round((Number(d.value.timeout_seconds) || 0) / 60)
  }
})
const meta = computed(() => TIPOS[props.node.type] || {})
const limiteTexto = computed(() =>
  (d.value.buttons || []).length ? LIMITE_TEXTO : LIMITE_TEXTO_SIMPLES)
const totalVariacoes = computed(() => {
  const n = (d.value.variants || []).filter((v) => (v || '').trim()).length
  return n ? `${n + 1} mensagens no rodízio` : 'sempre a mesma mensagem'
})
const cor = computed(() => corDe(props.node.type))
const suave = computed(() => suaveDe(props.node.type))

// Adicionar botão não cria outro passo: transforma esta mensagem numa mensagem com
// botões. Tirar o último botão desfaz. Quem edita nunca escolhe "tipo de nó".
function addBotao() {
  const bs = (d.value.buttons ||= [])
  if (bs.length >= MAX_BOTOES) return
  bs.push({ title: '', type: 'url', url: '', key: '' })
  props.node.type = 'buttons'
}

function removeBotao(i) {
  d.value.buttons.splice(i, 1)
  if (!d.value.buttons.length) props.node.type = 'text'
}
function addOpcao() {
  ;(d.value.options ||= []).length < 13 && d.value.options.push({ title: '', key: '' })
}
function addAcao() {
  ;(d.value.actions ||= []).push({ action: 'add_tag', tag: '' })
}
function addCard() {
  ;(d.value.elements ||= []).push({ title: '', image_url: '', subtitle: '', url: '' })
}
const camposVariacao = ref([])

// templates aprovados, pro nó Template WhatsApp. Instância sem WA (ou sem a rota)
// fica com a lista vazia.
const templatesWa = ref([])
onMounted(async () => {
  if (props.node.type !== 'template_wa') return
  try {
    const r = await fetch('/api/wa/templates?aprovados=1')
    templatesWa.value = r.ok ? await r.json() : []
  } catch { templatesWa.value = [] }
})
const marcaVariavel = (v) => `{${'{'}${v}}${'}'}`
const templateAtual = computed(() => templatesWa.value.find((t) => t.nome === d.value.template))
function escolheTemplate() {
  const t = templateAtual.value
  d.value.idioma = t?.idioma || 'pt_BR'
  d.value.botoes = [...(t?.botoes || [])]
  d.value.variaveis = Object.fromEntries((t?.variaveis || []).map((v) => [v, d.value.variaveis?.[v] || '']))
}

// o cursor vai pro campo novo. Sem isso o foco fica no botão, e quem digita direto
// depois de clicar acaba apertando o botão de novo a cada espaço: uma variação vazia
// atrás da outra, sem entender de onde vieram.
async function addVariacao() {
  ;(d.value.variants ||= []).push('')
  d.value.rotacao ||= 'rodizio'
  await nextTick()
  camposVariacao.value[d.value.variants.length - 1]?.focus()
}
</script>

<template>
  <aside class="painel">
    <header>
      <span class="chip" :style="{ background: suave, color: cor }">
        <Icone :nome="node.type" :tamanho="13" />{{ meta.rotulo }}
      </span>
      <button class="x" @click="emit('fechar')" aria-label="fechar"><Icone nome="fechar" :tamanho="16" /></button>
    </header>

    <div class="corpo">
      <!-- MENSAGEM (com ou sem botões: é o mesmo passo) -->
      <template v-if="['text', 'buttons'].includes(node.type)">
        <label>Mensagem
          <textarea v-cresce v-model="d.text" rows="6"
                    placeholder="Oi {username}! Aqui está o que prometi:"></textarea>
        </label>
        <p class="conta" :class="{ estourou: (d.text || '').length > limiteTexto }">
          {{ (d.text || '').length }}/{{ limiteTexto }}
          <span v-if="(d.text || '').length > limiteTexto">
            o que passar disso vai numa mensagem separada
          </span>
        </p>
        <p class="dica">Para chamar a pessoa pelo nome use
          <code>{primeiro_nome}</code>: ele tira o cargo e o emoji que o pessoal
          coloca no nome do Instagram e deixa só o primeiro nome, caindo no @ quando
          não há nome. Também existem <code>{username}</code> (o @),
          <code>{name}</code> (o nome inteiro, do jeito que está) e qualquer campo
          que você tenha guardado antes, como <code>{email}</code>.</p>
        <label>Link <span class="sub">opcional</span>
          <input v-model="d.link" placeholder="https://" />
        </label>
        <p class="dica">Se o texto não tiver <code>{link}</code>, ele entra numa linha no fim.</p>

        <h2>Botões <span class="sub">até {{ MAX_BOTOES }}, opcional</span></h2>
        <div v-for="(b, i) in d.buttons || []" :key="i" class="item">
          <input v-model="b.title" placeholder="Texto do botão" :maxlength="MAX_BOTAO" />
          <p class="conta" :class="{ estourou: (b.title || '').length >= MAX_BOTAO }">
            {{ (b.title || '').length }}/{{ MAX_BOTAO }} caracteres
          </p>
          <select v-model="b.type">
            <option value="url">abre um link</option>
            <option value="postback">continua o fluxo</option>
          </select>
          <input v-if="b.type === 'url'" v-model="b.url" placeholder="https://" />
          <input v-else v-model="b.key" placeholder="apelido da saída, ex: sou_aluna" />
          <button class="perigo" @click="removeBotao(i)">remover</button>
        </div>
        <button class="add" @click="addBotao" :disabled="(d.buttons || []).length >= MAX_BOTOES">
          adicionar botão
        </button>
        <p class="dica">Botão que <b>continua o fluxo</b> ganha uma saída própria no card,
          pra você ligar no passo seguinte. Botão de link encerra o caminho ali.
          <b>O botão só aparece no app do celular</b>: quem abrir o direct pelo computador
          vê a mensagem sem ele, então vale deixar o link no texto também.</p>
      </template>

      <!-- OPÇÕES RÁPIDAS -->
      <template v-else-if="node.type === 'quick_replies'">
        <label>Pergunta
          <textarea v-cresce v-model="d.text" rows="4"></textarea>
        </label>
        <h2>Opções <span class="sub">até 13</span></h2>
        <div v-for="(o, i) in d.options || []" :key="i" class="item linha">
          <input v-model="o.title" placeholder="Texto" maxlength="20" />
          <input v-model="o.key" placeholder="apelido" />
          <button class="perigo" @click="d.options.splice(i, 1)">remover</button>
        </div>
        <button class="add" @click="addOpcao">adicionar opção</button>
      </template>

      <!-- MÍDIA -->
      <template v-else-if="node.type === 'media'">
        <label>Tipo
          <select v-model="d.kind">
            <option value="image">imagem</option>
            <option value="video">vídeo</option>
            <option value="audio">áudio</option>
          </select>
        </label>
        <label>Endereço do arquivo
          <input v-model="d.url" placeholder="https://" />
        </label>
        <p class="dica">Precisa ser um endereço público: quem baixa o arquivo é a Meta.</p>
        <details>
          <summary>Ou monte um carrossel</summary>
          <div v-for="(e, i) in d.elements || []" :key="i" class="item">
            <input v-model="e.title" placeholder="Título do cartão" />
            <input v-model="e.image_url" placeholder="Imagem" />
            <input v-model="e.subtitle" placeholder="Subtítulo" />
            <input v-model="e.url" placeholder="Link ao tocar" />
            <button class="perigo" @click="d.elements.splice(i, 1)">remover</button>
          </div>
          <button class="add" @click="addCard">adicionar cartão</button>
        </details>
      </template>

      <!-- IA -->
      <template v-else-if="node.type === 'ai'">
        <label>Instrução pra IA
          <textarea v-cresce v-model="d.prompt" rows="7"
                    placeholder="Responda com simpatia à dúvida: {texto_recebido}"></textarea>
        </label>
        <label>Se a IA falhar, responder
          <input v-model="d.fallback" placeholder="Já te respondo por aqui" />
        </label>
        <p class="dica">Precisa da variável <code>AI_API_KEY</code> configurada no
          <code>.env</code> da instância.</p>
      </template>

      <!-- ESPERAR -->
      <template v-else-if="node.type === 'delay'">
        <label>Esperar antes do próximo passo
          <div class="linha">
            <input class="curto" type="number" min="0" v-model.number="d.minutes" />
            <span class="unid">minutos</span>
          </div>
        </label>
        <p class="dica">O Instagram só deixa responder por <b>24h</b> depois da última
          interação da pessoa. Espera longa demais e a mensagem não sai.</p>
      </template>

      <!-- AGENDAR -->
      <template v-else-if="node.type === 'schedule'">
        <label>Continuar em <span class="sub">data e hora, em UTC</span>
          <input v-model="d.run_at" placeholder="2026-08-01T14:00:00Z" />
        </label>
      </template>

      <!-- ESPERAR RESPOSTA -->
      <template v-else-if="node.type === 'wait_input'">
        <label>O que você espera receber
          <select v-model="d.expects">
            <option value="texto">qualquer texto</option>
            <option value="email">um e-mail</option>
            <option value="telefone">um telefone</option>
          </select>
        </label>
        <label>Guardar como
          <input v-model="d.save_as" placeholder="email" />
        </label>
        <p class="dica">Depois é só chamar de
          <code>{{ '{' + (d.save_as || 'campo') + '}' }}</code> nas mensagens seguintes.</p>
        <label>Se vier errado, responder
          <input v-model="d.retry_text" placeholder="Esse e-mail não parece certo, tenta de novo" />
        </label>
        <label>Desistir depois de <span class="sub">minutos; 0 nunca desiste</span>
          <input type="number" min="0" v-model.number="d.timeout_minutes"
                 @change="d.timeout_seconds = (d.timeout_minutes || 0) * 60" />
        </label>
      </template>

      <!-- CONDIÇÃO -->
      <template v-else-if="node.type === 'condition'">
        <label>Verificar se a pessoa
          <select v-model="d.check">
            <option value="tem_tag">tem a marcação</option>
            <option value="campo_preenchido">tem o campo preenchido</option>
            <option value="campo_igual">tem o campo igual a</option>
            <option value="e_seguidor">segue a conta</option>
          </select>
        </label>
        <label v-if="d.check === 'campo_igual'">Campo
          <input v-model="d.field" placeholder="email" />
        </label>
        <label v-if="d.check !== 'e_seguidor'">Valor
          <input v-model="d.value" list="tags-existentes" placeholder="ex: aluna" />
        </label>
        <datalist id="tags-existentes">
          <option v-for="t in tags" :key="t.tag" :value="t.tag" />
        </datalist>
      </template>

      <!-- TESTE A/B -->
      <template v-else-if="node.type === 'split'">
        <label>Quanto vai pelo caminho A
          <div class="linha">
            <input class="curto" type="number" min="0" max="100" v-model.number="d.percent_a" />
            <span class="unid">%   o resto segue pelo B</span>
          </div>
        </label>
      </template>

      <!-- AÇÃO -->
      <template v-else-if="node.type === 'action'">
        <h2>O que fazer nos bastidores</h2>
        <div v-for="(a, i) in d.actions || []" :key="i" class="item">
          <select v-model="a.action">
            <option value="add_tag">marcar a pessoa</option>
            <option value="remove_tag">tirar a marcação</option>
            <option value="set_field">guardar um valor</option>
          </select>
          <input v-if="a.action !== 'set_field'" v-model="a.tag" list="tags-existentes"
                 placeholder="nome da marcação" />
          <template v-else>
            <input v-model="a.key" placeholder="nome do campo" />
            <input v-model="a.value" placeholder="valor" />
          </template>
          <button class="perigo" @click="d.actions.splice(i, 1)">remover</button>
        </div>
        <datalist id="tags-existentes">
          <option v-for="t in tags" :key="t.tag" :value="t.tag" />
        </datalist>
        <button class="add" @click="addAcao">adicionar ação</button>
      </template>

      <!-- WEBHOOK -->
      <template v-else-if="node.type === 'webhook'">
        <label>Endereço
          <input v-model="d.url" placeholder="https://seu-n8n/webhook/..." />
        </label>
        <p class="dica">Mandamos quem é a pessoa e o que ela respondeu. Se voltar um JSON,
          os campos dele viram <code>{chave}</code> nas mensagens seguintes.</p>
      </template>

      <!-- PEDIR WHATSAPP: ponte do direct pro WhatsApp -->
      <template v-else-if="node.type === 'pedir_whatsapp'">
        <label>Pedido
          <textarea v-cresce v-model="d.text" rows="3"
                    placeholder="Me passa seu WhatsApp com DDD que eu te mando por lá?"></textarea>
        </label>
        <label>Consentimento <span class="sub">vai junto, logo abaixo do pedido</span>
          <textarea v-cresce v-model="d.consentimento" rows="3"
                    placeholder="Ao enviar seu número, você aceita receber nossas mensagens no WhatsApp. Pra parar, é só mandar SAIR."></textarea>
        </label>
        <p class="dica">Quem manda o número depois deste aviso entra como contato com
          consentimento (opt-in). O número fica no campo <code>{whatsapp}</code>.</p>
        <label>Se o número vier errado
          <input v-model="d.retry_text"
                 placeholder="Não consegui entender esse número. Manda de novo com DDD, só os números?" />
        </label>
        <label>Prazo pra responder <span class="sub">em minutos, opcional</span>
          <input type="number" min="0" :value="Math.round((d.timeout_seconds || 0) / 60)"
                 @input="d.timeout_seconds = Number($event.target.value || 0) * 60" />
        </label>
      </template>

      <!-- TEMPLATE WHATSAPP: abre (ou reabre) a conversa no WhatsApp -->
      <template v-else-if="node.type === 'template_wa'">
        <label>Template aprovado
          <select v-model="d.template" @change="escolheTemplate">
            <option value="">escolha</option>
            <option v-for="t in templatesWa" :key="t.nome + t.idioma" :value="t.nome">
              {{ t.nome }} ({{ t.idioma }})
            </option>
          </select>
        </label>
        <p v-if="!templatesWa.length" class="dica">Nenhum template aprovado ainda. Crie ou
          sincronize em <a href="/templates" target="_blank">Templates</a>; quem aprova é a Meta.</p>
        <p v-if="templateAtual" class="dica">{{ templateAtual.corpo }}</p>
        <template v-if="d.variaveis">
          <label v-for="v in (templateAtual?.variaveis || [])" :key="v">
            Variável <code>{{ marcaVariavel(v) }}</code>
            <input v-model="d.variaveis[v]" placeholder="{primeiro_nome}" />
          </label>
        </template>
        <p class="dica">Template não depende da janela de 24h. Quem pediu SAIR não recebe:
          o fluxo segue pela saída "não enviou".</p>
        <label>Prazo pra responder <span class="sub">em minutos, opcional</span>
          <input type="number" min="0" :value="Math.round((d.timeout_seconds || 0) / 60)"
                 @input="d.timeout_seconds = Number($event.target.value || 0) * 60" />
        </label>
      </template>

      <!-- JANELA DE 24H: saída alternativa pros nós de mensagem livre -->
      <label v-if="NOS_COM_JANELA.includes(node.type)" class="caixa">
        <input type="checkbox" v-model="d.desvio_janela" />
        Se a janela de 24h estiver fechada, seguir por outro caminho
      </label>

      <!-- VARIAÇÕES: vale pros três nós que mandam texto -->
      <template v-if="['text', 'buttons', 'quick_replies'].includes(node.type)">
        <h2>Variações <span class="sub">{{ totalVariacoes }}</span></h2>
        <p class="dica">A mensagem acima é a primeira variação. A cada envio sai uma
          diferente, então duas pessoas que comentam seguido não recebem o texto
          idêntico. É justamente o texto repetido que a Meta usa pra reconhecer
          automação.</p>
        <div v-for="(v, i) in d.variants || []" :key="i" class="item">
          <textarea v-cresce v-model="d.variants[i]" rows="3" ref="camposVariacao"
                    :placeholder="`Variação ${i + 2}`"></textarea>
          <button class="perigo" @click="d.variants.splice(i, 1)">remover</button>
        </div>
        <button class="add" @click="addVariacao">adicionar variação</button>
        <label v-if="(d.variants || []).length">Ordem
          <select v-model="d.rotacao">
            <option value="rodizio">rodízio: uma depois da outra, na ordem</option>
            <option value="aleatorio">aleatória: sorteia a cada envio</option>
          </select>
        </label>
      </template>
    </div>

    <footer>
      <button class="quieto largo" @click="emit('apagar', node.id)">Apagar este passo</button>
    </footer>
  </aside>
</template>

<style scoped>
.caixa { display: flex; flex-direction: row; align-items: center; gap: 8px; }
.caixa input { width: auto; }
.painel {
  width: 336px; flex: none; background: var(--panel); border-left: 1px solid var(--line);
  display: flex; flex-direction: column; height: 100%;
  animation: entra .16s ease;
}
@keyframes entra { from { opacity: 0; transform: translateX(10px) } to { opacity: 1 } }
header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 13px 16px; border-bottom: 1px solid var(--line);
}
.chip {
  display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px;
  border-radius: 999px; font-size: 10.5px; font-weight: 600;
  text-transform: uppercase; letter-spacing: .06em;
}
.x { background: none; color: var(--mut); font-size: 15px; padding: 2px 6px; }
.corpo { padding: 16px; overflow-y: auto; flex: 1; }

label { display: block; font-size: 12px; font-weight: 600; margin-top: 16px; }
label:first-child, .corpo > h2:first-child { margin-top: 0; }
h2 { margin: 18px 0 8px; }
input, textarea, select {
  width: 100%; padding: 9px 11px; border: 1px solid var(--line); border-radius: 8px;
  font: inherit; font-size: 13px; margin-top: 5px; background: var(--panel); color: var(--ink);
}
textarea { resize: vertical; line-height: 1.5; }
input:focus, textarea:focus, select:focus {
  outline: 2px solid var(--accent); outline-offset: -1px; border-color: transparent;
}
.linha { display: flex; gap: 8px; align-items: center; }
.curto { width: 90px; }
.unid { font-size: 12px; color: var(--mut); white-space: nowrap; margin-top: 5px; }
.conta {
  font-size: 11px; color: var(--mut); margin: 4px 0 0;
  font-family: var(--mono); font-variant-numeric: tabular-nums;
}
.conta.estourou { color: var(--err); font-family: inherit; }
.dica { font-size: 12px; color: var(--mut); margin: 6px 0 0; line-height: 1.5; }
code {
  font-family: var(--mono); font-size: .88em; background: var(--bg);
  padding: 1px 5px; border-radius: 4px;
}
.item {
  border: 1px solid var(--line); border-radius: 9px; padding: 10px;
  margin-bottom: 8px; display: grid; gap: 6px; background: var(--bg);
}
.item input, .item select { margin-top: 0; background: var(--panel); }
.item .perigo { justify-self: end; }
.add {
  width: 100%; background: var(--panel); border: 1px dashed #cfcfd8; color: var(--mut);
  font-weight: 500; font-size: 12.5px; padding: 8px; border-radius: 8px;
}
.add:hover { border-color: var(--accent); color: var(--accent); opacity: 1; }
.add:disabled { opacity: .45; }
details summary {
  font-size: 12.5px; color: var(--mut); cursor: pointer; margin: 18px 0 8px;
}
footer { padding: 14px 16px; border-top: 1px solid var(--line); }
.largo { width: 100%; }
</style>

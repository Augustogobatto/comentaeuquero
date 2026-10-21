<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import Icone from './Icone.vue'
import { TIPOS, NOMES_GATILHO, corDe, suaveDe, saidasDe } from './tipos'

const props = defineProps({ id: String, type: String, data: Object, selected: Boolean })

const meta = computed(() => TIPOS[props.type] || { rotulo: props.type })
const cor = computed(() => corDe(props.type))
const suave = computed(() => suaveDe(props.type))
const saidas = computed(() => saidasDe({ type: props.type, data: props.data }))
// Mostrar a mensagem quase inteira no card, e não um pedaço de duas linhas: quem
// olha o fluxo quer reconhecer a mensagem sem precisar abrir o passo.
const LIMITE_RESUMO = 260
const resumo = computed(() => {
  const t = meta.value.resumo ? meta.value.resumo(props.data || {}) : ''
  return t.length > LIMITE_RESUMO ? t.slice(0, LIMITE_RESUMO) + '…' : t
})
const botoes = computed(() => (props.data?.buttons || []).filter((b) => b.title || b.url))
const vazio = computed(() => !meta.value.resumo?.(props.data || {}))
</script>

<template>
  <div class="ficha" :class="{ sel: selected, entrada: type === 'gatilho' }">
    <!-- o gatilho é o começo: nada aponta pra ele, então não tem pino de entrada -->
    <Handle v-if="type !== 'gatilho'" type="target" :position="Position.Left" class="pino" />

    <div class="chip" :style="{ background: suave, color: cor }">
      <Icone :nome="type" :tamanho="12" />{{ meta.rotulo }}
    </div>
    <!-- o gatilho lista uma linha por entrada, com a palavra-chave destacada e o
         desligado apagado. Texto corrido virava um bloco ilegível com 4 ou 5 -->
    <div v-if="type === 'gatilho'" class="gatilhos">
      <div v-for="(g, i) in data?.triggers || []" :key="i"
           class="gat" :class="{ off: !g.active }">
        <span class="gat-nome">{{ NOMES_GATILHO[g.type] || g.type }}</span>
        <span v-for="k in g.keywords || []" :key="k" class="gat-kw">{{ k }}</span>
        <span v-if="!(g.keywords || []).length" class="gat-kw solto">qualquer texto</span>
        <span v-if="!g.active" class="gat-off">desligado</span>
      </div>
      <div v-if="!(data?.triggers || []).length" class="corpo vazio">
        sem gatilho, este fluxo não começa sozinho
      </div>
    </div>

    <div v-else class="corpo" :class="{ vazio }">{{ resumo }}</div>

    <!-- botões desenhados como a pessoa vai ver no direct -->
    <div v-if="botoes.length" class="botoes">
      <div v-for="(b, i) in botoes" :key="i" class="botao">{{ b.title || 'sem texto' }}</div>
    </div>

    <!-- saída única: pino discreto na borda -->
    <Handle v-if="!saidas.length" type="source" :position="Position.Right" class="pino" />

    <!-- saídas nomeadas viram linhas no rodapé, abaixo do texto, pra nunca cobrir
         o conteúdo da mensagem -->
    <div v-else class="saidas">
      <div v-for="(s, i) in saidas" :key="s.id || i" class="saida">
        <span class="saida-rot">{{ s.rotulo || 'sem nome' }}</span>
        <Handle type="source" :id="s.id" :position="Position.Right" class="pino pino-saida" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.ficha {
  background: var(--fundo); border: 1px solid var(--line); border-radius: 8px;
  min-width: 200px; max-width: 244px; position: relative;
  box-shadow: 0 1px 2px rgba(10, 10, 10, .04);
  transition: box-shadow .15s ease, transform .15s ease, border-color .15s ease;
}
.ficha:hover { border-color: color-mix(in srgb, var(--texto) 25%, var(--linha)); box-shadow: 0 4px 16px rgba(10, 10, 10, .08); }
.ficha.sel { border-color: var(--accent); box-shadow: 0 0 0 3px var(--acento-25); }
/* o começo do fluxo se distingue pelo filete, não por um canto redondo gigante:
   com quatro ou cinco gatilhos o raio de 999px passava por cima do texto */
.ficha.entrada { min-width: 232px; max-width: 288px; }

.gatilhos { padding: 8px 12px 11px; display: grid; gap: 6px; }
.gat {
  display: flex; align-items: center; flex-wrap: wrap; gap: 4px;
  font-size: 12px; line-height: 1.35;
}
.gat + .gat { border-top: 1px solid var(--line); padding-top: 6px; }
.gat-nome { color: var(--ink); }
.gat-kw {
  background: var(--texto-6); color: var(--texto); border-radius: 999px;
  padding: 1px 7px; font-size: 11px; font-weight: 500;
}
.gat-kw.solto { background: none; color: var(--mut); font-weight: 400; font-style: italic; }
.gat.off { opacity: .45; }
.gat-off {
  font-size: 10px; text-transform: uppercase; letter-spacing: .05em;
  color: var(--mut); border: 1px solid var(--line); border-radius: 4px; padding: 0 4px;
}

.chip {
  display: inline-flex; align-items: center; gap: 5px; margin: 10px 12px 0;
  padding: 3px 8px 3px 6px; border-radius: 999px;
  font-size: 11px; font-weight: 500;
}
.corpo {
  padding: 7px 12px 11px; font-size: 12.5px; line-height: 1.45; color: var(--ink);
  white-space: pre-wrap; word-break: break-word;
}
.corpo.vazio { color: var(--mut); font-style: italic; }

.botoes { padding: 0 12px 11px; display: grid; gap: 5px; }
.botao {
  border: 1px solid var(--line); border-radius: 6px; padding: 5px 8px;
  font-size: 12px; font-weight: 500; text-align: center; color: var(--texto);
  background: var(--fundo); white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis;
}

.saidas { border-top: 1px solid var(--line); }
.saida {
  position: relative; display: flex; justify-content: flex-end; align-items: center;
  padding: 6px 14px 6px 12px; border-bottom: 1px solid var(--line);
}
.saida:last-child { border-bottom: none; border-radius: 0 0 8px 8px; }
.saida-rot {
  font-size: 11px; color: var(--mut);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.pino {
  width: 9px; height: 9px; background: var(--fundo); border: 1.5px solid var(--mut);
  transition: border-color .12s ease, transform .12s ease;
}
.pino:hover { border-color: var(--accent); transform: scale(1.25); }
.pino-saida { top: 50% !important; right: -5px !important; }
</style>

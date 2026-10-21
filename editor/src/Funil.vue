<script setup>
import { computed } from 'vue'

const props = defineProps({ dados: Object, periodo: String })
const emit = defineEmits(['periodo'])

const d = computed(() => props.dados || {})
const base = computed(() => d.value.acionaram || 1)

const etapas = computed(() => [
  { chave: 'acionaram', rotulo: 'acionaram', valor: d.value.acionaram || 0 },
  { chave: 'receberam', rotulo: 'receberam', valor: d.value.entregues || 0 },
  { chave: 'leram', rotulo: 'leram', valor: d.value.leram || 0 },
  { chave: 'avançaram', rotulo: 'avançaram', valor: d.value.avancaram || 0 },
])

// o topo mostra a etapa mais funda com dado: sem isso um fluxo que só entregou
// (leitura e avanço ainda em zero) apareceria com 0% e pareceria quebrado
const hero = computed(() => {
  const x = d.value
  if (x.avancaram) return { n: pct(x.avancaram, base.value), rot: 'chegaram ao fim' }
  if (x.leram) return { n: pct(x.leram, base.value), rot: 'leram a mensagem' }
  return { n: pct(x.entregues || 0, base.value), rot: 'receberam a mensagem' }
})

function pct(parte, todo) {
  return todo ? Math.round((parte / todo) * 100) : 0
}
</script>

<template>
  <div class="metrica">
    <div class="topo-m">
      <div class="seg">
        <button v-for="p in ['7', '30', 'tudo']" :key="p"
                :class="{ on: periodo === p }" @click="emit('periodo', p)">
          {{ p === 'tudo' ? 'tudo' : p + ' dias' }}
        </button>
      </div>
      <div class="hero">
        <span class="hero-num">{{ hero.n }}<i>%</i></span>
        <span class="hero-rot">{{ hero.rot }}</span>
      </div>
    </div>

    <div class="funil">
      <div v-for="(e, i) in etapas" :key="e.chave" class="etapa">
        <span class="et-nome">{{ e.rotulo }}</span>
        <div class="trilho">
          <div class="preenche" :class="'s' + i"
               :style="{ width: (e.valor / base * 100) + '%' }"></div>
        </div>
        <span class="et-num">{{ e.valor }}</span>
        <span class="et-taxa">
          <template v-if="i === 0"><i>base</i></template>
          <template v-else>{{ pct(e.valor, etapas[i - 1].valor) }}%</template>
        </span>
      </div>
    </div>

    <p class="pe">
      {{ d.mensagens || 0 }} mensagem{{ (d.mensagens !== 1) ? 's' : '' }}
      entregue{{ (d.mensagens !== 1) ? 's' : '' }} no total.
      <template v-if="!d.avancaram">Botão de link não conta como avanço: a Meta não
      reporta o clique, meça pelo UTM no destino.</template>
      <span class="cinza">Leram depende do aviso de leitura do Instagram.</span>
    </p>
  </div>
</template>

<style scoped>
.metrica { max-width: 620px; margin: 24px auto; padding: 0 24px; }

.topo-m { display: flex; align-items: flex-end; justify-content: space-between;
          gap: 20px; margin-bottom: 26px; }
.seg { display: inline-flex; background: var(--texto-4); border: 1px solid var(--line);
       border-radius: 6px; padding: 2px; gap: 2px; }
.seg button { height: 28px; font-size: 13px; font-weight: 500; color: var(--mut); background: none;
              border: none; cursor: pointer; padding: 0 12px; border-radius: 4px; margin: 0; }
.seg button:hover { color: var(--ink); }
.seg button.on { background: var(--fundo); color: var(--ink);
                 box-shadow: 0 1px 2px rgba(10,10,10,.08); }

.hero { text-align: right; line-height: 1; }
.hero-num { font-size: 2rem; font-weight: 500;
            letter-spacing: -.03em; color: var(--ink); font-variant-numeric: tabular-nums; }
.hero-num i { font-size: 1rem; font-style: normal; color: var(--mut); margin-left: 1px; }
.hero-rot { display: block; font-size: 13px; font-weight: 500; color: var(--mut); margin-top: 6px; }

.funil { display: grid; gap: 9px; }
.etapa { display: grid; grid-template-columns: 84px 1fr auto auto; align-items: center; gap: 12px; }
.et-nome { font-size: 13px; color: var(--mut); font-weight: 500; }
.trilho { height: 30px; background: var(--texto-4); border-radius: 6px; overflow: hidden; }
.preenche { height: 100%; border-radius: 6px; min-width: 2px; transform-origin: left;
            animation: cresce .5s cubic-bezier(.2,.7,.3,1) backwards; }
@keyframes cresce { from { transform: scaleX(0); } }
.preenche.s0 { background: var(--texto); }
.preenche.s1 { background: color-mix(in srgb, var(--texto) 75%, transparent); }
.preenche.s2 { background: color-mix(in srgb, var(--texto) 50%, transparent); animation-delay: .06s; }
.preenche.s3 { background: color-mix(in srgb, var(--texto) 30%, transparent); animation-delay: .12s; }
.et-num { font-size: 14px; font-weight: 500;
          font-variant-numeric: tabular-nums; color: var(--ink); min-width: 30px; text-align: right; }
.et-taxa { font-size: 12px; color: var(--mut);
           font-variant-numeric: tabular-nums; min-width: 42px; text-align: right; }
.et-taxa i { font-style: normal; text-transform: uppercase; letter-spacing: .05em;
             font-family: var(--sans); font-size: 10px; }

.pe { font-size: 11.5px; color: var(--mut); line-height: 1.6; margin: 22px 0 0;
      padding-top: 16px; border-top: 1px solid var(--line); }
.pe .cinza { color: var(--suave); opacity: .7; }
</style>

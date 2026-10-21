<script setup>
// Ligação com botão de apagar. O Vue Flow desenha a linha dentro de um SVG, onde
// não cabe um <button>: o botão vai no EdgeLabelRenderer, que é uma camada HTML
// por cima do canvas — por isso ele precisa de pointer-events próprio.
import { computed } from 'vue'
import { BaseEdge, EdgeLabelRenderer, getBezierPath } from '@vue-flow/core'

const props = defineProps({
  id: { type: String, required: true },
  sourceX: Number, sourceY: Number, targetX: Number, targetY: Number,
  sourcePosition: String, targetPosition: String,
  markerEnd: String,
  style: { type: Object, default: () => ({}) },
  selected: Boolean,
  // aceso pelo hover na linha (o App avisa) ou pelo hover no próprio botão
  destaque: Boolean,
  // a ligação do gatilho é estrutural: ela vira o entry_node no banco, e apagar
  // não some com nada — o servidor recalcula a entrada sozinho. Some o botão.
  fixa: Boolean,
})
const emit = defineEmits(['apagar', 'entrou', 'saiu'])

const curva = computed(() => getBezierPath({
  sourceX: props.sourceX, sourceY: props.sourceY, sourcePosition: props.sourcePosition,
  targetX: props.targetX, targetY: props.targetY, targetPosition: props.targetPosition,
}))
</script>

<template>
  <BaseEdge :id="id" :path="curva[0]" :marker-end="markerEnd" :style="style" />
  <EdgeLabelRenderer>
    <button v-if="!fixa && (destaque || selected)" class="tira-ligacao"
            :style="{ transform: `translate(-50%,-50%) translate(${curva[1]}px,${curva[2]}px)` }"
            title="Apagar esta ligação"
            @mouseenter="emit('entrou')" @mouseleave="emit('saiu')"
            @click.stop="emit('apagar')">
      <svg viewBox="0 0 24 24" width="11" height="11" aria-hidden="true">
        <path d="M5 5l14 14M19 5L5 19" fill="none" stroke="currentColor"
              stroke-width="3" stroke-linecap="round" />
      </svg>
    </button>
  </EdgeLabelRenderer>
</template>

<style>
/* O SVG das linhas fica por cima da camada de rótulos: sem isto o clique no botão
   era comido pela faixa de interação da própria linha (.vue-flow__edge-interaction),
   que tem 20px de largura invisível. O botão aparecia, acendia no hover e não
   apagava nada. As linhas do Vue Flow chegam a z-index 1001, daí o 1002. */
.vue-flow__edge-labels { z-index: 1002; }

.tira-ligacao {
  position: absolute; pointer-events: all; z-index: 1002;
  width: 20px; height: 20px; padding: 0; border-radius: 50%;
  display: grid; place-items: center; cursor: pointer;
  background: var(--fundo, #fff); color: var(--suave, #6b6b6b);
  border: 1px solid var(--line, #e6e6e6);
  box-shadow: 0 1px 3px rgba(17, 17, 19, .14);
  animation: pisca-ligacao .12s ease;
}
.tira-ligacao:hover { color: #fff; background: var(--err, #b91c1c); border-color: var(--err, #b91c1c); }
@keyframes pisca-ligacao { from { opacity: 0; transform: scale(.7); } }
</style>

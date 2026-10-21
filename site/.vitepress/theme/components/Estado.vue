<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ v: 'planejado' | 'andamento' | 'feito' }>()
const texto = computed(
  () => ({ planejado: 'Planejado', andamento: 'Em andamento', feito: 'Feito' })[props.v],
)
</script>

<template>
  <span class="ceq-estado" :class="`ceq-estado--${v}`">{{ texto }}</span>
</template>

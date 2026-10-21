<script setup lang="ts">
import { icones } from './icones'
defineProps<{ nome: string }>()
</script>

<template>
  <svg class="ceq-icone" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path v-for="(d, i) in icones[nome]" :key="i" :d="d" />
  </svg>
</template>

<style>
.ceq-icone {
  width: 24px;
  height: 24px;
  flex: none;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.6;
  stroke-linecap: round;
  stroke-linejoin: round;
}
</style>

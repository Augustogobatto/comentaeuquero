<script setup lang="ts">
// Marca o lugar de um print da Meta que ainda não foi tirado.
// Uso no markdown: <!-- PRINT: descrição --> seguido de <Print>descrição</Print>
</script>

<template>
  <figure class="ceq-print" role="note">
    <span class="ceq-print__rotulo">Imagem em breve</span>
    <figcaption class="ceq-print__texto"><slot /></figcaption>
  </figure>
</template>

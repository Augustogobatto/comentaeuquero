<script setup>
// Conjunto próprio de ícones, todos na mesma grade de 24, traço 1.6, sem preenchimento,
// herdando a cor de quem os usa. Desenhados aqui em vez de virem de biblioteca pra
// não arrastar dependência por doze glifos.
const props = defineProps({ nome: String, tamanho: { type: Number, default: 16 } })

const FORMAS = {
  // começo: seta entrando no fluxo
  gatilho: 'M3 12h9M8.5 8.5 12 12l-3.5 3.5M14.5 4.5a1.5 1.5 0 0 1 1.5-1.5h3.5a1.5 1.5 0 0 1 1.5 1.5v15a1.5 1.5 0 0 1-1.5 1.5H16a1.5 1.5 0 0 1-1.5-1.5',
  // conversa
  text: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z',
  buttons: 'M4 4.5h16a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-13a1 1 0 0 1 1-1z',
  buttons2: 'M6.5 13.8h11v3.2h-11z',
  quick_replies: 'M13 2 4 14h7l-1 8 9-12h-7z',
  media: 'M4 4h16v16H4zM9 10a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0M20 15l-4.5-4.5L6 20',
  // ponte pro WhatsApp: balão com telefone / balão com linhas de modelo
  pedir_whatsapp: 'M21 11.5a8.5 8.5 0 0 1-12.6 7.4L3 21l2.1-5.4A8.5 8.5 0 1 1 21 11.5zM9.5 8.5c0 3.3 2.7 6 6 6l1-1.5-2-1-1 1a3 3 0 0 1-2.5-2.5l1-1-1-2z',
  template_wa: 'M21 11.5a8.5 8.5 0 0 1-12.6 7.4L3 21l2.1-5.4A8.5 8.5 0 1 1 21 11.5zM8.5 9.5h7M8.5 13h5',
  ai: 'M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM18.5 16.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z',
  // tempo
  delay: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7.5V12l3 2',
  schedule: 'M8 3v3.5M16 3v3.5M3.5 10h17M5 5h14a1.5 1.5 0 0 1 1.5 1.5v13A1.5 1.5 0 0 1 19 21H5a1.5 1.5 0 0 1-1.5-1.5v-13A1.5 1.5 0 0 1 5 5z',
  wait_input: 'M12 4.5v15M8.5 4.5h7M8.5 19.5h7M3.5 8.5V6a1.5 1.5 0 0 1 1.5-1.5M20.5 8.5V6A1.5 1.5 0 0 0 19 4.5M3.5 15.5V18A1.5 1.5 0 0 0 5 19.5M20.5 15.5V18a1.5 1.5 0 0 1-1.5 1.5',
  // caminhos
  condition: 'M6 20V9a3 3 0 0 1 3-3h9M6 20a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM6 7a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM18 7.5 20.5 6 18 4.5',
  split: 'M4 7h4l8 10h4M4 17h4l2-2.5M14 9.5l2-2.5h4M20.5 4.5 22 7l-1.5 2.5M20.5 14.5 22 17l-1.5 2.5',
  // bastidores
  action: 'M20.3 13.1 13.1 20.3a1.6 1.6 0 0 1-2.2 0l-7.2-7.2A1.6 1.6 0 0 1 3.2 12V4.8c0-.9.7-1.6 1.6-1.6H12c.4 0 .8.2 1.1.5l7.2 7.2a1.6 1.6 0 0 1 0 2.2zM7.8 7.8h.01',
  webhook: 'M10 13.5a4 4 0 0 0 6 .5l2.5-2.5a4 4 0 0 0-5.7-5.7L11.5 7',
  webhook2: 'M14 10.5a4 4 0 0 0-6-.5l-2.5 2.5a4 4 0 0 0 5.7 5.7L12.5 17',
  // interface
  fechar: 'M18 6 6 18M6 6l12 12',
  voltar: 'M19 12H5M11 18l-6-6 6-6',
  mais: 'M12 5v14M5 12h14',
}

// alguns ícones precisam de dois traços independentes
const SEGUNDO = { webhook: 'webhook2', buttons: 'buttons2' }
</script>

<template>
  <svg :width="tamanho" :height="tamanho" viewBox="0 0 24 24" fill="none"
       stroke="currentColor" stroke-width="1.6" stroke-linecap="round"
       stroke-linejoin="round" aria-hidden="true" class="icone">
    <path :d="FORMAS[nome] || FORMAS.text" />
    <path v-if="SEGUNDO[nome]" :d="FORMAS[SEGUNDO[nome]]" />
  </svg>
</template>

<style scoped>
.icone { display: block; flex: none; }
</style>

<script setup lang="ts">
import { icones } from './icones'
import Icone from './Icone.vue'

// Desenho do fluxo em coordenadas do viewBox (largura útil ~1110).
// Nó quadrado: 72x72. Linha principal em y=200.
const Y = 200

const nos = [
  { id: 'gatilho', x: 110, y: Y, icone: 'comentario', rotulo: ['Comentou', '“EU QUERO”'], forma: 'gatilho' },
  { id: 'espera', x: 300, y: 92, icone: 'relogio', rotulo: ['Espera 2 min'] },
  { id: 'pede', x: 790, y: Y, icone: 'pedir', rotulo: ['Pediu o WhatsApp'] },
  { id: 'template', x: 970, y: Y, icone: 'template', rotulo: ['Template no', 'WhatsApp'] },
]

// conectores principais, na ordem em que acendem
const linhas = [
  'M146 200 C 205 200, 205 92, 264 92',
  'M336 92 C 378 92, 378 200, 420 200',
  'M640 200 H 754',
  'M826 200 H 934',
  'M1006 200 H 1080',
]

const subs = [
  { x: 330, icone: 'etiqueta', rotulo: 'Etiqueta: lead', d: 'M455 242 C 455 296, 330 286, 330 318' },
  { x: 530, icone: 'ia', rotulo: 'IA responde dúvida', d: 'M530 242 V 318' },
  { x: 730, icone: 'banco', rotulo: 'Salva no SQLite', d: 'M605 242 C 605 296, 730 286, 730 318' },
]

const portas = [
  [146, 200, 0],
  [264, 92, 1],
  [336, 92, 1],
  [420, 200, 2],
  [640, 200, 3],
  [754, 200, 3],
  [826, 200, 4],
  [934, 200, 4],
  [1006, 200, 5],
]

function iconeEm(x: number, y: number, tam = 28) {
  const s = tam / 24
  return `translate(${x - tam / 2} ${y - tam / 2}) scale(${s})`
}

const passosV = [
  { icone: 'comentario', rotulo: 'Comentou “EU QUERO”', tipo: 'Gatilho' },
  { icone: 'relogio', rotulo: 'Espera 2 min', tipo: 'Tempo' },
  { icone: 'direct', rotulo: 'Manda o link no direct', tipo: 'Instagram', subs: true },
  { icone: 'pedir', rotulo: 'Pediu o WhatsApp', tipo: 'Instagram' },
  { icone: 'template', rotulo: 'Template no WhatsApp', tipo: 'WhatsApp' },
]
</script>

<template>
  <figure class="ceq-fluxo">
    <figcaption class="ceq-sr">
      Exemplo de fluxo: a pessoa comenta “EU QUERO”, o fluxo espera 2 minutos, manda o link no
      direct (marca a etiqueta lead, deixa a IA responder dúvidas e salva tudo no SQLite), pede o
      WhatsApp e envia um template no WhatsApp.
    </figcaption>

    <!-- desktop: fluxo horizontal -->
    <svg
      class="ceq-fluxo__h"
      viewBox="20 30 1110 400"
      aria-hidden="true"
      focusable="false"
      preserveAspectRatio="xMidYMid meet"
    >
      <!-- ramificações tracejadas para os sub-nós -->
      <g class="f-ramos">
        <path v-for="s in subs" :key="s.x" :d="s.d" class="f-ramo" />
      </g>

      <!-- conectores: base cinza + traço aceso por cima -->
      <g>
        <path v-for="(d, i) in linhas" :key="'b' + i" :d="d" class="f-linha" />
        <path
          v-for="(d, i) in linhas"
          :key="'a' + i"
          :d="d"
          pathLength="1"
          class="f-aceso"
          :style="{ '--d': i * 0.32 + 0.35 + 's' }"
        />
      </g>

      <!-- nó gatilho (lado esquerdo arredondado) -->
      <path
        class="f-no"
        d="M110 164 H136 Q146 164 146 174 V226 Q146 236 136 236 H110 A36 36 0 0 1 110 164 Z"
      />
      <g class="f-ic" :transform="iconeEm(112, 200)">
        <path v-for="(d, i) in icones.comentario" :key="i" :d="d" />
      </g>

      <!-- nós quadrados -->
      <template v-for="n in nos.slice(1)" :key="n.id">
        <rect class="f-no" :x="n.x - 36" :y="n.y - 36" width="72" height="72" rx="12" />
        <g class="f-ic" :transform="iconeEm(n.x, n.y)">
          <path v-for="(d, i) in icones[n.icone]" :key="i" :d="d" />
        </g>
      </template>

      <!-- nó largo: manda o link no direct -->
      <rect class="f-no" x="420" y="164" width="220" height="72" rx="12" />
      <g class="f-ic" :transform="iconeEm(456, 200, 26)">
        <path v-for="(d, i) in icones.direct" :key="i" :d="d" />
      </g>
      <text class="f-dentro" x="486" y="195">Manda o link</text>
      <text class="f-dentro" x="486" y="215">no direct</text>
      <path v-for="x in [455, 530, 605]" :key="'dm' + x" class="f-losango" :d="`M${x} 236 l6 6 -6 6 -6 -6z`" />

      <!-- sub-nós redondos -->
      <template v-for="s in subs" :key="'s' + s.x">
        <circle class="f-no" :cx="s.x" cy="350" r="32" />
        <g class="f-ic" :transform="iconeEm(s.x, 350, 24)">
          <path v-for="(d, i) in icones[s.icone]" :key="i" :d="d" />
        </g>
        <text class="f-rotulo" :x="s.x" y="406" text-anchor="middle">{{ s.rotulo }}</text>
      </template>

      <!-- portas -->
      <circle
        v-for="(p, i) in portas"
        :key="'p' + i"
        :cx="p[0]"
        :cy="p[1]"
        r="4.5"
        class="f-porta"
        :style="{ '--d': p[2] * 0.32 + 0.35 + 's' }"
      />

      <!-- rótulos humanos embaixo dos nós -->
      <template v-for="n in nos" :key="'r' + n.id">
        <text class="f-rotulo" :x="n.x" :y="n.y + 62" text-anchor="middle">
          <tspan v-for="(l, i) in n.rotulo" :key="i" :x="n.x" :dy="i === 0 ? 0 : 19">{{ l }}</tspan>
        </text>
      </template>

      <!-- botão + no fim -->
      <rect class="f-mais" x="1080" y="186" width="28" height="28" rx="6" />
      <path class="f-mais-ic" d="M1094 193 V207 M1087 200 H1101" />
    </svg>

    <!-- celular: o mesmo fluxo na vertical -->
    <ol class="ceq-fluxo__v" aria-hidden="true">
      <li v-for="(p, i) in passosV" :key="p.rotulo" :style="{ '--i': i }">
        <span class="v-no" :class="{ 'v-no--gatilho': i === 0 }"><Icone :nome="p.icone" /></span>
        <span class="v-texto">
          <span class="ceq-rotulo v-tipo">{{ p.tipo }}</span>
          <span class="v-rotulo">{{ p.rotulo }}</span>
          <span v-if="p.subs" class="v-subs">
            <span v-for="s in subs" :key="s.rotulo" class="v-sub">
              <span class="v-sub-no"><Icone :nome="s.icone" /></span>{{ s.rotulo }}
            </span>
          </span>
        </span>
      </li>
      <li class="v-fim" :style="{ '--i': 5 }"><span class="v-mais"><Icone nome="mais" /></span></li>
    </ol>
  </figure>
</template>

<style>
.ceq-sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
.ceq-fluxo {
  position: relative;
  margin: 0 auto;
  width: 100%;
  max-width: 1160px;
}
.ceq-fluxo__h {
  display: block;
  width: 100%;
  height: auto;
  overflow: visible;
}
.ceq-fluxo .f-no {
  fill: var(--ceq-soft-2);
  stroke: var(--ceq-line);
  stroke-width: 1;
}
.dark .ceq-fluxo .f-no {
  fill: var(--ceq-soft);
  stroke: var(--ceq-line);
}
.ceq-fluxo .f-ic {
  fill: none;
  stroke: var(--ceq-ink);
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.ceq-fluxo .f-linha {
  fill: none;
  stroke: var(--ceq-border);
  stroke-width: 1.5;
}
.ceq-fluxo .f-aceso {
  fill: none;
  stroke: var(--ceq-acc-line);
  stroke-width: 2;
  stroke-linecap: round;
  stroke-dasharray: 1;
  stroke-dashoffset: 0;
}
.ceq-fluxo .f-ramo {
  fill: none;
  stroke: var(--ceq-border);
  stroke-width: 1.4;
  stroke-dasharray: 5 5;
}
.ceq-fluxo .f-losango {
  fill: var(--ceq-ink-3);
}
.ceq-fluxo .f-porta {
  fill: var(--ceq-acc-line);
  stroke: var(--ceq-paper);
  stroke-width: 2;
}
.ceq-fluxo .f-rotulo {
  font-family: var(--ceq-sans);
  font-size: 14.5px;
  fill: var(--ceq-ink-2);
}
.ceq-fluxo .f-dentro {
  font-family: var(--ceq-sans);
  font-size: 15px;
  font-weight: 520;
  fill: var(--ceq-ink);
}
.ceq-fluxo .f-mais {
  fill: var(--ceq-ink);
}
.ceq-fluxo .f-mais-ic {
  fill: none;
  stroke: var(--ceq-paper);
  stroke-width: 1.8;
  stroke-linecap: round;
}

/* uma animação só: os conectores acendem em sequência na carga */
@media (prefers-reduced-motion: no-preference) {
  .ceq-fluxo .f-aceso {
    animation: ceq-acende 0.5s cubic-bezier(0.22, 1, 0.36, 1) var(--d) both;
  }
  .ceq-fluxo .f-porta {
    animation: ceq-porta 0.3s ease-out var(--d) both;
  }
  .ceq-fluxo .f-ramos {
    animation: ceq-aparece 0.6s ease-out 1.1s both;
  }
  .ceq-fluxo__v li::after {
    animation: ceq-desce 0.45s cubic-bezier(0.22, 1, 0.36, 1) calc(var(--i) * 0.28s + 0.3s) both;
  }
}
@keyframes ceq-acende {
  from {
    stroke-dashoffset: 1;
  }
  to {
    stroke-dashoffset: 0;
  }
}
@keyframes ceq-porta {
  from {
    fill: var(--ceq-border);
  }
  to {
    fill: var(--ceq-acc-line);
  }
}
@keyframes ceq-aparece {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
@keyframes ceq-desce {
  from {
    transform: scaleY(0);
  }
  to {
    transform: scaleY(1);
  }
}

/* ---- vertical ---- */
.ceq-fluxo__v {
  display: none;
  margin: 0 auto;
  padding: 0;
  max-width: 360px;
  list-style: none;
}
.ceq-fluxo__v li {
  position: relative;
  display: grid;
  grid-template-columns: 56px 1fr;
  column-gap: 16px;
  align-items: start;
  padding-bottom: 28px;
}
/* conector até o próximo nó: base + aceso */
.ceq-fluxo__v li::before,
.ceq-fluxo__v li::after {
  content: '';
  position: absolute;
  left: 27px;
  top: 56px;
  bottom: 0;
  width: 2px;
}
.ceq-fluxo__v li::before {
  background: var(--ceq-border);
  width: 1.5px;
}
.ceq-fluxo__v li::after {
  background: var(--ceq-acc-line);
  transform-origin: top;
}
.ceq-fluxo__v li.v-fim {
  padding-bottom: 0;
}
.ceq-fluxo__v li.v-fim::before,
.ceq-fluxo__v li.v-fim::after {
  display: none;
}
.v-no {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  border-radius: 12px;
  background: var(--ceq-soft-2);
  box-shadow: inset 0 0 0 1px var(--ceq-line);
  color: var(--ceq-ink);
}
.dark .v-no,
.dark .v-sub-no {
  background: var(--ceq-soft);
}
.v-no--gatilho {
  border-radius: 28px 12px 12px 28px;
}
.v-texto {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: 7px;
}
.v-tipo {
  color: var(--ceq-ink-3);
  font-size: 11px;
}
.v-rotulo {
  font-size: 16.5px;
  line-height: 1.35;
  color: var(--ceq-ink);
}
.v-subs {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
  padding: 12px 0 0 12px;
  border-left: 1px dashed var(--ceq-border);
}
.v-sub {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14.5px;
  color: var(--ceq-ink-2);
}
.v-sub-no {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--ceq-soft-2);
  box-shadow: inset 0 0 0 1px var(--ceq-line);
  color: var(--ceq-ink);
}
.v-sub-no .ceq-icone {
  width: 18px;
  height: 18px;
}
.v-fim {
  grid-template-columns: 56px;
}
.v-mais {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  margin-left: 14px;
  border-radius: 6px;
  background: var(--ceq-ink);
  color: var(--ceq-paper);
}
.v-mais .ceq-icone {
  width: 16px;
  height: 16px;
}

@media (max-width: 899px) {
  .ceq-fluxo__h {
    display: none;
  }
  .ceq-fluxo__v {
    display: block;
  }
}
</style>

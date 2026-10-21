<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { withBase } from 'vitepress'
import HomeFluxo from './HomeFluxo.vue'
import Icone from './Icone.vue'

const REPO = 'https://github.com/Augustogobatto/comentaeuquero'
const INSTA = 'https://www.instagram.com/augustogobatto/'
const CLUB = 'https://ia.augustogobatto.com/club'
const comando =
  'docker run -d -p 127.0.0.1:8080:8080 -v ceq_data:/data ghcr.io/augustogobatto/comentaeuquero:estavel'

/* ---------- copiar comando ---------- */
const copiado = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined
async function copiar() {
  try {
    await navigator.clipboard.writeText(comando)
    copiado.value = true
    clearTimeout(timer)
    timer = setTimeout(() => (copiado.value = false), 1800)
  } catch {
    // sem permissão de área de transferência: o texto continua selecionável
  }
}

/* ---------- o que roda ---------- */
const roda = [
  { rotulo: 'Seu servidor', texto: 'Uma VPS de R$ 20 a R$ 30 por mês, ou o seu computador. Leads e credenciais ficam num SQLite que é seu.' },
  { rotulo: 'API oficial da Meta', texto: 'Com um app seu na Meta. Nada de extensão, senha do Instagram ou automação de navegador.' },
  { rotulo: 'Sem limite de contatos', texto: 'O preço não sobe quando a lista cresce. 500 ou 50 mil leads custam o mesmo servidor.' },
  { rotulo: 'Código aberto', texto: 'Dá pra ler, auditar e mudar. Licença de uso sustentável: livre para o seu negócio.' },
]

/* ---------- casos de uso ---------- */
const casos = [
  {
    id: 'lancamento',
    aba: 'Infoprodutor, lançamento',
    titulo: 'Cada comentário vira inscrito na aula',
    texto:
      'Quem comenta AULA recebe o link de inscrição no direct e ganha a etiqueta do lançamento. Na véspera, um template no WhatsApp lembra o horário.',
    tutorial: '/tutoriais/primeiro-fluxo',
    passos: [
      { icone: 'comentario', rotulo: 'Comentou “AULA”', tipo: 'Gatilho' },
      { icone: 'direct', rotulo: 'Link de inscrição', tipo: 'Mensagem' },
      { icone: 'etiqueta', rotulo: 'Etiqueta: lançamento', tipo: 'Ação' },
      { icone: 'template', rotulo: 'Lembrete da aula', tipo: 'WhatsApp' },
    ],
  },
  {
    id: 'cupom',
    aba: 'Loja, cupom',
    titulo: 'O cupom chega antes da vontade passar',
    texto:
      'Quem comenta CUPOM escolhe o tamanho em botões e recebe o código com o link do produto. O tamanho fica salvo no lead para a próxima campanha.',
    tutorial: '/tutoriais/etiquetas-e-campos',
    passos: [
      { icone: 'comentario', rotulo: 'Comentou “CUPOM”', tipo: 'Gatilho' },
      { icone: 'botoes', rotulo: 'Qual o seu tamanho?', tipo: 'Botões' },
      { icone: 'cupom', rotulo: 'Cupom + link', tipo: 'Mensagem' },
      { icone: 'campo', rotulo: 'Campo: tamanho', tipo: 'Ação' },
    ],
  },
  {
    id: 'isca',
    aba: 'Criador, isca digital',
    titulo: 'O guia em troca do e-mail, sem formulário',
    texto:
      'Quem responde o story com GUIA recebe um pedido de e-mail no direct. O e-mail vai para um campo do lead e o link do guia sai na mensagem seguinte.',
    tutorial: '/tutoriais/story-e-live',
    passos: [
      { icone: 'story', rotulo: 'Respondeu o story', tipo: 'Gatilho' },
      { icone: 'arroba', rotulo: 'Qual o seu e-mail?', tipo: 'Esperar resposta' },
      { icone: 'campo', rotulo: 'Campo: e-mail', tipo: 'Ação' },
      { icone: 'link', rotulo: 'Link do guia', tipo: 'Mensagem' },
    ],
  },
  {
    id: 'agenda',
    aba: 'Serviço, agenda',
    titulo: 'Tira a dúvida e já entrega a agenda',
    texto:
      'Quem pergunta o preço no direct recebe a resposta da IA, escrita a partir do que você contou sobre o serviço, e o link para marcar horário. Quem preferir segue no WhatsApp.',
    tutorial: '/tutoriais/ia-no-fluxo',
    passos: [
      { icone: 'direct', rotulo: 'Mandou “PREÇO”', tipo: 'Gatilho' },
      { icone: 'ia', rotulo: 'IA responde', tipo: 'Resposta com IA' },
      { icone: 'agenda', rotulo: 'Link da agenda', tipo: 'Mensagem' },
      { icone: 'pedir', rotulo: 'Pediu o WhatsApp', tipo: 'WhatsApp' },
    ],
  },
]
const ativo = ref(casos[0].id)
const pronto = ref(false) // sem JS: todos os casos aparecem empilhados
onMounted(() => (pronto.value = true))

function escolher(id: string, e: Event) {
  e.preventDefault()
  ativo.value = id
}
function teclado(e: KeyboardEvent, i: number) {
  const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
  if (!d) return
  e.preventDefault()
  const n = (i + d + casos.length) % casos.length
  ativo.value = casos[n].id
  const el = document.getElementById(`aba-${casos[n].id}`)
  el?.focus()
}

/* ---------- linha do tempo ---------- */
const linha = [
  { hora: '21:03:00', texto: 'Ana comenta “EU QUERO” no seu Reel.', tag: 'Comentário' },
  { hora: '21:03:01', texto: 'O comentário dela ganha a resposta pública: “Te mandei no direct”.', tag: 'Resposta' },
  { hora: '21:03:03', texto: 'Chega no direct da Ana a mensagem com o botão “Quero o material”.', tag: 'Instagram' },
  { hora: '21:05:12', texto: 'Ana toca no botão. Ela ganha a etiqueta lead e recebe o link.', tag: 'Etiqueta' },
  { hora: '21:05:40', texto: 'O fluxo pede o WhatsApp. Ana manda o número e aceita receber mensagens.', tag: 'Consentimento' },
  { hora: 'Dia seguinte, 10:00', texto: 'Sai o template no WhatsApp com o link da aula. Ela responde e a conversa continua lá.', tag: 'WhatsApp' },
]
/* ---------- prova: números e comentários reais ----------
   Fonte: banco do CEQ da conta @augustogobatto (20/07 a 21/10/2026) e Graph API do
   Instagram (comentários públicos e a resposta pública que o CEQ deixou). Usuário
   anonimizado: primeira letra + ***** + última. Horário de Brasília. */
const numeros = [
  { valor: '3.600+', rotulo: 'Pessoas atendidas', nota: '3.652 leads' },
  { valor: '7.300+', rotulo: 'Mensagens no direct', nota: '7.331 enviadas' },
  { valor: '71%', rotulo: 'Lidas', nota: '5.203 de 7.331' },
  { valor: '3.600+', rotulo: 'Cliques em botão', nota: '3.632 cliques' },
]
const thread = [
  { u: 'w*****s', c: 'Jev', post: 'Reel 01/10', quando: '08/10 08:01', r: 'chegou aí no teu direct!', seg: 9 },
  { u: 'u*****s', c: 'Sistema', post: 'Reel 04/09', quando: '06/09 03:51', r: 'chegou ai no teu direct!', seg: 8 },
  { u: 'b*****o', c: 'Jev', post: 'Reel 01/10', quando: '01/10 20:56', r: 'mandei lá no teu direct 👇', seg: 10 },
  { u: 'j*****o', c: 'sistema', post: 'Reel 30/08', quando: '30/08 22:06', r: 'olha o direct 👀', seg: 8 },
  { u: 'e*****o', c: 'minerador', post: 'Reel 21/08', quando: '22/08 11:45', r: 'chegou ai no teu direct!', seg: 7 },
  { u: 't*****o', c: 'Clube', post: 'Reel 16/09', quando: '16/09 16:17', r: 'te mandei no direct 🤝', seg: 11 },
  { u: 'n*****a', c: 'Jev', post: 'Reel 01/10', quando: '03/10 15:15', r: 'chegou aí no teu direct!', seg: 10 },
  { u: 'o*****a', c: 'Sistema', post: 'Reel 28/08', quando: '29/08 02:28', r: 'chegou ai no teu direct!', seg: 9 },
]
/* movimento: só com JS e sem prefers-reduced-motion; sem isso fica tudo à mostra */
const provaEl = ref<HTMLElement | null>(null)
const provaAnima = ref(false)
const provaVisto = ref(false)
onMounted(() => {
  const el = provaEl.value
  if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  if (!('IntersectionObserver' in window)) return
  const r = el.getBoundingClientRect()
  if (r.top < window.innerHeight * 0.85) return // já está na tela: não esconde nada
  provaAnima.value = true
  const io = new IntersectionObserver(
    (es) => {
      if (es.some((e) => e.isIntersecting)) {
        provaVisto.value = true
        io.disconnect()
      }
    },
    { rootMargin: '0px 0px -20% 0px' },
  )
  io.observe(el)
})
</script>

<template>
  <div class="ceq-home">
    <!-- ================= hero ================= -->
    <section class="h-hero" aria-labelledby="h-titulo">
      <a class="h-selo ceq-rotulo" :href="REPO" target="_blank" rel="noopener">
        <span class="h-selo__ponto" aria-hidden="true" />Open source · código no GitHub
      </a>
      <p class="h-nome">Comenta <strong>EU QUERO</strong> e receba a DM.</p>
      <h1 id="h-titulo" class="h-titulo">
        <span>Quem comenta, recebe.</span>
        <span>No direct e no WhatsApp.</span>
      </h1>
      <p class="h-sub">
        <span>Automação de Instagram e WhatsApp que roda no seu servidor.</span>
        <span>Código aberto, pela API oficial da Meta, sem limite de contatos.</span>
      </p>
      <div class="h-acoes">
        <a class="h-btn h-btn--acc" :href="withBase('/instalar/')">Instalar</a>
        <a class="h-btn" :href="REPO" target="_blank" rel="noopener">Ver no GitHub</a>
      </div>
      <HomeFluxo class="h-fluxo" />
    </section>

    <!-- ================= o que roda ================= -->
    <section class="h-roda" aria-label="Como funciona">
      <span class="h-cruz h-cruz--a" aria-hidden="true" />
      <span class="h-cruz h-cruz--b" aria-hidden="true" />
      <span class="h-cruz h-cruz--c" aria-hidden="true" />
      <span class="h-cruz h-cruz--d" aria-hidden="true" />
      <dl class="h-roda__lista">
        <div v-for="r in roda" :key="r.rotulo" class="h-roda__item">
          <dt class="ceq-rotulo">{{ r.rotulo }}</dt>
          <dd>{{ r.texto }}</dd>
        </div>
      </dl>
    </section>

    <!-- ================= prova ================= -->
    <section
      ref="provaEl"
      class="h-prova"
      :class="{ 'is-anima': provaAnima, 'is-visto': provaVisto }"
      aria-labelledby="h-prova-t"
    >
      <div class="h-prova__cab">
        <span class="ceq-rotulo h-autor__rot">Rodando de verdade</span>
        <h2 id="h-prova-t" class="h-h2">Na conta de quem fez, desde julho</h2>
        <p class="h-lead">
          O CEQ responde os comentários do @augustogobatto. Os números saem do banco dele e os
          comentários aqui são reais, com o nome escondido.
        </p>
        <dl class="h-prova__nums">
          <div v-for="n in numeros" :key="n.rotulo" class="h-prova__num">
            <dt class="ceq-rotulo">{{ n.rotulo }}</dt>
            <dd>
              <span class="h-prova__valor">{{ n.valor }}</span>
              <span class="h-prova__nota ceq-rotulo">{{ n.nota }}</span>
            </dd>
          </div>
        </dl>
        <p class="h-prova__fonte">
          Fonte: banco do CEQ na conta @augustogobatto, de 20 de julho a 21 de outubro de 2026.
          Comentários públicos de reels da conta, lidos pela API do Instagram; horário de Brasília.
        </p>
      </div>

      <div class="h-prova__quadro">
        <div class="h-thread__cab">
          <span class="ceq-rotulo">Comentários</span>
          <span class="ceq-rotulo h-thread__cab-n">3.569 respondidos no período</span>
        </div>
        <ol class="h-thread">
          <li
            v-for="(t, i) in thread"
            :key="t.u + t.quando"
            class="h-thread__item"
            :style="{ '--i': i }"
          >
            <div class="h-com">
              <span class="h-com__av" aria-hidden="true">{{ t.u[0].toUpperCase() }}</span>
              <div class="h-com__corpo">
                <p class="h-com__linha">
                  <span class="h-com__user">@{{ t.u }}</span>
                  <span class="h-com__txt">{{ t.c }}</span>
                </p>
                <p class="h-com__meta ceq-rotulo">{{ t.post }} · {{ t.quando }}</p>
              </div>
            </div>
            <div class="h-com h-com--resp">
              <span class="h-com__av h-com__av--conta" aria-hidden="true">A</span>
              <div class="h-com__corpo">
                <p class="h-com__linha">
                  <span class="h-com__user">@augustogobatto</span>
                  <span class="h-com__txt">{{ t.r }}</span>
                </p>
                <p class="h-com__meta ceq-rotulo">Resposta pública · {{ t.seg }} s depois</p>
              </div>
            </div>
          </li>
        </ol>
      </div>
    </section>

    <!-- ================= depoimentos ================= -->
    <section class="h-dep" aria-labelledby="h-dep-t">
      <div class="h-dep__cab">
        <span class="ceq-rotulo h-autor__rot">Do grupo do Push Club</span>
        <h2 id="h-dep-t" class="h-h2">Quem já cancelou o ManyChat</h2>
        <p class="h-dep__nota">
          Mensagens reais de membros no grupo do Club. Sem nome, pra preservar quem escreveu.
        </p>
      </div>
      <div class="h-dep__lista">
        <figure class="h-dep__conversa">
          <figcaption class="ceq-rotulo">Membro do Push Club · 7 de outubro</figcaption>
          <p class="h-dep__balao">Valeu, migrei todos os fluxos pra ele</p>
          <p class="h-dep__balao">Blz, cancelando manychat agora</p>
          <img
            class="h-dep__print"
            :src="withBase('/img/cancelamento-manychat.jpg')"
            alt="Tela de confirmação: você solicitou o cancelamento da assinatura"
            width="720"
            height="383"
            loading="lazy"
          />
          <p class="h-dep__balao">Feito!</p>
          <p class="h-dep__pergunta ceq-rotulo">Quanto pagava no ManyChat?</p>
          <p class="h-dep__balao h-dep__balao--valor">US$ 348/ano</p>
        </figure>
        <figure class="h-dep__conversa">
          <figcaption class="ceq-rotulo">Membro do Push Club · 13 de setembro</figcaption>
          <p class="h-dep__balao">Vou tentar fazer e cancelar meu manychat. Kk</p>
          <p class="h-dep__sep ceq-rotulo">mais tarde, no mesmo dia</p>
          <p class="h-dep__balao h-dep__balao--valor">Economia feita kkk</p>
        </figure>
        <figure class="h-dep__conversa">
          <figcaption class="ceq-rotulo">Membro do Push Club · 18 de outubro</figcaption>
          <p class="h-dep__balao">Aqui usei o MCP do Club e foi bem tranquilo instalar</p>
        </figure>
      </div>
    </section>

    <!-- ================= sem parceiro ================= -->
    <section class="h-meta" aria-labelledby="h-meta-t">
      <div class="h-meta__cab">
        <span class="ceq-rotulo h-autor__rot">Sem intermediário</span>
        <h2 id="h-meta-t" class="h-h2">Por que você não precisa ser parceiro da Meta</h2>
      </div>
      <div class="h-meta__corpo">
        <p>
          O ManyChat e similares são parceiros oficiais da Meta porque rodam <em>um</em> app que
          atende milhões de contas de outras pessoas. Pra isso a Meta exige análise do app,
          verificação da empresa e contrato de parceiro.
        </p>
        <p>
          Aqui é diferente: cada pessoa cria o <strong>próprio app</strong> no painel de
          desenvolvedores da Meta e usa só na <strong>própria conta</strong>. Dono do app usando o
          app na conta que administra não passa por análise nem precisa de selo de parceiro. É a
          mesma API oficial, sem ninguém no meio.
        </p>
        <p>
          No WhatsApp vale o mesmo: a Cloud API é aberta direto pela Meta pra qualquer empresa. Você
          conecta o seu número, paga as mensagens direto pra Meta e não precisa de BSP (provedor
          intermediário) cobrando por cima.
        </p>
        <a class="h-autor__link" :href="withBase('/tutoriais/app-meta')">Ver como criar o app, passo a passo →</a>
      </div>
    </section>

    <!-- ================= casos ================= -->
    <section class="h-casos" :class="{ 'is-pronto': pronto }" aria-labelledby="h-casos-t">
      <h2 id="h-casos-t" class="ceq-sr">Casos de uso</h2>
      <div class="h-abas" role="tablist" aria-label="Casos de uso">
        <a
          v-for="(c, i) in casos"
          :id="`aba-${c.id}`"
          :key="c.id"
          class="h-aba ceq-rotulo"
          :class="{ 'is-ativa': pronto && ativo === c.id }"
          :href="`#caso-${c.id}`"
          role="tab"
          :aria-selected="pronto ? ativo === c.id : undefined"
          :aria-controls="`caso-${c.id}`"
          :tabindex="pronto && ativo !== c.id ? -1 : 0"
          @click="escolher(c.id, $event)"
          @keydown="teclado($event, i)"
          >{{ c.aba }}</a
        >
      </div>

      <div
        v-for="c in casos"
        :id="`caso-${c.id}`"
        :key="c.id"
        class="h-caso"
        role="tabpanel"
        :aria-labelledby="`aba-${c.id}`"
        :hidden="pronto && ativo !== c.id ? true : undefined"
      >
        <div class="h-caso__texto">
          <h3 class="h-caso__titulo">{{ c.titulo }}</h3>
          <p class="h-caso__p">{{ c.texto }}</p>
          <a class="h-caso__link" :href="withBase(c.tutorial)">Ver o tutorial</a>
        </div>
        <div class="h-caso__quadro">
          <ol class="h-mini">
            <li v-for="p in c.passos" :key="p.rotulo" class="h-mini__passo">
              <span class="h-mini__no"><Icone :nome="p.icone" /></span>
              <span class="h-mini__rotulo">{{ p.rotulo }}</span>
              <span class="h-mini__tipo ceq-rotulo">{{ p.tipo }}</span>
            </li>
          </ol>
        </div>
      </div>
    </section>

    <!-- ================= linha do tempo ================= -->
    <section class="h-tempo" aria-labelledby="h-tempo-t">
      <div class="h-tempo__cab">
        <h2 id="h-tempo-t" class="h-h2">Um comentário, do início ao fim</h2>
        <p class="h-lead">
          O que acontece com quem comenta no seu post, segundo a segundo. Você não precisa estar
          online para nada disso.
        </p>
      </div>
      <ol class="h-tempo__lista">
        <li v-for="l in linha" :key="l.hora" class="h-tempo__item">
          <span class="h-tempo__hora ceq-rotulo">{{ l.hora }}</span>
          <span class="h-tempo__ponto" aria-hidden="true" />
          <span class="h-tempo__texto">{{ l.texto }}</span>
          <span class="h-tempo__tag ceq-rotulo">{{ l.tag }}</span>
        </li>
      </ol>
    </section>

    <!-- ================= custo ================= -->
    <section class="h-custo" aria-labelledby="h-custo-t">
      <p id="h-custo-t" class="h-custo__frase">
        Com 10 mil contatos, o ManyChat cobra US$&nbsp;114 por mês. Aqui você paga só o servidor:
        R$&nbsp;20 a R$&nbsp;30.
      </p>
      <a class="h-custo__link" :href="withBase('/faq#quanto-custa-comparado-ao-manychat')"
        >Ver a comparação completa e o custo do WhatsApp</a
      >
    </section>

    <!-- ================= open source ================= -->
    <section class="h-aberto" aria-labelledby="h-aberto-t">
      <h2 id="h-aberto-t" class="h-aberto__titulo">Open source.<br />O código é seu.</h2>
      <p class="h-aberto__texto">
        O comenta EU QUERO é <a href="https://faircode.io" target="_blank" rel="noopener">fair-code</a>,
        distribuído sob a <a :href="withBase('/licenca')">Licença de Uso Sustentável</a>.
      </p>
      <ul class="h-aberto__lista">
        <li><strong>Código aberto:</strong> sempre visível no GitHub, pra ler e auditar</li>
        <li><strong>Self-hosted:</strong> roda onde você quiser, sem pagar nada</li>
        <li><strong>Extensível:</strong> mude, adapte e crie seus próprios fluxos e nós</li>
      </ul>
      <div class="h-acoes h-acoes--esq">
        <a class="h-btn h-btn--acc" :href="REPO" target="_blank" rel="noopener">Ver o código</a>
        <a class="h-btn" :href="withBase('/licenca')">Ler a licença</a>
      </div>
    </section>

    <!-- ================= push club ================= -->
    <section class="h-club" aria-labelledby="h-club-t">
      <div class="h-club__texto">
        <span class="ceq-rotulo h-club__rot">Push Club</span>
        <h2 id="h-club-t" class="h-club__titulo">Não quer instalar sozinho?</h2>
        <p>
          No Push Club tem aula de instalação do zero, fluxos prontos pra importar, o instalador de
          1 comando com atualização automática e um grupo pra tirar dúvida. Além do CEQ, as outras
          ferramentas e aulas de automação com IA que eu uso no meu negócio.
        </p>
        <div class="h-acoes h-acoes--esq">
          <a class="h-btn h-btn--acc" :href="CLUB" target="_blank" rel="noopener">Entrar no Push Club</a>
          <a class="h-btn h-btn--escuro" :href="INSTA" target="_blank" rel="noopener">@augustogobatto</a>
        </div>
      </div>
      <ul class="h-club__lista">
        <li><span class="ceq-rotulo">Aula</span>Instalação do CEQ passo a passo, do app da Meta ao primeiro fluxo</li>
        <li><span class="ceq-rotulo">Fluxos</span>Modelos prontos de lançamento, isca digital e WhatsApp</li>
        <li><span class="ceq-rotulo">Chão</span>Instalador de 1 comando que mantém tudo atualizado</li>
        <li><span class="ceq-rotulo">Grupo</span>Dúvida respondida por quem já rodou</li>
      </ul>
    </section>

    <!-- ================= instalar ================= -->
    <section class="h-instalar" aria-labelledby="h-instalar-t">
      <div class="h-instalar__cab">
        <h2 id="h-instalar-t" class="h-h2">Teste no seu computador</h2>
        <p class="h-lead">
          Precisa do Docker. Rode o comando, abra <code>localhost:8080</code> e crie a senha. Para
          deixar no ar numa VPS, com HTTPS e backup, siga o
          <a :href="withBase('/instalar/')">guia de instalação</a>.
        </p>
      </div>
      <div class="h-cmd">
        <span class="h-cmd__prompt ceq-rotulo" aria-hidden="true">$</span>
        <code class="h-cmd__texto">{{ comando }}</code>
        <button class="h-cmd__copiar ceq-rotulo" type="button" @click="copiar">
          <span aria-live="polite">{{ copiado ? 'Copiado' : 'Copiar' }}</span>
        </button>
      </div>
    </section>

    <!-- ================= autor ================= -->
    <section class="h-autor" aria-label="Quem fez">
      <div class="h-autor__item">
        <span class="ceq-rotulo h-autor__rot">Feito por</span>
        <p>Augusto Gobatto. Mostro no Instagram como monto ferramentas assim com IA.</p>
        <a class="h-autor__link" :href="INSTA" target="_blank" rel="noopener">@augustogobatto no Instagram →</a>
      </div>
      <div class="h-autor__item">
        <span class="ceq-rotulo h-autor__rot">Push Club</span>
        <p>Quer ajuda pra instalar, fluxos prontos e aulas de automação com IA? É no Club.</p>
        <a class="h-autor__link" :href="CLUB" target="_blank" rel="noopener">Conhecer o Push Club →</a>
      </div>
    </section>

    <!-- ================= rodapé ================= -->
    <footer class="h-rodape">
      <nav class="h-rodape__links" aria-label="Links do rodapé">
        <a class="ceq-rotulo" :href="withBase('/tutoriais/')">Docs</a>
        <a class="ceq-rotulo" :href="REPO" target="_blank" rel="noopener">GitHub</a>
        <a class="ceq-rotulo" :href="withBase('/upgrades')">Upgrades</a>
        <a class="ceq-rotulo" :href="withBase('/licenca')">Licença</a>
        <a class="ceq-rotulo" :href="INSTA" target="_blank" rel="noopener">Instagram</a>
        <a class="ceq-rotulo" :href="CLUB" target="_blank" rel="noopener">Push Club</a>
      </nav>
      <p class="h-rodape__nota">
        Código aberto, licença de uso sustentável. © 2026 Augusto Gobatto.
      </p>
    </footer>
  </div>
</template>

<style>
.ceq-home {
  --h-gutter: clamp(16px, 4vw, 48px);
  position: relative;
  color: var(--ceq-ink);
  overflow-x: clip;
}
.ceq-home a:focus-visible,
.ceq-home button:focus-visible {
  outline: 2px solid var(--ceq-ink);
  outline-offset: 3px;
}

/* ---------- hero ---------- */
.h-hero {
  position: relative;
  isolation: isolate;
  padding: clamp(40px, 8vh, 88px) var(--h-gutter) clamp(32px, 6vh, 64px);
  text-align: center;
}
/* grade de pontos forte no hero, sumindo no fim; o resto da página fica com a grade fraca */
.h-hero::before {
  content: '';
  position: absolute;
  z-index: -1;
  inset: calc(var(--vp-nav-height) * -1) 0 0;
  background-image: var(--ceq-dots);
  background-size: 22px 22px;
  -webkit-mask-image: linear-gradient(#000 80%, transparent);
  mask-image: linear-gradient(#000 80%, transparent);
}
.h-titulo {
  margin: 0 auto;
  max-width: 15ch;
  font-size: clamp(40px, 6.6vw, 88px);
  line-height: 1;
  font-weight: 540;
  letter-spacing: -0.035em;
  text-wrap: balance;
}
.h-titulo span,
.h-sub span {
  display: block;
}
@media (min-width: 900px) {
  .h-titulo {
    max-width: none;
  }
}
.h-sub {
  margin: 24px auto 0;
  max-width: 36em;
  font-size: clamp(17px, 1.6vw, 19.5px);
  line-height: 1.45;
  color: var(--ceq-ink-2);
  text-wrap: balance;
}
.h-acoes {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: 32px;
}
.h-btn {
  display: inline-block;
  padding: 0 20px;
  border-radius: 999px;
  background: var(--ceq-soft-2);
  color: var(--ceq-ink);
  font-family: var(--ceq-mono);
  font-size: 13px;
  line-height: 44px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  text-decoration: none;
  transition: background-color 0.15s;
}
.h-btn:hover {
  background: var(--ceq-line);
}
.dark .h-btn:not(.h-btn--acc):hover {
  background: var(--ceq-border);
}
.h-btn--acc {
  background: var(--ceq-acc);
  color: var(--ceq-acc-ink);
}
.h-btn--acc:hover {
  background: var(--ceq-acc-hover);
}
.h-fluxo {
  margin-top: clamp(40px, 7vh, 72px);
}
@media (max-width: 899px) {
  .h-fluxo {
    text-align: left;
  }
}

/* ---------- o que roda ---------- */
.h-roda {
  position: relative;
  margin: clamp(32px, 6vh, 64px) auto 0;
  max-width: 1160px;
  width: calc(100% - 2 * var(--h-gutter));
  border-top: 1px solid var(--ceq-line);
  border-bottom: 1px solid var(--ceq-line);
  background: var(--ceq-paper);
}
.h-cruz {
  position: absolute;
  width: 11px;
  height: 11px;
  background:
    linear-gradient(var(--ceq-ink-3), var(--ceq-ink-3)) center / 11px 1px no-repeat,
    linear-gradient(var(--ceq-ink-3), var(--ceq-ink-3)) center / 1px 11px no-repeat;
}
.h-cruz--a { top: -6px; left: -6px; }
.h-cruz--b { top: -6px; right: -6px; }
.h-cruz--c { bottom: -6px; left: -6px; }
.h-cruz--d { bottom: -6px; right: -6px; }
.h-roda__lista {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  margin: 0;
}
.h-roda__item {
  padding: 24px 24px 28px;
}
.h-roda__item + .h-roda__item {
  box-shadow: -1px 0 0 var(--ceq-line);
}
.h-roda__item dt {
  color: var(--ceq-ink);
}
.h-roda__item dd {
  margin: 10px 0 0;
  font-size: 15px;
  line-height: 1.5;
  color: var(--ceq-ink-2);
}
@media (max-width: 899px) {
  .h-roda__lista {
    grid-template-columns: repeat(2, 1fr);
  }
  .h-roda__item:nth-child(3) {
    box-shadow: 0 -1px 0 var(--ceq-line);
  }
  .h-roda__item:nth-child(4) {
    box-shadow: -1px 0 0 var(--ceq-line), 0 -1px 0 var(--ceq-line);
  }
}
@media (max-width: 559px) {
  .h-roda__lista {
    grid-template-columns: 1fr;
  }
  .h-roda__item {
    padding: 18px 16px 20px;
  }
  .h-roda__item + .h-roda__item,
  .h-roda__item:nth-child(4) {
    box-shadow: 0 -1px 0 var(--ceq-line);
  }
}

/* ---------- casos (bloco escuro) ---------- */
.h-casos {
  margin: clamp(64px, 12vh, 128px) auto 0;
  max-width: 1200px;
  width: calc(100% - 2 * var(--h-gutter));
  padding: clamp(20px, 3vw, 32px);
  border-radius: 28px;
  background: var(--ceq-vault);
  color: var(--ceq-vault-ink);
}
.dark .h-casos {
  box-shadow: inset 0 0 0 1px var(--ceq-line);
}
.h-abas {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.h-casos .h-aba {
  padding: 0 14px;
  border-radius: 999px;
  background: var(--ceq-vault-2);
  color: var(--ceq-vault-ink-2);
  line-height: 34px;
  text-decoration: none;
  transition: background-color 0.15s, color 0.15s;
}
.h-aba:hover {
  background: var(--ceq-vault-3);
  color: var(--ceq-vault-ink);
}
.h-aba.is-ativa {
  background: var(--ceq-acc);
  color: var(--ceq-acc-ink);
}
.h-casos .h-aba:focus-visible,
.h-casos a:focus-visible {
  outline-color: var(--ceq-acc);
}
.h-caso {
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
  gap: clamp(24px, 4vw, 56px);
  margin-top: 28px;
}
.h-casos:not(.is-pronto) .h-caso + .h-caso {
  padding-top: 28px;
  border-top: 1px solid var(--ceq-vault-3);
}
.h-caso[hidden] {
  display: none;
}
.h-caso__texto {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: clamp(8px, 2vw, 24px) 0;
}
.h-caso__titulo {
  margin: 0;
  font-size: clamp(28px, 3.4vw, 42px);
  line-height: 1.08;
  font-weight: 520;
  letter-spacing: -0.028em;
  text-wrap: balance;
}
.h-caso__p {
  margin: 20px 0 0;
  max-width: 42ch;
  font-size: 16.5px;
  line-height: 1.6;
  color: var(--ceq-vault-ink-2);
}
.h-caso__link {
  margin-top: 24px;
  padding-bottom: 3px;
  border-bottom: 1px solid var(--ceq-vault-ink-2);
  color: var(--ceq-vault-ink);
  font-size: 15px;
  text-decoration: none;
}
.h-caso__link:hover {
  border-bottom-color: var(--ceq-acc);
}
.h-caso__quadro {
  display: grid;
  place-items: center;
  min-height: 300px;
  padding: 32px 20px;
  border-radius: 16px;
  background-color: var(--ceq-vault-0);
  background-image: radial-gradient(circle at 1px 1px, var(--ceq-vault-dot) 1px, transparent 1.4px);
  background-size: 18px 18px;
  box-shadow: inset 0 0 0 1px var(--ceq-vault-2);
}
.h-mini {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  width: 100%;
  margin: 0;
  padding: 0;
  list-style: none;
}
.h-mini__passo {
  position: relative;
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  min-width: 0;
  text-align: center;
}
/* conector entre os mini-nós */
.h-mini__passo + .h-mini__passo::before {
  content: '';
  position: absolute;
  top: 30px;
  right: calc(50% + 30px);
  width: calc(100% - 60px);
  height: 1.5px;
  background: var(--ceq-vault-3);
}
.h-mini__passo + .h-mini__passo::after {
  content: '';
  position: absolute;
  top: 27px;
  right: calc(50% + 27px);
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ceq-acc);
}
.h-mini__no {
  display: grid;
  place-items: center;
  width: 60px;
  height: 60px;
  margin-bottom: 6px;
  border-radius: 12px;
  background: var(--ceq-vault-2);
  box-shadow: inset 0 0 0 1px var(--ceq-vault-3);
  color: var(--ceq-vault-ink);
}
.h-mini__passo:first-child .h-mini__no {
  border-radius: 30px 12px 12px 30px;
}
.h-mini__rotulo {
  padding: 0 4px;
  font-size: 14px;
  line-height: 1.3;
  color: var(--ceq-vault-ink);
}
.h-mini__tipo {
  font-size: 10.5px;
  color: var(--ceq-vault-ink-2);
}
@media (max-width: 899px) {
  .h-caso {
    grid-template-columns: 1fr;
    margin-top: 20px;
  }
  .h-caso__quadro {
    min-height: 0;
  }
}
@media (max-width: 559px) {
  .h-casos {
    border-radius: 20px;
  }
  /* abas roláveis numa linha só, como no app */
  .h-abas {
    flex-wrap: nowrap;
    overflow-x: auto;
    margin: 0 calc(clamp(20px, 3vw, 32px) * -1);
    padding: 0 clamp(20px, 3vw, 32px) 4px;
    scrollbar-width: none;
  }
  .h-abas::-webkit-scrollbar {
    display: none;
  }
  .h-casos .h-aba {
    flex: none;
    white-space: nowrap;
  }
  .h-caso__quadro {
    place-items: start;
    padding: 20px 16px;
  }
  .h-mini {
    flex-direction: column;
    gap: 18px;
  }
  .h-mini__passo {
    flex-direction: row;
    gap: 14px;
    text-align: left;
    flex-wrap: wrap;
  }
  .h-mini__no {
    width: 48px;
    height: 48px;
    margin: 0;
  }
  .h-mini__passo:first-child .h-mini__no {
    border-radius: 24px 10px 10px 24px;
  }
  .h-mini__rotulo {
    padding: 0;
  }
  .h-mini__passo > :not(.h-mini__no) {
    flex: 1 1 60%;
  }
  .h-mini__passo {
    display: grid;
    grid-template-columns: 48px 1fr;
    grid-template-rows: auto auto;
    column-gap: 14px;
    row-gap: 2px;
    align-items: center;
  }
  .h-mini__no {
    grid-row: 1 / 3;
  }
  .h-mini__tipo {
    grid-column: 2;
    grid-row: 1;
    align-self: end;
  }
  .h-mini__rotulo {
    grid-column: 2;
    grid-row: 2;
    align-self: start;
  }
  .h-mini__passo + .h-mini__passo::before {
    top: -18px;
    right: auto;
    left: 23px;
    width: 1.5px;
    height: 18px;
  }
  .h-mini__passo + .h-mini__passo::after {
    top: -4px;
    right: auto;
    left: 20px;
  }
}

/* ---------- depoimentos ---------- */
.h-dep {
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 6fr);
  gap: 32px clamp(32px, 5vw, 80px);
  margin: clamp(80px, 12vh, 128px) auto 0;
  max-width: 1160px;
  width: calc(100% - 2 * var(--h-gutter));
}
.h-dep__cab {
  display: grid;
  gap: 12px;
  align-content: start;
}
.h-dep__nota {
  margin: 4px 0 0;
  max-width: 40ch;
  font-size: 15px;
  line-height: 1.55;
  color: var(--ceq-ink-2);
}
.h-dep__lista {
  display: grid;
  gap: 16px;
  min-width: 0;
}
.h-dep__conversa {
  display: grid;
  justify-items: start;
  gap: 8px;
  margin: 0;
  padding: 18px 20px 20px;
  border-radius: 18px;
  background: var(--ceq-soft);
  box-shadow: inset 0 0 0 1px var(--ceq-line);
}
.h-dep__conversa figcaption {
  margin-bottom: 4px;
  color: var(--ceq-ink-3);
}
.h-dep__balao {
  margin: 0;
  max-width: 100%;
  padding: 9px 14px;
  border-radius: 4px 16px 16px 16px;
  background: var(--ceq-paper);
  box-shadow: inset 0 0 0 1px var(--ceq-line);
  font-size: 16px;
  line-height: 1.4;
  color: var(--ceq-ink);
}
.h-dep__balao--valor {
  background: var(--ceq-acc);
  box-shadow: none;
  color: var(--ceq-acc-ink);
  font-weight: 560;
}
.h-dep__pergunta,
.h-dep__sep {
  margin: 6px 0 0;
  color: var(--ceq-ink-3);
}
.h-dep__print {
  display: block;
  width: min(100%, 300px);
  height: auto;
  border-radius: 12px;
  box-shadow: inset 0 0 0 1px var(--ceq-line), 0 1px 0 var(--ceq-line);
  outline: 1px solid var(--ceq-line);
}
@media (max-width: 899px) {
  .h-dep {
    grid-template-columns: minmax(0, 1fr);
  }
}

/* ---------- prova ---------- */
.h-prova {
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 6fr);
  gap: 40px clamp(32px, 5vw, 80px);
  margin: clamp(80px, 12vh, 128px) auto 0;
  max-width: 1160px;
  width: calc(100% - 2 * var(--h-gutter));
}
.h-prova__cab {
  display: grid;
  gap: 12px;
  align-content: start;
  align-self: start;
  position: sticky;
  top: calc(var(--vp-nav-height) + 24px);
}
.h-prova__cab .h-lead {
  margin-top: 4px;
}
.h-prova__nums {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin: 20px 0 0;
  border-top: 1px solid var(--ceq-line);
}
.h-prova__num {
  padding: 18px 16px 18px 0;
  border-bottom: 1px solid var(--ceq-line);
}
.h-prova__num:nth-child(even) {
  padding-left: 20px;
  box-shadow: -1px 0 0 var(--ceq-line);
}
.h-prova__num dt {
  color: var(--ceq-ink-3);
}
.h-prova__num dd {
  display: grid;
  gap: 4px;
  margin: 8px 0 0;
}
.h-prova__valor {
  font-size: clamp(34px, 3.6vw, 48px);
  line-height: 1;
  font-weight: 520;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
}
.h-prova__nota {
  font-size: 11px;
  color: var(--ceq-ink-3);
  text-transform: none;
  letter-spacing: 0.02em;
}
.h-prova__fonte {
  margin: 8px 0 0;
  max-width: 46ch;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ceq-ink-3);
}

/* quadro pontilhado com o mock da thread */
.h-prova__quadro {
  min-width: 0;
  padding: clamp(16px, 2.4vw, 28px);
  border-radius: 20px;
  background-color: var(--ceq-soft);
  background-image: var(--ceq-dots);
  background-size: 18px 18px;
  box-shadow: inset 0 0 0 1px var(--ceq-line);
}
.h-thread__cab {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 4px 16px;
  padding: 0 4px 14px;
  color: var(--ceq-ink);
}
.h-thread__cab-n {
  color: var(--ceq-ink-3);
}
.h-thread {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.h-thread__item {
  display: grid;
  gap: 12px;
  padding: 14px 16px 16px;
  border-radius: 14px;
  background: var(--ceq-paper);
  box-shadow: inset 0 0 0 1px var(--ceq-line);
}
.h-com {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}
.h-com--resp {
  margin-left: 44px;
  grid-template-columns: 26px minmax(0, 1fr);
  gap: 10px;
}
.h-com__av {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--ceq-soft-2);
  color: var(--ceq-ink-2);
  font-family: var(--ceq-mono);
  font-size: 13px;
}
.h-com__av--conta {
  width: 26px;
  height: 26px;
  background: var(--ceq-ink);
  color: var(--ceq-paper);
  font-size: 11px;
}
.h-com__corpo {
  min-width: 0;
}
.h-com__linha {
  margin: 0;
  font-size: 15px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}
.h-com__user {
  margin-right: 6px;
  font-weight: 600;
}
.h-com__txt {
  color: var(--ceq-ink);
}
.h-com__meta {
  margin: 3px 0 0;
  font-size: 10.5px;
  color: var(--ceq-ink-3);
}
.h-com--resp .h-com__linha {
  font-size: 14.5px;
}

/* movimento: o comentário entra, depois a resposta aparece */
@media (prefers-reduced-motion: no-preference) {
  .h-prova.is-anima .h-thread__item,
  .h-prova.is-anima .h-com--resp {
    opacity: 0;
    transform: translateY(8px);
  }
  .h-prova.is-anima.is-visto .h-thread__item,
  .h-prova.is-anima.is-visto .h-com--resp {
    opacity: 1;
    transform: none;
    transition: opacity 0.45s ease-out, transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
  }
  .h-prova.is-anima.is-visto .h-thread__item {
    transition-delay: calc(var(--i) * 140ms);
  }
  .h-prova.is-anima.is-visto .h-com--resp {
    transition-delay: calc(var(--i) * 140ms + 420ms);
  }
}

@media (max-width: 899px) {
  .h-prova {
    grid-template-columns: 1fr;
  }
  .h-prova__cab {
    position: static;
  }
}
@media (max-width: 559px) {
  .h-prova__quadro {
    margin: 0 -4px;
    padding: 14px 12px;
    border-radius: 16px;
  }
  .h-thread__item {
    padding: 12px 12px 14px;
  }
  .h-com--resp {
    margin-left: 22px;
  }
  .h-thread__item:nth-child(n + 7) {
    display: none;
  }
  .h-prova__num {
    padding-right: 10px;
  }
  .h-prova__num:nth-child(even) {
    padding-left: 14px;
  }
}

/* ---------- títulos de seção ---------- */
.h-h2 {
  margin: 0;
  font-size: clamp(30px, 3.6vw, 46px);
  line-height: 1.05;
  font-weight: 540;
  letter-spacing: -0.03em;
  text-wrap: balance;
}
.h-lead {
  margin: 16px 0 0;
  max-width: 44ch;
  font-size: 17px;
  line-height: 1.55;
  color: var(--ceq-ink-2);
}
.h-lead code {
  font-family: var(--ceq-mono);
  font-size: 0.88em;
  color: var(--ceq-ink);
}
.h-lead a,
.h-custo__link {
  color: var(--ceq-ink);
  text-decoration: underline;
  text-decoration-color: var(--ceq-border);
  text-decoration-thickness: 1px;
  text-underline-offset: 4px;
}
.h-lead a:hover,
.h-custo__link:hover {
  text-decoration-color: var(--ceq-ink);
}

/* ---------- linha do tempo ---------- */
.h-tempo {
  display: grid;
  grid-template-columns: minmax(0, 4fr) minmax(0, 7fr);
  gap: clamp(32px, 5vw, 80px);
  margin: clamp(80px, 14vh, 144px) auto 0;
  max-width: 1160px;
  width: calc(100% - 2 * var(--h-gutter));
}
.h-tempo__cab {
  align-self: start;
  position: sticky;
  top: calc(var(--vp-nav-height) + 24px);
}
.h-tempo__lista {
  margin: 0;
  padding: 0;
  list-style: none;
  border-radius: 20px;
  background: var(--ceq-paper);
  box-shadow: 0 0 0 1px var(--ceq-line);
}
.h-tempo__item {
  position: relative;
  display: grid;
  grid-template-columns: 7.5em 14px 1fr auto;
  column-gap: 16px;
  align-items: baseline;
  padding: 20px 24px;
}
.h-tempo__item + .h-tempo__item {
  border-top: 1px solid var(--ceq-line);
}
.h-tempo__hora {
  color: var(--ceq-ink);
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
}
.h-tempo__ponto {
  align-self: center;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  box-shadow: inset 0 0 0 1.5px var(--ceq-ink-3);
}
.h-tempo__item:last-child .h-tempo__ponto {
  background: var(--ceq-acc-line);
  box-shadow: none;
}
.h-tempo__texto {
  font-size: 16px;
  line-height: 1.5;
  color: var(--ceq-ink);
}
.h-tempo .h-tempo__tag {
  padding: 0 8px;
  border-radius: 999px;
  background: var(--ceq-soft);
  color: var(--ceq-ink-3);
  font-size: 10.5px;
  line-height: 22px;
  white-space: nowrap;
}
@media (max-width: 899px) {
  .h-tempo {
    grid-template-columns: 1fr;
  }
  .h-tempo__cab {
    position: static;
  }
}
@media (max-width: 639px) {
  .h-tempo__item {
    grid-template-columns: 14px 1fr;
    grid-template-areas:
      'ponto hora'
      '. texto'
      '. tag';
    row-gap: 6px;
    column-gap: 12px;
    padding: 16px;
  }
  .h-tempo__hora { grid-area: hora; }
  .h-tempo__ponto { grid-area: ponto; }
  .h-tempo__texto { grid-area: texto; }
  .h-tempo__tag { grid-area: tag; justify-self: start; }
}

/* ---------- custo ---------- */
.h-custo {
  margin: clamp(80px, 14vh, 144px) auto 0;
  max-width: 1160px;
  width: calc(100% - 2 * var(--h-gutter));
  padding: clamp(40px, 6vw, 72px) 0;
  border-top: 1px solid var(--ceq-ink);
  border-bottom: 1px solid var(--ceq-line);
}
.h-custo__frase {
  margin: 0;
  max-width: 24ch;
  font-size: clamp(30px, 4.4vw, 58px);
  line-height: 1.06;
  font-weight: 500;
  letter-spacing: -0.032em;
  text-wrap: balance;
}
.h-custo__link {
  display: inline-block;
  margin-top: 24px;
  font-size: 16px;
}

/* ---------- instalar ---------- */
.h-instalar {
  display: grid;
  grid-template-columns: minmax(0, 4fr) minmax(0, 7fr);
  gap: clamp(24px, 5vw, 80px);
  align-items: start;
  margin: clamp(80px, 14vh, 144px) auto 0;
  max-width: 1160px;
  width: calc(100% - 2 * var(--h-gutter));
}
.h-cmd {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 14px;
  align-items: start;
  padding: 18px 16px 18px 20px;
  border-radius: 16px;
  background: var(--ceq-vault);
  color: var(--ceq-vault-ink);
}
.dark .h-cmd {
  box-shadow: inset 0 0 0 1px var(--ceq-line);
}
.h-cmd__prompt {
  color: var(--ceq-acc);
  line-height: 24px;
}
.h-cmd__texto {
  min-width: 0;
  font-family: var(--ceq-mono);
  font-size: 14.5px;
  line-height: 24px;
  color: var(--ceq-vault-ink);
  overflow-wrap: anywhere;
  user-select: all;
}
.h-cmd .h-cmd__copiar {
  padding: 0 14px;
  border: 0;
  border-radius: 999px;
  background: var(--ceq-vault-2);
  color: var(--ceq-vault-ink);
  line-height: 32px;
  cursor: pointer;
  transition: background-color 0.15s;
}
.h-cmd__copiar:hover {
  background: var(--ceq-vault-3);
}
.ceq-home .h-cmd__copiar:focus-visible {
  outline-color: var(--ceq-acc);
}
@media (max-width: 899px) {
  .h-instalar {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 559px) {
  .h-cmd {
    grid-template-columns: auto 1fr;
  }
  .h-cmd__copiar {
    grid-column: 1 / -1;
    justify-self: end;
  }
}

/* ---------- nome ---------- */
.h-nome {
  margin: 0 auto 16px;
  font-size: clamp(20px, 2.4vw, 28px);
  line-height: 1.2;
  letter-spacing: -0.01em;
  color: var(--ceq-ink-2);
}
.h-nome strong {
  color: var(--ceq-ink);
  font-weight: 640;
}

/* ---------- sem parceiro ---------- */
.h-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px 64px;
  margin: clamp(80px, 12vh, 128px) auto 0;
  max-width: 1160px;
  width: calc(100% - 2 * var(--h-gutter));
}
.h-meta__cab {
  display: grid;
  gap: 12px;
  align-content: start;
}
.h-meta__corpo {
  display: grid;
  gap: 16px;
  min-width: 0;
}
.h-meta__corpo p {
  margin: 0;
  max-width: 38em;
  line-height: 1.6;
  color: var(--ceq-ink-2);
}
.h-meta__corpo strong,
.h-meta__corpo em {
  color: var(--ceq-ink);
}

/* ---------- push club ---------- */
.h-club {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 32px 64px;
  align-items: center;
  margin: clamp(80px, 12vh, 128px) auto 0;
  max-width: 1200px;
  width: calc(100% - 2 * var(--h-gutter));
  padding: clamp(28px, 4vw, 56px);
  border-radius: 28px;
  background: var(--ceq-vault);
  color: var(--ceq-vault-ink);
}
.dark .h-club {
  box-shadow: inset 0 0 0 1px var(--ceq-line);
}
.h-club__texto {
  display: grid;
  gap: 16px;
  min-width: 0;
}
.h-club__rot {
  color: var(--ceq-acc);
}
.h-club__titulo {
  margin: 0;
  padding: 0;
  border: 0;
  font-size: clamp(32px, 4.4vw, 56px);
  line-height: 1.02;
  font-weight: 560;
  letter-spacing: -0.03em;
  color: inherit;
}
.h-club__texto p {
  margin: 0;
  max-width: 36em;
  line-height: 1.6;
  opacity: 0.78;
}
.h-btn--escuro {
  background: color-mix(in oklch, var(--ceq-vault-ink) 14%, transparent);
  color: var(--ceq-vault-ink);
}
.h-club__lista {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  min-width: 0;
}
.h-club__lista li {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 16px;
  padding: 16px 0;
  border-top: 1px solid color-mix(in oklch, var(--ceq-vault-ink) 16%, transparent);
  line-height: 1.5;
}
.h-club__lista li:last-child {
  border-bottom: 1px solid color-mix(in oklch, var(--ceq-vault-ink) 16%, transparent);
}
.h-club__lista .ceq-rotulo {
  padding-top: 3px;
  opacity: 0.6;
}

/* ---------- selo open source ---------- */
.h-selo {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 28px;
  padding: 8px 16px;
  border: 1px solid var(--ceq-line);
  border-radius: 999px;
  background: var(--vp-c-bg);
  color: var(--ceq-ink);
  text-decoration: none;
}
.h-selo:hover {
  border-color: var(--ceq-ink-3);
}
.h-selo__ponto {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ceq-acc);
  box-shadow: 0 0 0 3px color-mix(in oklch, var(--ceq-acc) 35%, transparent);
}

/* ---------- open source ---------- */
.h-aberto {
  display: grid;
  gap: 20px;
  margin: clamp(80px, 12vh, 128px) auto 0;
  max-width: 1160px;
  width: calc(100% - 2 * var(--h-gutter));
}
.h-aberto__titulo {
  margin: 0;
  font-size: clamp(48px, 9vw, 120px);
  line-height: 0.95;
  font-weight: 560;
  letter-spacing: -0.04em;
  border: 0;
  padding: 0;
}
.h-aberto__texto {
  margin: 0;
  max-width: 40em;
  font-size: clamp(17px, 1.6vw, 19.5px);
  line-height: 1.5;
  color: var(--ceq-ink-2);
}
.h-aberto__texto a {
  color: var(--ceq-ink);
  text-decoration: underline;
  text-underline-offset: 4px;
}
.h-aberto__lista {
  margin: 0;
  padding-left: 20px;
  display: grid;
  gap: 6px;
  font-size: clamp(16px, 1.4vw, 18px);
  color: var(--ceq-ink-2);
}
.h-aberto__lista strong {
  color: var(--ceq-ink);
}
.h-acoes--esq {
  justify-content: flex-start;
  margin-top: 8px;
}

/* ---------- autor ---------- */
.h-autor {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px 48px;
  margin: clamp(80px, 12vh, 128px) auto 0;
  max-width: 1160px;
  width: calc(100% - 2 * var(--h-gutter));
  padding-top: 32px;
  border-top: 1px solid var(--ceq-line);
}
.h-autor__item {
  display: grid;
  gap: 8px;
  align-content: start;
}
.h-autor__item p {
  margin: 0;
  max-width: 34em;
  color: var(--ceq-ink-2);
}
.h-autor__rot {
  color: var(--ceq-ink-3);
}
.h-autor__link {
  color: var(--ceq-ink);
  font-weight: 560;
  text-decoration: underline;
  text-underline-offset: 5px;
  text-decoration-thickness: 1px;
}

/* ---------- rodapé ---------- */
.h-rodape {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px 32px;
  margin: clamp(96px, 16vh, 160px) auto 0;
  max-width: 1160px;
  width: calc(100% - 2 * var(--h-gutter));
  padding: 28px 0 40px;
  border-top: 1px solid var(--ceq-line);
}
.h-rodape__links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 28px;
}
.h-rodape__links a {
  color: var(--ceq-ink);
  text-decoration: none;
}
.h-rodape__links a:hover {
  text-decoration: underline;
  text-underline-offset: 5px;
}
.h-rodape__nota {
  margin: 0;
  font-size: 14px;
  color: var(--ceq-ink-3);
}
</style>

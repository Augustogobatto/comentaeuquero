// Catálogo dos tipos de nó. É a fonte única: a paleta, a cor do card, o rótulo e
// as saídas de cada nó saem daqui. Somar um tipo novo no motor é somar uma linha
// aqui e um bloco de campos no NodePanel.
//
// Os nós se agrupam em quatro famílias, e a cor vem da família, não do tipo. Doze
// cores soltas viram confete; quatro famílias deixam a leitura do fluxo imediata:
// o que fala com a pessoa, o que espera, o que decide e o que trabalha por trás.

export const FAMILIAS = {
  entrada: { rotulo: 'Começo', cor: '#0f766e', suave: '#ccfbf1' },
  envio: { rotulo: 'Conversa', cor: '#5b3df5', suave: '#f1eefe' },
  tempo: { rotulo: 'Tempo', cor: '#b45309', suave: '#fef3c7' },
  logica: { rotulo: 'Caminhos', cor: '#047857', suave: '#d1fae5' },
  bastidor: { rotulo: 'Bastidores', cor: '#52525b', suave: '#f4f4f5' },
}

// Nomes dos gatilhos, iguais aos do painel e da janela de gatilhos.
export const NOMES_GATILHO = {
  comment: 'comentário em post ou Reel',
  live_comment: 'comentário durante a live',
  story_reply: 'resposta de story',
  dm: 'mensagem no direct',
  wa_message: 'mensagem no WhatsApp',
  wa_template_reply: 'clique em botão de template do WhatsApp',
}

// Gatilhos que só fazem sentido com um número de WhatsApp ligado na conta. Sem ele,
// somem do seletor e o editor fica exatamente como era.
export const GATILHOS_WA = ['wa_message', 'wa_template_reply']

export function gatilhosDisponiveis(wa) {
  return Object.fromEntries(Object.entries(NOMES_GATILHO)
    .filter(([k]) => wa || !GATILHOS_WA.includes(k)))
}

export const TIPOS = {
  // O gatilho não é um passo que se adiciona: ele já vem no fluxo, é sempre o
  // primeiro e mora na tabela de gatilhos, não no grafo. Aparece aqui só pro canvas
  // saber desenhá-lo. `oculto` mantém ele fora da paleta lateral.
  gatilho: {
    familia: 'entrada', rotulo: 'Quando começa', oculto: true,
    resumo: (d) => {
      const gs = d.triggers || []
      if (!gs.length) return 'sem gatilho, este fluxo não começa sozinho'
      return gs.map((g) => {
        const nome = NOMES_GATILHO[g.type] || g.type
        const kws = (g.keywords || []).join(', ')
        return kws ? `${nome}: ${kws}` : nome
      }).join('\n')
    },
  },
  text: {
    familia: 'envio', rotulo: 'Mensagem',
    resumo: (d) => {
      const n = (d.variants || []).filter((v) => (v || '').trim()).length
      const base = d.text || 'mensagem vazia'
      return n ? `${base}  ·  +${n} variações` : base
    },
  },
  // "Botões" não é um passo separado: é uma mensagem que tem botões. Fica fora da
  // paleta (oculto) e o tipo do nó troca sozinho quando se adiciona ou remove botão,
  // igual ao ManyChat, onde existe só "enviar mensagem".
  buttons: {
    familia: 'envio', rotulo: 'Mensagem', oculto: true,
    resumo: (d) => d.text || 'mensagem vazia',
    // cada botão de resposta vira uma saída própria; botão de link não tem saída
    saidas: (d) => (d.buttons || [])
      .filter((b) => b.type !== 'url' && !b.url)
      .map((b) => ({ id: b.key || b.title, rotulo: b.title || b.key })),
  },
  quick_replies: {
    familia: 'envio', rotulo: 'Opções rápidas',
    resumo: (d) => d.text || 'pergunta com opções',
    saidas: (d) => (d.options || []).map((o) => ({
      id: o.key || o.title, rotulo: o.title || o.key,
    })),
  },
  media: {
    familia: 'envio', rotulo: 'Mídia',
    resumo: (d) => d.url || (d.elements?.length ? `carrossel de ${d.elements.length}` : 'sem mídia'),
  },
  ai: {
    familia: 'envio', rotulo: 'Resposta com IA',
    resumo: (d) => d.prompt || 'sem instrução',
  },
  // Ponte Instagram -> WhatsApp. Só aparecem na paleta com número de WhatsApp
  // ligado na conta (`so_wa`).
  pedir_whatsapp: {
    familia: 'envio', rotulo: 'Pedir WhatsApp', so_wa: true,
    resumo: (d) => d.text || 'pede o número com DDD e o consentimento',
    saidas: (d) => (d.timeout_seconds ? [{ id: 'timeout', rotulo: 'se não responder' }] : []),
  },
  template_wa: {
    familia: 'envio', rotulo: 'Template WhatsApp', so_wa: true,
    resumo: (d) => (d.template ? `template ${d.template}` : 'escolha o template'),
    saidas: (d) => [
      ...(d.botoes || []).map((b) => ({ id: b, rotulo: b })),
      { id: '', rotulo: 'respondeu' },
      { id: 'falhou', rotulo: 'não enviou' },
      ...(d.timeout_seconds ? [{ id: 'timeout', rotulo: 'se não responder' }] : []),
    ],
  },
  delay: {
    familia: 'tempo', rotulo: 'Esperar',
    resumo: (d) => descreveTempo(Number(d.seconds || 0) + Number(d.minutes || 0) * 60),
  },
  schedule: {
    familia: 'tempo', rotulo: 'Agendar',
    resumo: (d) => d.run_at || 'sem data',
  },
  wait_input: {
    familia: 'tempo', rotulo: 'Esperar resposta',
    resumo: (d) => `guarda em {${d.save_as || '...'}}`,
    saidas: (d) => (d.timeout_seconds ? [{ id: 'timeout', rotulo: 'se não responder' }] : []),
  },
  condition: {
    familia: 'logica', rotulo: 'Condição',
    resumo: (d) => {
      const nomes = {
        tem_tag: 'tem a marcação', campo_preenchido: 'tem preenchido',
        campo_igual: 'campo igual a', e_seguidor: 'segue a conta',
      }
      return `${nomes[d.check] || d.check || 'condição'} ${d.value || ''}`.trim()
    },
    saidas: () => [{ id: 'sim', rotulo: 'sim' }, { id: 'nao', rotulo: 'não' }],
  },
  split: {
    familia: 'logica', rotulo: 'Teste A/B',
    resumo: (d) => `${d.percent_a ?? 50}% para o A`,
    saidas: () => [{ id: 'a', rotulo: 'A' }, { id: 'b', rotulo: 'B' }],
  },
  action: {
    familia: 'bastidor', rotulo: 'Ação',
    resumo: (d) => {
      const as = d.actions || []
      if (!as.length) return 'nenhuma ação'
      const a = as[0]
      const nome = { add_tag: 'marcar', remove_tag: 'desmarcar', set_field: 'guardar' }[a.action]
      return `${nome || a.action} ${a.tag || a.key || ''}${as.length > 1 ? ` e mais ${as.length - 1}` : ''}`
    },
  },
  webhook: {
    familia: 'bastidor', rotulo: 'Webhook',
    resumo: (d) => d.url || 'sem URL',
    saidas: () => [{ id: '', rotulo: 'ok' }, { id: 'erro', rotulo: 'erro' }],
  },
}

export function corDe(tipo) {
  return FAMILIAS[TIPOS[tipo]?.familia]?.cor || '#6f6f78'
}

export function suaveDe(tipo) {
  return FAMILIAS[TIPOS[tipo]?.familia]?.suave || '#f4f4f5'
}

export function descreveTempo(segundos) {
  if (!segundos) return 'sem espera'
  if (segundos < 60) return `${segundos}s`
  if (segundos < 3600) return `${Math.round(segundos / 60)} min`
  const h = segundos / 3600
  return h < 24 ? `${h.toFixed(h % 1 ? 1 : 0)}h` : `${(h / 24).toFixed(1)} dias`
}

// Nós que mandam mensagem livre e por isso dependem da janela de 24h. Com a caixa
// "seguir por outro caminho" marcada, ganham a saída fora_janela.
export const NOS_COM_JANELA = ['text', 'buttons', 'quick_replies', 'media', 'ai', 'pedir_whatsapp']

export function saidasDe(node) {
  const t = TIPOS[node.type]
  if (!t) return []
  const d = node.data || {}
  const saidas = t.saidas ? t.saidas(d) : []
  if (d.desvio_janela && NOS_COM_JANELA.includes(node.type)) {
    // a saída padrão do nó continua existindo (a aresta sem handle); sem ela listada
    // aqui, o card só desenharia o desvio
    const base = saidas.length ? saidas : [{ id: '', rotulo: 'enviou' }]
    return [...base, { id: 'fora_janela', rotulo: 'fora da janela 24h' }]
  }
  return saidas
}

// ordem da paleta, agrupada por família. `wa` liga os passos que só existem com
// WhatsApp configurado.
export function paleta(opcoes = {}) {
  const grupos = {}
  for (const [tipo, meta] of Object.entries(TIPOS)) {
    if (meta.oculto) continue   // gatilho não se adiciona: já vem no fluxo
    if (meta.so_wa && !opcoes.wa) continue
    ;(grupos[meta.familia] ||= []).push({ tipo, ...meta })
  }
  return Object.entries(FAMILIAS)
    .map(([chave, fam]) => ({ chave, ...fam, itens: grupos[chave] || [] }))
    .filter((fam) => fam.itens.length)   // família sem peça não vira título solto
}

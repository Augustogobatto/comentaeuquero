import { defineConfig, type DefaultTheme } from 'vitepress'

const REPO = 'https://github.com/Augustogobatto/comentaeuquero'

// Português na raiz. Inglês entra depois em /en/ (mesma árvore de pastas,
// mesmo sidebar traduzido): basta criar site/en/ e descomentar o locale abaixo.
const sidebarPt: DefaultTheme.Sidebar = {
  '/instalar/': [
    {
      text: 'Instalar',
      items: [
        { text: 'Escolha o caminho', link: '/instalar/' },
        { text: 'Chão (1 comando)', link: '/instalar/chao' },
        { text: 'Docker manual', link: '/instalar/docker' },
        { text: 'Computador + Cloudflare Tunnel', link: '/instalar/computador' },
      ],
    },
  ],
  '/tutoriais/': [
    {
      text: 'Começo',
      items: [
        { text: 'Visão geral', link: '/tutoriais/' },
        { text: 'Criar o app da Meta', link: '/tutoriais/app-meta' },
        { text: 'Conectar o Instagram', link: '/tutoriais/conectar-instagram' },
        { text: 'Primeiro fluxo: comenta e recebe', link: '/tutoriais/primeiro-fluxo' },
      ],
    },
    {
      text: 'Instagram',
      items: [
        { text: 'Story e live', link: '/tutoriais/story-e-live' },
        { text: 'IA no fluxo', link: '/tutoriais/ia-no-fluxo' },
        { text: 'Etiquetas e campos', link: '/tutoriais/etiquetas-e-campos' },
      ],
    },
    {
      text: 'WhatsApp',
      items: [
        { text: 'Conectar o WhatsApp', link: '/tutoriais/conectar-whatsapp' },
        { text: 'Ponte Instagram → WhatsApp', link: '/tutoriais/ponte-ig-wa' },
        { text: 'Criar um template', link: '/tutoriais/criar-template' },
        { text: 'Primeira transmissão', link: '/tutoriais/primeira-transmissao' },
      ],
    },
    {
      text: 'Manutenção',
      items: [
        { text: 'Backup e atualização', link: '/tutoriais/backup-e-atualizacao' },
        { text: 'Domínio próprio', link: '/tutoriais/dominio-proprio' },
      ],
    },
  ],
  '/referencia/': [
    {
      text: 'Referência',
      items: [
        { text: 'Visão geral', link: '/referencia/' },
        { text: 'Nós', link: '/referencia/nos' },
        { text: 'Gatilhos', link: '/referencia/gatilhos' },
        { text: 'Variáveis', link: '/referencia/variaveis' },
        { text: 'API', link: '/referencia/api' },
        { text: 'Configuração (.env)', link: '/referencia/env' },
      ],
    },
  ],
}

const themePt: DefaultTheme.Config = {
  nav: [
    { text: 'Instalar', link: '/instalar/', activeMatch: '^/instalar/' },
    { text: 'Tutoriais', link: '/tutoriais/', activeMatch: '^/tutoriais/' },
    { text: 'Referência', link: '/referencia/', activeMatch: '^/referencia/' },
    { text: 'FAQ', link: '/faq' },
    { text: 'Próximos upgrades', link: '/upgrades' },
    { text: 'Push Club', link: 'https://ia.augustogobatto.com/club' },
  ],
  sidebar: sidebarPt,
  outline: { level: [2, 3], label: 'Nesta página' },
  docFooter: { prev: 'Anterior', next: 'Próxima' },
  editLink: {
    pattern: `${REPO}/edit/main/site/:path`,
    text: 'Sugerir correção nesta página',
  },
  lastUpdated: { text: 'Atualizado em' },
  returnToTopLabel: 'Voltar ao topo',
  skipToContentLabel: 'Pular para o conteúdo',
  sidebarMenuLabel: 'Menu',
  darkModeSwitchLabel: 'Tema',
  lightModeSwitchTitle: 'Tema claro',
  darkModeSwitchTitle: 'Tema escuro',
  langMenuLabel: 'Idioma',
  notFound: {
    title: 'Página não encontrada',
    quote: 'O endereço pode ter mudado. Volte ao início ou use a busca.',
    linkLabel: 'Ir para o início',
    linkText: 'Voltar ao início',
  },
  footer: {
    message: 'Open source, licença de uso sustentável. <a href="/licenca">Ler a licença</a>. Feito por <a href="https://www.instagram.com/augustogobatto/" target="_blank" rel="noopener">@augustogobatto</a> · <a href="https://ia.augustogobatto.com/club" target="_blank" rel="noopener">Push Club</a>',
    copyright: '© 2026 Augusto Gobatto',
  },
  search: {
    provider: 'local',
    options: {
      translations: {
        button: { buttonText: 'Buscar', buttonAriaLabel: 'Buscar' },
        modal: {
          displayDetails: 'Mostrar detalhes',
          resetButtonTitle: 'Limpar busca',
          backButtonTitle: 'Fechar busca',
          noResultsText: 'Nada encontrado para',
          footer: { selectText: 'abrir', navigateText: 'navegar', closeText: 'fechar' },
        },
      },
    },
  },
  socialLinks: [
    { icon: 'github', link: REPO },
    { icon: 'instagram', link: 'https://www.instagram.com/augustogobatto/' },
  ],
}

export default defineConfig({
  title: 'comenta EU QUERO',
  titleTemplate: ':title · comenta EU QUERO',
  description:
    'Automação de Instagram e WhatsApp que roda no seu servidor. Código aberto, sem mensalidade e sem limite de contatos.',
  cleanUrls: true,
  lastUpdated: true,
  sitemap: { hostname: 'https://comentaeuquero.com' },
  head: [
    ['link', { rel: 'icon', href: '/favicon.svg', type: 'image/svg+xml' }],
    ['meta', { name: 'theme-color', content: '#f9faf8', media: '(prefers-color-scheme: light)' }],
    ['meta', { name: 'theme-color', content: '#151714', media: '(prefers-color-scheme: dark)' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:site_name', content: 'comenta EU QUERO' }],
    // Claro por padrão: só fica escuro se a pessoa escolher no botão de tema.
    [
      'script',
      {},
      "try{if(!localStorage.getItem('vitepress-theme-appearance'))localStorage.setItem('vitepress-theme-appearance','light')}catch(e){}",
    ],
  ],
  // A busca local só liga se estiver no themeConfig da raiz (o VitePress não lê a do locale).
  themeConfig: { search: themePt.search },
  locales: {
    root: {
      label: 'Português',
      lang: 'pt-BR',
      themeConfig: themePt,
    },
    // en: {
    //   label: 'English',
    //   lang: 'en-US',
    //   link: '/en/',
    //   themeConfig: themeEn,
    // },
  },
  markdown: {
    container: {
      tipLabel: 'Dica',
      warningLabel: 'Atenção',
      dangerLabel: 'Cuidado',
      infoLabel: 'Nota',
      detailsLabel: 'Detalhes',
    },
  },
})

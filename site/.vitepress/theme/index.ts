import DefaultTheme from 'vitepress/theme-without-fonts'
import type { Theme } from 'vitepress'
import Layout from './Layout.vue'
import Home from './components/Home.vue'
import Print from './components/Print.vue'
import Estado from './components/Estado.vue'
import '@fontsource-variable/host-grotesk/wght.css'
import '@fontsource/fragment-mono/400.css'
import './style.css'

export default {
  extends: DefaultTheme,
  Layout,
  enhanceApp({ app }) {
    app.component('Home', Home)
    app.component('Print', Print)
    app.component('Estado', Estado)
  },
} satisfies Theme

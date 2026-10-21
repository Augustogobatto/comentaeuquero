import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// O build sai direto pra dentro de app/static/editor, que o FastAPI serve como
// arquivo estático. Não tem servidor de node em produção: o editor é HTML+JS
// pronto, e quem instala o CEQ continua só subindo o container.
export default defineConfig({
  plugins: [vue()],
  base: '/static/editor/',
  build: {
    outDir: '../app/static/editor',
    emptyOutDir: true,
    assetsDir: 'assets',
  },
})

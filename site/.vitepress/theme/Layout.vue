<script setup lang="ts">
import DefaultTheme from 'vitepress/theme-without-fonts'
import { withBase } from 'vitepress'

const { Layout } = DefaultTheme
</script>

<template>
  <Layout>
    <template #nav-bar-title-before>
      <svg class="ceq-marca" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 5.5h14a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5h-7.5L7 20v-3.5H5A1.5 1.5 0 0 1 3.5 15V7A1.5 1.5 0 0 1 5 5.5z" />
        <path d="M8 11h8" />
      </svg>
    </template>
    <template #nav-bar-content-after>
      <a class="ceq-nav-cta" :href="withBase('/instalar/')">Instalar</a>
    </template>
  </Layout>
</template>

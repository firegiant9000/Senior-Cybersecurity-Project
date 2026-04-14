/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
  server: {
    host: '0.0.0.0',
    port: 5174,
    strictPort: false,
    watch: {
      usePolling: process.env.VITE_USE_POLLING === 'true',  // set in .env or docker-compose for Windows/Docker HMR
      interval: 300,
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-recharts': ['recharts'],
        },
      },
    },
  },
  css: {
    postcss: null, // Disable PostCSS config search (not using Tailwind/PostCSS)
  },
})

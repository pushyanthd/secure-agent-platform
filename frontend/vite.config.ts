import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    outDir: '../src/agentguard/ui',
    emptyOutDir: true,
    sourcemap: false,
    target: 'es2022',
  },
});

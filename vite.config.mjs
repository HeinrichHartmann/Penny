import { resolve } from 'node:path';
import { defineConfig } from 'vite';

const frontendRoot = resolve('src/penny/static');
const frontendDist = resolve('src/penny/static/dist');

export default defineConfig({
  root: frontendRoot,
  publicDir: false,
  server: {
    host: '127.0.0.1',
    port: 8000,
    strictPort: true,
    proxy: {
      '^/api/': 'http://127.0.0.1:8001',
    },
  },
  build: {
    outDir: frontendDist,
    emptyOutDir: true,
  },
});

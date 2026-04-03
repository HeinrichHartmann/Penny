import { resolve } from 'node:path';
import { defineConfig } from 'vite';

const frontendRoot = resolve('src/penny/static');
const frontendDist = resolve('src/penny/static/dist');

export default defineConfig({
  root: frontendRoot,
  publicDir: false,
  build: {
    outDir: frontendDist,
    emptyOutDir: true,
  },
});

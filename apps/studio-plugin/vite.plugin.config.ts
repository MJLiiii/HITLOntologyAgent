import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist-plugin',
    lib: { entry: 'src/index.ts', name: 'OntologyStudioPlugin', formats: ['iife'], fileName: () => 'ontology-studio.iife.js', cssFileName: 'ontology-studio' },
    rollupOptions: { external: ['react', 'react-dom', 'react/jsx-runtime'], output: { globals: { react: 'TrustKitShared.React', 'react-dom': 'TrustKitShared.ReactDOM', 'react/jsx-runtime': 'TrustKitShared.ReactJSX' }, exports: 'default' } },
  },
});

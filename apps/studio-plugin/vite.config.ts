import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, proxy: { '/api': { target: process.env.STUDIO_API_URL || 'http://127.0.0.1:8000', changeOrigin: true }, '/health': { target: process.env.STUDIO_API_URL || 'http://127.0.0.1:8000' } } },
  test: { environment: 'jsdom', setupFiles: ['./src/test-setup.ts'], css: false },
});

import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  test: {
    environment: 'happy-dom',
    globals: true,
    include: ['**/*.test.ts', '**/*.test.tsx'],
    setupFiles: ['./lib/testing/setup.ts'],
    pool: 'threads',
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './'),
    },
  },
});


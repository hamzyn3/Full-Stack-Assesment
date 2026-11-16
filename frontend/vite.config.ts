import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    // Component tests opt in to the DOM with `// @vitest-environment jsdom`; the rest run in plain node.
    environment: 'node',
    restoreMocks: true,
  },
})

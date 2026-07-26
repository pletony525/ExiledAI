import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base: './' is required - Electron loads the built page via file://, not an
// http server, so absolute asset paths like /assets/index.js would fail to resolve.
export default defineConfig({
  plugins: [react()],
  base: './',
})

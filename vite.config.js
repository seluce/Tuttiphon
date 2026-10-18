import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath } from 'node:url'

const here = (p) => fileURLToPath(new URL(p, import.meta.url))

// The interface is built from frontend/ into web/; the Python server (app/web.py) serves web/.
// Two pages: index.html (the app) and login.html (sign-in, reachable without a session).
// No dev server: to try things out, run `npm run build` (or `npm run watch`) and start the test server.
export default defineConfig({
  root: 'frontend',
  base: '/',
  plugins: [svelte(), tailwindcss()],
  build: {
    outDir: '../web',
    emptyOutDir: true,
    // File names with a content hash under /assets/: the server sends them with a long cache lifetime,
    // index.html and login.html with no-cache instead – so everything is fresh right after every build.
    assetsDir: 'assets',
    // The minified files lose the license comments of the bundled packages (Svelte, Lucide, Inter …): Vite writes
    // their licenses into web/third-party-licenses.md instead (in the image too; overview: THIRD-PARTY-NOTICES.md).
    license: { fileName: 'third-party-licenses.md' },
    rollupOptions: {
      input: {
        index: here('frontend/index.html'),
        login: here('frontend/login.html'),
      },
    },
  },
})

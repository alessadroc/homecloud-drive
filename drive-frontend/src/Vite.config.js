import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		// Match what nginx does in production, so the frontend talks to /api in
		// both places and no build is tied to one machine. Also means no CORS
		// in development: the browser only ever sees one origin.
		proxy: {
			'/api': {
				target: 'http://localhost:8008',
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/api/, '')
			}
		}
	}
});
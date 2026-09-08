import { sveltekit } from '@sveltejs/kit/vite';
import adapter from '@sveltejs/adapter-static';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit({
			kit: {
				adapter: adapter({
					pages: 'build',
					assets: 'build',
					fallback: 'index.html',
					precompress: false
				})
			}
		})
	],
	server: {
		// Mirrors what nginx does in production, so the app talks to /api in
		// both places and no build is tied to one machine.
		proxy: {
			'/api': {
				target: 'http://localhost:8008',
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/api/, '')
			}
		}
	}
});
import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		// Every page here is client-rendered - auth lives in sessionStorage and
		// the data arrives via onMount. There is nothing for a Node server to
		// do, so build to plain files and let nginx serve them.
		adapter: adapter({
			pages: 'build',
			assets: 'build',
			fallback: 'index.html', // SPA fallback: /trash resolves client-side
			precompress: false
		})
	}
};

export default config;
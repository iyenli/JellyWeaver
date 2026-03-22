import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		adapter: adapter({
			pages: '../src/jelly_weaver/static',
			assets: '../src/jelly_weaver/static',
			fallback: 'index.html',
			strict: false
		}),
		prerender: {
			handleHttpError: 'warn'
		}
	}
};

export default config;

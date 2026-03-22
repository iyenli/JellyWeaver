import type { Config } from 'tailwindcss';

export default {
	theme: {
		extend: {
			colors: {
				base: 'var(--base)',
				mantle: 'var(--mantle)',
				crust: 'var(--crust)',
				surface0: 'var(--surface0)',
				surface1: 'var(--surface1)',
				surface2: 'var(--surface2)',
				text: 'var(--text)',
				subtext0: 'var(--subtext0)',
				blue: 'var(--blue)',
				lavender: 'var(--lavender)',
				green: 'var(--green)',
				yellow: 'var(--yellow)',
				red: 'var(--red)'
			}
		}
	}
} satisfies Config;

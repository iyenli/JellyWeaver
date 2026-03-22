<script lang="ts">
	import type { Settings } from '$lib/types';

	export let open = false;
	export let value: Settings = { api_base: '', model: '', api_key: '', api_key_configured: false, api_key_preview: '' };
	export let onClose: () => void = () => {};
	export let onSave: (patch: Partial<Settings>) => void | Promise<void> = () => {};

	let draft = { api_base: '', model: '', api_key: '' };
	$: if (open) {
		draft = { api_base: value.api_base ?? '', model: value.model ?? '', api_key: '' };
	}
</script>

{#if open}
	<div class="fixed inset-0 z-40 bg-black/60" role="button" tabindex="0" aria-label="Close settings" onclick={onClose} onkeydown={(event) => event.key === 'Escape' && onClose()}></div>
	<div class="fixed left-1/2 top-1/2 z-50 w-[min(36rem,92vw)] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-[var(--surface0)] bg-[var(--mantle)] p-5 shadow-2xl shadow-black/50">
		<div class="mb-4">
			<h3 class="text-lg font-semibold">Settings</h3>
			<p class="mt-1 text-sm text-[var(--subtext0)]">Configure the OpenAI-compatible LLM endpoint.</p>
		</div>

		<div class="space-y-3">
			<label class="block space-y-1 text-sm">
				<span class="text-[var(--subtext0)]">API base</span>
				<input class="w-full rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2" bind:value={draft.api_base} />
			</label>
			<label class="block space-y-1 text-sm">
				<span class="text-[var(--subtext0)]">Model</span>
				<input class="w-full rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2" bind:value={draft.model} />
			</label>
			<label class="block space-y-1 text-sm">
				<span class="text-[var(--subtext0)]">API key</span>
				<input class="w-full rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2" type="password" bind:value={draft.api_key} placeholder={value.api_key_configured ? value.api_key_preview || 'Configured' : 'Paste API key'} />
			</label>
		</div>

		<div class="mt-5 flex justify-end gap-3">
			<button class="rounded-lg border border-[var(--surface0)] bg-[var(--surface0)] px-4 py-2 text-sm hover:bg-[var(--surface1)]" onclick={onClose}>Cancel</button>
			<button class="rounded-lg bg-[var(--blue)] px-4 py-2 text-sm font-medium text-[var(--crust)] hover:brightness-110" onclick={() => onSave(draft)}>
				Save
			</button>
		</div>
	</div>
{/if}

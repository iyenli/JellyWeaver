<script lang="ts">
	import type { Settings, LlmCheckResult } from '$lib/types';
	import { api } from '$lib/api';

	export let open = false;
	export let value: Settings = { api_base: '', model: '', api_key: '', api_key_configured: false, api_key_preview: '' };
	export let onClose: () => void = () => {};
	export let onSave: (patch: Partial<Settings>) => void | Promise<void> = () => {};

	let draft = { api_base: '', model: '', api_key: '' };
	let llmStatus: LlmCheckResult | null = null;
	let llmChecking = false;
	let prevOpen = false;

	$: if (open !== prevOpen) {
		prevOpen = open;
		if (open) {
			draft = { api_base: value.api_base ?? '', model: value.model ?? '', api_key: '' };
			llmStatus = null;
		}
	}

	// Handle late-arriving settings data: if dialog is open and draft is still empty
	// but value now has real data, update draft without wiping user edits
	$: if (open && !draft.api_base && value.api_base) {
		draft.api_base = value.api_base;
	}
	$: if (open && !draft.model && value.model) {
		draft.model = value.model;
	}

	async function handleLlmCheck() {
		llmChecking = true;
		llmStatus = null;
		try {
			llmStatus = await api.llmCheck();
		} catch (error) {
			llmStatus = { configured: false, ok: false, error: error instanceof Error ? error.message : 'Check failed' };
		} finally {
			llmChecking = false;
		}
	}

	async function handleOpenStateDir() {
		try {
			await api.openStateDir();
		} catch {
			// silently fail
		}
	}
</script>

{#if open}
	<div class="fixed inset-0 z-40 bg-black/60" role="button" tabindex="0" aria-label="Close settings" onclick={onClose} onkeydown={(event) => event.key === 'Escape' && onClose()}></div>
	<div class="fixed left-1/2 top-1/2 z-50 w-[min(36rem,92vw)] max-h-[85vh] overflow-y-auto -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-[var(--surface0)] bg-[var(--mantle)] p-5 shadow-2xl shadow-black/50">
		<div class="mb-5">
			<h3 class="text-lg font-semibold">Settings</h3>
		</div>

		<!-- LLM Section -->
		<div class="mb-5">
			<div class="mb-3 flex items-center justify-between">
				<h4 class="text-sm font-semibold uppercase tracking-wide text-[var(--subtext0)]">LLM</h4>
				<button
					class="rounded-lg border border-[var(--surface0)] bg-[var(--surface0)] px-3 py-1.5 text-xs hover:bg-[var(--surface1)] disabled:opacity-50"
					disabled={llmChecking}
					onclick={handleLlmCheck}
				>
					{llmChecking ? 'Testing...' : 'Test Connection'}
				</button>
			</div>

			{#if llmStatus}
				<div class={`mb-3 rounded-lg border px-3 py-2 text-sm ${llmStatus.ok ? 'border-[var(--green)] bg-[color:color-mix(in_srgb,var(--green)_12%,var(--base))] text-[var(--green)]' : 'border-[var(--red)] bg-[color:color-mix(in_srgb,var(--red)_12%,var(--base))] text-[var(--red)]'}`}>
					{llmStatus.ok ? 'Connection OK' : llmStatus.error || 'Connection failed'}
				</div>
			{/if}

			<div class="space-y-3">
				<label class="block space-y-1 text-sm">
					<span class="text-[var(--subtext0)]">API Base</span>
					<input class="w-full rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2" bind:value={draft.api_base} />
				</label>
				<label class="block space-y-1 text-sm">
					<span class="text-[var(--subtext0)]">Model</span>
					<input class="w-full rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2" bind:value={draft.model} />
				</label>
				<label class="block space-y-1 text-sm">
					<span class="text-[var(--subtext0)]">API Key</span>
					<input class="w-full rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2" type="password" bind:value={draft.api_key} placeholder={value.api_key_configured ? value.api_key_preview || 'Configured' : 'Paste API key'} />
				</label>
			</div>
		</div>

		<!-- State File Section -->
		<div class="mb-5">
			<h4 class="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--subtext0)]">Data Files</h4>
			<div class="space-y-2">
				<div class="flex items-center gap-2 rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2">
					<div class="min-w-0 flex-1">
						<div class="text-xs text-[var(--subtext0)]">State</div>
						<div class="truncate text-sm text-[var(--text)]">{value.state_file_path ?? 'Unknown'}</div>
					</div>
				</div>
				{#if value.llm_settings_file_path}
					<div class="flex items-center gap-2 rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2">
						<div class="min-w-0 flex-1">
							<div class="text-xs text-[var(--subtext0)]">LLM Settings</div>
							<div class="truncate text-sm text-[var(--text)]">{value.llm_settings_file_path}</div>
						</div>
					</div>
				{/if}
				<button
					class="rounded-md border border-[var(--surface1)] px-2 py-1 text-xs text-[var(--subtext0)] hover:bg-[var(--surface1)]"
					onclick={handleOpenStateDir}
				>
					Open folder
				</button>
			</div>
		</div>

		<div class="flex justify-end gap-3">
			<button class="rounded-lg border border-[var(--surface0)] bg-[var(--surface0)] px-4 py-2 text-sm hover:bg-[var(--surface1)]" onclick={onClose}>Cancel</button>
			<button class="rounded-lg bg-[var(--blue)] px-4 py-2 text-sm font-medium text-[var(--crust)] hover:brightness-110" onclick={() => onSave(draft)}>
				Save
			</button>
		</div>
	</div>
{/if}

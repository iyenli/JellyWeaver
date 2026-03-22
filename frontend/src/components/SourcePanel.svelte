<script lang="ts">
	import SourceTree from './SourceTree.svelte';
	import type { SourceSummary } from '$lib/types';

	export let sources: SourceSummary[] = [];
	export let showCompleted = false;
	export let showIgnored = false;
	export let loading = false;
	export let onAddSource: () => void = () => {};
	export let onRemoveSource: (path: string) => void | Promise<void> = () => {};
	export let onToggleIgnored: (path: string, nextIgnored: boolean) => void | Promise<void> = () => {};
	export let onShowCompletedChange: (value: boolean) => void = () => {};
	export let onShowIgnoredChange: (value: boolean) => void = () => {};
</script>

<section class="flex min-h-[70vh] flex-col rounded-2xl border border-[var(--surface0)] bg-[var(--mantle)] p-4 shadow-lg shadow-black/20">
	<div class="mb-4 flex items-center justify-between gap-3">
		<div>
			<h2 class="text-lg font-semibold">Sources</h2>
			<p class="text-sm text-[var(--subtext0)]">PT download directories</p>
		</div>
		<button class="rounded-lg bg-[var(--blue)] px-3 py-2 text-sm font-medium text-[var(--crust)] hover:brightness-110" onclick={onAddSource}>
			Add Source
		</button>
	</div>

	<div class="mb-4 flex flex-wrap gap-4 text-sm text-[var(--subtext0)]">
		<label class="flex items-center gap-2">
			<input type="checkbox" checked={showCompleted} onchange={(event) => onShowCompletedChange((event.currentTarget as HTMLInputElement).checked)} />
			<span>Show completed</span>
		</label>
		<label class="flex items-center gap-2">
			<input type="checkbox" checked={showIgnored} onchange={(event) => onShowIgnoredChange((event.currentTarget as HTMLInputElement).checked)} />
			<span>Show ignored</span>
		</label>
	</div>

	<div class="flex-1 space-y-4 overflow-auto pr-1">
		{#if loading}
			<div class="rounded-xl border border-[var(--surface0)] bg-[var(--base)] px-4 py-6 text-sm text-[var(--subtext0)]">
				Scanning sources...
			</div>
		{/if}

		{#each sources as source (source.path)}
			<div class="rounded-2xl border border-[var(--surface0)] bg-[var(--base)] p-3">
				<div class="mb-3 flex items-start justify-between gap-3">
					<div class="min-w-0">
						<div class="truncate text-sm font-medium">{source.path}</div>
						<div class="text-xs text-[var(--subtext0)]">{source.entries.length} entries</div>
					</div>
					<button class="rounded-md border border-[var(--surface1)] px-2 py-1 text-xs text-[var(--subtext0)] hover:bg-[var(--surface1)]" onclick={() => onRemoveSource(source.path)}>
						Remove
					</button>
				</div>

				<SourceTree {showCompleted} {showIgnored} entries={source.entries} {onToggleIgnored} />
			</div>
		{/each}

		{#if !loading && sources.length === 0}
			<div class="rounded-2xl border border-dashed border-[var(--surface1)] bg-[var(--base)] px-4 py-8 text-center text-sm text-[var(--subtext0)]">
				Add a source directory to start scanning PT downloads.
			</div>
		{/if}
	</div>
</section>

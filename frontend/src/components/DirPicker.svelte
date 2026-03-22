<script lang="ts">
	import type { FsItem } from '$lib/types';

	export let open = false;
	export let mode: 'source' | 'target' = 'source';
	export let currentPath = '';
	export let roots: string[] = [];
	export let home = '';
	export let items: FsItem[] = [];
	export let onClose: () => void = () => {};
	export let onNavigate: (path: string) => void | Promise<void> = () => {};
	export let onSelect: (path: string) => void | Promise<void> = () => {};
</script>

{#if open}
	<div class="fixed inset-0 z-40 bg-black/60" role="button" tabindex="0" aria-label="Close directory picker" onclick={onClose} onkeydown={(event) => event.key === 'Escape' && onClose()}></div>
	<div class="fixed left-1/2 top-1/2 z-50 w-[min(56rem,92vw)] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-[var(--surface0)] bg-[var(--mantle)] p-5 shadow-2xl shadow-black/50">
		<div class="mb-4 flex items-center justify-between gap-3">
			<div>
				<h3 class="text-lg font-semibold">Choose {mode === 'source' ? 'source' : 'target'} directory</h3>
				<p class="text-sm text-[var(--subtext0)]">{currentPath || 'No directory loaded'}</p>
			</div>
			<button class="rounded-lg border border-[var(--surface0)] bg-[var(--surface0)] px-3 py-2 text-sm hover:bg-[var(--surface1)]" onclick={onClose}>Close</button>
		</div>

		<div class="mb-4 flex flex-wrap gap-2">
			{#if home}
				<button class="rounded-md border border-[var(--surface1)] px-3 py-1.5 text-sm hover:bg-[var(--surface1)]" onclick={() => onNavigate(home)}>Home</button>
			{/if}
			{#each roots as root}
				<button class="rounded-md border border-[var(--surface1)] px-3 py-1.5 text-sm hover:bg-[var(--surface1)]" onclick={() => onNavigate(root)}>{root}</button>
			{/each}
			{#if currentPath}
				<button class="rounded-md border border-[var(--surface1)] px-3 py-1.5 text-sm hover:bg-[var(--surface1)]" onclick={() => onNavigate(currentPath.split(/[/\\]/).slice(0, -1).join('/') || currentPath)}>
					Up
				</button>
				<button class="rounded-md bg-[var(--blue)] px-3 py-1.5 text-sm font-medium text-[var(--crust)] hover:brightness-110" onclick={() => onSelect(currentPath)}>
					Select current
				</button>
			{/if}
		</div>

		<div class="max-h-[24rem] overflow-auto rounded-xl border border-[var(--surface0)] bg-[var(--base)]">
			{#if items.length > 0}
				{#each items.filter((item) => item.is_dir) as item (item.path)}
					<button class="flex w-full items-center justify-between border-b border-[var(--surface0)] px-4 py-3 text-left text-sm last:border-b-0 hover:bg-[var(--surface0)]" onclick={() => onNavigate(item.path)}>
						<span class="truncate">{item.name}</span>
						<span class="text-xs text-[var(--subtext0)]">open</span>
					</button>
				{/each}
			{:else}
				<div class="px-4 py-8 text-center text-sm text-[var(--subtext0)]">No subdirectories</div>
			{/if}
		</div>
	</div>
{/if}

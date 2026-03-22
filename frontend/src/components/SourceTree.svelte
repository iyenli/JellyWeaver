<script lang="ts">
	import type { EntryItem } from '$lib/types';

	export let entries: EntryItem[] = [];
	export let showCompleted = false;
	export let showIgnored = false;
	export let searchText = '';
	export let onToggleIgnored: (path: string, nextIgnored: boolean) => void | Promise<void> = () => {};
	export let onSmartAdd: (path: string) => void | Promise<void> = () => {};

	let smartAddLoading = '';

	$: visibleEntries = entries.filter((entry) => {
		if (entry.status === 'linked' && !showCompleted) return false;
		if (entry.status === 'ignored' && !showIgnored) return false;
		if (searchText && !entry.name.toLowerCase().includes(searchText.toLowerCase())) return false;
		return true;
	});

	function statusClass(status: EntryItem['status']) {
		if (status === 'linked') return 'bg-[var(--green)]';
		if (status === 'ignored') return 'bg-[var(--overlay0)]';
		return 'bg-[var(--yellow)]';
	}

	function handleDragStart(event: DragEvent, path: string) {
		event.dataTransfer?.setData('text/plain', path);
		event.dataTransfer?.setData('application/x-jelly-weaver-path', path);
		event.dataTransfer!.effectAllowed = 'copy';
	}

	async function handleSmartAdd(path: string) {
		smartAddLoading = path;
		try {
			await onSmartAdd(path);
		} finally {
			smartAddLoading = '';
		}
	}
</script>

<div class="space-y-2">
	{#each visibleEntries as entry (entry.path)}
		<div
			class="flex items-center gap-3 rounded-xl border border-[var(--surface0)] bg-[var(--mantle)] px-3 py-2 transition hover:border-[var(--surface1)] hover:bg-[var(--surface0)]"
			role="button"
			tabindex={entry.status !== 'ignored' ? 0 : -1}
			aria-label={`Source entry ${entry.name}`}
			draggable={entry.status !== 'ignored'}
			ondragstart={(event) => handleDragStart(event, entry.path)}
		>
			<span class={`h-2.5 w-2.5 shrink-0 rounded-full ${statusClass(entry.status)}`}></span>
			<div class="min-w-0 flex-1">
				<div class="truncate text-sm font-medium">{entry.name}</div>
				<div class="truncate text-xs text-[var(--subtext0)]">
					{entry.file_count} files · {entry.status}
					{#if entry.target_path}
						· {entry.target_path}
					{/if}
				</div>
			</div>
			<div class="flex shrink-0 gap-1">
				{#if entry.status === 'pending'}
					<button
						class="rounded-md border border-[var(--mauve)]/30 px-2 py-1 text-xs text-[var(--mauve)] hover:bg-[var(--mauve)]/10 disabled:opacity-40"
						title="Smart Add — AI auto-select library"
						disabled={smartAddLoading === entry.path}
						onclick={() => handleSmartAdd(entry.path)}
					>
						{smartAddLoading === entry.path ? '...' : '✦'}
					</button>
				{/if}
				<button
					class="rounded-md border border-[var(--surface1)] px-2 py-1 text-xs text-[var(--subtext0)] hover:bg-[var(--surface1)]"
					onclick={() => onToggleIgnored(entry.path, entry.status !== 'ignored')}
				>
					{entry.status === 'ignored' ? 'Unignore' : 'Ignore'}
				</button>
			</div>
		</div>
	{/each}

	{#if visibleEntries.length === 0}
		<div class="rounded-xl border border-dashed border-[var(--surface1)] px-4 py-6 text-center text-sm text-[var(--subtext0)]">
			No entries to show
		</div>
	{/if}
</div>

<script lang="ts">
	import type { EntryItem } from '$lib/types';

	export let entries: EntryItem[] = [];
	export let showCompleted = false;
	export let showIgnored = false;
	export let searchText = '';
	export let onToggleIgnored: (path: string, nextIgnored: boolean) => void | Promise<void> = () => {};
	export let onSmartAdd: (path: string) => void | Promise<void> = () => {};
	export let onGroupFiles: (paths: string[]) => void | Promise<void> = () => {};

	let smartAddLoading = '';
	let selectedFilePaths = new Set<string>();

	$: visibleEntries = entries.filter((entry) => {
		if (entry.status === 'linked' && !showCompleted) return false;
		if (entry.status === 'ignored' && !showIgnored) return false;
		if (searchText && !entry.name.toLowerCase().includes(searchText.toLowerCase())) return false;
		return true;
	});

	// Clear selection when entries change (e.g. after link)
	$: {
		entries;
		selectedFilePaths = new Set<string>();
	}

	$: selectedPending = [...selectedFilePaths].filter((p) => {
		const e = entries.find((e) => e.path === p);
		return e?.status === 'pending';
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

	function toggleSelect(path: string) {
		const next = new Set(selectedFilePaths);
		if (next.has(path)) next.delete(path);
		else next.add(path);
		selectedFilePaths = next;
	}

	async function handleGroupLink() {
		const paths = selectedPending;
		if (paths.length < 1) return;
		selectedFilePaths = new Set();
		await onGroupFiles(paths);
	}
</script>

<div class="space-y-2">
	{#if selectedPending.length >= 2}
		<div class="flex items-center justify-between rounded-lg border border-[var(--mauve)]/40 bg-[color:color-mix(in_srgb,var(--mauve)_8%,transparent)] px-3 py-2">
			<span class="text-xs text-[var(--mauve)]">{selectedPending.length} 个文件已选</span>
			<button
				class="rounded-md bg-[var(--mauve)] px-2.5 py-1 text-xs font-medium text-[var(--crust)] hover:brightness-110"
				onclick={handleGroupLink}
			>
				Group & Link
			</button>
		</div>
	{/if}

	{#each visibleEntries as entry (entry.path)}
		<div
			class="flex items-center gap-3 rounded-xl border border-[var(--surface0)] bg-[var(--mantle)] px-3 py-2 transition hover:border-[var(--surface1)] hover:bg-[var(--surface0)]"
			role="button"
			tabindex={entry.status !== 'ignored' ? 0 : -1}
			aria-label={`Source entry ${entry.name}`}
			draggable={entry.status !== 'ignored' && !entry.is_file}
			ondragstart={(event) => handleDragStart(event, entry.path)}
		>
			{#if entry.is_file && entry.status === 'pending'}
				<input
					type="checkbox"
					class="h-3.5 w-3.5 shrink-0 accent-[var(--mauve)]"
					checked={selectedFilePaths.has(entry.path)}
					onclick={(e) => { e.stopPropagation(); toggleSelect(entry.path); }}
				/>
			{:else}
				<span class={`h-2.5 w-2.5 shrink-0 rounded-full ${statusClass(entry.status)}`}></span>
			{/if}

			<div class="min-w-0 flex-1">
				<div class="flex items-center gap-1.5 truncate">
					{#if entry.is_file}
						<!-- file icon -->
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-3 w-3 shrink-0 text-[var(--subtext0)]">
							<path d="M4 1.75A.75.75 0 0 1 4.75 1h4.836c.464 0 .909.184 1.237.513l2.163 2.162c.329.328.513.773.513 1.237v8.588A.75.75 0 0 1 12.75 14h-8A.75.75 0 0 1 4 13.25V1.75ZM8.5 2.5v2.25c0 .138.112.25.25.25h2.25L8.5 2.5Z" />
						</svg>
					{/if}
					<span class="truncate text-sm font-medium">{entry.name}</span>
				</div>
				<div class="truncate text-xs text-[var(--subtext0)]">
					{entry.is_file ? 'file' : `${entry.file_count} files`} · {entry.status}
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

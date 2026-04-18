<script lang="ts">
	import type { TargetContentItem, TargetSection as TargetSectionType } from '$lib/types';

	export let section: TargetSectionType;
	export let items: TargetContentItem[] = [];
	export let linkedTargetPaths: Set<string> = new Set();
	export let active = false;
	export let onChange: (patch: Partial<TargetSectionType>) => void | Promise<void> = () => {};
	export let onRemove: () => void | Promise<void> = () => {};
	export let onPickPath: () => void = () => {};
	export let onDropSource: (sourcePath: string) => void | Promise<void> = () => {};
	export let onUnlink: (targetFolderPath: string) => void | Promise<void> = () => {};
	export let onReparse: (targetFolderPath: string, folderName: string) => void | Promise<void> = () => {};
	export let onRenameAll: () => void | Promise<void> = () => {};
	export let onJellyfinScan: () => void | Promise<void> = () => {};
	export let onRelinkAll: () => void | Promise<void> = () => {};

	let renameAllBusy = false;
	let jellyfinScanBusy = false;
	let relinkAllBusy = false;

	async function handleRenameAll() {
		renameAllBusy = true;
		try {
			await onRenameAll();
		} finally {
			renameAllBusy = false;
		}
	}

	async function handleJellyfinScan() {
		jellyfinScanBusy = true;
		try {
			await onJellyfinScan();
		} finally {
			jellyfinScanBusy = false;
		}
	}

	async function handleRelinkAll() {
		relinkAllBusy = true;
		try {
			await onRelinkAll();
		} finally {
			relinkAllBusy = false;
		}
	}

	function handleDrop(event: DragEvent) {
		event.preventDefault();
		const path =
			event.dataTransfer?.getData('application/x-jelly-weaver-path') ||
			event.dataTransfer?.getData('text/plain');
		if (path) onDropSource(path);
	}
</script>

<div
	class={`rounded-2xl border p-4 transition ${active ? 'border-[var(--blue)] bg-[color:color-mix(in_srgb,var(--surface0)_70%,var(--mantle))]' : 'border-[var(--surface0)] bg-[var(--mantle)]'}`}
	role="group"
	aria-label={`Target section ${section.name || 'library'}`}
	ondragover={(event) => event.preventDefault()}
	ondragenter={(event) => {
		event.preventDefault();
	}}
	ondrop={handleDrop}
>
	<div class="mb-4 flex items-start justify-between gap-3">
		<div>
			<h3 class="text-base font-semibold">
				Library
				{#if items.length > 0}
					{@const untrackedCount = items.filter((item) => !linkedTargetPaths.has(item.path)).length}
					<span class="ml-1.5 rounded-md bg-[var(--surface1)] px-1.5 py-0.5 text-xs font-normal text-[var(--subtext0)]">{items.length}</span>
					{#if untrackedCount > 0}
						<span class="ml-1 rounded-md bg-[color:color-mix(in_srgb,var(--sky)_20%,transparent)] px-1.5 py-0.5 text-xs font-normal text-[var(--sky)]">{untrackedCount} new</span>
					{/if}
				{/if}
			</h3>
			<p class="text-sm text-[var(--subtext0)]">Drop a source entry here to start parse and link.</p>
		</div>
		<div class="flex shrink-0 items-center gap-1.5">
			<!-- Relink All -->
			<button
				class="rounded-md border border-[var(--surface1)] p-1.5 text-[var(--subtext0)] hover:border-[var(--green)] hover:bg-[color:color-mix(in_srgb,var(--green)_10%,transparent)] hover:text-[var(--green)] disabled:cursor-not-allowed disabled:opacity-40"
				title="Relink All: unlink all tracked items and re-link using AI name cache (creates Season 01/ etc.)"
				disabled={relinkAllBusy || items.length === 0}
				onclick={handleRelinkAll}
			>
				{#if relinkAllBusy}
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4 animate-spin">
						<path fill-rule="evenodd" d="M15.312 11.424a5.5 5.5 0 0 1-9.201 2.466l-.312-.311h2.433a.75.75 0 0 0 0-1.5H3.989a.75.75 0 0 0-.75.75v4.242a.75.75 0 0 0 1.5 0v-2.43l.31.31a7 7 0 0 0 11.712-3.138.75.75 0 0 0-1.449-.39Zm1.23-3.723a.75.75 0 0 0 .219-.53V2.929a.75.75 0 0 0-1.5 0V5.36l-.31-.31A7 7 0 0 0 3.239 8.188a.75.75 0 1 0 1.448.389A5.5 5.5 0 0 1 13.89 6.11l.311.31h-2.432a.75.75 0 0 0 0 1.5h4.243a.75.75 0 0 0 .53-.219Z" clip-rule="evenodd" />
					</svg>
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4">
						<path fill-rule="evenodd" d="M4.755 10.059a7.5 7.5 0 0 1 12.548-3.364l1.903 1.903h-3.183a.75.75 0 1 0 0 1.5h4.992a.75.75 0 0 0 .75-.75V4.356a.75.75 0 0 0-1.5 0v3.18l-1.9-1.9A9 9 0 0 0 3.306 9.67a.75.75 0 1 0 1.45.388Zm15.408 3.352a.75.75 0 0 0-.919.53 7.5 7.5 0 0 1-12.548 3.364l-1.902-1.903h3.183a.75.75 0 0 0 0-1.5H3.984a.75.75 0 0 0-.75.75v4.992a.75.75 0 0 0 1.5 0v-3.18l1.9 1.9a9 9 0 0 0 15.059-4.035.75.75 0 0 0-.53-.918Z" clip-rule="evenodd" />
					</svg>
				{/if}
			</button>
			<!-- Rename All -->
			<button
				class="rounded-md border border-[var(--surface1)] p-1.5 text-[var(--subtext0)] hover:border-[var(--yellow)] hover:bg-[color:color-mix(in_srgb,var(--yellow)_10%,transparent)] hover:text-[var(--yellow)] disabled:cursor-not-allowed disabled:opacity-40"
				title="批量重命名（使用缓存的 AI 名称）"
				disabled={renameAllBusy || items.length === 0}
				onclick={handleRenameAll}
			>
				{#if renameAllBusy}
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4 animate-spin">
						<path fill-rule="evenodd" d="M15.312 11.424a5.5 5.5 0 0 1-9.201 2.466l-.312-.311h2.433a.75.75 0 0 0 0-1.5H3.989a.75.75 0 0 0-.75.75v4.242a.75.75 0 0 0 1.5 0v-2.43l.31.31a7 7 0 0 0 11.712-3.138.75.75 0 0 0-1.449-.39Zm1.23-3.723a.75.75 0 0 0 .219-.53V2.929a.75.75 0 0 0-1.5 0V5.36l-.31-.31A7 7 0 0 0 3.239 8.188a.75.75 0 1 0 1.448.389A5.5 5.5 0 0 1 13.89 6.11l.311.31h-2.432a.75.75 0 0 0 0 1.5h4.243a.75.75 0 0 0 .53-.219Z" clip-rule="evenodd" />
					</svg>
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4">
						<path d="M5.433 13.917l1.262-3.155A4 4 0 0 1 7.58 9.42l6.92-6.918a2.121 2.121 0 0 1 3 3l-6.92 6.918c-.383.383-.84.685-1.343.886l-3.154 1.262a.5.5 0 0 1-.65-.65Z" />
						<path d="M3.5 5.75c0-.69.56-1.25 1.25-1.25H10A.75.75 0 0 0 10 3H4.75A2.75 2.75 0 0 0 2 5.75v9.5A2.75 2.75 0 0 0 4.75 18h9.5A2.75 2.75 0 0 0 17 15.25V10a.75.75 0 0 0-1.5 0v5.25c0 .69-.56 1.25-1.25 1.25h-9.5c-.69 0-1.25-.56-1.25-1.25v-9.5Z" />
					</svg>
				{/if}
			</button>
			<!-- Jellyfin Scan -->
			<button
				class="rounded-md border border-[var(--surface1)] p-1.5 text-[var(--subtext0)] hover:border-[var(--mauve)] hover:bg-[color:color-mix(in_srgb,var(--mauve)_10%,transparent)] hover:text-[var(--mauve)] disabled:cursor-not-allowed disabled:opacity-40"
				title="触发 Jellyfin 刮削"
				disabled={jellyfinScanBusy}
				onclick={handleJellyfinScan}
			>
				{#if jellyfinScanBusy}
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4 animate-spin">
						<path fill-rule="evenodd" d="M15.312 11.424a5.5 5.5 0 0 1-9.201 2.466l-.312-.311h2.433a.75.75 0 0 0 0-1.5H3.989a.75.75 0 0 0-.75.75v4.242a.75.75 0 0 0 1.5 0v-2.43l.31.31a7 7 0 0 0 11.712-3.138.75.75 0 0 0-1.449-.39Zm1.23-3.723a.75.75 0 0 0 .219-.53V2.929a.75.75 0 0 0-1.5 0V5.36l-.31-.31A7 7 0 0 0 3.239 8.188a.75.75 0 1 0 1.448.389A5.5 5.5 0 0 1 13.89 6.11l.311.31h-2.432a.75.75 0 0 0 0 1.5h4.243a.75.75 0 0 0 .53-.219Z" clip-rule="evenodd" />
					</svg>
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4">
						<path fill-rule="evenodd" d="M5 2a1 1 0 0 1 1 1v1h1a1 1 0 0 1 0 2H6v1a1 1 0 0 1-2 0V6H3a1 1 0 0 1 0-2h1V3a1 1 0 0 1 1-1Zm0 10a1 1 0 0 1 1 1v1h1a1 1 0 0 1 0 2H6v1a1 1 0 0 1-2 0v-1H3a1 1 0 0 1 0-2h1v-1a1 1 0 0 1 1-1ZM12 2a1 1 0 0 1 .967.744L14.146 7.2 17.5 9.134a1 1 0 0 1 0 1.732l-3.354 1.935-1.18 4.455a1 1 0 0 1-1.933 0L9.854 12.8 6.5 10.866a1 1 0 0 1 0-1.732l3.354-1.935 1.18-4.455A1 1 0 0 1 12 2Z" clip-rule="evenodd" />
					</svg>
				{/if}
			</button>
			<button class="rounded-md border border-[var(--surface1)] px-2 py-1 text-xs text-[var(--subtext0)] hover:bg-[var(--surface1)]" onclick={onRemove}>
				Remove
			</button>
		</div>
	</div>

	<div class="grid gap-3 md:grid-cols-[1.4fr_0.8fr]">
		<label class="space-y-1 text-sm">
			<span class="text-[var(--subtext0)]">Name</span>
			<input
				class="w-full rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2 text-[var(--text)]"
				value={section.name}
				onchange={(event) => onChange({ name: (event.currentTarget as HTMLInputElement).value })}
			/>
		</label>
		<label class="space-y-1 text-sm">
			<span class="text-[var(--subtext0)]">Media type</span>
			<select
				class="w-full rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2 text-[var(--text)]"
				value={section.media_type}
				onchange={(event) => onChange({ media_type: (event.currentTarget as HTMLSelectElement).value as TargetSectionType['media_type'] })}
			>
				<option value="movies">Movies</option>
				<option value="tv">TV</option>
			</select>
		</label>
	</div>

	<div class="mt-3 flex gap-2">
		<input
			class="min-w-0 flex-1 rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2 text-sm text-[var(--text)]"
			placeholder="Choose target directory"
			value={section.path}
			onchange={(event) => onChange({ path: (event.currentTarget as HTMLInputElement).value })}
		/>
		<button class="rounded-lg border border-[var(--surface0)] bg-[var(--surface0)] px-3 py-2 text-sm hover:bg-[var(--surface1)]" onclick={onPickPath}>
			Browse
		</button>
	</div>

	<div class="mt-4 rounded-xl border border-dashed border-[var(--surface1)] px-4 py-4 text-center text-sm text-[var(--subtext0)]">
		Drop a source entry here
	</div>

	<div class="mt-4 space-y-2">
		<div class="text-xs font-medium uppercase tracking-wide text-[var(--subtext0)]">Existing folders</div>
		{#if items.length > 0}
			<div class="max-h-40 space-y-2 overflow-auto pr-1">
				{#each items as item (item.path)}
					{@const isTracked = linkedTargetPaths.has(item.path)}
					<div class="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors
							{isTracked
								? 'border-[var(--surface0)] bg-[var(--base)] text-[var(--overlay1)]'
								: 'border-[color:color-mix(in_srgb,var(--sky)_35%,transparent)] bg-[color:color-mix(in_srgb,var(--sky)_6%,var(--base))] text-[var(--sky)]'}">
						{#if item.is_file}
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5 shrink-0 opacity-50">
								<path d="M4 1.75A.75.75 0 0 1 4.75 1h4.836c.464 0 .909.184 1.237.513l2.163 2.162c.329.328.513.773.513 1.237v8.588A.75.75 0 0 1 12.75 14h-8A.75.75 0 0 1 4 13.25V1.75ZM8.5 2.5v2.25c0 .138.112.25.25.25h2.25L8.5 2.5Z" />
							</svg>
						{/if}
						<span class="min-w-0 flex-1 truncate">{item.name}</span>
						{#if !item.is_file}
							<button
								class="shrink-0 rounded-md p-1 text-[var(--subtext0)] hover:bg-[var(--surface1)] hover:text-[var(--mauve)]"
								title="Re-parse with AI"
								onclick={() => onReparse(item.path, item.name)}
							>
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4">
									<path d="M4.464 3.162A2 2 0 0 1 6.28 2h7.44a2 2 0 0 1 1.816 1.162l1.154 2.5c.203.44.31.921.31 1.408v1.825a2.91 2.91 0 0 0-1-.175c-1.615 0-2.94 1.267-3 2.857V13.5a.5.5 0 0 1-.5.5H7.5a.5.5 0 0 1-.5-.5v-1.923C7 10.025 5.675 8.757 4.06 8.757A2.91 2.91 0 0 0 3 8.945V7.07c0-.487.107-.968.31-1.408l1.154-2.5Z" />
									<path d="M1.06 10.757C1.06 9.787 1.846 9 2.817 9h1.243c.971 0 1.757.787 1.757 1.757v.486c0 .97-.786 1.757-1.757 1.757H2.817c-.97 0-1.757-.787-1.757-1.757v-.486ZM14.183 9c-.97 0-1.757.787-1.757 1.757v.486c0 .97.787 1.757 1.757 1.757h1.243c.971 0 1.757-.787 1.757-1.757v-.486c0-.97-.786-1.757-1.757-1.757h-1.243Z" />
									<path d="M6.5 15.5a.5.5 0 0 1 .5-.5h6a.5.5 0 0 1 .5.5v1a2.5 2.5 0 0 1-2.5 2.5h-2A2.5 2.5 0 0 1 6.5 16.5v-1Z" />
								</svg>
							</button>
						{/if}
						<button
							class="shrink-0 rounded-md p-1 text-[var(--subtext0)] hover:bg-[var(--surface1)] hover:text-[var(--red)]"
							title={item.is_file ? 'Delete file (hardlink)' : 'Return to sources (unlink)'}
							onclick={() => onUnlink(item.path)}
						>
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4">
								<path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
							</svg>
						</button>
					</div>
				{/each}
			</div>
		{:else}
			<div class="rounded-lg border border-dashed border-[var(--surface1)] px-3 py-4 text-sm text-[var(--subtext0)]">
				No subdirectories yet
			</div>
		{/if}
	</div>
</div>

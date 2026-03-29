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
			<h3 class="text-base font-semibold">Library</h3>
			<p class="text-sm text-[var(--subtext0)]">Drop a source entry here to start parse and link.</p>
		</div>
		<button class="rounded-md border border-[var(--surface1)] px-2 py-1 text-xs text-[var(--subtext0)] hover:bg-[var(--surface1)]" onclick={onRemove}>
			Remove
		</button>
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
						<span class="min-w-0 flex-1 truncate">{item.name}</span>
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
						<button
							class="shrink-0 rounded-md p-1 text-[var(--subtext0)] hover:bg-[var(--surface1)] hover:text-[var(--red)]"
							title="Return to sources (unlink)"
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

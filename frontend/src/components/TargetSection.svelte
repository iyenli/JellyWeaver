<script lang="ts">
	import type { TargetContentItem, TargetSection as TargetSectionType } from '$lib/types';

	export let section: TargetSectionType;
	export let items: TargetContentItem[] = [];
	export let active = false;
	export let onChange: (patch: Partial<TargetSectionType>) => void | Promise<void> = () => {};
	export let onRemove: () => void | Promise<void> = () => {};
	export let onPickPath: () => void = () => {};
	export let onDropSource: (sourcePath: string) => void | Promise<void> = () => {};

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
				<option value="movies">movies</option>
				<option value="tv">tv</option>
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
					<div class="truncate rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2 text-sm">
						{item.name}
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

<script lang="ts">
	import TargetSection from './TargetSection.svelte';
	import type { TargetContentItem, TargetSection as TargetSectionType } from '$lib/types';

	export let targets: TargetSectionType[] = [];
	export let targetContents: Record<string, TargetContentItem[]> = {};
	export let activeSectionId: string | null = null;
	export let onAddTarget: () => void | Promise<void> = () => {};
	export let onUpdateTarget: (id: string, patch: Partial<TargetSectionType>) => void | Promise<void> = () => {};
	export let onRemoveTarget: (id: string) => void | Promise<void> = () => {};
	export let onPickPath: (id: string) => void = () => {};
	export let onDropSource: (sourcePath: string, sectionId: string) => void | Promise<void> = () => {};
	export let onUnlink: (targetFolderPath: string) => void | Promise<void> = () => {};
	export let onReparse: (targetFolderPath: string, folderName: string, sectionId: string) => void | Promise<void> = () => {};
</script>

<section class="flex min-h-[70vh] flex-col rounded-2xl border border-[var(--surface0)] bg-[var(--mantle)] p-4 shadow-lg shadow-black/20">
	<div class="mb-4 flex items-center justify-between gap-3">
		<div>
			<h2 class="text-lg font-semibold">Libraries</h2>
			<p class="text-sm text-[var(--subtext0)]">1-4 target sections for Jellyfin libraries</p>
		</div>
		<button
			class="rounded-lg bg-[var(--blue)] px-3 py-2 text-sm font-medium text-[var(--crust)] hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
			disabled={targets.length >= 4}
			onclick={onAddTarget}
		>
			Add Library
		</button>
	</div>

	<div class="flex-1 space-y-4 overflow-auto pr-1">
		{#each targets as section (section.id)}
			<TargetSection
				{section}
				items={targetContents[section.id] ?? []}
				active={activeSectionId === section.id}
				onChange={(patch) => onUpdateTarget(section.id, patch)}
				onRemove={() => onRemoveTarget(section.id)}
				onPickPath={() => onPickPath(section.id)}
				onDropSource={(sourcePath) => onDropSource(sourcePath, section.id)}
				onUnlink={(targetFolderPath) => onUnlink(targetFolderPath)}
				onReparse={(targetFolderPath, folderName) => onReparse(targetFolderPath, folderName, section.id)}
			/>
		{/each}

		{#if targets.length === 0}
			<div class="rounded-2xl border border-dashed border-[var(--surface1)] bg-[var(--base)] px-4 py-8 text-center text-sm text-[var(--subtext0)]">
				Add a library section first.
			</div>
		{/if}
	</div>
</section>

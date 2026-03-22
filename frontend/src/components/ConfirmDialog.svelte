<script lang="ts">
	import type { ParseResult, TargetMediaType } from '$lib/types';

	export let open = false;
	export let sourceName = '';
	export let value: ParseResult = { media_type: 'movie', title_en: '', title_zh: '', year: new Date().getFullYear() };
	export let targetMediaType: TargetMediaType | null = null;
	export let onClose: () => void = () => {};
	export let onConfirm: (value: ParseResult) => void | Promise<void> = () => {};

	let draft: ParseResult = value;
	$: if (open) draft = { ...value };

	function isMismatch(parseType: string, targetType: TargetMediaType | null): boolean {
		if (!targetType) return false;
		if (parseType === 'movie' && targetType === 'movies') return false;
		if (parseType === 'tv' && targetType === 'tv') return false;
		return true;
	}

	function formatType(t: string): string {
		if (t === 'movie' || t === 'movies') return 'Movie';
		return 'TV';
	}
</script>

{#if open}
	<div class="fixed inset-0 z-40 bg-black/60" role="button" tabindex="0" aria-label="Close dialog" onclick={onClose} onkeydown={(event) => event.key === 'Escape' && onClose()}></div>
	<div class="fixed left-1/2 top-1/2 z-50 w-[min(34rem,92vw)] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-[var(--surface0)] bg-[var(--mantle)] p-5 shadow-2xl shadow-black/50">
		<div class="mb-4">
			<h3 class="text-lg font-semibold">Confirm media info</h3>
			<p class="mt-1 text-sm text-[var(--subtext0)]">Source: {sourceName}</p>
		</div>

		{#if isMismatch(draft.media_type, targetMediaType)}
			<div class="mb-4 rounded-lg border border-[var(--yellow)] bg-[color:color-mix(in_srgb,var(--yellow)_12%,var(--base))] px-3 py-2 text-sm text-[var(--yellow)]">
				AI suggests this is a {formatType(draft.media_type)}, but the target library is {formatType(targetMediaType ?? '')}.
			</div>
		{/if}

		<div class="space-y-3">
			<label class="block space-y-1 text-sm">
				<span class="text-[var(--subtext0)]">Type</span>
				<select class="w-full rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2" bind:value={draft.media_type}>
					<option value="movie">Movie</option>
					<option value="tv">TV</option>
				</select>
			</label>
			<label class="block space-y-1 text-sm">
				<span class="text-[var(--subtext0)]">English title</span>
				<input class="w-full rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2" bind:value={draft.title_en} />
			</label>
			<label class="block space-y-1 text-sm">
				<span class="text-[var(--subtext0)]">Chinese title</span>
				<input class="w-full rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2" bind:value={draft.title_zh} />
			</label>
			<label class="block space-y-1 text-sm">
				<span class="text-[var(--subtext0)]">Year</span>
				<input class="w-full rounded-lg border border-[var(--surface0)] bg-[var(--base)] px-3 py-2" type="number" bind:value={draft.year} />
			</label>
		</div>

		<div class="mt-4 rounded-xl border border-[var(--surface0)] bg-[var(--base)] px-4 py-3 text-sm text-[var(--subtext0)]">
			Target: {draft.title_en || '(fill in title)'} ({draft.year || 'year'})
		</div>

		<div class="mt-5 flex justify-end gap-3">
			<button class="rounded-lg border border-[var(--surface0)] bg-[var(--surface0)] px-4 py-2 text-sm hover:bg-[var(--surface1)]" onclick={onClose}>Cancel</button>
			<button class="rounded-lg bg-[var(--blue)] px-4 py-2 text-sm font-medium text-[var(--crust)] hover:brightness-110" onclick={() => onConfirm(draft)}>
				Start link
			</button>
		</div>
	</div>
{/if}

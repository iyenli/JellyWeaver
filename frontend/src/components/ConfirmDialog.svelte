<script lang="ts">
	import type { LinkPlan, ParseResult, PlanItem, TargetMediaType } from '$lib/types';

	export let open = false;
	export let sourceName = '';
	export let value: ParseResult = { media_type: 'movie', title_en: '', title_zh: '', year: new Date().getFullYear() };
	export let targetMediaType: TargetMediaType | null = null;
	export let linkPlan: LinkPlan | null = null;
	export let linkPlanLoading = false;
	export let linkPlanError: string | null = null;
	export let onClose: () => void = () => {};
	export let onConfirm: (value: ParseResult) => void | Promise<void> = () => {};
	export let onPlanUpdate: (plan: LinkPlan) => void = () => {};

	let draft: ParseResult = value;
	let draftPlan: PlanItem[] = [];

	$: if (open) draft = { ...value };
	$: if (linkPlan) draftPlan = linkPlan.items.map((item) => ({ ...item }));

	$: isCollection = linkPlan?.structure_type === 'movie_collection';

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

	function handleConfirm() {
		if (linkPlan && draftPlan.length > 0) {
			onPlanUpdate({ ...linkPlan, items: draftPlan });
		}
		onConfirm(draft);
	}
</script>

{#if open}
	<div class="fixed inset-0 z-40 bg-black/60" role="button" tabindex="0" aria-label="Close dialog" onclick={onClose} onkeydown={(event) => event.key === 'Escape' && onClose()}></div>
	<div class="fixed left-1/2 top-1/2 z-50 w-[min(42rem,92vw)] max-h-[85vh] overflow-y-auto -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-[var(--surface0)] bg-[var(--mantle)] p-5 shadow-2xl shadow-black/50">
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

		<!-- Link Plan Section -->
		<div class="mt-4">
			<div class="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--subtext0)]">Link Plan</div>

			{#if linkPlanLoading}
				<div class="flex items-center gap-2 rounded-lg border border-dashed border-[var(--surface1)] px-4 py-3 text-sm text-[var(--subtext0)]">
					<span class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-[var(--blue)] border-t-transparent"></span>
					Analyzing directory structure...
				</div>
			{:else if linkPlanError}
				<div class="rounded-lg border border-[var(--yellow)] bg-[color:color-mix(in_srgb,var(--yellow)_12%,var(--base))] px-3 py-2 text-sm text-[var(--yellow)]">
					{linkPlanError} — will use automatic file detection.
				</div>
			{:else if linkPlan && draftPlan.length > 0}
				<div class="overflow-x-auto rounded-lg border border-[var(--surface0)]">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-[var(--surface0)] bg-[var(--base)] text-left text-xs uppercase text-[var(--subtext0)]">
								<th class="px-3 py-2">Source</th>
								{#if isCollection}
									<th class="px-3 py-2">Title</th>
									<th class="px-3 py-2 w-20">Year</th>
								{:else}
									<th class="px-3 py-2">Target</th>
								{/if}
								<th class="px-3 py-2 w-16 text-right">Files</th>
							</tr>
						</thead>
						<tbody>
							{#each draftPlan as item, i}
								<tr class="border-b border-[var(--surface0)] last:border-0">
									<td class="px-3 py-2 truncate max-w-[12rem] text-[var(--subtext0)]" title={item.source_subdir || '(root)'}>
										{item.source_subdir || '(root)'}
									</td>
									{#if isCollection}
										<td class="px-3 py-1">
											<input
												class="w-full rounded border border-[var(--surface0)] bg-[var(--base)] px-2 py-1 text-sm"
												bind:value={draftPlan[i].title_en}
											/>
										</td>
										<td class="px-3 py-1">
											<input
												class="w-full rounded border border-[var(--surface0)] bg-[var(--base)] px-2 py-1 text-sm"
												type="number"
												bind:value={draftPlan[i].year}
											/>
										</td>
									{:else}
										<td class="px-3 py-1">
											<input
												class="w-full rounded border border-[var(--surface0)] bg-[var(--base)] px-2 py-1 text-sm"
												bind:value={draftPlan[i].target_subdir}
											/>
										</td>
									{/if}
									<td class="px-3 py-2 text-right text-[var(--subtext0)]">{item.file_count}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<div class="rounded-lg border border-dashed border-[var(--surface1)] px-4 py-3 text-sm text-[var(--subtext0)]">
					No structure analysis available — will use automatic file detection.
				</div>
			{/if}
		</div>

		<div class="mt-5 flex justify-end gap-3">
			<button class="rounded-lg border border-[var(--surface0)] bg-[var(--surface0)] px-4 py-2 text-sm hover:bg-[var(--surface1)]" onclick={onClose}>Cancel</button>
			<button class="rounded-lg bg-[var(--blue)] px-4 py-2 text-sm font-medium text-[var(--crust)] hover:brightness-110" onclick={handleConfirm}>
				Start link
			</button>
		</div>
	</div>
{/if}

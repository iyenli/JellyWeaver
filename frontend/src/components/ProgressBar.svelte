<script lang="ts">
	export let progress: { taskId: string; current: number; total: number } | null = null;

	$: percent = progress && progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;
</script>

{#if progress}
	<div class="fixed bottom-6 right-6 z-40 w-[22rem] rounded-2xl border border-[var(--surface0)] bg-[var(--mantle)] p-4 shadow-2xl shadow-black/40">
		<div class="mb-2 flex items-center justify-between text-sm">
			<span class="font-medium">Linking files</span>
			<span class="text-[var(--subtext0)]">{progress.taskId}</span>
		</div>

		<div class="mb-2 h-2 overflow-hidden rounded-full bg-[var(--surface0)]">
			<div class="h-full bg-[var(--blue)] transition-all" style={`width:${percent}%`}></div>
		</div>

		<div class="text-xs text-[var(--subtext0)]">
			{#if progress.total > 0}
				{progress.current} / {progress.total} files
			{:else}
				Preparing...
			{/if}
		</div>
	</div>
{/if}

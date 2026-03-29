<script lang="ts">
	export let wsConnected = false;
	export let onRefresh: () => void | Promise<void> = () => {};
	export let onReconcile: () => void | Promise<void> = () => {};
	export let onOpenSettings: () => void = () => {};

	let reconciling = false;
	async function handleReconcile() {
		reconciling = true;
		try { await onReconcile(); } finally { reconciling = false; }
	}
</script>

<div class="min-h-screen bg-[var(--base)] text-[var(--text)]">
	<header class="sticky top-0 z-10 border-b border-[var(--surface0)] bg-[color:color-mix(in_srgb,var(--mantle)_88%,transparent)] backdrop-blur">
		<div class="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
			<div>
				<h1 class="text-2xl font-bold text-[var(--lavender)]">Jelly Weaver</h1>
				<p class="text-sm text-[var(--subtext0)]">PT download organizer for Jellyfin</p>
			</div>

			<div class="flex items-center gap-3">
				<div class="flex items-center gap-2 rounded-full border border-[var(--surface0)] bg-[var(--mantle)] px-3 py-1.5 text-sm text-[var(--subtext0)]">
					<span class={`h-2.5 w-2.5 rounded-full ${wsConnected ? 'bg-[var(--green)]' : 'bg-[var(--red)]'}`}></span>
					<span>{wsConnected ? 'WebSocket connected' : 'WebSocket offline'}</span>
				</div>

				<button class="rounded-lg border border-[var(--surface0)] bg-[var(--surface0)] px-4 py-2 text-sm hover:bg-[var(--surface1)]" onclick={onRefresh}>
					Refresh
				</button>
				<button
					class="rounded-lg border px-4 py-2 text-sm transition-colors disabled:opacity-50
						{reconciling
							? 'border-[var(--sky)] bg-[color:color-mix(in_srgb,var(--sky)_12%,var(--surface0))] text-[var(--sky)]'
							: 'border-[var(--surface0)] bg-[var(--surface0)] hover:border-[var(--sky)] hover:text-[var(--sky)]'}"
					disabled={reconciling}
					onclick={handleReconcile}
					title="重新扫描并更新所有条目状态（不清除 LLM 缓存）"
				>
					{reconciling ? '重建中…' : '重建状态'}
				</button>
				<button class="rounded-lg border border-[var(--surface0)] bg-[var(--surface0)] px-4 py-2 text-sm hover:bg-[var(--surface1)]" onclick={onOpenSettings}>
					Settings
				</button>
			</div>
		</div>
	</header>

	<main class="mx-auto max-w-7xl px-6 py-6">
		<slot />
	</main>
</div>

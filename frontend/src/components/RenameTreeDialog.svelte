<script lang="ts">
	import type { CompanionFile, MediaType, RenameNode, TargetSection } from '$lib/types';
	import RenameTreeView from './RenameTreeView.svelte';

	export let open = false;
	export let sourceName = '';
	export let targets: TargetSection[] = [];
	export let initialSectionId: string = '';
	export let tree: RenameNode | null = null;
	export let loading = false;
	export let error: string | null = null;
	export let mediaType: MediaType | null = null;
	export let resolvedCount = 0;
	export let totalDirCount = 0;
	export let companionFiles: CompanionFile[] = [];
	export let onClose: () => void;
	export let onConfirm: (tree: RenameNode, mediaType: MediaType, sectionId: string, companionPaths: string[]) => void | Promise<void>;

	let regenLoadingKeys = new Set<string>();
	let localMediaType: MediaType = mediaType ?? 'tv';
	$: localMediaType = mediaType ?? 'tv';

	let localSectionId: string = initialSectionId;
	$: if (open) localSectionId = initialSectionId;

	// Companion file selection: reset whenever the list changes
	let selectedCompanionPaths = new Set<string>();
	$: {
		companionFiles;
		selectedCompanionPaths = new Set(companionFiles.map((c) => c.path));
	}

	function toggleCompanion(path: string) {
		const next = new Set(selectedCompanionPaths);
		if (next.has(path)) next.delete(path);
		else next.add(path);
		selectedCompanionPaths = next;
	}

	// When LLM resolves media type, auto-switch to first matching library
	$: if (mediaType) {
		const targetMediaType = mediaType === 'movie' ? 'movies' : 'tv';
		const match = targets.find((t) => t.media_type === targetMediaType);
		if (match) localSectionId = match.id;
	}

	$: sectionName = targets.find((t) => t.id === localSectionId)?.name ?? '';

	$: if (tree) totalDirCount = countDirs(tree);
	function countDirs(n: RenameNode): number {
		return (n.is_dir ? 1 : 0) + n.children.reduce((a, c) => a + countDirs(c), 0);
	}

	$: canConfirm = tree !== null && !loading && !error && !!localSectionId;

	function updateNode(root: RenameNode, key: string, updater: (n: RenameNode) => void): RenameNode {
		function walk(n: RenameNode): RenameNode {
			if (n.key === key) {
				const copy = { ...n, children: n.children.map(walk) };
				updater(copy);
				return copy;
			}
			return { ...n, children: n.children.map(walk) };
		}
		return walk(root);
	}

	function handleAccept(key: string, name: string) {
		if (!tree) return;
		tree = updateNode(tree, key, (n) => { n.accepted_name = name; });
	}
	function handleKeep(key: string) {
		if (!tree) return;
		tree = updateNode(tree, key, (n) => { n.accepted_name = n.name; });
	}
	function handleEdit(key: string, name: string) {
		if (!tree) return;
		tree = updateNode(tree, key, (n) => { n.accepted_name = name; });
	}
	async function handleRegenerate(key: string) {
		regenLoadingKeys = new Set([...regenLoadingKeys, key]);
		// placeholder — future: call targeted regen endpoint
		setTimeout(() => { regenLoadingKeys = new Set([...regenLoadingKeys].filter((k) => k !== key)); }, 500);
	}

	async function handleConfirm() {
		if (!tree || !localMediaType || !localSectionId) return;
		const rootAccepted = tree.accepted_name ?? tree.suggested_name ?? tree.name;
		const companionPaths = [...selectedCompanionPaths];
		await onConfirm({ ...tree, accepted_name: rootAccepted }, localMediaType, localSectionId, companionPaths);
	}

	export function applyNodeUpdate(key: string, suggestedName: string) {
		if (!tree) return;
		tree = updateNode(tree, key, (n) => {
			n.suggested_name = suggestedName;
			if (n.accepted_name === null) n.accepted_name = suggestedName;
		});
		regenLoadingKeys = new Set([...regenLoadingKeys].filter((k) => k !== key));
	}

	export function applyTreeDone(newTree: RenameNode, detectedMediaType: MediaType) {
		tree = newTree;
		mediaType = detectedMediaType;
		localMediaType = detectedMediaType;
		loading = false;
	}
</script>

{#if open}
	<div class="backdrop" onclick={onClose} role="presentation"></div>

	<div class="dialog" role="dialog" aria-modal="true">
		<!-- Header -->
		<div class="dialog-header">
			<div>
				<div class="header-title">重命名目录树</div>
				<div class="header-sub">{sourceName} → {sectionName}</div>
			</div>
			<button class="close-btn" onclick={onClose}>✕</button>
		</div>

		<!-- Meta row -->
		<div class="meta-row">
			<div class="type-group">
				<span class="meta-label">类型</span>
				<div class="type-btns">
					<button class="type-btn" class:active={localMediaType === 'movie'} onclick={() => (localMediaType = 'movie')}>🎬 电影</button>
					<button class="type-btn" class:active={localMediaType === 'tv'}    onclick={() => (localMediaType = 'tv')}>📺 剧集</button>
				</div>
			</div>

			<div class="library-group">
				<span class="meta-label">目标库</span>
				<select class="library-select" bind:value={localSectionId}>
					{#each targets as t}
						<option value={t.id}>{t.name}</option>
					{/each}
				</select>
			</div>

			{#if loading}
				<span class="progress-text">⏳ 分析中… {resolvedCount}/{totalDirCount}</span>
			{:else if tree}
				<span class="done-badge">✓ {totalDirCount} 个目录已分析</span>
			{/if}
		</div>

		{#if error}
			<div class="error-bar">⚠ {error}</div>
		{/if}

		{#if companionFiles.length > 0}
			<div class="companion-bar">
				<div class="companion-header">
					<span class="companion-icon">📎</span>
					<span>发现 {companionFiles.length} 个伴随文件（勾选后一起 link）</span>
				</div>
				<div class="companion-list">
					{#each companionFiles as cf (cf.path)}
						<label class="companion-item">
							<input
								type="checkbox"
								checked={selectedCompanionPaths.has(cf.path)}
								onchange={() => toggleCompanion(cf.path)}
								class="companion-check"
							/>
							<span class="companion-name">{cf.name}</span>
						</label>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Tree -->
		<div class="tree-scroll">
			{#if !tree && loading}
				<div class="loading-center">
					<span class="spin">⏳</span>
					<p>正在构建目录树…</p>
				</div>
			{:else if tree}
				<RenameTreeView
					node={tree}
					isRoot={true}
					onAccept={handleAccept}
					onRegenerate={handleRegenerate}
					onKeep={handleKeep}
					onEdit={handleEdit}
					{regenLoadingKeys}
				/>
			{/if}
		</div>

		<!-- Footer -->
		<div class="dialog-footer">
			<button class="btn-cancel" onclick={onClose}>取消</button>
			<button class="btn-confirm" disabled={!canConfirm} onclick={handleConfirm}>
				{loading ? '⏳ 分析中…' : '开始 Link'}
			</button>
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.65);
		z-index: 200;
	}

	.dialog {
		position: fixed;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		z-index: 201;
		width: min(800px, 96vw);
		max-height: 88vh;
		display: flex;
		flex-direction: column;
		background: var(--mantle);
		border: 1px solid var(--surface1);
		border-radius: 12px;
		box-shadow: 0 24px 80px rgba(0, 0, 0, 0.7);
		overflow: hidden;
	}

	.dialog-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 14px 18px 12px;
		border-bottom: 1px solid var(--surface0);
		flex-shrink: 0;
	}
	.header-title { font-weight: 600; color: var(--text); font-size: 0.95rem; }
	.header-sub { color: var(--subtext0); font-size: 0.74rem; font-family: monospace; margin-top: 2px; }
	.close-btn {
		background: none; border: none; color: var(--overlay1);
		cursor: pointer; font-size: 1rem; padding: 4px 6px;
		border-radius: 4px; transition: color 0.15s;
	}
	.close-btn:hover { color: var(--text); }

	.meta-row {
		display: flex; align-items: center; gap: 16px;
		padding: 9px 18px;
		border-bottom: 1px solid var(--surface0);
		flex-shrink: 0;
		background: var(--base);
	}
	.meta-label { font-size: 0.76rem; color: var(--subtext0); margin-right: 6px; }
	.type-group { display: flex; align-items: center; }
	.type-btns { display: flex; gap: 4px; }
	.type-btn {
		background: var(--surface0);
		border: 1px solid var(--surface2);
		border-radius: 5px;
		color: var(--subtext0);
		cursor: pointer; padding: 3px 11px; font-size: 0.78rem;
		transition: background 0.1s, color 0.1s;
	}
	.type-btn.active { background: var(--blue); border-color: var(--blue); color: var(--base); font-weight: 500; }

	.library-group { display: flex; align-items: center; }
	.library-select {
		background: var(--surface0);
		border: 1px solid var(--surface2);
		border-radius: 5px;
		color: var(--text);
		cursor: pointer; padding: 3px 8px; font-size: 0.78rem;
		outline: none;
	}
	.library-select:focus { border-color: var(--blue); }

	.progress-text { color: var(--yellow); font-size: 0.8rem; }
	.done-badge { color: var(--green); font-size: 0.8rem; }

	.error-bar {
		background: color-mix(in srgb, var(--red) 15%, transparent);
		border-left: 3px solid var(--red);
		color: var(--red);
		padding: 7px 18px; font-size: 0.8rem; flex-shrink: 0;
	}

	.companion-bar {
		border-left: 3px solid var(--teal);
		background: color-mix(in srgb, var(--teal) 8%, transparent);
		padding: 8px 18px; flex-shrink: 0;
	}
	.companion-header {
		display: flex; align-items: center; gap: 6px;
		color: var(--teal); font-size: 0.78rem; margin-bottom: 5px;
	}
	.companion-icon { font-size: 0.85rem; }
	.companion-list { display: flex; flex-wrap: wrap; gap: 4px 12px; }
	.companion-item {
		display: flex; align-items: center; gap: 5px;
		cursor: pointer; font-size: 0.76rem; color: var(--subtext0);
	}
	.companion-item:hover { color: var(--text); }
	.companion-check { accent-color: var(--teal); cursor: pointer; }
	.companion-name { font-family: monospace; }

	.tree-scroll {
		flex: 1; overflow-y: auto;
		padding: 12px 14px;
		background: var(--base);
	}

	.loading-center {
		display: flex; flex-direction: column; align-items: center;
		justify-content: center; gap: 10px; padding: 48px 0;
		color: var(--subtext0);
	}
	.spin { font-size: 2rem; animation: spin 1.2s linear infinite; display: inline-block; }
	@keyframes spin { to { transform: rotate(360deg); } }

	.dialog-footer {
		display: flex; justify-content: flex-end; gap: 10px;
		padding: 11px 18px;
		border-top: 1px solid var(--surface0);
		flex-shrink: 0;
		background: var(--mantle);
	}
	.btn-cancel {
		background: var(--surface0); border: 1px solid var(--surface2);
		border-radius: 6px; color: var(--subtext0); cursor: pointer;
		padding: 6px 18px; font-size: 0.86rem;
		transition: background 0.1s;
	}
	.btn-cancel:hover { background: var(--surface1); }

	.btn-confirm {
		background: var(--blue); border: none; border-radius: 6px;
		color: var(--base); cursor: pointer;
		padding: 6px 22px; font-size: 0.86rem; font-weight: 600;
		transition: opacity 0.15s;
	}
	.btn-confirm:disabled { opacity: 0.4; cursor: not-allowed; }
	.btn-confirm:not(:disabled):hover { opacity: 0.85; }
</style>

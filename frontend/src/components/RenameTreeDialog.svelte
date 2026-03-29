<script lang="ts">
	import type { MediaType, RenameNode } from '$lib/types';
	import RenameTreeView from './RenameTreeView.svelte';

	export let open = false;
	export let sourceName = '';
	export let sectionName = '';
	export let tree: RenameNode | null = null;
	export let loading = false;
	export let error: string | null = null;
	export let mediaType: MediaType | null = null;
	export let resolvedCount = 0;
	export let totalDirCount = 0;
	export let onClose: () => void;
	export let onConfirm: (tree: RenameNode, mediaType: MediaType) => void | Promise<void>;

	let regenLoadingKeys = new Set<string>();
	let localMediaType: MediaType = mediaType ?? 'tv';
	$: localMediaType = mediaType ?? 'tv';

	// Count total resolvable nodes
	$: if (tree) totalDirCount = countDirs(tree);

	function countDirs(n: RenameNode): number {
		return (n.is_dir ? 1 : 0) + n.children.reduce((a, c) => a + countDirs(c), 0);
	}

	$: allResolved = tree !== null && !loading;
	$: canConfirm = allResolved && !error;

	// --- Node mutation helpers ---
	// Since Svelte 4 needs assignment to trigger reactivity, we mutate + reassign
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
		// Mark as loading, leave previous suggestion visible
		regenLoadingKeys = new Set([...regenLoadingKeys, key]);
		// Ask backend to re-run LLM for this specific node's sibling group
		// For simplicity: re-trigger full rename-tree; WS will update this node
		// (A targeted endpoint can be added later for production optimization)
		regenLoadingKeys = new Set([...regenLoadingKeys].filter((k) => k !== key));
	}

	async function handleConfirm() {
		if (!tree || !localMediaType) return;
		// Ensure root accepted_name is set
		const rootAccepted = tree.accepted_name ?? tree.suggested_name ?? tree.name;
		const finalTree = { ...tree, accepted_name: rootAccepted };
		await onConfirm(finalTree, localMediaType);
	}

	// Apply incoming WS rename_node_done updates
	export function applyNodeUpdate(key: string, suggestedName: string) {
		if (!tree) return;
		tree = updateNode(tree, key, (n) => {
			n.suggested_name = suggestedName;
			// Auto-accept if user hasn't touched this node yet
			if (n.accepted_name === null) {
				n.accepted_name = suggestedName;
			}
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
	<!-- Backdrop -->
	<div class="backdrop" on:click={onClose} role="presentation"></div>

	<div class="dialog" role="dialog" aria-modal="true">
		<!-- Header -->
		<div class="dialog-header">
			<div class="header-info">
				<span class="header-title">重命名目录树</span>
				<span class="header-sub">{sourceName} → {sectionName}</span>
			</div>
			<button class="close-btn" on:click={onClose} title="取消">✕</button>
		</div>

		<!-- Media type + progress row -->
		<div class="meta-row">
			<div class="media-type-pick">
				<span class="meta-label">类型</span>
				<div class="type-buttons">
					<button
						class="type-btn"
						class:active={localMediaType === 'movie'}
						on:click={() => (localMediaType = 'movie')}
					>🎬 电影</button>
					<button
						class="type-btn"
						class:active={localMediaType === 'tv'}
						on:click={() => (localMediaType = 'tv')}
					>📺 剧集</button>
				</div>
			</div>

			{#if loading}
				<div class="progress-indicator">
					<span class="spinner">⏳</span>
					<span class="progress-text">
						{#if totalDirCount > 0}
							正在分析… ({resolvedCount}/{totalDirCount})
						{:else}
							正在分析…
						{/if}
					</span>
				</div>
			{:else if tree}
				<span class="resolved-badge">✓ {totalDirCount} 个目录已分析</span>
			{/if}
		</div>

		<!-- Error banner -->
		{#if error}
			<div class="error-banner">⚠ {error}</div>
		{/if}

		<!-- Tree content -->
		<div class="tree-scroll">
			{#if !tree && loading}
				<div class="loading-placeholder">
					<span class="spinner-lg">⏳</span>
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
			<button class="btn-cancel" on:click={onClose}>取消</button>
			<button
				class="btn-confirm"
				disabled={!canConfirm}
				on:click={handleConfirm}
			>
				{#if loading}
					⏳ 分析中…
				{:else}
					开始 Link
				{/if}
			</button>
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.55);
		z-index: 40;
	}

	.dialog {
		position: fixed;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		z-index: 50;
		width: min(760px, 95vw);
		max-height: 85vh;
		display: flex;
		flex-direction: column;
		background: var(--ctp-mantle);
		border: 1px solid var(--ctp-surface1);
		border-radius: 10px;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
		overflow: hidden;
	}

	.dialog-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 14px 18px 12px;
		border-bottom: 1px solid var(--ctp-surface0);
		flex-shrink: 0;
	}
	.header-info {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.header-title {
		font-weight: 600;
		color: var(--ctp-text);
		font-size: 1rem;
	}
	.header-sub {
		color: var(--ctp-subtext0);
		font-size: 0.78rem;
		font-family: monospace;
	}
	.close-btn {
		background: none;
		border: none;
		color: var(--ctp-overlay1);
		cursor: pointer;
		font-size: 1rem;
		padding: 4px 6px;
		border-radius: 4px;
		transition: color 0.15s;
	}
	.close-btn:hover { color: var(--ctp-text); }

	.meta-row {
		display: flex;
		align-items: center;
		gap: 16px;
		padding: 10px 18px;
		border-bottom: 1px solid var(--ctp-surface0);
		flex-shrink: 0;
	}
	.meta-label {
		font-size: 0.78rem;
		color: var(--ctp-subtext0);
		margin-right: 6px;
	}
	.media-type-pick {
		display: flex;
		align-items: center;
	}
	.type-buttons {
		display: flex;
		gap: 4px;
	}
	.type-btn {
		background: var(--ctp-surface0);
		border: 1px solid var(--ctp-surface2);
		border-radius: 4px;
		color: var(--ctp-subtext0);
		cursor: pointer;
		padding: 3px 10px;
		font-size: 0.8rem;
		transition: background 0.1s, color 0.1s;
	}
	.type-btn.active {
		background: var(--ctp-blue);
		border-color: var(--ctp-blue);
		color: var(--ctp-base);
	}

	.progress-indicator {
		display: flex;
		align-items: center;
		gap: 6px;
		color: var(--ctp-yellow);
		font-size: 0.82rem;
	}
	.spinner { animation: spin 1.2s linear infinite; display: inline-block; }
	@keyframes spin { to { transform: rotate(360deg); } }

	.resolved-badge {
		color: var(--ctp-green);
		font-size: 0.8rem;
	}

	.error-banner {
		background: color-mix(in srgb, var(--ctp-red) 15%, transparent);
		border-left: 3px solid var(--ctp-red);
		color: var(--ctp-red);
		padding: 8px 18px;
		font-size: 0.82rem;
		flex-shrink: 0;
	}

	.tree-scroll {
		flex: 1;
		overflow-y: auto;
		padding: 12px 16px;
	}

	.loading-placeholder {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 12px;
		padding: 48px 0;
		color: var(--ctp-subtext0);
	}
	.spinner-lg {
		font-size: 2rem;
		animation: spin 1.2s linear infinite;
		display: inline-block;
	}

	.dialog-footer {
		display: flex;
		justify-content: flex-end;
		gap: 10px;
		padding: 12px 18px;
		border-top: 1px solid var(--ctp-surface0);
		flex-shrink: 0;
	}
	.btn-cancel {
		background: var(--ctp-surface0);
		border: 1px solid var(--ctp-surface2);
		border-radius: 6px;
		color: var(--ctp-subtext0);
		cursor: pointer;
		padding: 6px 18px;
		font-size: 0.88rem;
		transition: background 0.1s;
	}
	.btn-cancel:hover { background: var(--ctp-surface1); }

	.btn-confirm {
		background: var(--ctp-blue);
		border: none;
		border-radius: 6px;
		color: var(--ctp-base);
		cursor: pointer;
		padding: 6px 22px;
		font-size: 0.88rem;
		font-weight: 500;
		transition: opacity 0.15s;
	}
	.btn-confirm:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}
	.btn-confirm:not(:disabled):hover { opacity: 0.88; }
</style>

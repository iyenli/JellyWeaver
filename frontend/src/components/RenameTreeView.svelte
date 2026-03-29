<script lang="ts">
	import type { RenameNode } from '$lib/types';

	export let node: RenameNode;
	export let isRoot = false;
	// Callbacks from parent
	export let onAccept: (key: string, name: string) => void;
	export let onRegenerate: (key: string) => void;
	export let onKeep: (key: string) => void;
	export let onEdit: (key: string, name: string) => void;
	export let regenLoadingKeys: Set<string> = new Set();

	let collapsed = !isRoot && node.depth > 0;

	$: dirChildren = node.children.filter((c) => c.is_dir);
	$: effective = node.accepted_name ?? node.suggested_name ?? node.name;
	$: isKept = node.accepted_name === node.name && node.suggested_name !== node.name;
	$: isAccepted = node.accepted_name !== null && node.accepted_name !== node.name;
	$: isEdited = node.accepted_name !== null && node.accepted_name !== (node.suggested_name ?? node.name);
	$: isLoading = regenLoadingKeys.has(node.key);
	$: hasAllChildrenResolved = dirChildren.every((c) => c.suggested_name !== null || regenLoadingKeys.has(c.key) === false);

	function handleAccept() {
		onAccept(node.key, node.suggested_name ?? node.name);
	}
	function handleKeep() {
		onKeep(node.key);
	}
	function handleRegen() {
		onRegenerate(node.key);
	}
	function handleEditInput(e: Event) {
		onEdit(node.key, (e.target as HTMLInputElement).value);
	}
	function acceptAll() {
		acceptSubtree(node);
	}
	function keepAll() {
		keepSubtree(node);
	}
	function regenAll() {
		regenSubtree(node);
	}

	function acceptSubtree(n: RenameNode) {
		if (n.is_dir) {
			onAccept(n.key, n.suggested_name ?? n.name);
			n.children.forEach((c) => c.is_dir && acceptSubtree(c));
		}
	}
	function keepSubtree(n: RenameNode) {
		if (n.is_dir) {
			onKeep(n.key);
			n.children.forEach((c) => c.is_dir && keepSubtree(c));
		}
	}
	function regenSubtree(n: RenameNode) {
		if (n.is_dir) {
			onRegenerate(n.key);
			n.children.forEach((c) => c.is_dir && regenSubtree(c));
		}
	}
</script>

<div class="rename-node" style="--indent: {node.depth * 16}px">
	<div class="node-row" class:root-row={isRoot}>
		<!-- Collapse toggle for non-root nodes with children -->
		{#if !isRoot && dirChildren.length > 0}
			<button class="collapse-btn" on:click={() => (collapsed = !collapsed)} title={collapsed ? 'Expand' : 'Collapse'}>
				<span class="icon">{collapsed ? '▶' : '▼'}</span>
			</button>
		{:else}
			<span class="collapse-spacer"></span>
		{/if}

		<!-- Folder icon -->
		<span class="folder-icon">📁</span>

		<!-- Original name -->
		<span class="original-name" title={node.name}>{node.name}</span>

		<span class="arrow">→</span>

		<!-- Editable suggested name -->
		{#if isLoading}
			<span class="spinner-label">⏳ 生成中…</span>
		{:else}
			<input
				class="name-input"
				class:accepted={isAccepted}
				class:kept={isKept}
				class:edited={isEdited}
				class:pending={!node.suggested_name}
				value={effective}
				placeholder={node.suggested_name ? '' : '等待 LLM…'}
				disabled={!node.suggested_name && !node.accepted_name}
				on:input={handleEditInput}
			/>
		{/if}

		<!-- File count badge -->
		<span class="file-count" title="{node.file_count} media files">{node.file_count}f</span>

		<!-- Per-row action buttons -->
		{#if !isLoading && node.suggested_name}
			<div class="row-actions">
				<button class="btn-accept" on:click={handleAccept} title="接受建议名">✓</button>
				<button class="btn-regen" on:click={handleRegen} title="重新生成">↻</button>
				<button class="btn-keep" on:click={handleKeep} title="保留原名">—</button>
			</div>
		{/if}
	</div>

	<!-- Bulk controls for this level's children -->
	{#if !isRoot && dirChildren.length > 1 && !collapsed}
		<div class="bulk-bar" style="padding-left: calc({node.depth * 16}px + 48px)">
			<span class="bulk-label">全部子目录：</span>
			<button class="bulk-btn" on:click={acceptAll}>✓ 接受</button>
			<button class="bulk-btn" on:click={regenAll}>↻ 重新生成</button>
			<button class="bulk-btn" on:click={keepAll}>— 保留</button>
		</div>
	{/if}

	<!-- Root-level bulk controls always visible -->
	{#if isRoot && dirChildren.length > 0}
		<div class="bulk-bar root-bulk">
			<span class="bulk-label">全部子目录：</span>
			<button class="bulk-btn" on:click={acceptAll}>✓ 全部接受</button>
			<button class="bulk-btn" on:click={regenAll}>↻ 全部重新生成</button>
			<button class="bulk-btn" on:click={keepAll}>— 全部保留</button>
		</div>
	{/if}

	<!-- Children -->
	{#if !collapsed && dirChildren.length > 0}
		<div class="children">
			{#each dirChildren as child (child.key)}
				<svelte:self
					node={child}
					{onAccept}
					{onRegenerate}
					{onKeep}
					{onEdit}
					{regenLoadingKeys}
				/>
			{/each}
		</div>
	{/if}
</div>

<!-- Sample files tooltip hint (shown on hover via CSS) -->
{#if node.sample_files.length > 0}
	<div class="samples-hint" style="padding-left: calc({node.depth * 16}px + 48px)">
		<span class="samples-label">例：{node.sample_files.slice(0, 3).join(' · ')}</span>
	</div>
{/if}

<style>
	.rename-node {
		font-size: 0.85rem;
	}

	.node-row {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 4px 6px 4px calc(var(--indent) + 4px);
		border-radius: 4px;
		transition: background 0.1s;
	}
	.node-row:hover {
		background: color-mix(in srgb, var(--ctp-surface0) 60%, transparent);
	}
	.root-row {
		background: color-mix(in srgb, var(--ctp-surface1) 40%, transparent);
		border-radius: 6px;
		padding: 6px 8px;
		margin-bottom: 4px;
	}

	.collapse-btn {
		background: none;
		border: none;
		cursor: pointer;
		color: var(--ctp-overlay1);
		padding: 0 2px;
		font-size: 0.7rem;
		flex-shrink: 0;
	}
	.collapse-spacer {
		width: 18px;
		flex-shrink: 0;
	}

	.folder-icon {
		flex-shrink: 0;
		font-size: 0.9rem;
	}

	.original-name {
		color: var(--ctp-subtext0);
		max-width: 200px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		flex-shrink: 0;
		font-family: monospace;
		font-size: 0.8rem;
	}

	.arrow {
		color: var(--ctp-overlay1);
		flex-shrink: 0;
	}

	.name-input {
		flex: 1;
		min-width: 120px;
		background: var(--ctp-surface0);
		border: 1px solid var(--ctp-surface2);
		border-radius: 4px;
		color: var(--ctp-text);
		padding: 2px 6px;
		font-size: 0.85rem;
		font-family: inherit;
		transition: border-color 0.15s;
	}
	.name-input:focus {
		outline: none;
		border-color: var(--ctp-blue);
	}
	.name-input.accepted {
		border-color: var(--ctp-green);
		color: var(--ctp-green);
	}
	.name-input.kept {
		border-color: var(--ctp-overlay1);
		color: var(--ctp-subtext0);
		text-decoration: line-through;
	}
	.name-input.edited {
		border-color: var(--ctp-yellow);
	}
	.name-input.pending {
		border-color: var(--ctp-surface2);
		color: var(--ctp-overlay0);
		font-style: italic;
	}
	.name-input:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.spinner-label {
		flex: 1;
		color: var(--ctp-overlay1);
		font-style: italic;
		font-size: 0.8rem;
	}

	.file-count {
		color: var(--ctp-overlay0);
		font-size: 0.72rem;
		flex-shrink: 0;
		min-width: 24px;
		text-align: right;
	}

	.row-actions {
		display: flex;
		gap: 2px;
		flex-shrink: 0;
	}
	.row-actions button {
		background: none;
		border: 1px solid var(--ctp-surface2);
		border-radius: 3px;
		color: var(--ctp-subtext0);
		cursor: pointer;
		padding: 1px 5px;
		font-size: 0.78rem;
		transition: background 0.1s, color 0.1s;
	}
	.btn-accept:hover { background: var(--ctp-green); color: var(--ctp-base); border-color: var(--ctp-green); }
	.btn-regen:hover  { background: var(--ctp-blue);  color: var(--ctp-base); border-color: var(--ctp-blue); }
	.btn-keep:hover   { background: var(--ctp-overlay1); color: var(--ctp-base); border-color: var(--ctp-overlay1); }

	.bulk-bar {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 3px 6px;
		margin: 2px 0;
		background: color-mix(in srgb, var(--ctp-surface0) 30%, transparent);
		border-radius: 4px;
	}
	.root-bulk {
		padding-left: 12px;
		margin-bottom: 8px;
	}
	.bulk-label {
		color: var(--ctp-overlay1);
		font-size: 0.75rem;
		flex-shrink: 0;
	}
	.bulk-btn {
		background: none;
		border: 1px solid var(--ctp-surface2);
		border-radius: 3px;
		color: var(--ctp-subtext0);
		cursor: pointer;
		padding: 1px 7px;
		font-size: 0.75rem;
		transition: background 0.1s;
	}
	.bulk-btn:hover { background: var(--ctp-surface1); }

	.children {
		border-left: 1px solid var(--ctp-surface1);
		margin-left: calc(var(--indent) + 14px);
		padding-left: 0;
	}

	.samples-hint {
		margin-bottom: 1px;
	}
	.samples-label {
		color: var(--ctp-overlay0);
		font-size: 0.72rem;
		font-family: monospace;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		display: block;
	}
</style>

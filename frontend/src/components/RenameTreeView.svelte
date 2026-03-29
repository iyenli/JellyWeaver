<script lang="ts">
	import type { RenameNode } from '$lib/types';

	export let node: RenameNode;
	export let isRoot = false;
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

	function handleAccept() { onAccept(node.key, node.suggested_name ?? node.name); }
	function handleKeep() { onKeep(node.key); }
	function handleRegen() { onRegenerate(node.key); }
	function handleEditInput(e: Event) { onEdit(node.key, (e.target as HTMLInputElement).value); }

	function acceptSubtree(n: RenameNode) {
		if (n.is_dir) { onAccept(n.key, n.suggested_name ?? n.name); n.children.forEach((c) => c.is_dir && acceptSubtree(c)); }
	}
	function keepSubtree(n: RenameNode) {
		if (n.is_dir) { onKeep(n.key); n.children.forEach((c) => c.is_dir && keepSubtree(c)); }
	}
	function regenSubtree(n: RenameNode) {
		if (n.is_dir) { onRegenerate(n.key); n.children.forEach((c) => c.is_dir && regenSubtree(c)); }
	}
</script>

<div class="rename-node" style="--indent: {node.depth * 16}px">
	<div class="node-row" class:root-row={isRoot}>
		{#if !isRoot && dirChildren.length > 0}
			<button class="collapse-btn" on:click={() => (collapsed = !collapsed)} title={collapsed ? 'Expand' : 'Collapse'}>
				{collapsed ? '▶' : '▼'}
			</button>
		{:else}
			<span class="collapse-spacer"></span>
		{/if}

		<span class="folder-icon">📁</span>
		<span class="original-name" title={node.name}>{node.name}</span>
		<span class="arrow">→</span>

		{#if isLoading}
			<span class="spinner-label">⏳ 生成中…</span>
		{:else}
			<input
				class="name-input"
				class:accepted={isAccepted}
				class:kept={isKept}
				class:edited={isEdited}
				class:pending={!node.suggested_name && !node.accepted_name}
				value={effective}
				placeholder={node.suggested_name ? '' : '等待 LLM…'}
				disabled={!node.suggested_name && !node.accepted_name}
				on:input={handleEditInput}
			/>
		{/if}

		<span class="file-count">{node.file_count}f</span>

		{#if !isLoading && node.suggested_name}
			<div class="row-actions">
				<button class="btn btn-accept" on:click={handleAccept} title="接受">✓</button>
				<button class="btn btn-regen" on:click={handleRegen} title="重新生成">↻</button>
				<button class="btn btn-keep" on:click={handleKeep} title="保留原名">—</button>
			</div>
		{/if}
	</div>

	{#if dirChildren.length > 1 && !collapsed}
		<div class="bulk-bar" style="padding-left: calc({node.depth * 16}px + 44px)">
			<span class="bulk-label">全部：</span>
			<button class="bulk-btn" on:click={() => acceptSubtree(node)}>✓ 接受</button>
			<button class="bulk-btn" on:click={() => regenSubtree(node)}>↻ 重新生成</button>
			<button class="bulk-btn" on:click={() => keepSubtree(node)}>— 保留</button>
		</div>
	{/if}

	{#if node.sample_files.length > 0}
		<div class="samples-hint" style="padding-left: calc({node.depth * 16}px + 44px)">
			<span class="samples-label">例：{node.sample_files.slice(0, 2).join(' · ')}</span>
		</div>
	{/if}

	{#if !collapsed && dirChildren.length > 0}
		<div class="children">
			{#each dirChildren as child (child.key)}
				<svelte:self node={child} {onAccept} {onRegenerate} {onKeep} {onEdit} {regenLoadingKeys} />
			{/each}
		</div>
	{/if}
</div>

<style>
	.rename-node { font-size: 0.84rem; }

	.node-row {
		display: flex;
		align-items: center;
		gap: 5px;
		padding: 3px 6px 3px calc(var(--indent) + 4px);
		border-radius: 4px;
		transition: background 0.1s;
	}
	.node-row:hover { background: rgba(255,255,255,0.04); }

	.root-row {
		background: var(--surface0);
		border: 1px solid var(--surface1);
		border-radius: 6px;
		padding: 7px 10px;
		margin-bottom: 6px;
	}

	.collapse-btn {
		background: none; border: none; cursor: pointer;
		color: var(--overlay1); padding: 0 2px; font-size: 0.65rem; flex-shrink: 0;
	}
	.collapse-spacer { width: 16px; flex-shrink: 0; }
	.folder-icon { flex-shrink: 0; font-size: 0.85rem; }

	.original-name {
		color: var(--subtext0);
		max-width: 220px;
		overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
		flex-shrink: 0;
		font-family: monospace; font-size: 0.78rem;
	}

	.arrow { color: var(--overlay1); flex-shrink: 0; font-size: 0.9rem; }

	.name-input {
		flex: 1; min-width: 130px;
		background: var(--base);
		border: 1px solid var(--surface2);
		border-radius: 4px;
		color: var(--text);
		padding: 3px 7px;
		font-size: 0.84rem;
		font-family: inherit;
		transition: border-color 0.15s;
	}
	.name-input:focus { outline: none; border-color: var(--blue); }
	.name-input.accepted { border-color: var(--green); color: var(--green); }
	.name-input.kept { border-color: var(--overlay1); color: var(--overlay1); }
	.name-input.edited { border-color: var(--yellow); }
	.name-input.pending { border-color: var(--surface2); color: var(--overlay0); font-style: italic; }
	.name-input:disabled { opacity: 0.4; cursor: not-allowed; }

	.spinner-label { flex: 1; color: var(--overlay1); font-style: italic; font-size: 0.78rem; }

	.file-count {
		color: var(--overlay0); font-size: 0.7rem;
		flex-shrink: 0; min-width: 22px; text-align: right;
	}

	.row-actions { display: flex; gap: 2px; flex-shrink: 0; }
	.btn {
		background: none;
		border: 1px solid var(--surface2);
		border-radius: 3px;
		color: var(--subtext0);
		cursor: pointer; padding: 1px 6px; font-size: 0.76rem;
		transition: background 0.1s, color 0.1s, border-color 0.1s;
	}
	.btn-accept:hover { background: var(--green); color: var(--base); border-color: var(--green); }
	.btn-regen:hover  { background: var(--blue);  color: var(--base); border-color: var(--blue); }
	.btn-keep:hover   { background: var(--surface2); color: var(--text); }

	.bulk-bar {
		display: flex; align-items: center; gap: 5px;
		padding: 2px 6px; margin: 1px 0;
		background: rgba(255,255,255,0.03);
		border-radius: 3px;
	}
	.bulk-label { color: var(--overlay0); font-size: 0.72rem; flex-shrink: 0; }
	.bulk-btn {
		background: none; border: 1px solid var(--surface1);
		border-radius: 3px; color: var(--overlay1);
		cursor: pointer; padding: 1px 7px; font-size: 0.72rem;
		transition: background 0.1s;
	}
	.bulk-btn:hover { background: var(--surface1); color: var(--text); }

	.children {
		border-left: 1px solid var(--surface1);
		margin-left: calc(var(--indent) + 12px);
	}

	.samples-hint { margin: 1px 0 3px; }
	.samples-label {
		color: var(--overlay0); font-size: 0.7rem;
		font-family: monospace;
		white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
		display: block;
	}
</style>

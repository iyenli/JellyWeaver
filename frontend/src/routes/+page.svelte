<script lang="ts">
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import AppShell from '../components/AppShell.svelte';
	import RenameTreeDialog from '../components/RenameTreeDialog.svelte';
	import DirPicker from '../components/DirPicker.svelte';
	import ProgressBar from '../components/ProgressBar.svelte';
	import SettingsDialog from '../components/SettingsDialog.svelte';
	import SourcePanel from '../components/SourcePanel.svelte';
	import TargetPanel from '../components/TargetPanel.svelte';
	import { api } from '$lib/api';
	import { loading, refreshAll, refreshSettings, refreshSources, refreshTargets, settings, sources, targetContents, targets } from '$lib/stores/state';
	import {
		companionFiles,
		dirPickerMode,
		dirPickerOpen,
		pendingSectionId,
		pendingSourcePath,
		pendingSourcePaths,
		progress,
		renameDialogOpen,
		renameTree,
		renameTreeError,
		renameTreeLoading,
		renameTreeMediaType,
		renameTreeTaskId,
		selectedTargetId,
		settingsOpen,
		showCompleted,
		showIgnored,
		sourceSearch,
		toast
	} from '$lib/stores/ui';
	import type { FsItem, MediaType, RenameNode, Settings, WsMessage } from '$lib/types';
	import { ws } from '$lib/ws';

	const defaultSettings: Settings = {
		api_base: '',
		model: '',
		api_key: '',
		api_key_configured: false,
		api_key_preview: '',
		max_parallel: 5,
		state_file_path: '',
		state_file_exists: false
	};

	let fsItems: FsItem[] = [];
	let fsRoots: string[] = [];
	let fsHome = '';
	let currentFsPath = '';
	let activeSectionId: string | null = null;
	let wsConnected = false;
	let toastTimer: ReturnType<typeof setTimeout> | null = null;

	// Derive the set of target paths that are tracked by a source entry
	$: linkedTargetPaths = new Set<string>(
		$sources.flatMap((s) => s.entries)
			.filter((e) => e.status === 'linked' && e.target_path)
			.map((e) => e.target_path as string)
	);

	// Ref to dialog for applying WS updates
	let renameDialogRef: RenameTreeDialog | undefined;

	// Resolved node count for progress display
	let resolvedNodeCount = 0;

	function setToast(type: 'info' | 'error' | 'success', message: string) {
		toast.set({ type, message });
		if (toastTimer) clearTimeout(toastTimer);
		toastTimer = setTimeout(() => toast.set(null), 3000);
	}

	function clearPendingState() {
		pendingSourcePath.set(null);
		pendingSourcePaths.set(null);
		pendingSectionId.set(null);
		companionFiles.set([]);
		renameTree.set(null);
		renameTreeTaskId.set(null);
		renameTreeLoading.set(false);
		renameTreeError.set(null);
		renameTreeMediaType.set(null);
		selectedTargetId.set(null);
		activeSectionId = null;
		resolvedNodeCount = 0;
	}

	function startRenameTree(sourcePath: string, sourcePaths?: string[]) {
		renameTreeLoading.set(true);
		renameTreeError.set(null);
		renameTree.set(null);
		renameTreeMediaType.set(null);
		resolvedNodeCount = 0;

		api.startRenameTree(sourcePath, sourcePaths)
			.then((result) => {
				renameTreeTaskId.set(result.task_id);
				renameTree.set(result.tree);
				companionFiles.set(result.companion_files ?? []);
				// Count nodes already resolved from cache
				resolvedNodeCount = countResolved(result.tree);
				// If all nodes are resolved from cache, no LLM calls are needed.
				// The background task's rename_tree_done WS message would arrive before
				// renameTreeTaskId is set (race condition), so handle it here instead.
				if (resolvedNodeCount >= countDirs(result.tree)) {
					const hasSeasons = result.tree.children.some(
						(c) => c.suggested_name?.startsWith('Season ')
					);
					renameTreeMediaType.set(hasSeasons ? 'tv' : 'movie');
					renameTreeLoading.set(false);
				}
			})
			.catch((err) => {
				renameTreeError.set(err instanceof Error ? err.message : 'Tree analysis failed');
				renameTreeLoading.set(false);
			});
	}

	function countResolved(node: RenameNode): number {
		let count = node.suggested_name !== null ? 1 : 0;
		for (const c of node.children) count += countResolved(c);
		return count;
	}

	function countDirs(node: RenameNode): number {
		let count = node.is_dir ? 1 : 0;
		for (const c of node.children) count += countDirs(c);
		return count;
	}

	async function loadDir(path: string) {
		const data = await api.listDir(path);
		currentFsPath = data.path;
		fsItems = data.items;
	}

	async function openDirPicker(mode: 'source' | 'target', targetId?: string) {
		dirPickerMode.set(mode);
		selectedTargetId.set(targetId ?? null);
		const roots = await api.listRoots();
		fsRoots = roots.roots;
		fsHome = roots.home;
		const targetPath = mode === 'target' && targetId ? get(targets).find((item) => item.id === targetId)?.path : '';
		await loadDir(targetPath || roots.home);
		dirPickerOpen.set(true);
	}

	async function handleSelectDir(path: string) {
		try {
			if ($dirPickerMode === 'source') {
				await api.addSource(path);
				await refreshSources();
				setToast('success', 'Source added');
			} else {
				const targetId = get(selectedTargetId);
				if (!targetId) return;
				await api.updateTarget(targetId, { path });
				await refreshTargets();
				setToast('success', 'Target path updated');
			}
			dirPickerOpen.set(false);
		} catch (error) {
			setToast('error', error instanceof Error ? error.message : 'Directory update failed');
		}
	}

	async function handleDropSource(sourcePath: string, sectionId: string) {
		pendingSourcePath.set(sourcePath);
		pendingSectionId.set(sectionId);
		selectedTargetId.set(sectionId);
		activeSectionId = sectionId;
		renameDialogOpen.set(true);
		startRenameTree(sourcePath);
	}

	async function handleConfirm(tree: RenameNode, mediaType: MediaType, sectionId: string, companionPaths: string[]) {
		const sourcePath = get(pendingSourcePath);
		const sourcePaths = get(pendingSourcePaths);
		if (!sourcePath && !sourcePaths?.length) return;
		if (!sectionId) return;

		const rootAccepted = tree.accepted_name ?? tree.suggested_name ?? tree.name;

		try {
			renameDialogOpen.set(false);
			const result = await api.startLink({
				source_path: sourcePath ?? '',
				source_paths: sourcePaths ?? undefined,
				companion_paths: companionPaths.length > 0 ? companionPaths : undefined,
				section_id: sectionId,
				media_type: mediaType,
				title_en: rootAccepted,
				title_zh: '',
				year: 0,
				tree_plan: tree
			});
			progress.set({ taskId: result.task_id, current: 0, total: 0 });
			setToast('info', `Link started: ${result.task_id}`);
		} catch (error) {
			setToast('error', error instanceof Error ? error.message : 'Link failed to start');
			clearPendingState();
		}
	}

	async function handleSmartAdd(sourcePath: string) {
		// Pick target library: use first available
		const allTargets = get(targets);
		if (!allTargets.length) {
			setToast('error', 'No libraries configured — add one first');
			return;
		}
		const firstTarget = allTargets[0];
		pendingSourcePath.set(sourcePath);
		pendingSourcePaths.set(null);
		pendingSectionId.set(firstTarget.id);
		selectedTargetId.set(firstTarget.id);
		activeSectionId = firstTarget.id;
		renameDialogOpen.set(true);
		startRenameTree(sourcePath);
	}

	async function handleGroupFiles(paths: string[]) {
		const allTargets = get(targets);
		if (!allTargets.length) {
			setToast('error', 'No libraries configured — add one first');
			return;
		}
		const firstTarget = allTargets[0];
		pendingSourcePath.set(null);
		pendingSourcePaths.set(paths);
		pendingSectionId.set(firstTarget.id);
		selectedTargetId.set(firstTarget.id);
		activeSectionId = firstTarget.id;
		renameDialogOpen.set(true);
		startRenameTree('', paths);
	}

	async function handleWsMessage(message: WsMessage) {
		if (message.type === 'link_progress') {
			progress.set({ taskId: message.task_id, current: message.current, total: message.total });
			return;
		}
		if (message.type === 'link_done') {
			progress.set(null);
			await refreshSources();
			await refreshTargets();
			setToast('success', `Linked ${message.result.linked} files`);
			clearPendingState();
			return;
		}
		if (message.type === 'link_error') {
			progress.set(null);
			setToast('error', message.error);
			clearPendingState();
			return;
		}
		if (message.type === 'rename_node_done') {
			if (message.task_id === get(renameTreeTaskId)) {
				resolvedNodeCount += 1;
				renameDialogRef?.applyNodeUpdate(message.key, message.suggested_name);
			}
			return;
		}
		if (message.type === 'rename_tree_done') {
			if (message.task_id === get(renameTreeTaskId)) {
				renameTreeMediaType.set(message.media_type as MediaType);
				renameTreeLoading.set(false);
				renameDialogRef?.applyTreeDone(message.tree, message.media_type);
			}
			return;
		}
		if (message.type === 'rename_error') {
			if (message.task_id === get(renameTreeTaskId)) {
				renameTreeLoading.set(false);
				renameTreeError.set(message.error);
			}
			return;
		}
		if (message.type === 'relink_progress') {
			progress.set({ taskId: message.task_id, current: message.done, total: message.total });
			return;
		}
		if (message.type === 'relink_done') {
			progress.set(null);
			await refreshSources();
			await refreshTargets();
			const parts = [];
			if (message.relinked) parts.push(`${message.relinked} re-linked`);
			if (message.unlinked_only) parts.push(`${message.unlinked_only} unlinked (no cache — drag to re-link)`);
			const msg = parts.length ? parts.join(', ') : 'No items to re-link';
			if (message.errors.length) {
				setToast('error', `${msg}; ${message.errors[0]}`);
			} else {
				setToast(message.relinked > 0 ? 'success' : 'info', msg);
			}
			return;
		}
		if (message.type === 'state_changed') {
			if (message.scope === 'sources' || message.scope === 'entries') await refreshSources();
			if (message.scope === 'targets') await refreshTargets();
			if (message.scope === 'settings') await refreshSettings();
		}
	}

	onMount(() => {
		ws.connect();
		const unsubscribeWsConnected = ws.connected.subscribe((value) => {
			wsConnected = value;
		});
		const unsubscribeMessages = ws.subscribe((message) => {
			void handleWsMessage(message);
		});
		void refreshAll().catch((error) => {
			setToast('error', error instanceof Error ? error.message : 'Initial load failed');
		});

		return () => {
			unsubscribeWsConnected();
			unsubscribeMessages();
			if (toastTimer) clearTimeout(toastTimer);
		};
	});
</script>

<AppShell {wsConnected} onRefresh={() => refreshAll()} onOpenSettings={() => settingsOpen.set(true)} onReconcile={async () => {
		try {
			const result = await api.reconcile();
			await refreshSources();
			await refreshTargets();
			const parts = [];
			if (result.newly_linked) parts.push(`${result.newly_linked} newly linked`);
			if (result.reset_to_pending) parts.push(`${result.reset_to_pending} reset to pending`);
			if (result.removed) parts.push(`${result.removed} stale entries removed`);
			setToast('success', parts.length ? parts.join(', ') : 'State up to date — no changes');
		} catch (error) {
			setToast('error', error instanceof Error ? error.message : 'Reconcile failed');
		}
	}}>
	<div class="grid gap-6 xl:grid-cols-2 xl:items-start">
		<SourcePanel
			sources={$sources}
			showCompleted={$showCompleted}
			showIgnored={$showIgnored}
			searchText={$sourceSearch}
			loading={$loading}
			onAddSource={() => openDirPicker('source')}
			onRemoveSource={async (path) => {
				try {
					await api.removeSource(path);
					await refreshSources();
					setToast('success', 'Source removed');
				} catch (error) {
					setToast('error', error instanceof Error ? error.message : 'Failed to remove source');
				}
			}}
			onToggleIgnored={async (path, nextIgnored) => {
				try {
					await api.updateEntry(path, nextIgnored ? 'ignored' : 'pending');
					await refreshSources();
				} catch (error) {
					setToast('error', error instanceof Error ? error.message : 'Failed to update entry');
				}
			}}
			onShowCompletedChange={(value) => showCompleted.set(value)}
			onShowIgnoredChange={(value) => showIgnored.set(value)}
			onSearchChange={(value) => sourceSearch.set(value)}
			onSmartAdd={handleSmartAdd}
		/>

		<TargetPanel
			targets={$targets}
			targetContents={$targetContents}
			{linkedTargetPaths}
			{activeSectionId}
			onAddTarget={async () => {
				try {
					await api.addTarget({ name: `Library ${$targets.length + 1}`, media_type: 'movies', path: '' });
					await refreshTargets();
				} catch (error) {
					setToast('error', error instanceof Error ? error.message : 'Failed to add target');
				}
			}}
			onUpdateTarget={async (id, patch) => {
				try {
					await api.updateTarget(id, patch);
					await refreshTargets();
				} catch (error) {
					setToast('error', error instanceof Error ? error.message : 'Failed to update target');
				}
			}}
			onRemoveTarget={async (id) => {
				try {
					await api.deleteTarget(id);
					await refreshTargets();
				} catch (error) {
					setToast('error', error instanceof Error ? error.message : 'Failed to remove target');
				}
			}}
			onPickPath={(id) => openDirPicker('target', id)}
			onDropSource={handleDropSource}
			onUnlink={async (targetFolderPath) => {
				try {
					await api.unlinkFolder(targetFolderPath);
					await refreshSources();
					await refreshTargets();
					setToast('success', 'Unlinked and returned to sources');
				} catch (error) {
					setToast('error', error instanceof Error ? error.message : 'Unlink failed');
				}
			}}
			onReparse={async (targetFolderPath, _folderName, sectionId) => {
				let sourceKey: string | null = null;
				try {
					const result = await api.unlinkFolder(targetFolderPath);
					sourceKey = result.source_key;
					await refreshSources();
					await refreshTargets();
				} catch (error) {
					setToast('error', error instanceof Error ? error.message : 'Unlink failed');
					return;
				}
				const sourcePath = sourceKey ?? targetFolderPath;
				pendingSourcePath.set(sourcePath);
				pendingSectionId.set(sectionId);
				selectedTargetId.set(sectionId);
				activeSectionId = sectionId;
				renameDialogOpen.set(true);
				startRenameTree(sourcePath);
			}}
		onRenameAll={async (sectionId) => {
				try {
					const result = await api.renameLibrary(sectionId);
					await refreshTargets();
					const parts = [];
					if (result.renamed) parts.push(`${result.renamed} 个已重命名`);
					if (result.unchanged) parts.push(`${result.unchanged} 个无需更改`);
					if (result.no_cache) parts.push(`${result.no_cache} 个无缓存名称`);
					const msg = parts.length ? parts.join('，') : '没有可重命名的文件夹';
					if (result.errors.length) {
						setToast('error', `${msg}；${result.errors[0]}`);
					} else {
						setToast(result.renamed > 0 ? 'success' : 'info', msg);
					}
				} catch (error) {
					setToast('error', error instanceof Error ? error.message : '批量重命名失败');
				}
			}}
		onJellyfinScan={async (sectionId) => {
				try {
					const result = await api.jellyfinScan(sectionId);
					setToast('success', result.matched_library ? 'Jellyfin 刮削已触发（精确匹配）' : 'Jellyfin 全库刮削已触发');
				} catch (error) {
					setToast('error', error instanceof Error ? error.message : 'Jellyfin 刮削请求失败');
				}
			}}
		onRelinkAll={async (sectionId) => {
				try {
					const result = await api.relinkSection(sectionId);
					if (result.total === 0) {
						setToast('info', 'No linked items to re-link');
						return;
					}
					progress.set({ taskId: result.task_id, current: 0, total: result.total });
					setToast('info', `Relink started: ${result.total} items`);
				} catch (error) {
					setToast('error', error instanceof Error ? error.message : 'Relink All failed');
				}
			}}
		/>
	</div>
</AppShell>

<DirPicker
	open={$dirPickerOpen}
	mode={$dirPickerMode}
	currentPath={currentFsPath}
	roots={fsRoots}
	home={fsHome}
	items={fsItems}
	onClose={() => dirPickerOpen.set(false)}
	onNavigate={loadDir}
	onSelect={handleSelectDir}
/>

<RenameTreeDialog
	bind:this={renameDialogRef}
	open={$renameDialogOpen}
	sourceName={$pendingSourcePath?.split(/[/\\]/).at(-1) ?? ''}
	targets={$targets}
	initialSectionId={$pendingSectionId ?? $selectedTargetId ?? ''}
	tree={$renameTree}
	loading={$renameTreeLoading}
	error={$renameTreeError}
	mediaType={$renameTreeMediaType}
	resolvedCount={resolvedNodeCount}
	totalDirCount={$renameTree ? countDirs($renameTree) : 0}
	companionFiles={$companionFiles}
	onClose={() => {
		renameDialogOpen.set(false);
		clearPendingState();
	}}
	onConfirm={handleConfirm}
/>

<SettingsDialog
	open={$settingsOpen}
	value={$settings ?? defaultSettings}
	onClose={() => settingsOpen.set(false)}
	onSave={async (patch) => {
		try {
			await api.updateSettings(patch);
			await refreshSettings();
			settingsOpen.set(false);
			setToast('success', 'Settings saved');
		} catch (error) {
			setToast('error', error instanceof Error ? error.message : 'Failed to save settings');
		}
	}}
/>

<ProgressBar progress={$progress} />

{#if $toast}
	<div class={`fixed left-1/2 top-6 z-50 -translate-x-1/2 rounded-xl border px-4 py-3 text-sm shadow-lg ${$toast.type === 'error' ? 'border-[var(--red)] bg-[color:color-mix(in_srgb,var(--red)_18%,var(--mantle))]' : $toast.type === 'success' ? 'border-[var(--green)] bg-[color:color-mix(in_srgb,var(--green)_18%,var(--mantle))]' : 'border-[var(--blue)] bg-[color:color-mix(in_srgb,var(--blue)_18%,var(--mantle))]'}`}>
		{$toast.message}
	</div>
{/if}

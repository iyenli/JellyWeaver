<script lang="ts">
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import AppShell from '../components/AppShell.svelte';
	import ConfirmDialog from '../components/ConfirmDialog.svelte';
	import DirPicker from '../components/DirPicker.svelte';
	import ProgressBar from '../components/ProgressBar.svelte';
	import SettingsDialog from '../components/SettingsDialog.svelte';
	import SourcePanel from '../components/SourcePanel.svelte';
	import TargetPanel from '../components/TargetPanel.svelte';
	import { api } from '$lib/api';
	import { loading, refreshAll, refreshSettings, refreshSources, refreshTargets, settings, sources, targetContents, targets } from '$lib/stores/state';
	import {
		confirmOpen,
		dirPickerMode,
		dirPickerOpen,
		pendingParse,
		pendingSectionId,
		pendingSourcePath,
		progress,
		selectedTargetId,
		settingsOpen,
		showCompleted,
		showIgnored,
		sourceSearch,
		toast
	} from '$lib/stores/ui';
	import type { FsItem, ParseResult, Settings, WsMessage } from '$lib/types';
	import { ws } from '$lib/ws';

	const defaultSettings: Settings = {
		api_base: '',
		model: '',
		api_key: '',
		api_key_configured: false,
		api_key_preview: '',
		state_file_path: '',
		state_file_exists: false
	};

	function emptyParse(title = ''): ParseResult {
		return {
			media_type: 'movie',
			title_en: title,
			title_zh: '',
			year: new Date().getFullYear()
		};
	}

	let fsItems: FsItem[] = [];
	let fsRoots: string[] = [];
	let fsHome = '';
	let currentFsPath = '';
	let activeSectionId: string | null = null;
	let wsConnected = false;
	let toastTimer: ReturnType<typeof setTimeout> | null = null;

	function setToast(type: 'info' | 'error' | 'success', message: string) {
		toast.set({ type, message });
		if (toastTimer) clearTimeout(toastTimer);
		toastTimer = setTimeout(() => toast.set(null), 3000);
	}

	function clearPendingState() {
		pendingSourcePath.set(null);
		pendingSectionId.set(null);
		pendingParse.set(null);
		selectedTargetId.set(null);
		activeSectionId = null;
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
		const sourceName = sourcePath.split(/[/\\]/).at(-1) ?? sourcePath;
		const target = get(targets).find((item) => item.id === sectionId);
		const hint = target?.media_type === 'movies' ? 'movie' : 'tv';

		try {
			const parsed = await api.parseFolder(sourceName, hint);
			pendingParse.set(parsed);
		} catch {
			pendingParse.set({ ...emptyParse(sourceName), media_type: hint === 'movie' ? 'movie' : 'tv' });
		}

		confirmOpen.set(true);
	}

	async function handleConfirm(parse: ParseResult) {
		const sourcePath = get(pendingSourcePath);
		const sectionId = get(pendingSectionId) ?? get(selectedTargetId);
		if (!sourcePath || !sectionId) return;

		try {
			confirmOpen.set(false);
			const result = await api.startLink({ ...parse, source_path: sourcePath, section_id: sectionId });
			progress.set({ taskId: result.task_id, current: 0, total: 0 });
			setToast('info', `Link started: ${result.task_id}`);
		} catch (error) {
			setToast('error', error instanceof Error ? error.message : 'Link failed to start');
			clearPendingState();
		}
	}

	async function handleSmartAdd(sourcePath: string) {
		const sourceName = sourcePath.split(/[/\\]/).at(-1) ?? sourcePath;
		try {
			const parsed = await api.parseFolder(sourceName);
			// Auto-select matching target library
			const targetMediaType = parsed.media_type === 'movie' ? 'movies' : 'tv';
			const matchingTarget = get(targets).find((t) => t.media_type === targetMediaType);
			if (!matchingTarget) {
				setToast('error', `No library configured for type "${parsed.media_type}" — add one first`);
				return;
			}
			pendingSourcePath.set(sourcePath);
			pendingSectionId.set(matchingTarget.id);
			selectedTargetId.set(matchingTarget.id);
			activeSectionId = matchingTarget.id;
			pendingParse.set(parsed);
			confirmOpen.set(true);
		} catch {
			// LLM failed — fall back: pick first target if available
			const firstTarget = get(targets)[0];
			if (!firstTarget) {
				setToast('error', 'No libraries configured — add one first');
				return;
			}
			const hint = firstTarget.media_type === 'movies' ? 'movie' : 'tv';
			pendingSourcePath.set(sourcePath);
			pendingSectionId.set(firstTarget.id);
			selectedTargetId.set(firstTarget.id);
			activeSectionId = firstTarget.id;
			pendingParse.set({ ...emptyParse(sourceName), media_type: hint === 'movie' ? 'movie' : 'tv' });
			confirmOpen.set(true);
		}
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

		if (message.scope === 'sources' || message.scope === 'entries') await refreshSources();
		if (message.scope === 'targets') await refreshTargets();
		if (message.scope === 'settings') await refreshSettings();
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

<AppShell {wsConnected} onRefresh={() => refreshAll()} onOpenSettings={() => settingsOpen.set(true)}>
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

<ConfirmDialog
	open={$confirmOpen}
	sourceName={$pendingSourcePath?.split(/[/\\]/).at(-1) ?? ''}
	value={$pendingParse ?? emptyParse($pendingSourcePath?.split(/[/\\]/).at(-1) ?? '')}
	targetMediaType={$targets.find((t) => t.id === ($pendingSectionId ?? $selectedTargetId))?.media_type ?? null}
	onClose={() => {
		confirmOpen.set(false);
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

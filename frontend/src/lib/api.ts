import type {
	CompanionFile,
	EntryStatus,
	FsListResponse,
	LinkRequest,
	LlmCheckResult,
	RenameNode,
	RenameTreeResult,
	Settings,
	TargetContentItem,
	TargetSection
} from '$lib/types';

interface SourceEntryRecord {
	path: string;
	status: EntryStatus;
	file_count?: number;
	target_path?: string | null;
	linked_at?: string | null;
}

interface ScannedEntry {
	path: string;
	name: string;
	file_count: number;
	status: EntryStatus;
	target_path?: string | null;
}

function basename(path: string) {
	return path.split(/[/\\]/).at(-1) ?? path;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
	const response = await fetch(path, {
		headers: {
			'Content-Type': 'application/json',
			...(init?.headers ?? {})
		},
		...init
	});

	if (!response.ok) {
		let message = `${response.status} ${response.statusText}`;
		try {
			const data = await response.json();
			message = data.detail ?? message;
		} catch {
			// ignore json parse failures
		}
		throw new Error(message);
	}

	if (response.status === 204) {
		return undefined as T;
	}

	return response.json() as Promise<T>;
}

export const api = {
	listSources: async () => {
		const data = await request<{ sources: string[]; entries: Record<string, SourceEntryRecord[]> }>('/api/sources');
		return data.sources.map((path) => ({
			path,
			entries: (data.entries[path] ?? []).map((entry) => ({
				path: entry.path,
				name: basename(entry.path),
				file_count: entry.file_count ?? 0,
				status: entry.status,
				target_path: entry.target_path,
				linked_at: entry.linked_at
			}))
		}));
	},
	addSource: (path: string) => request('/api/sources', { method: 'POST', body: JSON.stringify({ path }) }),
	removeSource: (path: string) => request('/api/sources', { method: 'DELETE', body: JSON.stringify({ path }) }),
	scanSource: (path: string) => request<{ entries: ScannedEntry[] }>(`/api/sources/scan?path=${encodeURIComponent(path)}`),
	listTargets: () => request<{ sections: TargetSection[] }>('/api/targets'),
	addTarget: (body: Partial<TargetSection>) => request<TargetSection>('/api/targets', { method: 'POST', body: JSON.stringify(body) }),
	updateTarget: (id: string, body: Partial<TargetSection>) => request<TargetSection>(`/api/targets/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
	deleteTarget: (id: string) => request(`/api/targets/${id}`, { method: 'DELETE' }),
	listTargetContents: async (id: string): Promise<TargetContentItem[]> => {
		const data = await request<{ items: TargetContentItem[] }>(`/api/targets/${id}/contents`);
		return data.items;
	},
	updateEntry: (path: string, status: 'pending' | 'ignored') =>
		request(`/api/entries/${encodeURI(path)}`, { method: 'PATCH', body: JSON.stringify({ status }) }),
	getSettings: () => request<Settings>('/api/settings'),
	updateSettings: (body: Partial<Settings> & { jellyfin_api_key?: string }) => request('/api/settings', { method: 'PUT', body: JSON.stringify(body) }),
	listRoots: () => request<{ roots: string[]; home: string }>('/api/fs/roots'),
	listDir: (path: string) => request<FsListResponse>(`/api/fs/list?path=${encodeURIComponent(path)}`),
	startRenameTree: (sourcePath: string, sourcePaths?: string[]) =>
		request<{ task_id: string; tree: RenameNode; companion_files?: CompanionFile[] }>('/api/ops/rename-tree', {
			method: 'POST',
			body: JSON.stringify(
				sourcePaths && sourcePaths.length > 0
					? { source_paths: sourcePaths }
					: { source_path: sourcePath }
			)
		}).then((r): RenameTreeResult => ({
			task_id: r.task_id,
			tree: _initRenameNode(r.tree),
			companion_files: r.companion_files ?? []
		})),
	startLink: (body: LinkRequest) => request<{ task_id: string; target_path: string }>('/api/ops/link', { method: 'POST', body: JSON.stringify(body) }),
	unlinkFolder: (targetFolderPath: string) => request<{ ok: boolean; removed_files: number; source_key: string | null }>('/api/ops/unlink', { method: 'POST', body: JSON.stringify({ target_folder_path: targetFolderPath }) }),
	openStateDir: () => request('/api/settings/open-state-dir', { method: 'POST' }),
	llmCheck: () => request<LlmCheckResult>('/api/settings/llm-check', { method: 'POST' }),
	clearNameCache: () => request<{ ok: boolean; cleared: number }>('/api/ops/name-cache', { method: 'DELETE' }),
	reconcile: () => request<{ ok: boolean; newly_linked: number; reset_to_pending: number; removed: number }>('/api/ops/reconcile', { method: 'POST' }),
	renameLibrary: (sectionId: string) =>
		request<{ ok: boolean; renamed: number; unchanged: number; no_cache: number; errors: string[] }>('/api/ops/rename-library', {
			method: 'POST',
			body: JSON.stringify({ section_id: sectionId })
		}),
	jellyfinScan: (sectionId: string) =>
		request<{ ok: boolean; matched_library: boolean }>('/api/ops/jellyfin-scan', {
			method: 'POST',
			body: JSON.stringify({ section_id: sectionId })
		}),
	relinkSection: (sectionId: string) =>
		request<{ task_id: string; total: number }>('/api/ops/relink-section', {
			method: 'POST',
			body: JSON.stringify({ section_id: sectionId })
		}),
};

/** Ensure every RenameNode has accepted_name initialized to null. */
function _initRenameNode(node: RenameNode): RenameNode {
	return {
		...node,
		accepted_name: node.accepted_name ?? null,
		suggested_name: node.suggested_name ?? null,
		children: node.children.map(_initRenameNode)
	};
}

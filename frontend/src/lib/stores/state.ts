import { writable } from 'svelte/store';
import { api } from '$lib/api';
import type { EntryItem, Settings, SourceSummary, TargetContentItem, TargetSection } from '$lib/types';

export const loading = writable(false);
export const sources = writable<SourceSummary[]>([]);
export const targets = writable<TargetSection[]>([]);
export const targetContents = writable<Record<string, TargetContentItem[]>>({});
export const settings = writable<Settings | null>(null);

export async function refreshSources() {
	loading.set(true);
	try {
		const sourceList = await api.listSources();
		const merged = await Promise.all(
			sourceList.map(async (source) => {
				const scanned = await api.scanSource(source.path);
				const recordMap = new Map(source.entries.map((entry) => [entry.path, entry]));
				const entries: EntryItem[] = scanned.entries.map((item) => ({
					path: item.path,
					name: item.name,
					file_count: item.file_count,
					status: item.status,
					target_path: recordMap.get(item.path)?.target_path ?? null,
					linked_at: recordMap.get(item.path)?.linked_at ?? null
				}));
				return { path: source.path, entries };
			})
		);
		sources.set(merged);
	} finally {
		loading.set(false);
	}
}

export async function refreshTargets() {
	const data = await api.listTargets();
	targets.set(data.sections);

	const contents = Object.fromEntries(
		await Promise.all(
			data.sections.map(async (section) => [section.id, await api.listTargetContents(section.id)])
		)
	);
	targetContents.set(contents);
}

export async function refreshSettings() {
	settings.set(await api.getSettings());
}

export async function refreshAll() {
	await Promise.all([refreshSources(), refreshTargets(), refreshSettings()]);
}

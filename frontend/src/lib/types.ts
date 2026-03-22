export type MediaType = 'movie' | 'tv';
export type TargetMediaType = 'movies' | 'tv';
export type EntryStatus = 'pending' | 'linked' | 'ignored';

export interface EntryItem {
	path: string;
	name: string;
	file_count: number;
	status: EntryStatus;
	target_path?: string | null;
	linked_at?: string | null;
}

export interface SourceSummary {
	path: string;
	entries: EntryItem[];
}

export interface TargetSection {
	id: string;
	name: string;
	media_type: TargetMediaType;
	path: string;
}

export interface TargetContentItem {
	name: string;
	path: string;
}

export interface Settings {
	api_base: string;
	model: string;
	api_key: string;
	api_key_configured: boolean;
	api_key_preview: string;
}

export interface FsItem {
	name: string;
	path: string;
	is_dir: boolean;
}

export interface FsListResponse {
	path: string;
	parent: string;
	items: FsItem[];
}

export interface ParseResult {
	media_type: MediaType;
	title_en: string;
	title_zh: string;
	year: number;
}

export interface LinkRequest extends ParseResult {
	source_path: string;
	section_id: string;
}

export interface LinkResult {
	linked: number;
	skipped: number;
	errors: string[];
}

export interface WsLinkProgress {
	type: 'link_progress';
	task_id: string;
	current: number;
	total: number;
}

export interface WsLinkDone {
	type: 'link_done';
	task_id: string;
	result: LinkResult;
}

export interface WsLinkError {
	type: 'link_error';
	task_id: string;
	error: string;
}

export interface WsStateChanged {
	type: 'state_changed';
	scope: 'sources' | 'targets' | 'entries' | 'settings';
}

export type WsMessage = WsLinkProgress | WsLinkDone | WsLinkError | WsStateChanged;

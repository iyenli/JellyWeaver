import { writable } from 'svelte/store';
import type { ParseResult } from '$lib/types';

export const showCompleted = writable(false);
export const showIgnored = writable(false);
export const sourceSearch = writable('');
export const dirPickerOpen = writable(false);
export const settingsOpen = writable(false);
export const confirmOpen = writable(false);
export const dirPickerMode = writable<'source' | 'target'>('source');
export const selectedTargetId = writable<string | null>(null);
export const pickedPath = writable('');
export const dragPath = writable<string | null>(null);
export const pendingSourcePath = writable<string | null>(null);
export const pendingSectionId = writable<string | null>(null);
export const pendingParse = writable<ParseResult | null>(null);
export const progress = writable<{ taskId: string; current: number; total: number } | null>(null);
export const toast = writable<{ type: 'info' | 'error' | 'success'; message: string } | null>(null);

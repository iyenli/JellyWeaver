import { browser } from '$app/environment';
import { writable } from 'svelte/store';
import type { WsMessage } from '$lib/types';

const connected = writable(false);

let socket: WebSocket | null = null;
const listeners = new Set<(message: WsMessage) => void>();

function buildUrl() {
	if (!browser) return '';
	const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
	return `${protocol}//${window.location.host}/api/ws`;
}

function connect() {
	if (!browser || socket) return;
	socket = new WebSocket(buildUrl());

	socket.addEventListener('open', () => {
		connected.set(true);
	});

	socket.addEventListener('message', (event) => {
		const message = JSON.parse(event.data) as WsMessage;
		for (const listener of listeners) listener(message);
	});

	socket.addEventListener('close', () => {
		connected.set(false);
		socket = null;
		setTimeout(connect, 1500);
	});

	socket.addEventListener('error', () => {
		socket?.close();
	});
}

export const ws = {
	connected,
	connect,
	subscribe(handler: (message: WsMessage) => void) {
		listeners.add(handler);
		return () => listeners.delete(handler);
	}
};

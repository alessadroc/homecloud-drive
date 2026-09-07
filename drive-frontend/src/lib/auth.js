import { writable } from 'svelte/store';
import { browser } from '$app/environment';

// sessionStorage only exists in the browser; SvelteKit may render on the server.
const storedToken = browser ? sessionStorage.getItem('token') : null;
const storedUsername = browser ? sessionStorage.getItem('username') : null;

export const token = writable(storedToken);
export const username = writable(storedUsername);

if (browser) {
	token.subscribe((value) => {
		if (value) sessionStorage.setItem('token', value);
		else sessionStorage.removeItem('token');
	});

	username.subscribe((value) => {
		if (value) sessionStorage.setItem('username', value);
		else sessionStorage.removeItem('username');
	});
}

export function signIn(newToken, name) {
	token.set(newToken);
	username.set(name);
}

export function signOut() {
	token.set(null);
	username.set(null);
}
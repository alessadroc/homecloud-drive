import { writable } from 'svelte/store';
import { browser } from '$app/environment';

const initialToken = browser ? sessionStorage.getItem('token') : null;

export const token = writable(initialToken);

if (browser) {
    token.subscribe((value) => {
        if (value) sessionStorage.setItem('token', value);
        else sessionStorage.removeItem('token');
    });
}

export function setToken(newToken) {
    token.set(newToken);
}

export function clearToken() {
    token.set(null);
}
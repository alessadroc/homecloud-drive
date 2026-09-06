import { get } from 'svelte/store';
import { env } from '$env/dynamic/public';
import { token } from './auth.js';

const BASE_URL = env.PUBLIC_API_URL || 'http://localhost:8008';

async function request(path, options = {}) {
    const currentToken = get(token);
    const headers = { ...options.headers };
    if (currentToken) headers['Authorization'] = `Bearer ${currentToken}`;
    const response = await fetch(`${BASE_URL}${path}`, { ...options, headers });
    if (!response.ok) {
        let detail = 'Request failed';
        try {
            const body = await response.json();
            detail = body.detail || detail;
        } catch (_) { /* non-JSON error body */ }
        if (response.status === 401) throw new Error('UNAUTHORIZED');
        throw new Error(detail);
    }
    return response;
}

export const api = {
    async getJSON(path) {
        const res = await request(path, { method: 'GET' });
        return res.json();
    },
    async post(path, options = {}) {
        return request(path, { method: 'POST', ...options });
    },
    async upload(path, formData) {
        return request(path, { method: 'POST', body: formData });
    },
    async getRaw(path) {
        return request(path, { method: 'GET' });
    },
    async delete(path) {
        return request(path, { method: 'DELETE' });
    },
};
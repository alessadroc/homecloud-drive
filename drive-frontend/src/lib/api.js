import { get } from 'svelte/store';
import { token } from './auth.js';

// Set VITE_API_URL in the frontend's .env to point at the server
// (e.g. http://10.0.0.50:8008 once this is deployed to the Optiplex).
const BASE_URL = import.meta.env.VITE_API_URL ?? '/api';

/** Thrown for any non-2xx response. `status` lets callers treat 401 specially. */
export class ApiError extends Error {
	constructor(message, status) {
		super(message);
		this.name = 'ApiError';
		this.status = status;
	}
}

async function request(path, options = {}) {
	const currentToken = get(token);
	const headers = { ...options.headers };
	if (currentToken) headers['Authorization'] = `Bearer ${currentToken}`;

	let response;
	try {
		response = await fetch(`${BASE_URL}${path}`, { ...options, headers });
	} catch {
		// fetch only rejects when the request never reached the server.
		throw new ApiError(`Can't reach the server at ${BASE_URL}.`, 0);
	}

	if (!response.ok) {
		let detail = `The server returned ${response.status}.`;
		try {
			const body = await response.json();
			if (body?.detail) detail = body.detail;
		} catch {
			// Error body wasn't JSON - keep the status-based message.
		}
		throw new ApiError(detail, response.status);
	}

	return response;
}

export const api = {
	async getJSON(path) {
		const res = await request(path, { method: 'GET' });
		return res.json();
	},

	async postJSON(path) {
		const res = await request(path, { method: 'POST' });
		return res.json();
	},

	/**
	 * POST multipart/form-data. Used for both uploads and any route taking
	 * FastAPI Form(...) fields. Never set Content-Type by hand here - the
	 * browser has to add the multipart boundary itself.
	 */
	async postForm(path, formData) {
		return request(path, { method: 'POST', body: formData });
	},

	/** Raw response, for streaming a file body into a blob. */
	async getRaw(path) {
		return request(path, { method: 'GET' });
	},

	async remove(path) {
		return request(path, { method: 'DELETE' });
	}
};

export function query(params) {
	return new URLSearchParams(params).toString();
}
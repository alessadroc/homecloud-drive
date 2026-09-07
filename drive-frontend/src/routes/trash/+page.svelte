<script>
	import { onMount } from 'svelte';
	import { api } from '$lib/api.js';
	import { signOut } from '$lib/auth.js';
	import { goto } from '$app/navigation';
	import Header from '$lib/Header.svelte';

	// Must match DEFAULT_RETENTION_DAYS in cleanup.py.
	const RETENTION_DAYS = 30;

	let folders = $state([]);
	let files = $state([]);
	let loading = $state(true);
	let error = $state('');

	let isEmpty = $derived(!loading && folders.length === 0 && files.length === 0);
	let itemCount = $derived(folders.length + files.length);

	function report(e) {
		if (e.status === 401) {
			signOut();
			goto('/login');
			return;
		}
		error = e.message;
	}

	async function load() {
		error = '';
		loading = true;
		try {
			const data = await api.getJSON('/trash');
			folders = data.folders ?? [];
			files = data.files ?? [];
		} catch (e) {
			report(e);
		} finally {
			loading = false;
		}
	}

	async function restoreFile(file) {
		error = '';
		const previous = files;
		files = files.filter((f) => f.file_id !== file.file_id);
		try {
			await api.postForm(`/files/${file.file_id}/restore`, new FormData());
		} catch (e) {
			files = previous;
			report(e);
		}
	}

	async function restoreFolder(folder) {
		error = '';
		const previous = folders;
		folders = folders.filter((f) => f.folder_id !== folder.folder_id);
		try {
			await api.postForm(`/folders/${folder.folder_id}/restore`, new FormData());
			// Restoring a folder brings its files back with it.
			await load();
		} catch (e) {
			folders = previous;
			report(e);
		}
	}

	function extensionOf(filename) {
		const dot = filename.lastIndexOf('.');
		if (dot < 1 || dot === filename.length - 1) return 'file';
		return filename.slice(dot + 1).toLowerCase().slice(0, 4);
	}

	function daysLeft(deletedAt) {
		if (!deletedAt) return null;
		const deleted = new Date(deletedAt);
		if (Number.isNaN(deleted.getTime())) return null;
		const elapsed = (Date.now() - deleted.getTime()) / 86400000;
		return Math.max(0, Math.ceil(RETENTION_DAYS - elapsed));
	}

	function remainingLabel(deletedAt) {
		const left = daysLeft(deletedAt);
		if (left === null) return '';
		if (left === 0) return 'Deleted for good soon';
		return `${left} ${left === 1 ? 'day' : 'days'} left`;
	}

	function deletedLabel(deletedAt) {
		if (!deletedAt) return '';
		const date = new Date(deletedAt);
		if (Number.isNaN(date.getTime())) return '';
		const sameYear = date.getFullYear() === new Date().getFullYear();
		return `Deleted ${date.toLocaleDateString(undefined, {
			day: 'numeric',
			month: 'short',
			year: sameYear ? undefined : 'numeric'
		})}`;
	}

	onMount(load);
</script>

<svelte:head><title>Trash · homecloud</title></svelte:head>

<Header />

<main>
	<h1>Trash</h1>
	<p class="count">
		{#if loading}
			Loading…
		{:else if itemCount === 0}
			Empty
		{:else}
			{itemCount}
			{itemCount === 1 ? 'item' : 'items'}, removed for good after {RETENTION_DAYS} days
		{/if}
	</p>

	{#if error}
		<p class="notice">{error}</p>
	{/if}

	{#if loading}
		<p class="quiet">Checking the trash.</p>
	{:else if isEmpty}
		<div class="empty">
			<p class="empty-head">Nothing in the trash</p>
			<p class="quiet">Files and folders you delete wait here for {RETENTION_DAYS} days.</p>
		</div>
	{:else}
		<ul class="list">
			{#each folders as folder (folder.folder_id)}
				<li class="row">
					<span class="badge folder" aria-hidden="true"></span>
					<span class="detail">
						<span class="label">{folder.name}</span>
						<span class="meta">
							<span>{deletedLabel(folder.deleted_at)}</span>
							<span>{remainingLabel(folder.deleted_at)}</span>
						</span>
					</span>
					<span class="actions">
						<button class="btn btn-quiet small" onclick={() => restoreFolder(folder)}>
							Restore
						</button>
					</span>
				</li>
			{/each}

			{#each files as file (file.file_id)}
				<li class="row">
					<span class="badge">{extensionOf(file.filename)}</span>
					<span class="detail">
						<span class="label">{file.filename}</span>
						<span class="meta">
							<span>{deletedLabel(file.deleted_at)}</span>
							<span>{remainingLabel(file.deleted_at)}</span>
						</span>
					</span>
					<span class="actions">
						<button class="btn btn-quiet small" onclick={() => restoreFile(file)}>Restore</button>
					</span>
				</li>
			{/each}
		</ul>
	{/if}
</main>

<style>
	main {
		max-width: 46rem;
		margin: 0 auto;
		padding: 2rem 1.5rem 4rem;
	}

	.count {
		margin: 0.2rem 0 0;
		font-size: 0.925rem;
		color: var(--ink-soft);
	}

	.quiet {
		margin: 0;
		color: var(--ink-soft);
	}

	.list {
		list-style: none;
		margin: 1.75rem 0 0;
		padding: 0;
		border-top: 1px solid var(--line);
	}

	.row {
		display: flex;
		align-items: center;
		gap: 0.85rem;
		padding: 0.7rem 0.5rem;
		border-bottom: 1px solid var(--line);
	}

	.row:hover {
		background: var(--surface);
	}

	.badge {
		flex: none;
		display: grid;
		place-items: center;
		width: 2.25rem;
		height: 2.25rem;
		font-size: 0.65rem;
		font-weight: 600;
		color: var(--teal-dark);
		background: var(--mint-wash);
		border: 1px solid var(--line);
		border-radius: 6px;
		overflow: hidden;
		/* Trashed items read as inactive until you bring them back. */
		filter: grayscale(0.6);
	}

	.badge.folder {
		background: var(--mint);
		border-color: var(--teal);
	}

	.detail {
		display: flex;
		flex: 1;
		flex-direction: column;
		min-width: 0;
	}

	.label {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--ink-soft);
	}

	.meta {
		display: flex;
		gap: 0.75rem;
		font-size: 0.8rem;
		color: var(--ink-soft);
	}

	.actions {
		display: flex;
		flex: none;
		gap: 0.35rem;
	}

	.small {
		padding: 0.3rem 0.7rem;
		font-size: 0.875rem;
	}

	.empty {
		margin-top: 1.75rem;
		padding: 3.5rem 1.5rem;
		text-align: center;
		border: 2px dashed var(--line);
		border-radius: 12px;
	}

	.empty-head {
		margin: 0 0 0.35rem;
		font-size: 1.1rem;
		font-weight: 600;
	}
</style>
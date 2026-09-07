<script>
	import { onMount } from 'svelte';
	import { api } from '$lib/api.js';
	import { signOut, username } from '$lib/auth.js';
	import { goto } from '$app/navigation';

	let folders = $state([]);
	let files = $state([]);
	let rootFolderId = $state(null);

	let loading = $state(true);
	let error = $state('');
	let uploadingCount = $state(0);
	let dragDepth = $state(0);

	let fileInput;

	let isEmpty = $derived(!loading && folders.length === 0 && files.length === 0);
	let dragging = $derived(dragDepth > 0);
	let itemCount = $derived(folders.length + files.length);

	/** A dead session should drop you at sign-in rather than showing an error. */
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
			const data = await api.getJSON('/get-root-contents');
			rootFolderId = data.root_folder_id;
			folders = data.folders ?? [];
			files = data.files ?? [];
		} catch (e) {
			report(e);
		} finally {
			loading = false;
		}
	}

	async function uploadAll(fileList) {
		const chosen = Array.from(fileList ?? []);
		if (chosen.length === 0) return;

		if (rootFolderId === null) {
			error = 'The server didn’t return a root folder, so there’s nowhere to put these. Reload and try again.';
			return;
		}

		error = '';
		uploadingCount = chosen.length;

		for (const file of chosen) {
			try {
				const form = new FormData();
				form.append('folder_id', rootFolderId);
				form.append('file', file);
				await api.upload('/files', form);
			} catch (e) {
				if (e.status === 401) {
					uploadingCount = 0;
					report(e);
					return;
				}
				error = `Couldn’t upload ${file.name}. ${e.message}`;
				break;
			} finally {
				uploadingCount -= 1;
			}
		}

		uploadingCount = 0;
		await load();
	}

	function onPick(event) {
		uploadAll(event.target.files);
		event.target.value = ''; // let the same file be picked twice in a row
	}

	function onDrop(event) {
		event.preventDefault();
		dragDepth = 0;
		uploadAll(event.dataTransfer?.files);
	}

	async function download(file) {
		error = '';
		try {
			const res = await api.getRaw(`/files/${file.file_id}/download`);
			const blob = await res.blob();
			const url = URL.createObjectURL(blob);

			const link = document.createElement('a');
			link.href = url;
			link.download = file.filename;
			document.body.appendChild(link);
			link.click();
			link.remove();
			URL.revokeObjectURL(url);
		} catch (e) {
			report(e);
		}
	}

	async function trash(file) {
		error = '';
		// Drop it from the list immediately, put it back if the server disagrees.
		const previous = files;
		files = files.filter((f) => f.file_id !== file.file_id);
		try {
			await api.remove(`/files/${file.file_id}`);
		} catch (e) {
			files = previous;
			report(e);
		}
	}

	function leave() {
		signOut();
		goto('/login');
	}

	/** Extension badge, since the backend doesn't store a MIME type. */
	function extensionOf(filename) {
		const dot = filename.lastIndexOf('.');
		if (dot < 1 || dot === filename.length - 1) return 'file';
		return filename.slice(dot + 1).toLowerCase().slice(0, 4);
	}

	onMount(load);
</script>

<svelte:head><title>Your files · homecloud</title></svelte:head>

<div
	class="page"
	class:dragging
	ondragenter={(e) => {
		e.preventDefault();
		dragDepth += 1;
	}}
	ondragleave={() => {
		dragDepth = Math.max(0, dragDepth - 1);
	}}
	ondragover={(e) => e.preventDefault()}
	ondrop={onDrop}
	role="region"
	aria-label="File drop area"
>
	<header>
		<p class="mark"><span class="dot" aria-hidden="true"></span>homecloud</p>
		<div class="who">
			{#if $username}<span class="name">{$username}</span>{/if}
			<button class="btn btn-quiet" onclick={leave}>Sign out</button>
		</div>
	</header>

	<main>
		<div class="bar">
			<div>
				<h1>Your files</h1>
				<p class="count">
					{#if loading}
						Loading…
					{:else if itemCount === 0}
						Empty
					{:else}
						{itemCount}
						{itemCount === 1 ? 'item' : 'items'}
					{/if}
				</p>
			</div>

			<button class="btn" onclick={() => fileInput.click()} disabled={uploadingCount > 0}>
				{#if uploadingCount > 0}
					Uploading {uploadingCount}…
				{:else}
					Upload files
				{/if}
			</button>
			<input bind:this={fileInput} type="file" multiple onchange={onPick} hidden />
		</div>

		{#if error}
			<p class="notice">{error}</p>
		{/if}

		{#if loading}
			<p class="quiet">Fetching your files.</p>
		{:else if isEmpty}
			<div class="empty">
				<p class="empty-head">Nothing here yet</p>
				<p class="quiet">Drag files anywhere on this page, or use Upload files above.</p>
			</div>
		{:else}
			<ul class="list">
				{#each folders as folder (folder.folder_id)}
					<li class="row">
						<span class="badge folder" aria-hidden="true"></span>
						<span class="label">{folder.name}</span>
					</li>
				{/each}

				{#each files as file (file.file_id)}
					<li class="row">
						<span class="badge">{extensionOf(file.filename)}</span>
						<span class="label">{file.filename}</span>
						<span class="actions">
							<button class="btn btn-quiet small" onclick={() => download(file)}>Download</button>
							<button class="btn btn-danger small" onclick={() => trash(file)}>Trash</button>
						</span>
					</li>
				{/each}
			</ul>
		{/if}
	</main>

	{#if dragging}
		<div class="curtain" aria-hidden="true">
			<p>Drop to upload</p>
		</div>
	{/if}
</div>

<style>
	.page {
		min-height: 100vh;
	}

	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 1rem 1.5rem;
		border-bottom: 1px solid var(--line);
		background: var(--surface);
	}

	.mark {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0;
		font-weight: 600;
		color: var(--teal);
	}

	.dot {
		width: 0.7rem;
		height: 0.7rem;
		border-radius: 2px;
		background: var(--mint);
		border: 2px solid var(--teal);
	}

	.who {
		display: flex;
		align-items: center;
		gap: 0.85rem;
	}

	.name {
		font-size: 0.925rem;
		color: var(--ink-soft);
	}

	main {
		max-width: 46rem;
		margin: 0 auto;
		padding: 2rem 1.5rem 4rem;
	}

	.bar {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 1rem;
		margin-bottom: 1.5rem;
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
		margin: 1.25rem 0 0;
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
	}

	.badge.folder {
		background: var(--mint);
		border-color: var(--teal);
	}

	.label {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.actions {
		display: flex;
		flex: none;
		gap: 0.35rem;
		opacity: 0;
	}

	.row:hover .actions,
	.row:focus-within .actions {
		opacity: 1;
	}

	.small {
		padding: 0.3rem 0.7rem;
		font-size: 0.875rem;
	}

	.empty {
		margin-top: 1.5rem;
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

	.curtain {
		position: fixed;
		inset: 0;
		display: grid;
		place-items: center;
		background: rgba(233, 251, 247, 0.85);
		border: 3px solid var(--mint);
		pointer-events: none;
	}

	.curtain p {
		margin: 0;
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--teal-dark);
	}

	/* Touch devices have no hover, so actions must always be reachable. */
	@media (hover: none) {
		.actions {
			opacity: 1;
		}
	}

	@media (max-width: 32rem) {
		.bar {
			flex-direction: column;
			align-items: stretch;
		}

		.actions {
			opacity: 1;
		}
	}
</style>
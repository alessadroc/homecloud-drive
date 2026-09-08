<script>
	import { onMount, tick } from 'svelte';
	import { api } from '$lib/api.js';
	import { signOut } from '$lib/auth.js';
	import { goto } from '$app/navigation';
	import Header from '$lib/Header.svelte';
	import Quota from '$lib/Quota.svelte';

	let folders = $state([]);
	let files = $state([]);
	let rootFolderId = $state(null);

	// Where we are. First entry is always root; clicking a crumb truncates.
	let trail = $state([]);

	let loading = $state(true);
	let error = $state('');
	let uploadingCount = $state(0);
	let dragDepth = $state(0);

	let makingFolder = $state(false);
	let newFolderName = $state('');
	let savingFolder = $state(false);

	let bytesUsed = $state(0);
	let quotaBytes = $state(0);

	let movingFile = $state(null);
	let moveTarget = $state('');
	let savingMove = $state(false);

	// bind:this targets are reassigned by Svelte, so they need $state too.
	let fileInput = $state();
	let folderNameInput = $state();

	let currentFolderId = $derived(trail.length ? trail[trail.length - 1].folder_id : null);
	let isEmpty = $derived(!loading && folders.length === 0 && files.length === 0);
	let dragging = $derived(dragDepth > 0);
	let itemCount = $derived(folders.length + files.length);

	/** Somewhere a file in this folder could go: any subfolder here, plus the
	    folder above if we aren't at the root. */
	let moveOptions = $derived.by(() => {
		const options = [];
		if (trail.length > 1) {
			const parent = trail[trail.length - 2];
			options.push({ folder_id: parent.folder_id, label: `Up to ${parent.name}` });
		}
		for (const folder of folders) {
			options.push({ folder_id: folder.folder_id, label: folder.name });
		}
		return options;
	});

	/** A dead session should drop you at sign-in rather than showing an error. */
	function report(e) {
		if (e.status === 401) {
			signOut();
			goto('/login');
			return;
		}
		error = e.message;
	}

	/** Usage is decoration, not data the page depends on - a failure here
	    should leave the bar blank, never break the file list. */
	async function loadUsage() {
		try {
			const data = await api.getJSON('/usage');
			bytesUsed = data.used_bytes ?? 0;
			quotaBytes = data.quota_bytes ?? 0;
		} catch {
			// leave the previous figures in place
		}
	}

	/** First load: discover the root folder and start the trail there. */
	async function bootstrap() {
		error = '';
		loading = true;
		try {
			const data = await api.getJSON('/get-root-contents');
			rootFolderId = data.root_folder_id;
			trail = [{ folder_id: data.root_folder_id, name: 'Your files' }];
			folders = data.folders ?? [];
			files = data.files ?? [];
		} catch (e) {
			report(e);
		} finally {
			loading = false;
		}
		loadUsage();
	}

	async function loadFolder(folderId) {
		error = '';
		loading = true;
		try {
			const data = await api.getJSON(`/folders/${folderId}/contents`);
			folders = data.folders ?? [];
			files = data.files ?? [];
		} catch (e) {
			report(e);
		} finally {
			loading = false;
		}
		loadUsage();
	}

	function refresh() {
		return currentFolderId === null ? bootstrap() : loadFolder(currentFolderId);
	}

	function openFolder(folder) {
		cancelMove();
		trail = [...trail, { folder_id: folder.folder_id, name: folder.name }];
		loadFolder(folder.folder_id);
	}

	function goToCrumb(index) {
		if (index === trail.length - 1) return;
		cancelMove();
		trail = trail.slice(0, index + 1);
		loadFolder(trail[index].folder_id);
	}

	// --- creating folders -------------------------------------------------

	async function startNewFolder() {
		makingFolder = true;
		newFolderName = '';
		await tick();
		folderNameInput?.focus();
	}

	function cancelNewFolder() {
		makingFolder = false;
		newFolderName = '';
	}

	async function saveNewFolder() {
		const name = newFolderName.trim();
		if (!name || savingFolder || currentFolderId === null) return;

		savingFolder = true;
		error = '';
		try {
			const form = new FormData();
			form.append('name', name);
			form.append('parent_folder_id', currentFolderId);
			await api.postForm('/folders', form);
			cancelNewFolder();
			await refresh();
		} catch (e) {
			report(e);
		} finally {
			savingFolder = false;
		}
	}

	function onFolderNameKey(event) {
		if (event.key === 'Enter') {
			event.preventDefault();
			saveNewFolder();
		} else if (event.key === 'Escape') {
			cancelNewFolder();
		}
	}

	// --- moving files -----------------------------------------------------

	function startMove(file) {
		movingFile = file;
		moveTarget = moveOptions.length ? String(moveOptions[0].folder_id) : '';
	}

	function cancelMove() {
		movingFile = null;
		moveTarget = '';
	}

	async function confirmMove() {
		if (!movingFile || !moveTarget || savingMove) return;

		savingMove = true;
		error = '';
		try {
			const form = new FormData();
			form.append('folder_id', moveTarget);
			await api.postForm(`/files/${movingFile.file_id}/move`, form);
			cancelMove();
			await refresh();
		} catch (e) {
			report(e);
		} finally {
			savingMove = false;
		}
	}

	// --- uploading --------------------------------------------------------

	async function uploadAll(fileList) {
		const chosen = Array.from(fileList ?? []);
		if (chosen.length === 0) return;

		if (currentFolderId === null) {
			error = 'Still working out which folder you’re in. Reload and try again.';
			return;
		}

		error = '';
		uploadingCount = chosen.length;

		for (const file of chosen) {
			try {
				const form = new FormData();
				form.append('folder_id', currentFolderId);
				form.append('file', file);
				await api.postForm('/files', form);
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
		await refresh();
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

	// --- file actions -----------------------------------------------------

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

	async function trashFile(file) {
		error = '';
		const previous = files;
		files = files.filter((f) => f.file_id !== file.file_id);
		try {
			await api.remove(`/files/${file.file_id}`);
		} catch (e) {
			files = previous;
			report(e);
		}
	}

	async function trashFolder(folder) {
		error = '';
		const previous = folders;
		folders = folders.filter((f) => f.folder_id !== folder.folder_id);
		try {
			await api.remove(`/folders/${folder.folder_id}`);
		} catch (e) {
			folders = previous;
			report(e);
		}
	}

	// --- display helpers --------------------------------------------------

	/** Extension badge, since the backend doesn't store a MIME type. */
	function extensionOf(filename) {
		const dot = filename.lastIndexOf('.');
		if (dot < 1 || dot === filename.length - 1) return 'file';
		return filename.slice(dot + 1).toLowerCase().slice(0, 4);
	}

	/** Files uploaded before the size column existed report 0; show nothing. */
	function formatSize(bytes) {
		if (!bytes) return '';
		const units = ['B', 'KB', 'MB', 'GB', 'TB'];
		let value = bytes;
		let unit = 0;
		while (value >= 1024 && unit < units.length - 1) {
			value /= 1024;
			unit += 1;
		}
		return `${value < 10 && unit > 0 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
	}

	function formatDate(stamp) {
		if (!stamp) return '';
		const date = new Date(stamp);
		if (Number.isNaN(date.getTime())) return '';
		const sameYear = date.getFullYear() === new Date().getFullYear();
		return date.toLocaleDateString(undefined, {
			day: 'numeric',
			month: 'short',
			year: sameYear ? undefined : 'numeric'
		});
	}

	onMount(bootstrap);
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
	<Header />

	<main>
		<div class="bar">
			<div class="place">
				<nav class="crumbs" aria-label="Folder path">
					{#each trail as crumb, i (crumb.folder_id)}
						{#if i > 0}<span class="sep" aria-hidden="true">/</span>{/if}
						{#if i === trail.length - 1}
							<span class="here" aria-current="page">{crumb.name}</span>
						{:else}
							<button class="crumb" onclick={() => goToCrumb(i)}>{crumb.name}</button>
						{/if}
					{/each}
				</nav>
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

			<div class="tools">
				<button class="btn btn-quiet" onclick={startNewFolder} disabled={makingFolder || loading}>
					New folder
				</button>
				<button class="btn" onclick={() => fileInput.click()} disabled={uploadingCount > 0}>
					{#if uploadingCount > 0}
						Uploading {uploadingCount}…
					{:else}
						Upload files
					{/if}
				</button>
			</div>
			<input bind:this={fileInput} type="file" multiple onchange={onPick} hidden />
		</div>

		{#if error}
			<p class="notice">{error}</p>
		{/if}

		{#if makingFolder}
			<div class="inline-row">
				<span class="badge folder" aria-hidden="true"></span>
				<input
					bind:this={folderNameInput}
					bind:value={newFolderName}
					class="field"
					type="text"
					placeholder="Folder name"
					onkeydown={onFolderNameKey}
					disabled={savingFolder}
				/>
				<button
					class="btn small"
					onclick={saveNewFolder}
					disabled={savingFolder || !newFolderName.trim()}
				>
					{savingFolder ? 'Creating…' : 'Create'}
				</button>
				<button class="btn btn-quiet small" onclick={cancelNewFolder} disabled={savingFolder}>
					Cancel
				</button>
			</div>
		{/if}

		{#if loading}
			<p class="quiet">Fetching your files.</p>
		{:else if isEmpty && !makingFolder}
			<div class="empty">
				<p class="empty-head">Nothing in this folder</p>
				<p class="quiet">Drag files anywhere on this page, or use Upload files above.</p>
			</div>
		{:else if !isEmpty}
			<ul class="list">
				{#each folders as folder (folder.folder_id)}
					<li class="row">
						<button class="open" onclick={() => openFolder(folder)}>
							<span class="badge folder" aria-hidden="true"></span>
							<span class="label">{folder.name}</span>
						</button>
						<span class="actions">
							<button class="btn btn-danger small" onclick={() => trashFolder(folder)}>Trash</button>
						</span>
					</li>
				{/each}

				{#each files as file (file.file_id)}
					<li class="row">
						<span class="badge">{extensionOf(file.filename)}</span>
						<span class="detail">
							<span class="label">{file.filename}</span>
							{#if formatSize(file.size) || formatDate(file.created_at)}
								<span class="meta">
									{#if formatSize(file.size)}<span>{formatSize(file.size)}</span>{/if}
									{#if formatDate(file.created_at)}<span>{formatDate(file.created_at)}</span>{/if}
								</span>
							{/if}
						</span>

						{#if movingFile?.file_id === file.file_id}
							<span class="actions open-actions">
								<select class="field compact" bind:value={moveTarget} disabled={savingMove}>
									{#each moveOptions as option (option.folder_id)}
										<option value={String(option.folder_id)}>{option.label}</option>
									{/each}
								</select>
								<button class="btn small" onclick={confirmMove} disabled={savingMove || !moveTarget}>
									{savingMove ? 'Moving…' : 'Move'}
								</button>
								<button class="btn btn-quiet small" onclick={cancelMove} disabled={savingMove}>
									Cancel
								</button>
							</span>
						{:else}
							<span class="actions">
								{#if moveOptions.length > 0}
									<button class="btn btn-quiet small" onclick={() => startMove(file)}>Move</button>
								{/if}
								<button class="btn btn-quiet small" onclick={() => download(file)}>Download</button>
								<button class="btn btn-danger small" onclick={() => trashFile(file)}>Trash</button>
							</span>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}

		{#if quotaBytes > 0}
			<Quota used={bytesUsed} limit={quotaBytes} />
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

	.tools {
		display: flex;
		flex: none;
		gap: 0.5rem;
	}

	.crumbs {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.4rem;
		font-size: 1.5rem;
		font-weight: 600;
		letter-spacing: -0.01em;
	}

	.crumb {
		font: inherit;
		padding: 0;
		color: var(--teal);
		background: none;
		border: none;
		cursor: pointer;
	}

	.crumb:hover {
		text-decoration: underline;
		text-underline-offset: 3px;
	}

	.sep {
		color: var(--line);
		font-weight: 400;
	}

	.here {
		color: var(--ink);
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

	.inline-row {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		margin-top: 1.25rem;
		padding: 0.6rem 0.5rem;
		background: var(--mint-wash);
		border: 1px solid var(--mint);
		border-radius: var(--radius);
	}

	.inline-row .field {
		flex: 1;
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

	/* Folder rows are a button so they're keyboard reachable, but they must
	   still lay out like the file rows beside them. */
	.open {
		display: flex;
		flex: 1;
		align-items: center;
		gap: 0.85rem;
		min-width: 0;
		padding: 0;
		font: inherit;
		color: inherit;
		text-align: left;
		background: none;
		border: none;
		cursor: pointer;
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
		opacity: 0;
	}

	/* The move controls are mid-interaction, so they stay put. */
	.open-actions {
		opacity: 1;
	}

	.row:hover .actions,
	.row:focus-within .actions {
		opacity: 1;
	}

	.small {
		padding: 0.3rem 0.7rem;
		font-size: 0.875rem;
	}

	.compact {
		width: auto;
		max-width: 12rem;
		padding: 0.3rem 0.5rem;
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

		.crumbs {
			font-size: 1.25rem;
		}
	}
</style>
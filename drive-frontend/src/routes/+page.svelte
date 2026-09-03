<script>
    import { onMount } from 'svelte';
    import { api } from '$lib/api.js';
    import { clearToken } from '$lib/auth.js';
    import { goto } from '$app/navigation';

    // Raw-tuple column positions (one place to change if schema reorders).
    // files:   [file_id, user_id, folder_id, filename, file_uid, deleted_at]
    // folders: [folder_id, user_id, parent_folder_id, name, is_root, deleted_at]
    const FILE = { id: 0, name: 3 };
    const FOLDER = { id: 0, name: 3, isRoot: 4 };

    let folders = $state([]);
    let files = $state([]);
    let rootFolderId = $state(null);
    let error = $state('');
    let loading = $state(true);
    let uploading = $state(false);

    function handleAuthError(e) {
        if (e.message === 'UNAUTHORIZED') {
            clearToken();
            goto('/login');
            return true;
        }
        error = e.message;
        return false;
    }

    async function loadContents() {
        error = '';
        loading = true;
        try {
            const data = await api.getJSON('/get-root-contents');
            rootFolderId = data.root_folder_id;   // <-- use it directly
            folders = data.folders || [];
            files = data.files || [];
        } catch (e) {
            handleAuthError(e);
        } finally {
            loading = false;
        }
    }

    async function handleUpload(event) {
        const file = event.target.files[0];
        if (!file) return;
        if (rootFolderId === null) {
            error = 'Could not determine your root folder — try reloading.';
            return;
        }

        uploading = true;
        error = '';
        try {
            const formData = new FormData();
            formData.append('folder_id', rootFolderId);
            formData.append('file', file);
            await api.upload('/files', formData);
            await loadContents();
        } catch (e) {
            handleAuthError(e);
        } finally {
            uploading = false;
            event.target.value = '';
        }
    }

    async function downloadFile(fileId, filename) {
        try {
            const res = await api.getRaw(`/files/${fileId}/download`);
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
        } catch (e) {
            handleAuthError(e);
        }
    }

    async function trashFile(fileId) {
        try {
            await api.delete(`/files/${fileId}`);
            await loadContents();
        } catch (e) {
            handleAuthError(e);
        }
    }

    function logout() {
        clearToken();
        goto('/login');
    }

    onMount(loadContents);
</script>

<div class="drive">
    <header>
        <h1>My Drive</h1>
        <button onclick={logout} class="logout">Log out</button>
    </header>

    {#if error}<p class="error">{error}</p>{/if}

    <div class="upload-bar">
        <label class="upload-btn">
            {uploading ? 'Uploading…' : 'Upload file'}
            <input type="file" onchange={handleUpload} disabled={uploading} hidden />
        </label>
    </div>

    {#if loading}
        <p>Loading…</p>
    {:else}
        <section>
            <h2>Folders</h2>
            {#if folders.length === 0}
                <p class="empty">No folders</p>
            {:else}
                <ul>
                    {#each folders as folder}
                        <li>📁 {folder[FOLDER.name]}</li>
                    {/each}
                </ul>
            {/if}
        </section>

        <section>
            <h2>Files</h2>
            {#if files.length === 0}
                <p class="empty">No files</p>
            {:else}
                <ul>
                    {#each files as file}
                        <li>
                            <span>📄 {file[FILE.name]}</span>
                            <span class="actions">
                                <button onclick={() => downloadFile(file[FILE.id], file[FILE.name])}>Download</button>
                                <button onclick={() => trashFile(file[FILE.id])} class="trash">Trash</button>
                            </span>
                        </li>
                    {/each}
                </ul>
            {/if}
        </section>
    {/if}
</div>

<style>
    .drive { max-width: 700px; margin: 2rem auto; padding: 0 1rem; }
    header { display: flex; justify-content: space-between; align-items: center; }
    .upload-bar { margin: 1rem 0; }
    .upload-btn { display: inline-block; padding: 0.5rem 1rem; background: #2563eb; color: white; border-radius: 4px; cursor: pointer; }
    ul { list-style: none; padding: 0; }
    li { display: flex; justify-content: space-between; align-items: center; padding: 0.5rem; border-bottom: 1px solid #eee; }
    .actions button { margin-left: 0.5rem; cursor: pointer; }
    .trash { color: #dc2626; }
    .empty { color: #888; font-style: italic; }
    .error { color: #dc2626; }
    .logout { cursor: pointer; }
</style>
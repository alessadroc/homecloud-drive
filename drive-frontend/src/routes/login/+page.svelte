<script>
    import { goto } from '$app/navigation';
    import { api } from '$lib/api.js';
    import { setToken } from '$lib/auth.js';

    let username = $state('');
    let password = $state('');
    let error = $state('');
    let loading = $state(false);

    async function handleLogin() {
        error = '';
        loading = true;
        try {
            const res = await api.post(
                `/sign-in?username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
            );
            const data = await res.json();
            setToken(data.token);
            goto('/');
        } catch (e) {
            error = e.message === 'UNAUTHORIZED' ? 'Invalid username or password' : e.message;
        } finally {
            loading = false;
        }
    }
</script>

<div class="auth-container">
    <h1>Sign In</h1>
    <form onsubmit={(e) => { e.preventDefault(); handleLogin(); }}>
        <input type="text" placeholder="Username" bind:value={username} autocomplete="username" />
        <input type="password" placeholder="Password" bind:value={password} autocomplete="current-password" />
        {#if error}<p class="error">{error}</p>{/if}
        <button type="submit" disabled={loading}>{loading ? 'Signing in…' : 'Sign In'}</button>
    </form>
    <p class="switch">Don't have an account? <a href="/signup">Sign up</a></p>
</div>

<style>
    .auth-container { max-width: 320px; margin: 4rem auto; display: flex; flex-direction: column; gap: 1rem; }
    form { display: flex; flex-direction: column; gap: 0.75rem; }
    input { padding: 0.6rem; font-size: 1rem; border: 1px solid #ccc; border-radius: 4px; }
    button { padding: 0.6rem; font-size: 1rem; cursor: pointer; border: none; border-radius: 4px; background: #2563eb; color: white; }
    button:disabled { opacity: 0.6; cursor: default; }
    .error { color: #dc2626; font-size: 0.9rem; margin: 0; }
    .switch { font-size: 0.9rem; text-align: center; }
</style>
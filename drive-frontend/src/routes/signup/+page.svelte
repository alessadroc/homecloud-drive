<script>
    import { goto } from '$app/navigation';
    import { api } from '$lib/api.js';

    let username = $state('');
    let password = $state('');
    let error = $state('');
    let loading = $state(false);

    async function handleSignup() {
        error = '';
        loading = true;
        try {
            await api.post(
                `/sign-up?username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
            );
            goto('/login');
        } catch (e) {
            error = e.message;
        } finally {
            loading = false;
        }
    }
</script>

<div class="auth-container">
    <h1>Sign Up</h1>
    <form onsubmit={(e) => { e.preventDefault(); handleSignup(); }}>
        <input type="text" placeholder="Username" bind:value={username} autocomplete="username" />
        <input type="password" placeholder="Password" bind:value={password} autocomplete="new-password" />
        {#if error}<p class="error">{error}</p>{/if}
        <button type="submit" disabled={loading}>{loading ? 'Creating account…' : 'Sign Up'}</button>
    </form>
    <p class="switch">Already have an account? <a href="/login">Sign in</a></p>
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
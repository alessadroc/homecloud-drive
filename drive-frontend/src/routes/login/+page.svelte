<script>
	import { goto } from '$app/navigation';
	import { api, query } from '$lib/api.js';
	import { signIn } from '$lib/auth.js';

	let name = $state('');
	let password = $state('');
	let error = $state('');
	let busy = $state(false);

	async function submit(event) {
		event.preventDefault();
		if (busy) return;

		error = '';
		busy = true;
		try {
			const data = await api.postJSON('/sign-in', { username: name, password });
			signIn(data.token, name);
			goto('/');
		} catch (e) {
			error = e.status === 401 ? 'That username and password don’t match an account.' : e.message;
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head><title>Sign in · homecloud</title></svelte:head>

<main>
	<p class="mark"><span class="dot" aria-hidden="true"></span>homecloud</p>

	<h1>Sign in</h1>
	<p class="sub">Your files, on the machine in your house.</p>

	<form onsubmit={submit}>
		<label>
			Username
			<input class="field" type="text" bind:value={name} autocomplete="username" required />
		</label>

		<label>
			Password
			<input
				class="field"
				type="password"
				bind:value={password}
				autocomplete="current-password"
				required
			/>
		</label>

		{#if error}<p class="notice">{error}</p>{/if}

		<button class="btn" type="submit" disabled={busy}>
			{busy ? 'Signing in…' : 'Sign in'}
		</button>
	</form>

	<p class="alt">No account yet? <a href="/signup">Create one</a></p>
</main>

<style>
	main {
		max-width: 22rem;
		margin: 5rem auto;
		padding: 0 1.25rem;
	}

	.mark {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0 0 2.5rem;
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

	.sub {
		margin: 0.35rem 0 2rem;
		color: var(--ink-soft);
	}

	form {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	label {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		font-size: 0.9rem;
		color: var(--ink-soft);
	}

	.alt {
		margin-top: 2rem;
		font-size: 0.925rem;
		color: var(--ink-soft);
	}
</style>
<script>
	import { page } from '$app/stores';
	import { signOut, username } from '$lib/auth.js';
	import { goto } from '$app/navigation';

	function leave() {
		signOut();
		goto('/login');
	}
</script>

<header>
	<p class="mark"><span class="dot" aria-hidden="true"></span>homecloud</p>

	<nav>
		<a href="/" class:current={$page.url.pathname === '/'}>Files</a>
		<a href="/trash" class:current={$page.url.pathname === '/trash'}>Trash</a>
	</nav>

	<div class="who">
		{#if $username}<span class="name">{$username}</span>{/if}
		<button class="btn btn-quiet" onclick={leave}>Sign out</button>
	</div>
</header>

<style>
	header {
		display: flex;
		align-items: center;
		gap: 1.5rem;
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

	nav {
		display: flex;
		gap: 1rem;
		font-size: 0.95rem;
	}

	nav a {
		color: var(--ink-soft);
		text-decoration: none;
		padding-bottom: 2px;
		border-bottom: 2px solid transparent;
	}

	nav a:hover {
		color: var(--teal);
	}

	nav a.current {
		color: var(--ink);
		border-bottom-color: var(--mint);
	}

	.who {
		display: flex;
		align-items: center;
		gap: 0.85rem;
		margin-left: auto;
	}

	.name {
		font-size: 0.925rem;
		color: var(--ink-soft);
	}

	@media (max-width: 32rem) {
		header {
			flex-wrap: wrap;
			gap: 0.75rem 1rem;
		}

		.who {
			margin-left: auto;
		}
	}
</style>
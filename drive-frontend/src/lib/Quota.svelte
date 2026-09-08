<script>
	let { used = 0, limit = 0 } = $props();

	let ratio = $derived(limit > 0 ? Math.min(1, used / limit) : 0);
	let percent = $derived(Math.round(ratio * 100));
	// Colour shifts only when it means something: you're nearly out of room.
	let tight = $derived(ratio >= 0.9);

	function format(bytes) {
		if (!bytes) return '0 B';
		const units = ['B', 'KB', 'MB', 'GB', 'TB'];
		let value = bytes;
		let unit = 0;
		while (value >= 1024 && unit < units.length - 1) {
			value /= 1024;
			unit += 1;
		}
		return `${value < 10 && unit > 0 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
	}
</script>

<div class="quota">
	<div
		class="track"
		role="progressbar"
		aria-label="Storage used"
		aria-valuemin="0"
		aria-valuemax={limit}
		aria-valuenow={used}
	>
		<div class="fill" class:tight style="width: {percent}%"></div>
	</div>

	<p class="line">
		<span>{format(used)} of {format(limit)} used</span>
		{#if tight}
			<span class="warn">Nearly full</span>
		{/if}
	</p>
</div>

<style>
	.quota {
		margin-top: 2.5rem;
		padding-top: 1.25rem;
		border-top: 1px solid var(--line);
	}

	.track {
		height: 6px;
		background: var(--mint-wash);
		border-radius: 3px;
		overflow: hidden;
	}

	.fill {
		height: 100%;
		background: var(--teal);
		border-radius: 3px;
		transition: width 200ms ease;
	}

	.fill.tight {
		background: var(--rust);
	}

	.line {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		margin: 0.5rem 0 0;
		font-size: 0.85rem;
		color: var(--ink-soft);
	}

	.warn {
		color: var(--rust);
	}
</style>
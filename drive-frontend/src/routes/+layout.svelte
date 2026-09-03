<script>
    import { token } from '$lib/auth.js';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import { browser } from '$app/environment';

    let { children } = $props();

    const publicRoutes = ['/login', '/signup'];

    let isPublic = $derived(publicRoutes.includes($page.url.pathname));
    let canRender = $derived(isPublic ? !$token : !!$token);

    $effect(() => {
        if (!browser) return;
        if (!$token && !isPublic) goto('/login');
        if ($token && isPublic) goto('/');
    });
</script>

{#if canRender}
    {@render children()}
{/if}
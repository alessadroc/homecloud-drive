// The auth guard, the token store and every fetch need a browser. Rendering
// any of this on the server would produce a signed-out shell that flashes
// before the real state loads, so opt out entirely.
export const ssr = false;
export const prerender = false;
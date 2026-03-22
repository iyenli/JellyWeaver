<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	import '../app.css';
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Jelly Weaver</title>
</svelte:head>

<slot />

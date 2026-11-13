<script lang="ts">
  import "../app.css";
  import { page } from "$app/state";
  import { Badge } from "@arlen/ui-kit/components/ui/badge";
  import { LIVE } from "$lib/api/client";
  import { CLOCK } from "$lib/api/fixture";
  import { dayTime } from "$lib/format";

  let { children } = $props();

  const NAV = [
    { href: "/", label: "Inbox", match: (p: string) => p === "/" || p.startsWith("/requests") },
    { href: "/steady", label: "Steady Orders", match: (p: string) => p.startsWith("/steady") },
    { href: "/ledger", label: "Open Ledger", match: (p: string) => p.startsWith("/ledger") },
  ];
  // The phone page is one question and two buttons, nothing else.
  const phone = $derived(page.url.pathname.startsWith("/approve"));
</script>

<div class="app" class:phone>
  <header class="bar">
    <a class="brand" href="/" id="nav-home">
      <span class="word">Validio</span>
      <span class="kitchen">Hotel Espoo kitchen</span>
    </a>
    {#if !phone}
      <nav aria-label="Main">
        {#each NAV as item (item.href)}
          <a href={item.href} id="nav-{item.label.toLowerCase().replace(' ', '-')}" aria-current={item.match(page.url.pathname) ? "page" : undefined}>{item.label}</a>
        {/each}
      </nav>
    {/if}
    <div class="meta">
      {#if !LIVE}<Badge variant="warn" id="fixture-mark">Fixture data</Badge>{/if}
      <span class="clock">Clock {dayTime(CLOCK)}</span>
    </div>
  </header>
  <main>
    {@render children()}
  </main>
</div>

<style>
  .app {
    min-height: 100dvh;
    background: var(--background);
  }
  .bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 1.5rem;
    padding: 0.625rem var(--space-page, 1.5rem);
    border-bottom: 1px solid color-mix(in srgb, var(--foreground) 10%, transparent);
    background: var(--card);
  }
  .brand {
    display: flex;
    align-items: baseline;
    gap: 0.625rem;
    text-decoration: none;
    color: var(--foreground);
    border-radius: var(--radius-button);
  }
  .word {
    font-size: var(--text-lg);
    font-weight: 700;
    letter-spacing: -0.01em;
  }
  .kitchen {
    font-size: var(--text-xs);
    color: color-mix(in srgb, var(--foreground) 64%, transparent);
  }
  nav {
    display: flex;
    gap: 0.25rem;
  }
  nav a {
    display: inline-flex;
    align-items: center;
    height: var(--height-control, 30px);
    padding-inline: 0.625rem;
    border-radius: var(--radius-button);
    font-size: var(--text-sm);
    font-weight: 500;
    text-decoration: none;
    color: color-mix(in srgb, var(--foreground) 70%, transparent);
  }
  nav a:hover {
    background: color-mix(in srgb, var(--foreground) 6%, transparent);
    color: var(--foreground);
  }
  nav a[aria-current="page"] {
    background: color-mix(in srgb, var(--foreground) 9%, transparent);
    color: var(--foreground);
  }
  a:focus-visible {
    outline: 2px solid var(--ring);
    outline-offset: 1px;
  }
  .meta {
    margin-inline-start: auto;
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }
  .clock {
    font-size: var(--text-xs);
    color: color-mix(in srgb, var(--foreground) 64%, transparent);
    font-variant-numeric: tabular-nums;
  }
  @media (max-width: 640px) {
    .bar {
      padding-inline: 1rem;
    }
    nav {
      order: 3;
      width: 100%;
      margin-inline-start: -0.625rem;
    }
    .kitchen,
    .clock {
      display: none;
    }
  }
</style>

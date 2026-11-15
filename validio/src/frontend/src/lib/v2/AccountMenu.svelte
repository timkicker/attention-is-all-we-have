<script lang="ts">
  /// The kitchen in the band, as an account menu (plans/025, S2): its initials and its name. On
  /// the desk a menu opens under it; on the phone the same choices rise as a sheet from the
  /// bottom, which a flick down closes. What is in it: who is logged in, Settings, the theme,
  /// the keys, Log out.
  import { goto } from "$app/navigation";
  import { DropdownMenu } from "bits-ui";
  import { Check, Keyboard, LogOut, Settings } from "@lucide/svelte";
  import type { Account } from "$lib/api/types";
  import { reduced } from "$lib/motion";
  import { setMode, theme, type Mode } from "$lib/theme.svelte";
  import { logOut } from "../../routes/settings/sections";

  let {
    account,
    phone = false,
    current = false,
    onkeys,
  }: { account: Account; phone?: boolean; current?: boolean; onkeys?: () => void } = $props();

  /** "Hotel Espoo kitchen" → "HE": the first letters of the first two words. */
  const initials = $derived(
    account.name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w[0]?.toUpperCase() ?? "")
      .join("") || "K",
  );
  const who = $derived(account.isDemo ? "Demo kitchen" : (account.email ?? ""));

  const MODES: { value: Mode; label: string }[] = [
    { value: "system", label: "System" },
    { value: "light", label: "Light" },
    { value: "dark", label: "Dark" },
  ];

  let trigger = $state<HTMLElement>();
  let open = $state(false);
  const origin = () => {
    const r = trigger?.getBoundingClientRect();
    return r ? { x: r.left + r.width / 2, y: r.top + r.height / 2 } : undefined;
  };
  function pickTheme(m: Mode) {
    // The reveal grows from the account mark, where it was asked for.
    setMode(m, origin());
  }

  // ---------- the phone's sheet ----------
  let sheet = $state<HTMLDialogElement>();
  let dragY = $state(0);
  let dragging = $state(false);
  let startY = 0;
  function openSheet() {
    if (!sheet || sheet.open) return;
    dragY = 0;
    sheet.showModal();
    open = true;
  }
  function closeSheet() {
    if (!sheet?.open) return;
    if (reduced()) {
      sheet.close();
      return;
    }
    sheet.classList.add("leaving");
    setTimeout(() => {
      sheet?.classList.remove("leaving");
      sheet?.close();
      dragY = 0;
    }, 220);
  }
  function down(e: PointerEvent) {
    dragging = true;
    startY = e.clientY;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function move(e: PointerEvent) {
    if (!dragging) return;
    // Up resists (a fifth), down follows the finger.
    const d = e.clientY - startY;
    dragY = d > 0 ? d : d / 5;
  }
  function up() {
    if (!dragging) return;
    dragging = false;
    if (dragY > 80) closeSheet();
    else dragY = 0;
  }
  async function go(fn: () => unknown) {
    closeSheet();
    await fn();
  }
</script>

{#snippet mark(big = false)}
  <span class="av num" class:big aria-hidden="true">{initials}</span>
{/snippet}

{#snippet header()}
  <div class="am-head">
    {@render mark(true)}
    <span class="am-who">
      <span class="am-name">{account.name}</span>
      <span class="am-sub">{who}{#if account.customerNumber}{who ? ", " : ""}Valio customer {account.customerNumber}{/if}</span>
    </span>
  </div>
{/snippet}

{#if !phone}
  <DropdownMenu.Root bind:open>
    <DropdownMenu.Trigger id="nav-settings">
      {#snippet child({ props })}
        <button
          type="button"
          {...props}
          class="acct"
          class:on={current}
          data-testid="nav-settings"
          aria-label="Account: {account.name}"
          bind:this={trigger}
        >
          {@render mark()}
          <span class="acct-name">{account.name}</span>
          {#if current}<span class="acct-ink" aria-hidden="true"></span>{/if}
        </button>
      {/snippet}
    </DropdownMenu.Trigger>
    <DropdownMenu.Portal>
      <DropdownMenu.Content class="am" align="end" sideOffset={6} data-testid="account-menu">
        {@render header()}
        <DropdownMenu.Separator class="am-sep" />
        <DropdownMenu.Item class="am-item" onSelect={() => goto("/settings")} data-testid="menu-settings">
          <Settings size={16} strokeWidth={1.75} aria-hidden="true" />
          <span class="am-label">Settings</span>
          <kbd class="am-key">g s</kbd>
        </DropdownMenu.Item>
        <DropdownMenu.Item class="am-item" onSelect={() => onkeys?.()} data-testid="menu-keys">
          <Keyboard size={16} strokeWidth={1.75} aria-hidden="true" />
          <span class="am-label">Keyboard shortcuts</span>
          <kbd class="am-key">?</kbd>
        </DropdownMenu.Item>
        <DropdownMenu.Separator class="am-sep" />
        <DropdownMenu.Group>
          <DropdownMenu.GroupHeading class="am-group">Theme</DropdownMenu.GroupHeading>
          <DropdownMenu.RadioGroup value={theme.mode} onValueChange={(v) => pickTheme(v as Mode)}>
            {#each MODES as m (m.value)}
              <DropdownMenu.RadioItem class="am-item" value={m.value} closeOnSelect={false} data-testid="menu-theme-{m.value}">
                {#snippet children({ checked })}
                  <span class="am-check">{#if checked}<Check size={16} strokeWidth={2} aria-hidden="true" />{/if}</span>
                  <span class="am-label">{m.label}</span>
                {/snippet}
              </DropdownMenu.RadioItem>
            {/each}
          </DropdownMenu.RadioGroup>
        </DropdownMenu.Group>
        <DropdownMenu.Separator class="am-sep" />
        <DropdownMenu.Item class="am-item" onSelect={() => logOut()} data-testid="menu-logout">
          <LogOut size={16} strokeWidth={1.75} aria-hidden="true" />
          <span class="am-label">Log out</span>
        </DropdownMenu.Item>
      </DropdownMenu.Content>
    </DropdownMenu.Portal>
  </DropdownMenu.Root>
{:else}
  <button
    type="button"
    class="acct phone"
    class:on={current}
    id="phone-settings"
    data-testid="phone-settings"
    aria-label="Account: {account.name}"
    aria-haspopup="dialog"
    bind:this={trigger}
    onclick={openSheet}
  >
    {@render mark()}
    <span class="acct-name">{account.name}</span>
  </button>
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions (a click on the backdrop closes, Escape is the keyboard's way) -->
  <dialog
    class="sheet"
    bind:this={sheet}
    aria-label="Account"
    data-testid="account-sheet"
    onclose={() => (open = false)}
    onclick={(e) => e.target === sheet && closeSheet()}
    oncancel={(e) => {
      e.preventDefault();
      closeSheet();
    }}
    style:transform={dragY ? `translateY(${dragY}px)` : undefined}
    class:dragging
  >
    <div class="sh-grab" onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={up} role="presentation">
      <span class="sh-bar"></span>
    </div>
    {@render header()}
    <div class="sh-list">
      <button type="button" class="am-item" onclick={() => go(() => goto("/settings"))} data-testid="sheet-settings">
        <Settings size={18} strokeWidth={1.75} aria-hidden="true" /><span class="am-label">Settings</span>
      </button>
      <div class="am-group" id="sheet-theme">Theme</div>
      <div class="sh-seg" role="radiogroup" aria-labelledby="sheet-theme">
        {#each MODES as m (m.value)}
          <button
            type="button"
            role="radio"
            aria-checked={theme.mode === m.value}
            class:on={theme.mode === m.value}
            onclick={(e) => setMode(m.value, { x: e.clientX, y: e.clientY })}
            data-testid="sheet-theme-{m.value}">{m.label}</button
          >
        {/each}
      </div>
      <button type="button" class="am-item" onclick={() => go(() => logOut())} data-testid="sheet-logout">
        <LogOut size={18} strokeWidth={1.75} aria-hidden="true" /><span class="am-label">Log out</span>
      </button>
    </div>
  </dialog>
{/if}

<style>
  /* ---------- the mark in the band ---------- */
  .acct {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
    height: 40px;
    margin: auto 0;
    padding: 0 10px 0 6px;
    border: 0;
    border-radius: var(--radius-button);
    background: none;
    font: inherit;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    font-weight: 500;
    color: var(--valio-band-fg);
    transition:
      background-color var(--duration-fast) ease,
      transform var(--v-dur-press) var(--v-ease-out);
  }
  @media (hover: hover) and (pointer: fine) {
    .acct:hover {
      background: var(--valio-band-hover);
    }
  }
  .acct:active {
    transform: scale(0.97);
  }
  .acct[data-state="open"] {
    background: var(--valio-band-hover);
  }
  .acct:focus-visible {
    outline-color: var(--valio-band-fg);
    outline-offset: 0;
  }
  .acct-name {
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .acct-ink {
    position: absolute;
    left: 6px;
    right: 10px;
    bottom: -10px;
    height: 2px;
    background: var(--valio-band-fg);
  }
  .av {
    display: inline-grid;
    place-items: center;
    flex: none;
    width: 28px;
    height: 28px;
    border-radius: var(--radius-button);
    border: 1px solid var(--valio-band-muted);
    color: var(--valio-band-fg);
    font-size: 12px;
    line-height: 1;
    font-weight: 600;
    letter-spacing: 0.02em;
  }
  .av.big {
    width: 40px;
    height: 40px;
    font-size: 15px;
    border-color: var(--valio);
    background: var(--valio-tint);
    color: var(--valio);
  }
  .acct.phone {
    height: 44px;
    padding-right: 4px;
  }
  .acct.phone .acct-name {
    max-width: 150px;
  }

  /* ---------- the menu ---------- */
  :global(.am) {
    z-index: 60;
    min-width: 280px;
    max-width: 340px;
    padding: 6px;
    border: 1px solid var(--v-line-strong);
    border-radius: var(--radius-card);
    background: var(--v-surface);
    color: var(--v-fg);
    transform-origin: var(--bits-dropdown-menu-content-transform-origin);
    animation: am-in 160ms var(--v-ease-out);
  }
  :global(.am[data-state="closed"]) {
    animation: am-out 120ms var(--v-ease-out) forwards;
  }
  @keyframes am-in {
    from {
      opacity: 0;
      transform: scale(0.97);
    }
  }
  @keyframes am-out {
    to {
      opacity: 0;
      transform: scale(0.97);
    }
  }
  .am-head {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 10px 12px;
  }
  .am-who {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .am-name {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 600;
    overflow-wrap: anywhere;
  }
  .am-sub {
    font-size: var(--fs-cap);
    line-height: 16px;
    color: var(--v-muted);
  }
  :global(.am-sep) {
    height: 1px;
    margin: 4px 0;
    background: var(--v-line);
  }
  :global(.am-group),
  .am-group {
    padding: 8px 10px 4px;
    font-size: var(--fs-cap);
    line-height: 16px;
    color: var(--v-muted);
  }
  :global(.am-item) {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    min-height: 36px;
    padding: 0 10px;
    border: 0;
    border-radius: var(--radius-button);
    background: none;
    font: inherit;
    font-size: var(--fs-head);
    line-height: var(--lh-head);
    color: var(--v-fg);
    text-align: left;
    outline: none;
    cursor: pointer;
  }
  :global(.am-item[data-highlighted]) {
    background: var(--v-subtle);
    color: var(--valio);
  }
  :global(.am-item[data-state="checked"]) {
    color: var(--valio);
    font-weight: 500;
  }
  .am-label {
    flex: 1;
  }
  .am-check {
    display: inline-grid;
    width: 16px;
    place-items: center;
  }
  .am-key {
    font-family: var(--v-sans);
    font-size: var(--fs-cap);
    color: var(--v-faint);
  }

  /* ---------- the phone's sheet ---------- */
  .sheet {
    position: fixed;
    inset: auto 0 0 0;
    width: 100%;
    max-width: none;
    margin: 0;
    padding: 0 0 calc(12px + env(safe-area-inset-bottom));
    border: 0;
    border-top: 1px solid var(--v-line-strong);
    border-radius: var(--radius-modal) var(--radius-modal) 0 0;
    background: var(--v-surface);
    color: var(--v-fg);
    transition: transform var(--v-dur-ui) var(--v-ease-drawer);
  }
  .sheet[open] {
    animation: sh-in 320ms var(--v-ease-drawer);
  }
  .sheet.dragging {
    transition: none;
  }
  .sheet:global(.leaving) {
    transform: translateY(100%) !important;
    transition: transform 220ms var(--v-ease-out);
  }
  .sheet::backdrop {
    background: var(--v-tint-strong);
    animation: v-fade-in 200ms var(--v-ease-out);
  }
  @keyframes sh-in {
    from {
      transform: translateY(100%);
    }
  }
  .sh-grab {
    display: grid;
    place-items: center;
    height: 28px;
    touch-action: none;
    cursor: grab;
  }
  .sh-bar {
    width: 36px;
    height: 4px;
    border-radius: var(--radius-chip);
    background: var(--v-line-strong);
  }
  .sheet .am-head {
    padding: 4px 16px 12px;
    border-bottom: 1px solid var(--v-line);
  }
  .sh-list {
    padding: 6px 8px 0;
  }
  .sh-list :global(.am-item) {
    min-height: 48px;
    font-size: var(--fs-body);
  }
  .sh-list .am-group {
    padding: 12px 10px 6px;
  }
  .sh-seg {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    padding: 0 10px 8px;
  }
  .sh-seg button {
    min-height: 44px;
    border: 1px solid var(--v-line-strong);
    border-radius: var(--radius-button);
    background: var(--v-surface);
    font: inherit;
    font-size: var(--fs-head);
    color: var(--v-fg);
  }
  .sh-seg button.on {
    border-color: var(--valio);
    background: var(--valio-tint);
    color: var(--valio);
    font-weight: 500;
  }
  @media (prefers-reduced-motion: reduce) {
    :global(.am),
    :global(.am[data-state="closed"]),
    .sheet[open] {
      animation: v-fade-in 120ms linear;
    }
  }
</style>

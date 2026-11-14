<script lang="ts">
  /// The page menu ⋯: the demo switches and the theme. A dropdown on the
  /// desktop, a sheet (kit Dialog) on the phone.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Dialog } from "@arlen/ui-kit/components/ui/dialog";
  import * as DropdownMenu from "@arlen/ui-kit/components/ui/dropdown-menu";
  import { Check, Ellipsis } from "@lucide/svelte";
  import { LIVE } from "$lib/api/client";
  import { chrome, demoActions } from "$lib/chrome.svelte";
  import { setMode, theme, type Mode } from "$lib/theme.svelte";

  const MODES: { id: Mode; label: string }[] = [
    { id: "system", label: "System" },
    { id: "light", label: "Light" },
    { id: "dark", label: "Dark" },
  ];
  let sheet = $state(false);

  // A radio group is one tab stop; the arrows move the choice (WAI-ARIA radio).
  function arrows(e: KeyboardEvent) {
    const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
    const home = e.key === "Home" ? 0 : e.key === "End" ? MODES.length - 1 : undefined;
    if (step === undefined && home === undefined) return;
    e.preventDefault();
    const at = MODES.findIndex((m) => m.id === theme.mode);
    const next = home ?? (at + (step ?? 0) + MODES.length) % MODES.length;
    setMode(MODES[next].id);
    const group = e.currentTarget as HTMLElement;
    group.querySelectorAll<HTMLElement>('[role="radio"]')[next]?.focus();
  }

  function run(fn: () => Promise<void>) {
    sheet = false;
    void fn();
  }
</script>

{#if chrome.phone}
  <span class="menu-wrap" id="page-menu">
    <Button variant="ghost" size="icon-sm" aria-label="Page menu" aria-haspopup="dialog" data-testid="page-menu" class="menu-btn" onclick={() => (sheet = true)}>
      <Ellipsis />
    </Button>
  </span>
  <Dialog open={sheet} onClose={() => (sheet = false)} ariaLabel="Page menu" size="lg">
    <div class="v-sheet">
      <div class="grab" aria-hidden="true"></div>
      <p class="mlabel" id="demo-label">Demo</p>
      {#if !LIVE}<p class="mi note">Recorded from the backend</p>{/if}
      <button type="button" class="mi" id="menu-ask" data-testid="menu-ask" onclick={() => run(demoActions.ask)}>Ask as the kitchen's agent</button>
      <button
        type="button"
        class="mi"
        role="switch"
        aria-checked={chrome.stockIsOut}
        id="stock-out"
        data-testid="stock-out"
        onclick={() => run(chrome.stockIsOut ? demoActions.stockBack : demoActions.stockOut)}
      >
        Mozzarella stock-out
        <span class="vsw" class:on={chrome.stockIsOut} aria-hidden="true"><span class="thumb"></span></span>
      </button>
      <button type="button" class="mi" id="menu-reset" onclick={() => run(demoActions.reset)}>Start over</button>
      <div class="msep" role="separator"></div>
      <p class="mlabel" id="theme-label">Theme</p>
      <div role="radiogroup" aria-labelledby="theme-label" tabindex="-1" onkeydown={arrows}>
        {#each MODES as m (m.id)}
          <button type="button" class="mi" role="radio" aria-checked={theme.mode === m.id} tabindex={theme.mode === m.id ? 0 : -1} onclick={() => setMode(m.id)}>
            {m.label}<span class="ck end" class:on={theme.mode === m.id}><Check size={16} strokeWidth={1.75} aria-hidden="true" /></span>
          </button>
        {/each}
      </div>
    </div>
  </Dialog>
{:else}
  <DropdownMenu.Root>
    <DropdownMenu.Trigger>
      {#snippet child({ props })}
        <span class="menu-wrap" id="page-menu">
          <Button {...props} variant="ghost" size="icon-sm" aria-label="Page menu" data-testid="page-menu" class="menu-btn">
            <Ellipsis />
          </Button>
        </span>
      {/snippet}
    </DropdownMenu.Trigger>
    <DropdownMenu.Content align="end" class="v-menu">
      <DropdownMenu.Label>Demo</DropdownMenu.Label>
      {#if !LIVE}<DropdownMenu.Item disabled>Recorded from the backend</DropdownMenu.Item>{/if}
      <DropdownMenu.Item id="menu-ask" data-testid="menu-ask" onSelect={() => void demoActions.ask()}>Ask as the kitchen's agent</DropdownMenu.Item>
      <DropdownMenu.CheckboxItem
        class="stock-item"
        id="stock-out"
        data-testid="stock-out"
        checked={chrome.stockIsOut}
        onSelect={() => void (chrome.stockIsOut ? demoActions.stockBack() : demoActions.stockOut())}
      >
        Mozzarella stock-out
        <span class="vsw" class:on={chrome.stockIsOut} aria-hidden="true"><span class="thumb"></span></span>
      </DropdownMenu.CheckboxItem>
      <DropdownMenu.Item id="menu-reset" onSelect={() => void demoActions.reset()}>Start over</DropdownMenu.Item>
      <DropdownMenu.Separator />
      <DropdownMenu.Label>Theme</DropdownMenu.Label>
      <DropdownMenu.RadioGroup value={theme.mode} onValueChange={(v) => setMode(v as Mode)}>
        {#each MODES as m (m.id)}
          <DropdownMenu.RadioItem value={m.id}>{m.label}</DropdownMenu.RadioItem>
        {/each}
      </DropdownMenu.RadioGroup>
    </DropdownMenu.Content>
  </DropdownMenu.Root>
{/if}

<style>
  .menu-wrap {
    display: inline-flex;
  }
  .v-sheet {
    padding: 8px 6px calc(16px + env(safe-area-inset-bottom));
  }
  .grab {
    width: 36px;
    height: 4px;
    border-radius: var(--radius-chip);
    background: var(--v-tint-strong);
    margin: 0 auto 8px;
  }
  .mi {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    min-height: 44px;
    padding: 0 10px;
    margin: 0;
    border-radius: var(--radius-button);
    background: none;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    color: var(--v-fg);
    text-align: left;
  }
  button.mi:hover {
    background: var(--v-tint-mid);
  }
  .mi:disabled,
  .mi.note {
    color: var(--v-muted);
  }
  .end {
    margin-left: auto;
    display: inline-flex;
  }
  .ck {
    visibility: hidden;
    display: inline-flex;
    color: var(--v-muted);
  }
  .ck.on {
    visibility: visible;
  }
  .msep {
    height: 1px;
    background: var(--v-line);
    margin: 6px -6px;
  }
  .mlabel {
    margin: 0;
    padding: 12px 10px 4px;
    font-size: var(--fs-cap);
    line-height: 16px;
    color: var(--v-muted);
  }
  /* The stock-out row: one toggle row with the kit Switch's look (the whole row is the control). */
  :global(.v-menu .stock-item) {
    padding-inline-start: 8px;
  }
  :global(.v-menu .stock-item [data-slot="dropdown-menu-checkbox-item-indicator"]) {
    display: none;
  }
  .vsw {
    position: relative;
    margin-left: auto;
    width: 32px;
    height: 18px;
    flex-shrink: 0;
    border-radius: var(--radius-input);
    border: 1px solid var(--control-border);
    background: var(--control-bg-strong);
  }
  .vsw .thumb {
    position: absolute;
    top: 1px;
    left: 1px;
    width: 14px;
    height: 14px;
    border-radius: max(0px, calc(var(--radius-input) - 2px));
    background: var(--foreground);
    box-shadow: var(--v-shadow-thumb);
  }
  .vsw.on {
    background: var(--valio);
    border-color: var(--valio);
  }
  .vsw.on .thumb {
    background: var(--v-on-valio);
    transform: translateX(14px);
  }
  :global(.dialog-backdrop:has(.v-sheet)) {
    align-items: flex-end;
    padding: 0;
  }
  :global(.dialog-card:has(.v-sheet)) {
    max-width: none;
    border-radius: var(--radius-modal) var(--radius-modal) 0 0;
  }
</style>

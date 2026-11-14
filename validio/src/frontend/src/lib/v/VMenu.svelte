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
  const stockLabel = $derived(chrome.stockIsOut ? "Stock-out simulated" : "Simulate stock-out of mozzarella");

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
      {#if !LIVE}<p class="mi note">Demo data, recorded from the backend</p>{/if}
      <button type="button" class="mi" id="stock-out" data-testid="stock-out" disabled={chrome.stockIsOut} onclick={() => run(demoActions.stockOut)}>{stockLabel}</button>
      <button type="button" class="mi" id="menu-reset" onclick={() => run(demoActions.reset)}>Start over</button>
      <div class="msep" role="separator"></div>
      <p class="mlabel" id="theme-label">Theme</p>
      <div role="radiogroup" aria-labelledby="theme-label">
        {#each MODES as m (m.id)}
          <button type="button" class="mi" role="radio" aria-checked={theme.mode === m.id} onclick={() => setMode(m.id)}>
            <span class="ck" class:on={theme.mode === m.id}><Check size={16} strokeWidth={1.75} aria-hidden="true" /></span>{m.label}
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
      {#if !LIVE}<DropdownMenu.Item disabled>Demo data, recorded from the backend</DropdownMenu.Item>{/if}
      <DropdownMenu.Item id="stock-out" data-testid="stock-out" disabled={chrome.stockIsOut} onSelect={() => void demoActions.stockOut()}>{stockLabel}</DropdownMenu.Item>
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
    border-radius: 999px;
    background: color-mix(in srgb, var(--v-fg) 20%, transparent);
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
    border-radius: 6px;
    background: none;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    color: var(--v-fg);
    text-align: left;
  }
  button.mi:hover {
    background: color-mix(in srgb, var(--v-fg) 8%, transparent);
  }
  .mi:disabled,
  .mi.note {
    color: var(--v-muted);
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
  :global(.dialog-backdrop:has(.v-sheet)) {
    align-items: flex-end;
    padding: 0;
  }
  :global(.dialog-card:has(.v-sheet)) {
    max-width: none;
    border-radius: 12px 12px 0 0;
  }
</style>

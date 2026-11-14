<script lang="ts">
  /// The owner's 6-digit approval code. Inserted where a write needs it,
  /// scrolled into view and focused; Enter submits.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Input } from "@arlen/ui-kit/components/ui/input";
  import { LIVE } from "$lib/api/client";
  import { session } from "$lib/owner.svelte";

  let {
    value = $bindable(""),
    error = "",
    onsubmit,
    submitLabel,
    oncancel,
    focus = true,
    busy = false,
  }: {
    value?: string;
    error?: string;
    onsubmit: () => void;
    submitLabel?: string;
    oncancel?: () => void;
    /** Off where the code is the last field of a longer form (Agent Rules). */
    focus?: boolean;
    busy?: boolean;
  } = $props();

  let box: HTMLElement | undefined = $state();
  $effect(() => {
    if (!focus) return;
    box?.scrollIntoView({ block: "nearest" });
    document.getElementById("approve-code")?.focus();
  });
  $effect(() => {
    if (error) document.getElementById("approve-code")?.focus();
  });
</script>

<form
  class="vcode"
  class:bad={!!error}
  bind:this={box}
  onsubmit={(e) => {
    e.preventDefault();
    onsubmit();
  }}
>
  <label for="approve-code">Approval code</label>
  <div class="line">
    <Input
      id="approve-code"
      bind:value
      inputmode="numeric"
      autocomplete="one-time-code"
      maxlength={6}
      class="code mono"
      data-testid="code-input"
      aria-invalid={error ? true : undefined}
      aria-describedby="code-help"
    />
    {#if submitLabel}
      {#if oncancel}<Button variant="outline" onclick={oncancel}>Cancel</Button>{/if}
      <Button type="submit" data-testid="code-submit" disabled={busy}>{submitLabel}</Button>
    {/if}
  </div>
  <p class="help" id="code-help">
    <!-- a demo copy's code stands in the demo bar, once -->{#if error}{error}{:else if !session.account?.demoCode}{LIVE ? "The 6-digit code you set for approvals." : "Demo: any 6 digits"}{/if}
  </p>
</form>

<style>
  /* Field and buttons at the one control height (tokens.css): 32 on the desk, 44 on the phone. */
  .vcode {
    display: flex;
    flex-direction: column;
    gap: 4px;
    scroll-margin-bottom: 84px;
  }
  label {
    font-size: 14px;
    line-height: 20px;
    font-weight: 500;
  }
  .line {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .line :global(.code) {
    max-width: 160px;
    font-size: 16px;
    line-height: 24px;
    font-variant-numeric: tabular-nums;
  }
  .help {
    margin: 0;
    font-size: 14px;
    line-height: 20px;
    color: var(--v-muted);
  }
  .bad .help {
    color: var(--v-bad-text);
  }
</style>

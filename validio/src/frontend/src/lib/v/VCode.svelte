<script lang="ts">
  /// The owner's 6-digit approval code. Inserted where a write needs it,
  /// scrolled into view and focused; Enter submits.
  ///
  /// Six cells over one real input (plans/007): the input keeps its id, its value and the
  /// keyboard; the cells only draw it. A digit lands with a small settle, the next cell is
  /// petrol, and a wrong code shakes the row once (reduced motion: the colour only).
  import { tick } from "svelte";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { LIVE } from "$lib/api/client";
  import { reduced } from "$lib/motion";
  import { session } from "$lib/owner.svelte";
  import BusyLabel from "$lib/v2/BusyLabel.svelte";

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
  let focused = $state(false);
  let shake = $state(false);
  $effect(() => {
    if (!focus) return;
    box?.scrollIntoView({ block: "nearest" });
    document.getElementById("approve-code")?.focus();
  });
  // Every new problem focuses the field and shakes the row once more.
  $effect(() => {
    if (!error) return;
    document.getElementById("approve-code")?.focus();
    if (reduced()) return;
    shake = false;
    tick().then(() => requestAnimationFrame(() => (shake = true)));
  });
  const at = $derived(Math.min(value.length, 5));
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
    <div class="cells" class:shake class:focused onanimationend={() => (shake = false)}>
      {#each Array(6) as _, i (i)}
        <span class="cell" class:active={focused && i === at && value.length < 6} class:full={focused && value.length === 6 && i === 5} aria-hidden="true">
          {#if value[i]}<span class="digit">{value[i]}</span>{:else if focused && i === value.length}<span class="caret"></span>{/if}
        </span>
      {/each}
      <input
        id="approve-code"
        class="code-overlay"
        data-testid="code-input"
        bind:value
        oninput={(e) => (value = e.currentTarget.value.replace(/\D/g, "").slice(0, 6))}
        onfocus={() => (focused = true)}
        onblur={() => (focused = false)}
        inputmode="numeric"
        autocomplete="one-time-code"
        maxlength={6}
        spellcheck="false"
        aria-invalid={error ? true : undefined}
        aria-describedby="code-help"
      />
    </div>
    {#if submitLabel}
      {#if oncancel}<Button variant="outline" onclick={oncancel}>Cancel</Button>{/if}
      <Button type="submit" data-testid="code-submit" disabled={busy}><BusyLabel {busy} idle={submitLabel} working="Checking" /></Button>
    {/if}
  </div>
  <p class="help" id="code-help">
    {#if error}{error}{:else if session.account?.demoCode}Demo code: <span class="mono" data-code>{session.account.demoCode}</span>{:else}{LIVE ? "The 6-digit code you set for approvals." : "Demo: any 6 digits"}{/if}
  </p>
</form>

<style>
  /* Cells and buttons at the one control height (tokens.css): 34 on the desk, 44 on the phone. */
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
    transition: color var(--duration-fast) ease;
  }
  .vcode:focus-within label {
    color: var(--valio);
  }
  .vcode.bad:focus-within label {
    color: var(--v-bad-text);
  }
  .line {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .cells {
    position: relative;
    display: grid;
    grid-template-columns: repeat(6, 30px);
    gap: 5px;
    height: var(--height-control);
  }
  .cell {
    display: grid;
    place-items: center;
    border: 1px solid var(--v-line-strong);
    border-radius: var(--radius-input);
    background: var(--v-surface);
    font-family: var(--font-mono);
    font-size: 17px;
    line-height: 1;
    font-variant-numeric: tabular-nums;
    transition: border-color var(--duration-fast) ease;
  }
  .cell.active,
  .cell.full {
    border-color: var(--valio);
  }
  .bad .cell {
    border-color: var(--v-bad);
  }
  .digit {
    animation: v-digit 120ms var(--v-ease-out);
  }
  @keyframes v-digit {
    from {
      opacity: 0;
      transform: scale(0.9);
    }
  }
  .caret {
    width: 2px;
    height: 18px;
    background: var(--valio);
    animation: v-caret 1s steps(1) infinite;
  }
  @keyframes v-caret {
    50% {
      opacity: 0;
    }
  }
  .cells.focused {
    outline: 2px solid var(--valio);
    outline-offset: 2px;
    border-radius: var(--radius-input);
  }
  .bad .cells.focused {
    outline-color: var(--v-bad);
  }
  .cells.focused:not(:has(:focus-visible)) {
    outline: none;
  }
  .cells.shake {
    animation: v-shake 320ms var(--v-ease-out);
  }
  @keyframes v-shake {
    20% {
      transform: translateX(-6px);
    }
    40% {
      transform: translateX(6px);
    }
    60% {
      transform: translateX(-4px);
    }
    80% {
      transform: translateX(4px);
    }
  }
  /* The real field, over the cells: it takes the keys, the paste and the one-time code. */
  .code-overlay {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
    border: 0;
    background: transparent;
    color: transparent;
    caret-color: transparent;
    font-size: 16px;
    letter-spacing: 30px;
    opacity: 0.01;
    outline: none;
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
  /* The phone: one box of six segments, so the cells, Cancel and Approve stay on one line. */
  @media (max-width: 760px) {
    .cells {
      grid-template-columns: repeat(6, 24px);
      gap: 0;
      border: 1px solid var(--v-line-strong);
      border-radius: var(--radius-input);
      overflow: hidden;
    }
    .cell {
      border: 0;
      border-radius: 0;
    }
    .cell + .cell {
      border-left: 1px solid var(--v-line);
    }
    .cell.active,
    .cell.full {
      background: var(--valio-tint);
    }
    .bad .cells {
      border-color: var(--v-bad);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .caret,
    .cells.shake,
    .digit {
      animation: none;
    }
  }
</style>

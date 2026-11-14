<script lang="ts">
  /// The owner's 6 digit approval code, asked once and kept in memory for the
  /// session. A write the server refused for want of it comes back here.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Input } from "@arlen/ui-kit/components/ui/input";
  import { isCode, owner } from "$lib/owner.svelte";

  let {
    onready,
    problem = "",
    action = "Continue",
    value = $bindable(""),
  }: { onready?: () => void; problem?: string; action?: string; value?: string } = $props();

  let wrong = $state(false);
  // The field appears because a write needs it, so the keyboard lands in it.
  $effect(() => {
    document.getElementById("approve-code")?.focus();
  });

  // Inside another form (the approve page) this is a plain field; on its own
  // it is a form with its own button.
  function use(e: SubmitEvent) {
    e.preventDefault();
    if (!isCode(value)) {
      wrong = true;
      return;
    }
    wrong = false;
    owner.code = value;
    onready?.();
  }
</script>

<svelte:element this={onready ? "form" : "div"} class="code-field" onsubmit={onready ? use : undefined}>
  <label for="approve-code">Approval code</label>
  <div class="line">
    <Input
      id="approve-code"
      bind:value
      inputmode="numeric"
      autocomplete="one-time-code"
      maxlength={6}
      placeholder="6-digit code"
      class="code num"
      data-testid="code-input"
      aria-invalid={wrong || problem ? true : undefined}
      aria-describedby="code-help"
    />
    {#if onready}<Button type="submit" id="use-code" data-testid="code-submit">{action}</Button>{/if}
  </div>
  <p class="help" id="code-help" class:t-bad={wrong || problem}>
    {wrong ? "The code has 6 digits." : problem || "Asked once per visit."}
  </p>
</svelte:element>

<style>
  .code-field {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  label {
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--color-fg-secondary);
  }
  .line {
    display: flex;
    gap: 0.5rem;
  }
  .line :global(.code) {
    max-width: 10rem;
    font-variant-numeric: tabular-nums;
  }
  .line :global(.code:not(:placeholder-shown)) {
    letter-spacing: 0.2em;
  }
  .help {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
</style>

<script lang="ts">
  /// The notification stack (plans/012): bottom right on the desk, above the dock on the phone.
  /// A toast rises from the bottom edge and leaves by it (400 ms ease, Sonner's timing), older
  /// ones glide up, each goes after 6 s unless the pointer or focus rests on the stack. On the
  /// phone a flick sideways dismisses it.
  import { flip } from "svelte/animate";
  import { X } from "@lucide/svelte";
  import { ease, reduced } from "$lib/motion";
  import { dismiss, toasts, type Toast } from "$lib/toast.svelte";

  const LIFE = 6000;
  const timers = new Map<number, { left: number; started: number; t?: ReturnType<typeof setTimeout> }>();
  let held = false;

  function start(id: number) {
    const tm = timers.get(id) ?? { left: LIFE, started: 0 };
    tm.started = Date.now();
    clearTimeout(tm.t);
    tm.t = setTimeout(() => close(id), tm.left);
    timers.set(id, tm);
  }
  function pause() {
    held = true;
    for (const tm of timers.values()) {
      clearTimeout(tm.t);
      tm.left = Math.max(1200, tm.left - (Date.now() - tm.started));
    }
  }
  function resume() {
    held = false;
    for (const id of timers.keys()) start(id);
  }
  function close(id: number) {
    clearTimeout(timers.get(id)?.t);
    timers.delete(id);
    dismiss(id);
  }
  $effect(() => {
    for (const t of toasts.list) if (!timers.has(t.id)) (held ? timers.set(t.id, { left: LIFE, started: 0 }) : start(t.id));
  });

  // Enter and leave by the bottom edge; a swiped toast leaves the way it was flung.
  const flung = new Map<number, number>();
  const enter = (_n: Element) =>
    reduced() ? { duration: 120, css: (t: number) => `opacity:${t}` } : { duration: 400, easing: ease, css: (t: number, u: number) => `opacity:${t};transform:translateY(${u * 100}%)` };
  const leave = (_n: Element, { id }: { id: number }) => {
    if (reduced()) return { duration: 120, css: (t: number) => `opacity:${t}` };
    const dx = flung.get(id);
    flung.delete(id);
    if (dx !== undefined) return { duration: 200, easing: ease, css: (t: number, u: number) => `opacity:${t};transform:translateX(${dx + Math.sign(dx) * u * 120}px)` };
    return { duration: 400, easing: ease, css: (t: number, u: number) => `opacity:${t};transform:translateY(${u * 100}%)` };
  };

  // Swipe to dismiss: 1:1 with the finger, away by distance or by speed, back with ease-out otherwise.
  let drag: { id: number; x0: number; t0: number; dx: number; el: HTMLElement } | null = null;
  function down(e: PointerEvent, t: Toast) {
    if (e.pointerType === "mouse" || (e.target as HTMLElement).closest("a, button")) return;
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    el.style.transition = "none";
    drag = { id: t.id, x0: e.clientX, t0: performance.now(), dx: 0, el };
  }
  function move(e: PointerEvent) {
    if (!drag) return;
    drag.dx = e.clientX - drag.x0;
    drag.el.style.transform = `translateX(${drag.dx}px)`;
  }
  function up() {
    if (!drag) return;
    const { id, dx, t0, el } = drag;
    drag = null;
    const v = Math.abs(dx) / Math.max(1, performance.now() - t0);
    if (Math.abs(dx) > 80 || v > 0.11) {
      flung.set(id, dx);
      close(id);
    } else {
      el.style.transition = "transform 200ms var(--v-ease-out)";
      el.style.transform = "";
    }
  }
</script>

<section class="toaster" aria-label="Notifications" onpointerenter={pause} onpointerleave={resume} onfocusin={pause} onfocusout={resume}>
  <ol aria-live="polite">
    {#each toasts.list as t (t.id)}
      <!-- svelte-ignore a11y_no_noninteractive_element_interactions (the swipe is a touch extra; Dismiss is the button) -->
      <li
        class="toast tone-{t.tone}"
        data-testid="toast"
        animate:flip={{ duration: reduced() ? 0 : 400, easing: ease }}
        in:enter
        out:leave={{ id: t.id }}
        onpointerdown={(e) => down(e, t)}
        onpointermove={move}
        onpointerup={up}
        onpointercancel={up}
        onkeydown={(e) => e.key === "Escape" && close(t.id)}
      >
        <div class="t-main">
          <p class="t-title">{t.title}</p>
          {#if t.body}<p class="t-body">{t.body}</p>{/if}
          {#if t.action}<a class="t-act q-link" href={t.action.href} onclick={() => close(t.id)}>{t.action.label}</a>{/if}
        </div>
        <button type="button" class="t-x" aria-label="Dismiss" onclick={() => close(t.id)}><X size={14} aria-hidden="true" /></button>
      </li>
    {/each}
  </ol>
</section>

<style>
  .toaster {
    position: fixed;
    right: 24px;
    bottom: 24px;
    z-index: 40;
    width: 360px;
    pointer-events: none;
  }
  ol {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .toast {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px;
    padding: 12px 8px 12px 14px;
    border: 1px solid var(--v-line-strong);
    border-left: 2px solid var(--valio);
    border-radius: var(--radius-card);
    background: var(--v-surface);
    pointer-events: auto;
    touch-action: pan-y;
  }
  .toast.tone-ok {
    border-left-color: var(--v-ok);
  }
  .toast.tone-bad {
    border-left-color: var(--v-bad);
  }
  .t-main {
    min-width: 0;
  }
  .t-title {
    margin: 0;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
  }
  .t-body {
    margin: 2px 0 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
    overflow-wrap: anywhere;
  }
  .t-act {
    display: inline-block;
    margin-top: 6px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    font-weight: 500;
    color: var(--valio);
  }
  .t-x {
    display: grid;
    place-items: center;
    width: 32px;
    height: 32px;
    margin: -6px 0 0;
    padding: 0;
    border: 0;
    border-radius: var(--radius-button);
    background: none;
    color: var(--v-faint);
    transition:
      color var(--duration-fast) ease,
      transform var(--v-dur-press) var(--v-ease-out);
  }
  @media (hover: hover) and (pointer: fine) {
    .t-x:hover {
      color: var(--v-fg);
    }
  }
  .t-x:active {
    transform: scale(0.95);
  }
  @media (max-width: 760px) {
    .toaster {
      left: 16px;
      right: 16px;
      bottom: calc(56px + env(safe-area-inset-bottom) + 12px);
      width: auto;
    }
  }
</style>

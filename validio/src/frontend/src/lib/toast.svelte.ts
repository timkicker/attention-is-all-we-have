// The notifications the agent's news raises (plans/012). The layout decides when; Toaster draws them.
export type Tone = "wait" | "ok" | "bad";
export interface Toast {
  id: number;
  tone: Tone;
  title: string;
  body?: string;
  action?: { href: string; label: string };
}
let next = 1;
export const toasts = $state<{ list: Toast[] }>({ list: [] });

export function toast(t: Omit<Toast, "id">): void {
  toasts.list = [...toasts.list, { ...t, id: next++ }].slice(-3);
}
export function dismiss(id: number): void {
  toasts.list = toasts.list.filter((t) => t.id !== id);
}

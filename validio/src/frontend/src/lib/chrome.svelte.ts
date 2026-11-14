// What the shell knows across pages: phone or not, and a counter that goes up
// after a demo reset (so every page fetches again).
const phoneQuery = typeof window !== "undefined" ? window.matchMedia("(max-width: 760px)") : null;

export const chrome = $state({
  title: "",
  version: 0,
  /** At most 760 px: no sidebar, a tab bar and a sticky header instead. */
  phone: phoneQuery?.matches ?? false,
  /** A detail page (VHead with a way back): on the phone it draws its own header. */
  detail: false,
});

phoneQuery?.addEventListener("change", (e) => (chrome.phone = e.matches));

export function setTitle(title: string) {
  chrome.title = title;
}

export function bump() {
  chrome.version += 1;
}

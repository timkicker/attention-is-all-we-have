// What the shell knows across pages: phone or not, a counter that goes up
// when the presenter changes the demo state (so every page fetches again),
// and the demo bar's Reset.
const phoneQuery = typeof window !== "undefined" ? window.matchMedia("(max-width: 760px)") : null;

export const chrome = $state({
  title: "",
  version: 0,
  /** At most 760 px: no sidebar, a dock and a sticky header instead. */
  phone: phoneQuery?.matches ?? false,
  /** A detail page (VHead with a way back): on the phone it draws its own header. */
  detail: false,
  /** Approve asks for the code now: on the phone the demo bar shows only then. */
  asking: false,
});

phoneQuery?.addEventListener("change", (e) => (chrome.phone = e.matches));

export function setTitle(title: string) {
  chrome.title = title;
}

export function bump() {
  chrome.version += 1;
}

/** The demo bar's Reset, set by the layout (which owns the token dialog). */
export const demoActions: { reset: () => Promise<void> } = {
  reset: async () => {},
};

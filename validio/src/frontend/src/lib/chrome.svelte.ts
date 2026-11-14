// What the shell knows across pages: phone or not, a counter that goes up
// when the presenter changes the demo state (so every page fetches again),
// and the demo switches the page menu offers.
const phoneQuery = typeof window !== "undefined" ? window.matchMedia("(max-width: 760px)") : null;

export const chrome = $state({
  title: "",
  version: 0,
  /** At most 760 px: no sidebar, a dock and a sticky header instead. */
  phone: phoneQuery?.matches ?? false,
  /** Whether the stock-out is on, for the menu. */
  stockIsOut: false,
});

phoneQuery?.addEventListener("change", (e) => (chrome.phone = e.matches));

export function setTitle(title: string) {
  chrome.title = title;
}

export function bump() {
  chrome.version += 1;
}

/** The presenter's demo switches, set by the layout (which owns the token dialog). */
export const demoActions: {
  stockOut: () => Promise<void>;
  stockBack: () => Promise<void>;
  reset: () => Promise<void>;
  ask: () => Promise<void>;
} = {
  stockOut: async () => {},
  stockBack: async () => {},
  reset: async () => {},
  ask: async () => {},
};

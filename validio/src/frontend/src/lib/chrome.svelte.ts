// What the window chrome shows for the current page: the bar title, the door
// back on the phone, and a counter that goes up when the presenter changes the
// demo state, so every page fetches again.
export const chrome = $state({
  title: "",
  back: null as null | { href: string; label: string },
  version: 0,
  /** Below 760px: no sidebar, the bar carries the way back. */
  phone: false,
});

export function setChrome(title: string, back: null | { href: string; label: string } = null) {
  chrome.title = title;
  chrome.back = back;
}

export function bump() {
  chrome.version += 1;
}

/** The presenter's demo switches, set by the layout (which owns the token
 *  dialog) so a page can offer them where the demo script says. */
export const demoActions: { stockOut: () => Promise<void> } = { stockOut: async () => {} };

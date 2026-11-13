// What the window chrome shows for the current page: the bar title, the door
// back on the phone, and a counter that goes up when the presenter changes the
// demo state, so every page fetches again.
export const chrome = $state({
  title: "",
  back: null as null | { href: string; label: string },
  version: 0,
});

export function setChrome(title: string, back: null | { href: string; label: string } = null) {
  chrome.title = title;
  chrome.back = back;
}

export function bump() {
  chrome.version += 1;
}

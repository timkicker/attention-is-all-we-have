// The theme menu: System follows the device, Light and Dark stay.
export type Mode = "system" | "light" | "dark";
const KEY = "validio-theme";

function stored(): Mode {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark") return v;
  } catch {
    // no storage: System
  }
  return "system";
}

export const theme = $state({ mode: stored() as Mode });

export function setMode(m: Mode) {
  theme.mode = m;
  try {
    if (m === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, m);
  } catch {
    // no storage: this visit only
  }
  const light = m === "system" ? matchMedia("(prefers-color-scheme: light)").matches : m === "light";
  document.documentElement.dataset.theme = light ? "light" : "dark";
}

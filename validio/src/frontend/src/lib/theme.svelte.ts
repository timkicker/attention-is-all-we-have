// The theme menu: Light is the default, System follows the device, Dark stays.
export type Mode = "system" | "light" | "dark";
const KEY = "validio-theme";

function stored(): Mode {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "system" || v === "dark") return v;
  } catch {
    // no storage: Light
  }
  return "light";
}

export const theme = $state({ mode: stored() as Mode });

export function setMode(m: Mode) {
  theme.mode = m;
  try {
    if (m === "light") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, m);
  } catch {
    // no storage: this visit only
  }
  const light = m === "system" ? matchMedia("(prefers-color-scheme: light)").matches : m === "light";
  document.documentElement.dataset.theme = light ? "light" : "dark";
}

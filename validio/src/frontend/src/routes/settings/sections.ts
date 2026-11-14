// The Settings sections, in the order of the list. Log out is the last item
// of the list and no page of its own.
import { goto } from "$app/navigation";
import { api } from "$lib/api/client";
import { session } from "$lib/owner.svelte";

export const SECTIONS = [
  { id: "kitchen", label: "Kitchen" },
  { id: "diet", label: "Diet and allergens" },
  { id: "login", label: "Login and approval code" },
  { id: "theme", label: "Theme" },
] as const;
export type SectionId = (typeof SECTIONS)[number]["id"];

export async function logOut() {
  try {
    await api.logout();
  } finally {
    session.account = null;
    await goto("/login");
  }
}

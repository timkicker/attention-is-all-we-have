// Log out: the session ends on the server, then the login page.
import { goto } from "$app/navigation";
import { api } from "$lib/api/client";
import { viewTransition } from "$lib/motion";
import { session } from "$lib/owner.svelte";

/** The session ends on the server; the whole page then crossfades to the door (plans/025). */
export async function logOut() {
  try {
    await api.logout();
  } finally {
    await viewTransition(async () => {
      session.account = null;
      await goto("/login");
    });
  }
}

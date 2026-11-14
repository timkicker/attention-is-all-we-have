// Log out: the session ends on the server, then the login page.
import { goto } from "$app/navigation";
import { api } from "$lib/api/client";
import { session } from "$lib/owner.svelte";

export async function logOut() {
  try {
    await api.logout();
  } finally {
    session.account = null;
    await goto("/login");
  }
}

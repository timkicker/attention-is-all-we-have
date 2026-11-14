import { redirect } from "@sveltejs/kit";

// v1 Orders lives in Activity now.
export const load = () => {
  redirect(308, "/activity");
};

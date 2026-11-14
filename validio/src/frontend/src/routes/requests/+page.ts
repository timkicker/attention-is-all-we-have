import { redirect } from "@sveltejs/kit";

// v1 requests are Activity items.
export const load = () => {
  redirect(308, "/activity");
};

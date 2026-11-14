import { redirect } from "@sveltejs/kit";

// The steady list is the Orders page's "Steady" filter now.
export const load = () => redirect(307, "/orders?f=steady");

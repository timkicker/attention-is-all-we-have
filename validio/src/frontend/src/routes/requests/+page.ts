import { redirect } from "@sveltejs/kit";

// Requests are listed on the Orders page.
export const load = () => redirect(307, "/orders");

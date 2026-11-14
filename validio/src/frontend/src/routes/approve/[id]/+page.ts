import { redirect } from "@sveltejs/kit";

// v1 approve links name an order, not a request: approval happens in the waiting item's detail.
export const load = () => {
  redirect(308, "/activity?status=waiting");
};

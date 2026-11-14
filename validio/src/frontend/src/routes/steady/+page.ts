import { redirect } from "@sveltejs/kit";

// Standing orders are an Activity filter.
export const load = () => {
  redirect(308, "/activity?status=standing");
};

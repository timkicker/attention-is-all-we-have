import { redirect } from "@sveltejs/kit";

// The Spend Pass limits are the Rules now.
export const load = () => {
  redirect(308, "/rules");
};

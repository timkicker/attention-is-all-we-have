// The pass's limits are the Agent page's Rules now; old links land there.
import { redirect } from "@sveltejs/kit";

export const load = () => {
  redirect(307, "/agent#rules");
};

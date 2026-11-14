import { redirect } from "@sveltejs/kit";

// v1 Ledger lives in Activity now: every detail has its Proof.
export const load = () => {
  redirect(308, "/activity");
};

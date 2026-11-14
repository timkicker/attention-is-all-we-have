import { redirect } from "@sveltejs/kit";

// A v1 request link opens the same request in Activity.
export const load = ({ params }: { params: { id: string } }) => {
  redirect(308, `/activity/${encodeURIComponent(params.id)}`);
};

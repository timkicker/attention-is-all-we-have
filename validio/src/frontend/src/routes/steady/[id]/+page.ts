import { redirect } from "@sveltejs/kit";

// A standing order opens as an Activity item under its own id.
export const load = ({ params }: { params: { id: string } }) => {
  redirect(308, `/activity/${encodeURIComponent(params.id)}`);
};

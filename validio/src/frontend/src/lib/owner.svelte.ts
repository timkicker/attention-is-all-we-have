import type { Account } from "./api/types";

// The two secrets a person types into the web app, kept in memory only: gone
// on reload, never in storage, never in the build.
//   code       the owner's 6 digit approval code, sent as X-Approve-Code on
//              every write (approve, reject, renew, accept)
//   demoToken  the presenter's token for the demo switches, X-Demo-Token
export const owner = $state({ code: "", demoToken: "", askToken: false });

export const isCode = (v: string) => /^\d{6}$/.test(v);

// Who is logged in. `checked` turns true once the server answered; `account`
// stays null when nobody is, and the layout then sends the page to /login.
export const session = $state({ checked: false, account: null as Account | null });

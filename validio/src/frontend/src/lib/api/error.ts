/** An answer that was not 2xx. `status` lets a page react, e.g. ask for the code on 403. */
/** Refused for want of the presenter's demo token: the kitchen gate (401) or a demo switch (403). */
export const needsToken = (e: unknown): boolean =>
  e instanceof ApiError && (e.status === 401 || (e.status === 403 && /demo token|kitchen/i.test(e.message)));

/** Set by the layout: opens the demo-token dialog, true once the presenter typed one. */
export const tokenPrompt: { ask: null | (() => Promise<boolean>) } = { ask: null };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

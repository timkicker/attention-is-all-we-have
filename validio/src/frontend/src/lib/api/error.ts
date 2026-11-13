/** An answer that was not 2xx. `status` lets a page react, e.g. ask for the code on 403. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

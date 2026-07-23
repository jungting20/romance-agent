import type { ApiError } from "./contracts";

export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly error: ApiError,
  ) {
    super(error.message);
    this.name = "ApiRequestError";
  }
}

interface JsonRequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH";
  body?: unknown;
}

export async function requestJson<ResponseBody>(
  path: string,
  { method = "GET", body }: JsonRequestOptions = {},
): Promise<ResponseBody> {
  const response = await fetch(path, {
    method,
    headers: body === undefined ? { Accept: "application/json" } : jsonHeaders,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const responseBody: unknown = await response.json();

  if (!response.ok) {
    throw new ApiRequestError(response.status, responseBody as ApiError);
  }

  return responseBody as ResponseBody;
}

const jsonHeaders = {
  Accept: "application/json",
  "Content-Type": "application/json",
};

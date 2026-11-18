import { readSession } from "@/src/auth/session";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

type ApiRequestOptions = RequestInit & {
  params?: Record<string, string | number | boolean>;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiRequest<T>(
  endpoint: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  if (!API_BASE_URL) {
    throw new Error("API URL is not configured.");
  }

  const { params, headers, ...requestOptions } = options;
  const requestHeaders = new Headers(headers);
  if (requestOptions.body && !requestHeaders.has("Content-Type")) {
    requestHeaders.set("Content-Type", "application/json");
  }
  const session = readSession();
  if (session && !requestHeaders.has("Authorization")) {
    requestHeaders.set("Authorization", `Bearer ${session.token}`);
  }

  const url = new URL(
    `${API_BASE_URL}${endpoint}`,
    typeof window === "undefined"
      ? "http://localhost"
      : window.location.origin
  );

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      url.searchParams.set(key, String(value));
    });
  }

  const response = await fetch(url.toString(), {
    ...requestOptions,
    headers: requestHeaders,
    credentials: "include",
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);

    let message = `API request failed: ${response.status}`;
    if (typeof errorData?.detail === "string") message = errorData.detail;
    else if (typeof errorData?.error?.message === "string") message = errorData.error.message;
    else if (Array.isArray(errorData?.detail)) message = "Please check the form fields and try again.";
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}


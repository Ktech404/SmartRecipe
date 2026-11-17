
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
    headers: {
      ...(requestOptions.body
        ? { "Content-Type": "application/json" }
        : {}),
      ...headers,
    },
    credentials: "include",
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);

    throw new ApiError(
      errorData?.detail ||
        `API request failed: ${response.status}`,
      response.status
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

// Thin fetch wrapper: adds the base URL and auth token, and turns error responses into ApiError.

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

const TOKEN_KEY = "crashcart.token";

export const tokenStore = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

interface FastApiValidationItem {
  loc: (string | number)[];
  msg: string;
}

// The backend sends {"detail": {"code", "message"}} for business errors and FastAPI's
// {"detail": [{loc, msg}, ...]} list for request-validation errors.
function toApiError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (Array.isArray(detail)) {
    const message = (detail as FastApiValidationItem[])
      .map((item) => `${item.loc[item.loc.length - 1]}: ${item.msg}`)
      .join("; ");
    return new ApiError(status, "validation_error", message);
  }
  if (detail && typeof detail === "object" && "code" in detail) {
    const { code, message } = detail as { code: string; message: string };
    return new ApiError(status, code, message);
  }
  return new ApiError(status, "http_error", `Request failed with status ${status}`);
}

export async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; headers?: Record<string, string> } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(0, "network_error", "Can't reach the store server. Is the backend running?");
  }

  if (response.status === 204) return undefined as T;
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw toApiError(response.status, body);
  return body as T;
}

export function toQueryString(params: object): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

import axios, { AxiosError } from "axios";
import { signOut } from "firebase/auth";
import { getIdToken } from "./auth";
import { auth } from "./firebase";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export const api = axios.create({
  baseURL,
  timeout: 20000,
  headers: { Accept: "application/json" },
});

export interface ApiError {
  status: number;
  message: string;
  detail?: unknown;
}

function normalizeError(error: unknown): ApiError {
  if (error instanceof AxiosError) {
    const status = error.response?.status ?? 0;
    const data = error.response?.data as { detail?: unknown } | undefined;
    const detail = data?.detail;
    let message: string;
    if (typeof detail === "string") message = detail;
    else if (status === 401) message = "Your session has expired";
    else if (status === 403) message = "You don't have permission to do that";
    else if (status === 404) message = "Not found";
    else if (status === 0) message = "Cannot reach the API server";
    else if (status >= 500) message = "The server encountered an error";
    else message = error.message || "Request failed";
    return { status, message, detail };
  }
  return { status: 0, message: "Unexpected error" };
}

api.interceptors.request.use(async (config) => {
  config.headers.set("X-Request-Id", Math.random().toString(36).slice(2, 10));
  const token = await getIdToken();
  if (token) config.headers.set("Authorization", `Bearer ${token}`);
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (error) => {
    const normalized = normalizeError(error);
    // An expired/invalid token, or a verified identity with no local
    // profile: sign out and bounce to login (but not while already there).
    if (normalized.status === 401 && window.location.pathname !== "/login") {
      signOut(auth);
      window.location.assign(
        `/login?next=${encodeURIComponent(
          window.location.pathname + window.location.search,
        )}`,
      );
    }
    return Promise.reject(normalized);
  },
);

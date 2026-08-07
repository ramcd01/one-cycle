import { APP_CONFIG } from "./config.js";
import { clearAuthSession } from "./auth.js";

export async function apiFetch(path, options = {}) {
  const response = await fetch(`${APP_CONFIG.API_BASE_URL}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });

  if (response.status === 401) {
    clearAuthSession();
    window.location.replace(APP_CONFIG.LOGIN_PAGE);
    throw new Error("로그인이 만료되었습니다.");
  }

  if (!response.ok) {
    let message = "요청을 처리하지 못했습니다.";
    try {
      const data = await response.json();
      message = data.detail || data.message || message;
    } catch {
      // JSON 응답이 아닌 경우 기본 메시지를 사용합니다.
    }
    throw new Error(message);
  }

  if (response.status === 204) return null;
  return response.json();
}

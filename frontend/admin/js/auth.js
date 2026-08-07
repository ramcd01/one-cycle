import { APP_CONFIG } from "./config.js";
import { createMockJwt, decodeJwtPayload, isJwtExpired } from "./token.js";

const MOCK_ADMIN = Object.freeze({
  id: 1,
  loginId: "admin",
  password: "admin1234",
  name: "관리자",
  role: "admin",
});

function saveSession(token, admin) {
  sessionStorage.setItem(APP_CONFIG.ACCESS_TOKEN_KEY, token);
  sessionStorage.setItem(APP_CONFIG.ADMIN_INFO_KEY, JSON.stringify(admin));
}

export function getAccessToken() {
  return sessionStorage.getItem(APP_CONFIG.ACCESS_TOKEN_KEY);
}

export function getStoredAdmin() {
  const raw = sessionStorage.getItem(APP_CONFIG.ADMIN_INFO_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function clearAuthSession() {
  sessionStorage.removeItem(APP_CONFIG.ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(APP_CONFIG.ADMIN_INFO_KEY);
}

export function isAuthenticated() {
  const token = getAccessToken();
  if (!token || isJwtExpired(token)) {
    clearAuthSession();
    return false;
  }

  const payload = decodeJwtPayload(token);
  return payload?.role === "admin" && payload?.type === "access";
}

export async function loginAdmin(loginId, password) {
  if (!APP_CONFIG.USE_MOCK_AUTH) {
    const response = await fetch(`${APP_CONFIG.API_BASE_URL}/admin/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        login_id: loginId,
        password,
      }),
    });

    if (!response.ok) {
      throw new Error("아이디 또는 비밀번호가 올바르지 않습니다.");
    }

    return response.json();
  }

  await new Promise((resolve) => setTimeout(resolve, 450));

  if (loginId !== MOCK_ADMIN.loginId || password !== MOCK_ADMIN.password) {
    throw new Error("아이디 또는 비밀번호가 올바르지 않습니다.");
  }

  const admin = {
    id: MOCK_ADMIN.id,
    loginId: MOCK_ADMIN.loginId,
    name: MOCK_ADMIN.name,
    role: MOCK_ADMIN.role,
  };

  const token = createMockJwt(admin);
  saveSession(token, admin);

  return { admin, accessToken: token };
}

export async function getCurrentAdmin() {
  if (!APP_CONFIG.USE_MOCK_AUTH) {
    const response = await fetch(`${APP_CONFIG.API_BASE_URL}/admin/auth/me`, {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
    });

    if (response.status === 401) {
      clearAuthSession();
      return null;
    }

    if (!response.ok) {
      throw new Error("관리자 정보를 확인하지 못했습니다.");
    }

    return response.json();
  }

  if (!isAuthenticated()) return null;
  return getStoredAdmin();
}

export async function logoutAdmin() {
  if (!APP_CONFIG.USE_MOCK_AUTH) {
    try {
      await fetch(`${APP_CONFIG.API_BASE_URL}/admin/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      clearAuthSession();
    }
    return;
  }

  clearAuthSession();
}

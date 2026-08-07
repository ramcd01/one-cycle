import { APP_CONFIG } from "./config.js";
import { getCurrentAdmin, isAuthenticated } from "./auth.js";

export async function requireAdminAuth() {
  if (!isAuthenticated()) {
    window.location.replace(APP_CONFIG.LOGIN_PAGE);
    return null;
  }

  const admin = await getCurrentAdmin();
  if (!admin || admin.role !== "admin") {
    window.location.replace(APP_CONFIG.LOGIN_PAGE);
    return null;
  }

  return admin;
}

export function redirectAuthenticatedAdmin() {
  if (isAuthenticated()) {
    window.location.replace(APP_CONFIG.DEFAULT_ADMIN_PAGE);
  }
}

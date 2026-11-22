import { apiRequest } from "@/src/api/client";
import { API_ENDPOINTS } from "@/src/api/endpoints";
import { clearSession } from "@/src/auth/session";
import type { AuthProfile, RegisterRequest, LoginRequest, TokenResponse } from "@/src/types/user";

export function registerUser(data: RegisterRequest): Promise<AuthProfile> {
  return apiRequest<AuthProfile>(API_ENDPOINTS.REGISTER, {
    method: "POST", body: JSON.stringify(data),
  });
}

export function loginUser(data: LoginRequest): Promise<TokenResponse> {
  return apiRequest<TokenResponse>(API_ENDPOINTS.LOGIN, {
    method: "POST", body: JSON.stringify(data),
  });
}

export function getAuthenticatedProfile(signal?: AbortSignal): Promise<AuthProfile> {
  return apiRequest<AuthProfile>(API_ENDPOINTS.AUTH_PROFILE, { signal });
}

// The current backend issues access tokens without a logout/revocation endpoint.
export async function logoutUser(): Promise<void> {
  clearSession();
}


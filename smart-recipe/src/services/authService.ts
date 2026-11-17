import { apiRequest } from "@/src/api/client";
import { API_ENDPOINTS } from "@/src/api/endpoints";
import type {
  User,
  RegisterRequest,
  LoginRequest,
} from "@/src/types/user";

export async function registerUser(
  data: RegisterRequest
): Promise<User> {
  return apiRequest<User>(API_ENDPOINTS.REGISTER, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function loginUser(
  data: LoginRequest
): Promise<User> {
  return apiRequest<User>(API_ENDPOINTS.LOGIN, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function logoutUser(): Promise<void> {
  return apiRequest<void>(API_ENDPOINTS.LOGOUT, {
    method: "POST",
  });
}

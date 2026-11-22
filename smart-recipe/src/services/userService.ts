import { apiRequest } from "@/src/api/client";
import { API_ENDPOINTS } from "@/src/api/endpoints";
import type { User, UserPreferences } from "@/src/types/user";

export async function getCurrentUser(): Promise<User> {
  return apiRequest<User>(API_ENDPOINTS.CURRENT_USER);
}

export async function updateUserPreferences(
  preferences: UserPreferences
): Promise<User> {
  return apiRequest<User>(
    API_ENDPOINTS.USER_PREFERENCES,
    {
      method: "PUT",
      body: JSON.stringify(preferences),
    }
  );
}

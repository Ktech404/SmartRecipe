export interface User {
  id: string;
  username: string;
  email: string;
  allergies: string[];
  dietaryPreferences: string[];
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface AuthProfile {
  user_id: number;
  username: string;
  email: string;
  avatar_url: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserPreferences {
  allergies: string[];
  dietaryPreferences: string[];
}


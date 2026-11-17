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
  email: string;
  password: string;
}

export interface UserPreferences {
  allergies: string[];
  dietaryPreferences: string[];
}

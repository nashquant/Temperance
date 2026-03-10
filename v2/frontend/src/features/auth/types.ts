export interface AuthSession {
  token: string;
  user: string;
  role: 'admin' | 'viewer';
}

export interface LoginPayload {
  username: string;
  password: string;
}

export interface MeResponse {
  user: string;
  role: 'admin' | 'viewer';
  owner: string;
  auth_enabled: boolean;
}

export interface OwnersResponse {
  owners: string[];
}

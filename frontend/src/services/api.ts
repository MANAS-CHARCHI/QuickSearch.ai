/**
 * Vault City API Service & Strict Security Token Interceptor
 * 
 * Enforces dual-token authentication:
 * - 15-minute Access Token
 * - 7-day Refresh Token
 * 
 * Security Guard:
 * If tokens are missing, tampered, expired, or rejected with 401:
 * - Automatically attempts rolling refresh via POST /api/v1/auth/refresh
 * - If refresh fails or tokens are missing, immediately purges all credentials
 *   and triggers forced logout to the login view "no matter what".
 */
import { AuthTokens, AuthResponseData, UserProfile } from '../types';

const API_BASE = '/api/v1';

export const ACCESS_TOKEN_KEY = 'vault_access_token';
export const REFRESH_TOKEN_KEY = 'vault_refresh_token';
export const USER_KEY = 'vault_user';

type LogoutListener = (reason: string) => void;
const logoutListeners: Set<LogoutListener> = new Set();

/** Register a listener callback invoked whenever a forced logout occurs */
export function onForcedLogout(listener: LogoutListener): () => void {
  logoutListeners.add(listener);
  return () => logoutListeners.delete(listener);
}

/** Check if both access and refresh tokens exist and are non-empty */
export function hasValidTokens(): boolean {
  const access = localStorage.getItem(ACCESS_TOKEN_KEY);
  const refresh = localStorage.getItem(REFRESH_TOKEN_KEY);
  return Boolean(access && access.trim() && refresh && refresh.trim());
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function getStoredUser(): UserProfile | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/** Store session tokens and user profile securely in localStorage */
export function setAuthSession(tokens: AuthTokens, user?: UserProfile): void {
  if (tokens.accessToken) {
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken);
  }
  if (tokens.refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
  }
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }
}

/** Immediately purge all tokens and cached user state */
export function clearAuthSession(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

/**
 * Trigger an immediate, uncompromising forced logout across the entire application.
 * Clears storage and notifies all listeners and other browser tabs.
 */
export function triggerForcedLogout(reason = 'Authentication required'): void {
  clearAuthSession();

  // Notify registered callbacks
  logoutListeners.forEach((listener) => {
    try {
      listener(reason);
    } catch (e) {
      console.error('Logout listener error:', e);
    }
  });

  // Dispatch custom window event
  window.dispatchEvent(
    new CustomEvent('vault:unauthorized', { detail: { reason } })
  );
}

// Track in-flight refresh promise to prevent duplicate concurrent refresh requests
let refreshPromise: Promise<string | null> | null = null;

/**
 * Execute silent refresh against backend using refresh_token.
 * Rotates both access_token and refresh_token.
 */
async function silentRefreshToken(): Promise<string | null> {
  const currentRefresh = getRefreshToken();
  if (!currentRefresh) {
    triggerForcedLogout('Missing refresh token');
    return null;
  }

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: currentRefresh }),
    });

    if (!res.ok) {
      triggerForcedLogout('Refresh token rejected or expired');
      return null;
    }

    const data: AuthResponseData = await res.json();
    if (!data.access_token || !data.refresh_token) {
      triggerForcedLogout('Malformed refresh payload from server');
      return null;
    }

    // Persist new token pair
    setAuthSession({
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      tokenType: data.token_type,
    });

    return data.access_token;
  } catch (err) {
    console.error('Silent refresh network failure:', err);
    triggerForcedLogout('Network failure during session refresh');
    return null;
  }
}

/**
 * Centralized fetch interceptor:
 * 1. Injects Authorization: Bearer <access_token>
 * 2. Catches 401 Unauthorized responses
 * 3. Attempts silent refresh via refresh token
 * 4. Retries original request with new token
 * 5. Forces logout immediately if refresh fails or tokens are missing
 */
export async function apiFetch(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
  const headers = new Headers(options.headers || {});

  // Add Bearer token if available
  const token = getAccessToken();
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (networkError) {
    throw networkError;
  }

  // Handle 401 Unauthorized (Expired / Revoked / Invalid Token)
  if (response.status === 401 && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/register')) {
    // If we're already calling refresh and it failed, do not loop
    if (endpoint.includes('/auth/refresh')) {
      triggerForcedLogout('Refresh token expired or revoked');
      return response;
    }

    // Guard: Both tokens must exist
    if (!hasValidTokens()) {
      triggerForcedLogout('Session tokens missing');
      return response;
    }

    // Initiate or share active token refresh
    if (!refreshPromise) {
      refreshPromise = silentRefreshToken().finally(() => {
        refreshPromise = null;
      });
    }

    const newAccessToken = await refreshPromise;
    if (!newAccessToken) {
      // Refresh failed, user is logged out
      return response;
    }

    // Retry original request with newly issued access token
    const retryHeaders = new Headers(options.headers || {});
    retryHeaders.set('Authorization', `Bearer ${newAccessToken}`);
    return fetch(url, { ...options, headers: retryHeaders });
  }

  return response;
}

/**
 * Verify if current user is authorized with backend (GET /api/v1/auth/me).
 * Strict verification: if no tokens or 401, forces immediate logout.
 */
export async function verifyAuthSession(): Promise<UserProfile | null> {
  // Guard 1: Must have both access and refresh tokens locally
  if (!hasValidTokens()) {
    triggerForcedLogout('No authentication tokens found in storage');
    return null;
  }

  try {
    const res = await apiFetch('/auth/me');
    if (!res.ok) {
      // 401 handled in apiFetch with refresh; if still not ok, logout
      triggerForcedLogout('Session verification failed');
      return null;
    }

    const userData = await res.json();
    const user: UserProfile = {
      id: userData.id,
      email: userData.email,
      name: userData.username || userData.email.split('@')[0],
      fullName: userData.username || userData.email.split('@')[0],
      username: userData.username,
      role: userData.role || 'user',
      hasGoogle: userData.has_google,
      hasPassword: userData.has_password,
    };

    localStorage.setItem(USER_KEY, JSON.stringify(user));
    return user;
  } catch (e) {
    console.warn('verifyAuthSession network error:', e);
    // If completely offline, fall back to stored user temporarily
    return getStoredUser();
  }
}

/** User Login with Email & Password */
export async function apiLogin(payload: {
  email: string;
  password: string;
  turnstile_token?: string;
}): Promise<{ user: UserProfile; tokens: AuthTokens }> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Authentication failed. Please verify credentials.');
  }

  const tokens: AuthTokens = {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    tokenType: data.token_type || 'bearer',
  };

  const user: UserProfile = {
    id: data.user.id,
    email: data.user.email,
    name: data.user.username || data.user.email.split('@')[0],
    fullName: data.user.username || data.user.email.split('@')[0],
    username: data.user.username,
    role: data.user.role || 'user',
    hasGoogle: data.user.has_google,
    hasPassword: data.user.has_password,
  };

  setAuthSession(tokens, user);
  return { user, tokens };
}

/** User Registration */
export async function apiRegister(payload: {
  email: string;
  password: string;
  username?: string;
  turnstile_token?: string;
}): Promise<{ user: UserProfile; tokens: AuthTokens }> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Registration failed.');
  }

  const tokens: AuthTokens = {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    tokenType: data.token_type || 'bearer',
  };

  const user: UserProfile = {
    id: data.user.id,
    email: data.user.email,
    name: data.user.username || data.user.email.split('@')[0],
    fullName: data.user.username || data.user.email.split('@')[0],
    username: data.user.username,
    role: data.user.role || 'user',
    hasGoogle: data.user.has_google,
    hasPassword: data.user.has_password,
  };

  setAuthSession(tokens, user);
  return { user, tokens };
}

/** Google Social Authentication with Google Identity Services ID Token */
export async function apiGoogleAuth(payload: {
  id_token: string;
  turnstile_token?: string;
}): Promise<{ user: UserProfile; tokens: AuthTokens }> {
  const res = await fetch(`${API_BASE}/auth/google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Google authentication failed.');
  }

  const tokens: AuthTokens = {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    tokenType: data.token_type || 'bearer',
  };

  const user: UserProfile = {
    id: data.user.id,
    email: data.user.email,
    name: data.user.username || data.user.email.split('@')[0],
    fullName: data.user.username || data.user.email.split('@')[0],
    username: data.user.username,
    role: data.user.role || 'user',
    hasGoogle: data.user.has_google,
    hasPassword: data.user.has_password,
  };

  setAuthSession(tokens, user);
  return { user, tokens };
}

/** User Logout (Revokes tokens on server & clears local storage) */
export async function apiLogout(): Promise<void> {
  const refreshToken = getRefreshToken();
  try {
    await apiFetch('/auth/logout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch (err) {
    console.warn('Server logout error (clearing local session anyway):', err);
  } finally {
    triggerForcedLogout('User logged out');
  }
}

/** Check system health ready status */
export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health/ready`);
    return await res.json();
  } catch (error) {
    return { status: 'error', checks: { error: String(error) } };
  }
}

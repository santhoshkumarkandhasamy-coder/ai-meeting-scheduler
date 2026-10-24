import { GoogleSignin, isSuccessResponse } from '@react-native-google-signin/google-signin';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { api, ApiError, clearToken, getToken, saveToken, type UserProfile } from './api';

GoogleSignin.configure({
  webClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID,
  iosClientId: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID,
  // offlineAccess returns a serverAuthCode the backend exchanges for a refresh token,
  // so reminders keep working while the app is closed.
  offlineAccess: true,
  forceCodeForRefreshToken: true,
  scopes: [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.readonly',
  ],
});

type AuthState = {
  user: UserProfile | null;
  loading: boolean;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  setUser: (user: UserProfile) => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        if (await getToken()) setUser(await api.me());
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) await clearToken();
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const signIn = useCallback(async () => {
    await GoogleSignin.hasPlayServices();
    const response = await GoogleSignin.signIn();
    if (!isSuccessResponse(response)) return; // user cancelled
    const code = response.data.serverAuthCode;
    if (!code) throw new Error('Google did not return an authorization code. Check the web client ID.');
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const result = await api.signIn(code, timezone);
    await saveToken(result.token);
    setUser(result.user);
  }, []);

  const signOut = useCallback(async () => {
    await clearToken();
    await GoogleSignin.signOut().catch(() => null);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, signIn, signOut, setUser }), [user, loading, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}

import { create } from 'zustand';
import { authApi, AdminUser } from '../api';

interface AuthState {
  token: string | null;
  user: AdminUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  fetchUser: () => Promise<void>;
  initialize: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('admin_token'),
  user: (() => {
    try {
      const raw = localStorage.getItem('admin_user');
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  })(),
  loading: false,

  login: async (username: string, password: string) => {
    set({ loading: true });
    try {
      const result: any = await authApi.login({ username, password });
      const access_token = result.data?.access_token || result.access_token;
      const user = result.data?.user || result.user;
      localStorage.setItem('admin_token', access_token);
      localStorage.setItem('admin_user', JSON.stringify(user));
      set({ token: access_token, user, loading: false });
    } catch (error) {
      set({ loading: false });
      throw error;
    }
  },

  logout: async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore
    } finally {
      localStorage.removeItem('admin_token');
      localStorage.removeItem('admin_user');
      set({ token: null, user: null });
    }
  },

  fetchUser: async () => {
    try {
      const user = await authApi.me();
      localStorage.setItem('admin_user', JSON.stringify(user));
      set({ user });
    } catch {
      localStorage.removeItem('admin_token');
      localStorage.removeItem('admin_user');
      set({ token: null, user: null });
    }
  },

  initialize: () => {
    const token = localStorage.getItem('admin_token');
    const userRaw = localStorage.getItem('admin_user');
    if (token && userRaw) {
      try {
        const user = JSON.parse(userRaw);
        set({ token, user });
      } catch {
        set({ token: null, user: null });
      }
    }
  },
}));

import { create } from 'zustand';
import { authApi } from '../api';
import { message } from 'antd';

export interface User {
  id: number;
  username: string;
  role: string;
  display_name?: string;
  avatar?: string;
  status?: string;
  department?: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  fetchMe: () => Promise<void>;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
}

const useAuthStore = create<AuthState>((set, get) => ({
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  token: localStorage.getItem('token'),
  isAuthenticated: !!localStorage.getItem('token'),
  loading: false,

  setUser: (user) => {
    if (user) {
      localStorage.setItem('user', JSON.stringify(user));
    } else {
      localStorage.removeItem('user');
    }
    set({ user, isAuthenticated: !!user && !!get().token });
  },

  setToken: (token) => {
    if (token) {
      localStorage.setItem('token', token);
    } else {
      localStorage.removeItem('token');
    }
    set({ token, isAuthenticated: !!token && !!get().user });
  },

  login: async (username: string, password: string) => {
    set({ loading: true });
    try {
      const res: any = await authApi.login(username, password);
      const { access_token, user } = res;
      localStorage.setItem('token', access_token);
      localStorage.setItem('user', JSON.stringify(user));
      set({
        token: access_token,
        user,
        isAuthenticated: true,
        loading: false,
      });
      message.success('登录成功');
    } catch (error: any) {
      set({ loading: false });
      const detail = error?.response?.data?.detail || error?.detail || '登录失败';
      message.error(detail);
      throw error;
    }
  },

  logout: async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore logout errors
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      set({
        token: null,
        user: null,
        isAuthenticated: false,
        loading: false,
      });
    }
  },

  fetchMe: async () => {
    try {
      const res: any = await authApi.me();
      const user = res.data || res;
      set({ user });
      localStorage.setItem('user', JSON.stringify(user));
    } catch {
      set({
        token: null,
        user: null,
        isAuthenticated: false,
        loading: false,
      });
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    }
  },
}));

export default useAuthStore;

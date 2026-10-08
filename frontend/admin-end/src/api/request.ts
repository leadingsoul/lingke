import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { message } from 'antd';

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('admin_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  },
);

request.interceptors.response.use(
  (response) => {
    // Blob response (e.g. file download) — bypass JSON parsing
    if (response.config.responseType === 'blob') {
      return response.data;
    }
    const body = response.data;
    if (body?.code === 200) {
      return body.data;
    }
    message.error(body?.message || '请求失败');
    return Promise.reject(new Error(body?.message));
  },
  (error: AxiosError<{ detail?: string; message?: string }>) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('admin_token');
      localStorage.removeItem('admin_user');
      const currentPath = window.location.pathname;
      if (currentPath !== '/login') {
        window.location.href = '/login';
      }
    }

    const errorMsg =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      '请求失败';

    message.error(errorMsg);

    return Promise.reject(error);
  },
);

export default request;

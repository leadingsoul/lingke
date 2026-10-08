import axios from 'axios';
import { message } from 'antd';

const request = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

request.interceptors.response.use(
  (response) => {
    const body = response.data;
    if (body?.code === 200) {
      return body.data;
    }
    message.error(body?.message || '请求失败');
    return Promise.reject(new Error(body?.message));
  },
  (error) => {
    if (error.response) {
      const { status, data } = error.response;
      switch (status) {
        case 401:
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          message.error('登录已过期，请重新登录');
          window.location.href = '/login';
          break;
        case 403:
          message.error('没有权限执行此操作');
          break;
        case 404:
          message.error('请求的资源不存在');
          break;
        case 500:
          message.error(data?.detail || '服务器内部错误');
          break;
        default:
          message.error(data?.detail || '请求失败');
      }
    } else if (error.request) {
      message.error('网络连接失败，请检查网络');
    }
    return Promise.reject(error);
  }
);

export default request;

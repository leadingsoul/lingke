import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'vue'
import type { ApiResponse } from '@/types'
import { showToast } from 'vant'

const instance: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器
instance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    // FormData 上传时让浏览器自动设置 Content-Type 和 boundary
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type']
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器
instance.interceptors.response.use(
  (response: AxiosResponse<any>) => {
    const body = response.data
    const code = body?.code

    // 成功：code 为 200
    if (code === 200) {
      return body.data
    }

    // 401 未授权 — 清除 token 并跳转登录页（使用 location.href 确保 history 栈正确）
    if (code === 401 || response.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/#/login'
      return Promise.reject(new Error('未授权'))
    }

    showToast(body?.message || '请求失败')
    return Promise.reject(new Error(body?.message))
  },
  (error) => {
    if (error.code === 'ECONNABORTED') {
      showToast('请求超时，请重试')
    } else if (!error.response) {
      showToast('网络异常，请检查网络')
    } else if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/#/login'
    } else if (error.response?.status === 404) {
      // 404 可能有两类：真正不存在的接口 / 不存在的业务资源（如会话已删除）
      const detail = error.response?.data?.detail
      if (typeof detail === 'string') {
        showToast(detail)  // 显示后端返回的具体原因，如"会话不存在或无权操作"
      }
      // 兜底：不弹 toast，调用方可自行 catch 处理
      return Promise.reject(error)
    } else {
      // 尝试提取后端真实错误信息
      const detail = error.response?.data?.detail
      let msg = '服务异常，请稍后再试'
      if (typeof detail === 'string' && error.response?.status !== 404) {
        msg = detail
      } else if (Array.isArray(detail) && detail.length > 0) {
        // Pydantic validation error
        const first = detail[0]
        msg = first?.msg || `字段 ${first?.loc?.join('.') || ''} 校验失败`
      }
      showToast(msg)
      return Promise.reject(new Error(msg))
    }
  }
)

export function get<T = any>(url: string, params?: any, config?: AxiosRequestConfig): Promise<T> {
  return instance.get(url, { params, ...config }) as any
}

export function post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
  return instance.post(url, data, config) as any
}

export function put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
  return instance.put(url, data, config) as any
}

export function del<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return instance.delete(url, config) as any
}

export default instance

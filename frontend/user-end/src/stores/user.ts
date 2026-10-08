import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserInfo } from '@/types'
import { authApi } from '@/api'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>('')
  const userInfo = ref<UserInfo | null>(null)
  const isLoggedIn = computed(() => !!token.value && !!userInfo.value)

  function setToken(t: string) {
    token.value = t
    localStorage.setItem('token', t)
  }

  function setUserInfo(info: UserInfo) {
    userInfo.value = info
  }

  /** 用户名密码登录 */
  async function login(username: string, password: string) {
    const res = await authApi.login(username, password)
    setToken(res.access_token)
    setUserInfo(res.user)
    return res
  }

  /** 微信登录 */
  async function wechatLogin(code: string) {
    const res = await authApi.wechatLogin(code)
    setToken(res.access_token)
    setUserInfo(res.user)
    return res
  }

  /** 获取用户信息 */
  async function fetchMe() {
    const user = await authApi.me()
    setUserInfo(user)
    return user
  }

  /** 退出登录 */
  async function logout() {
    try {
      await authApi.logout()
    } catch {
      // ignore logout errors
    }
    forceClearAuth()
  }

  /** 强制清除登录态（不调用后端API，直接清空本地数据） */
  function forceClearAuth() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
  }

  /** 检查本地token恢复登录态 */
  function restoreLogin() {
    const savedToken = localStorage.getItem('token')
    if (savedToken) {
      token.value = savedToken
    }
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    setToken,
    setUserInfo,
    login,
    wechatLogin,
    fetchMe,
    logout,
    forceClearAuth,
    restoreLogin,
  }
})

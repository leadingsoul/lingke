import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/home',
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
    meta: { parent: '/home' },
  },
  {
    path: '/order/:id',
    name: 'OrderDetail',
    component: () => import('@/views/OrderDetail.vue'),
    meta: { parent: '/home' },
  },
  {
    path: '/consult',
    name: 'ConsultList',
    component: () => import('@/views/ConsultList.vue'),
    meta: { parent: '/home' },
  },
  {
    path: '/consult/:sessionId',
    name: 'Consult',
    component: () => import('@/views/Consult.vue'),
    meta: { parent: '/consult' },
  },
  {
    path: '/aftersale/apply/:orderId',
    name: 'AftersaleApply',
    component: () => import('@/views/AftersaleApply.vue'),
    meta: { parent: '/home' },
  },
  {
    path: '/aftersale/list',
    name: 'AftersaleList',
    component: () => import('@/views/AftersaleList.vue'),
    meta: { parent: '/home' },
  },
  {
    path: '/aftersale/:id',
    name: 'AftersaleDetail',
    component: () => import('@/views/AftersaleDetail.vue'),
    meta: { parent: '/aftersale/list' },
  },
  {
    path: '/evaluate',
    name: 'EvaluateList',
    component: () => import('@/views/EvaluateList.vue'),
    meta: { parent: '/home' },
  },
  {
    path: '/evaluate/:orderId',
    name: 'EvaluateSubmit',
    component: () => import('@/views/EvaluateSubmit.vue'),
    meta: { parent: '/evaluate' },
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('@/views/Profile.vue'),
    meta: { parent: '/home' },
  },
  {
    path: '/profile/edit',
    name: 'ProfileEdit',
    component: () => import('@/views/ProfileEdit.vue'),
    meta: { parent: '/profile' },
  },
  {
    path: '/notice',
    name: 'NoticeList',
    component: () => import('@/views/NoticeList.vue'),
    meta: { parent: '/profile' },
  },
  {
    path: '/feedback',
    name: 'Feedback',
    component: () => import('@/views/Feedback.vue'),
    meta: { parent: '/profile' },
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// session 恢复标记：首次导航时尝试验证 token
let sessionRestored = false

router.beforeEach(async (to, _from, next) => {
  if (!sessionRestored) {
    sessionRestored = true
    const savedToken = localStorage.getItem('token')
    if (savedToken) {
      try {
        // 动态导入 store 避免循环依赖
        const { useUserStore } = await import('@/stores/user')
        const store = useUserStore()
        store.restoreLogin()
        await store.fetchMe()
        // token 有效 → 放行；已登录用户访问 /login → 重定向到 /home
        if (to.path === '/login') return next('/home')
        return next()
      } catch {
        // token 失效 → 清除
        localStorage.removeItem('token')
      }
    }
    // 无有效 token，只允许访问 /login
    if (to.path !== '/login') return next('/login')
  }

  // 后续导航：仅检查 token 是否存在
  const token = localStorage.getItem('token')
  if (!token && to.path !== '/login') return next('/login')
  if (token && to.path === '/login') return next('/home')
  next()
})

export default router

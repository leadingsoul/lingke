<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useGlobalWS, useWebSocket } from '@/composables/useWebSocket'

const route = useRoute()
const router = useRouter()

// ── 全局通知弹窗 ──
interface NotifyBanner {
  visible: boolean
  type: string
  title: string
  content: string
  icon: string
  color: string
}
const banner = ref<NotifyBanner>({
  visible: false, type: '', title: '', content: '',
  icon: '🔔', color: '#0D9488',
})
let bannerTimer: ReturnType<typeof setTimeout> | null = null

function showBanner(data: any) {
  if (bannerTimer) clearTimeout(bannerTimer)

  const type = data?.type || 'system'
  const config: Record<string, { icon: string; color: string }> = {
    aftersale: { icon: '📦', color: '#EA580C' },
    system:    { icon: '🔔', color: '#0D9488' },
    service:   { icon: '💬', color: '#16A34A' },
  }
  const cfg = config[type] || config.system

  banner.value = {
    visible: true,
    type,
    title: data?.title || '系统通知',
    content: data?.content || '',
    icon: cfg.icon,
    color: cfg.color,
  }

  bannerTimer = setTimeout(() => { banner.value.visible = false }, 4500)
}

function dismissBanner() {
  if (bannerTimer) clearTimeout(bannerTimer)
  banner.value.visible = false
}

function goNotices() {
  dismissBanner()
  router.push('/notice')
}

// ── 全局 WebSocket 初始化 ──
onMounted(() => {
  useGlobalWS()
  const ws = useWebSocket()
  ws.on('system_notice', showBanner)
})

// ── Tabbar ──
const tabRoutes = ['/home', '/consult', '/aftersale/list', '/evaluate', '/profile']
const tabMap: Record<string, string> = {
  '/home': 'home',
  '/consult': 'consult',
  '/aftersale/list': 'aftersale',
  '/evaluate': 'evaluate',
  '/profile': 'profile',
}

const showTabbar = computed(() => tabRoutes.includes(route.path))
const active = ref(tabMap[route.path] || 'home')

watch(() => route.path, (path) => {
  if (tabMap[path]) active.value = tabMap[path]
})

function onTabChange(name: string | number) {
  const pathMap: Record<string, string> = {
    'home': '/home',
    'consult': '/consult',
    'aftersale': '/aftersale/list',
    'evaluate': '/evaluate',
    'profile': '/profile',
  }
  const nameStr = String(name)
  if (pathMap[nameStr]) router.push(pathMap[nameStr])
}
</script>

<template>
  <!-- ── 全局通知横幅 ── -->
  <Teleport to="body">
    <Transition name="banner">
      <div
        v-if="banner.visible"
        class="notify-banner"
        @click="goNotices"
      >
        <div class="banner-accent" :style="{ background: banner.color }"></div>
        <span class="banner-icon">{{ banner.icon }}</span>
        <div class="banner-body">
          <div class="banner-title">{{ banner.title }}</div>
          <div class="banner-content" v-if="banner.content">{{ banner.content }}</div>
        </div>
        <span class="banner-close" @click.stop="dismissBanner">✕</span>
      </div>
    </Transition>
  </Teleport>

  <!-- ── 页面内容 + 路由过渡 ── -->
  <div :class="{ 'page-with-tabbar': showTabbar }">
    <router-view v-slot="{ Component: C }">
      <keep-alive include="Home,ConsultList,Consult,AftersaleList,EvaluateList,Profile">
        <component :is="C" />
      </keep-alive>
    </router-view>
  </div>

  <!-- ── 浮动玻璃胶囊 Tabbar ── -->
  <van-tabbar
    v-if="showTabbar"
    v-model="active"
    :fixed="true"
    :border="false"
    :safe-area-inset-bottom="true"
    active-color="#0D9488"
    inactive-color="rgba(0,0,0,0.35)"
    @change="onTabChange"
  >
    <van-tabbar-item name="home" icon="home-o">首页</van-tabbar-item>
    <van-tabbar-item name="consult" icon="chat-o">咨询</van-tabbar-item>
    <van-tabbar-item name="aftersale" icon="records-o">售后</van-tabbar-item>
    <van-tabbar-item name="evaluate" icon="star-o">评价</van-tabbar-item>
    <van-tabbar-item name="profile" icon="user-o">我的</van-tabbar-item>
  </van-tabbar>
</template>

<style>
/* ── 通知横幅 ── */
.notify-banner {
  position: fixed;
  top: 12px;
  left: 16px;
  right: 16px;
  z-index: 9999;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 14px 14px 0;
  background: rgba(255,255,255,0.95);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border-radius: 20px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.08), 0 2px 8px rgba(0,0,0,0.04);
  border: 1px solid rgba(0,0,0,0.06);
  cursor: pointer;
  overflow: hidden;
}

.banner-accent {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  border-radius: 0 2px 2px 0;
}

.banner-icon {
  font-size: 22px;
  flex-shrink: 0;
  margin-left: 16px;
  line-height: 1.2;
}

.banner-body {
  flex: 1;
  min-width: 0;
}

.banner-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a1a1a;
  line-height: 1.3;
}

.banner-content {
  font-size: 13px;
  color: rgba(0,0,0,0.45);
  margin-top: 3px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.banner-close {
  flex-shrink: 0;
  width: 24px; height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: rgba(0,0,0,0.25);
  border-radius: 50%;
  margin-right: 4px;
  transition: all 0.2s ease;
}
.banner-close:hover {
  background: rgba(0,0,0,0.05);
  color: rgba(0,0,0,0.55);
}

/* ── 通知横幅动画 ── */
.banner-enter-active {
  transition: all 0.4s cubic-bezier(0.32,0.72,0,1);
}
.banner-leave-active {
  transition: all 0.25s ease-in;
}
.banner-enter-from {
  opacity: 0;
  transform: translateY(-32px);
}
.banner-leave-to {
  opacity: 0;
  transform: translateY(-16px);
}
</style>

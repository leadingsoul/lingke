<script setup lang="ts">
import { onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

onMounted(async () => {
  if (!userStore.isLoggedIn) { router.replace('/login'); return }
  try { await userStore.fetchMe() } catch { /* */ }
})

onActivated(async () => {
  if (userStore.isLoggedIn) {
    try { await userStore.fetchMe() } catch { /* */ }
  }
})

function handleLogout() {
  localStorage.removeItem('token')
  window.location.href = '/#/login'
}

function avatarChar(): string {
  const name = userStore.userInfo?.nickname || '用'
  return name.charAt(0)
}
</script>

<template>
  <div class="profile-page">
    <!-- ═══ Hero ═══ -->
    <div class="profile-hero">
      <div class="profile-avatar">{{ avatarChar() }}</div>
      <div class="profile-name">{{ userStore.userInfo?.nickname || '用户' }}</div>
      <div class="profile-phone">{{ userStore.userInfo?.phone || '未绑定手机号' }}</div>
    </div>

    <!-- ═══ Stats ═══ -->
    <div class="stats-row">
      <div class="stat-card" @click="router.push('/home')">
        <div class="stat-num">—</div>
        <div class="stat-label">我的订单</div>
      </div>
      <div class="stat-card" @click="router.push('/aftersale/list')">
        <div class="stat-num">—</div>
        <div class="stat-label">售后</div>
      </div>
      <div class="stat-card" @click="router.push('/evaluate')">
        <div class="stat-num">—</div>
        <div class="stat-label">评价</div>
      </div>
    </div>

    <!-- ═══ Menu Groups ═══ -->
    <div class="menu-section">
      <div class="menu-section-title">服务</div>
      <div class="menu-list">
        <div class="menu-row" @click="router.push('/home')">
          <span class="menu-row-icon">📦</span>
          <span class="menu-row-label">我的订单</span>
          <svg class="menu-row-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
        </div>
        <div class="menu-row" @click="router.push('/aftersale/list')">
          <span class="menu-row-icon">📋</span>
          <span class="menu-row-label">我的售后</span>
          <svg class="menu-row-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
        </div>
        <div class="menu-row" @click="router.push('/evaluate')">
          <span class="menu-row-icon">⭐</span>
          <span class="menu-row-label">我的评价</span>
          <svg class="menu-row-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
        </div>
        <div class="menu-row" @click="router.push('/notice')">
          <span class="menu-row-icon">🔔</span>
          <span class="menu-row-label">消息通知</span>
          <svg class="menu-row-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
        </div>
      </div>
    </div>

    <div class="menu-section">
      <div class="menu-section-title">设置</div>
      <div class="menu-list">
        <div class="menu-row" @click="router.push('/profile/edit')">
          <span class="menu-row-icon">📱</span>
          <span class="menu-row-label">绑定手机号</span>
          <span class="menu-row-hint" :class="{ bound: userStore.userInfo?.phone }">
            {{ userStore.userInfo?.phone ? '已绑定' : '未绑定' }}
          </span>
          <svg class="menu-row-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
        </div>
        <div class="menu-row" @click="router.push('/feedback')">
          <span class="menu-row-icon">💬</span>
          <span class="menu-row-label">意见反馈</span>
          <svg class="menu-row-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
        </div>
      </div>
    </div>

    <!-- ═══ Logout ═══ -->
    <button class="logout-btn" @click="handleLogout">退出登录</button>
  </div>
</template>

<style scoped>
.profile-page {
  min-height: 100dvh; background: var(--bg-page);
  padding-bottom: 80px;
}

/* ═══ Hero ═══ */
.profile-hero {
  display: flex; flex-direction: column; align-items: center;
  padding: 40px 0 24px; gap: 8px;
}
.profile-avatar {
  width: 80px; height: 80px; border-radius: 50%;
  background: var(--brand-gradient);
  display: flex; align-items: center; justify-content: center;
  font-size: 36px; font-weight: 800; color: #fff;
  box-shadow: 0 4px 20px rgba(13,148,136,0.25);
  letter-spacing: -0.02em;
}
.profile-name {
  font-size: var(--text-xl); font-weight: 700;
  color: var(--text); margin-top: 8px; letter-spacing: -0.02em;
}
.profile-phone {
  font-size: var(--text-sm); color: var(--text-tertiary);
}

/* ═══ Stats ═══ */
.stats-row {
  display: flex; gap: 10px; padding: 0 var(--space-md); margin-bottom: var(--space-lg);
}
.stat-card {
  flex: 1; background: #fff; border-radius: var(--radius-lg);
  padding: 18px 12px; text-align: center;
  box-shadow: var(--shadow-xs); border: 1px solid var(--border-light);
  cursor: pointer; transition: all 0.25s var(--ease-out-expo);
}
.stat-card:active { transform: scale(0.96); background: rgba(13,148,136,0.03); }
.stat-num {
  font-size: var(--text-2xl); font-weight: 800; color: var(--text);
  letter-spacing: -0.03em; font-variant-numeric: tabular-nums;
}
.stat-label {
  font-size: var(--text-xs); color: var(--text-tertiary);
  margin-top: 2px; font-weight: 500;
}

/* ═══ Menu ═══ */
.menu-section { padding: 0 var(--space-md); margin-bottom: var(--space-md); }
.menu-section-title {
  font-size: var(--text-xs); font-weight: 600; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: 0.06em;
  padding: 0 4px 8px;
}
.menu-list {
  background: #fff; border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xs); border: 1px solid var(--border-light);
  overflow: hidden;
}
.menu-row {
  display: flex; align-items: center; gap: 10px;
  padding: 16px 18px; cursor: pointer;
  transition: background 0.2s ease; border-bottom: 1px solid rgba(0,0,0,0.03);
}
.menu-row:last-child { border-bottom: none; }
.menu-row:active { background: rgba(0,0,0,0.015); }
.menu-row-icon { font-size: 18px; flex-shrink: 0; width: 28px; text-align: center; }
.menu-row-label {
  flex: 1; font-size: var(--text-base); font-weight: 500; color: var(--text);
}
.menu-row-hint {
  font-size: var(--text-sm); color: var(--text-tertiary);
}
.menu-row-hint.bound { color: var(--green); }
.menu-row-arrow {
  flex-shrink: 0; color: rgba(0,0,0,0.2);
}

/* ═══ Logout ═══ */
.logout-btn {
  display: block; margin: var(--space-lg) auto 0;
  border: none; background: none; font-size: var(--text-base); font-weight: 500;
  color: var(--red); cursor: pointer; padding: 12px 24px;
  transition: opacity 0.2s ease; font-family: inherit;
}
.logout-btn:active { opacity: 0.6; }
</style>

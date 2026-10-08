<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { noticeApi } from '@/api'
import type { Notice } from '@/types'
import { showToast } from 'vant'
import { useWebSocket } from '@/composables/useWebSocket'

const router = useRouter()
const ws = useWebSocket()
const notices = ref<Notice[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try { const res = await noticeApi.list(); notices.value = res.items }
  catch { showToast('加载失败') }
  finally { loading.value = false }
})

ws.on('system_notice', (_data: any) => { loadList() })
ws.on('ticket_update', (_data: any) => { loadList() })

async function loadList() {
  try { const res = await noticeApi.list(); notices.value = res.items }
  catch { /* 静默刷新失败不影响当前显示 */ }
}

function getTypeIcon(type: string) {
  const map: Record<string, string> = { 'system': '🔔', 'aftersale': '📦', 'service': '💬', '售后': '📦', '系统': '🔔', '客服': '💬', '通知': '🔔' }
  return map[type] || '📌'
}

async function markAsRead(notice: Notice) {
  if (notice.is_read === 1) return
  try { await noticeApi.markAsRead(notice.id); notice.is_read = 1 } catch { /* */ }
}

// Group by date
const groupedNotices = computed(() => {
  const groups: { label: string; items: Notice[] }[] = []
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)

  for (const n of notices.value) {
    const d = new Date(n.created_at)
    const day = new Date(d.getFullYear(), d.getMonth(), d.getDate())
    let label: string
    if (day.getTime() === today.getTime()) label = '今天'
    else if (day.getTime() === yesterday.getTime()) label = '昨天'
    else label = `${d.getMonth() + 1}月${d.getDate()}日`

    const last = groups[groups.length - 1]
    if (last && last.label === label) { last.items.push(n) }
    else { groups.push({ label, items: [n] }) }
  }
  return groups
})
</script>

<template>
  <div class="notice-page">
    <!-- ═══ Header ═══ -->
    <div class="detail-header">
      <button class="detail-back" @click="router.push('/profile')">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
      </button>
      <span class="detail-header-title">消息通知</span>
      <span style="width:36px;"></span>
    </div>

    <van-loading v-if="loading" type="spinner" style="display:flex;justify-content:center;padding:40px;" />

    <div v-if="!loading && notices.length === 0" class="empty-state">
      <span class="empty-state-icon">🔔</span>
      <p>暂无消息</p>
    </div>

    <div v-else class="page" style="padding-top:8px;">
      <template v-for="group in groupedNotices" :key="group.label">
        <div class="notice-group-label">{{ group.label }}</div>
        <div
          v-for="notice in group.items"
          :key="notice.id"
          class="notice-card"
          :class="{ unread: notice.is_read === 0 }"
          @click="markAsRead(notice)"
        >
          <div class="notice-accent" :class="notice.is_read === 0 ? 'accent-unread' : 'accent-read'"></div>
          <span class="notice-icon">{{ getTypeIcon(notice.type) }}</span>
          <div class="notice-body">
            <div class="notice-title">
              {{ notice.title }}
              <span v-if="notice.is_read === 0" class="notice-unread-dot"></span>
            </div>
            <div class="notice-content">{{ notice.content }}</div>
            <div class="notice-time">{{ notice.created_at?.slice(0, 16)?.replace('T', ' ') }}</div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.notice-page { min-height: 100dvh; background: var(--bg-page); }

/* ═══ Header ═══ */
.detail-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px var(--space-md); background: rgba(255,255,255,0.82);
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border-bottom: 1px solid var(--border-light); position: sticky; top: 0; z-index: 10;
}
.detail-back {
  width: 36px; height: 36px; border-radius: 50%;
  border: none; background: transparent;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: var(--text-secondary); transition: all 0.2s ease;
}
.detail-back:active { background: rgba(0,0,0,0.04); color: var(--text); }
.detail-header-title { font-size: var(--text-base); font-weight: 700; color: var(--text); }

/* ═══ Group label ═══ */
.notice-group-label {
  font-size: var(--text-xs); font-weight: 600; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: 0.06em;
  padding: var(--space-md) 0 6px;
}

/* ═══ Notice card ═══ */
.notice-card {
  display: flex; gap: 10px; align-items: flex-start;
  padding: 14px; background: #fff; border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs); border: 1px solid var(--border-light);
  margin-bottom: 10px; cursor: pointer;
  transition: all 0.25s var(--ease-out-expo);
  overflow: hidden; position: relative;
}
.notice-card.unread { background: rgba(13,148,136,0.025); }
.notice-card:active { transform: scale(0.985); }
.notice-accent {
  position: absolute; left: 0; top: 0; bottom: 0; width: 3px; border-radius: 0 2px 2px 0;
}
.accent-unread { background: var(--primary); }
.accent-read { background: transparent; }
.notice-icon { font-size: 22px; flex-shrink: 0; margin-top: 2px; margin-left: 4px; }
.notice-body { flex: 1; min-width: 0; }
.notice-title {
  font-size: var(--text-base); font-weight: 600; color: var(--text);
  display: flex; align-items: center; gap: 6px; letter-spacing: -0.01em;
}
.notice-unread-dot {
  width: 5px; height: 5px; border-radius: 50%; background: var(--primary); flex-shrink: 0;
}
.notice-content {
  font-size: var(--text-sm); color: var(--text-secondary);
  line-height: 1.5; margin-top: 3px;
}
.notice-time {
  font-size: var(--text-xs); color: var(--text-tertiary); margin-top: 4px;
}
</style>

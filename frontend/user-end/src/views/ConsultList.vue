<script setup lang="ts">
import { ref, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { chatApi } from '@/api'
import { showToast, showConfirmDialog } from 'vant'

const router = useRouter()

const sessions = ref<any[]>([])
const loading = ref(true)

async function loadSessions() {
  loading.value = true
  try {
    const res: any = await chatApi.getSessions(1, 50)
    sessions.value = res?.items || []
  } catch { showToast('加载失败') }
  finally { loading.value = false }
}

onMounted(loadSessions)
onActivated(loadSessions)

function goChat(session: any) {
  router.push(`/consult/${session.id}?orderId=${session.order_id || ''}`)
}

async function handleDelete(session: any) {
  try {
    await showConfirmDialog({
      title: '删除会话',
      message: `确定删除「${session.product_name || '售后咨询'}」的会话记录吗？删除后不可恢复。`,
      confirmButtonColor: '#DC2626',
    })
  } catch { return }
  try {
    await chatApi.deleteSession(session.id)
    sessions.value = sessions.value.filter(s => s.id !== session.id)
    showToast('已删除')
  } catch { showToast('删除失败') }
}

function formatTime(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    if (diff < 86400000) {
      const hh = String(d.getHours()).padStart(2, '0')
      const mm = String(d.getMinutes()).padStart(2, '0')
      return `${hh}:${mm}`
    }
    return `${d.getMonth() + 1}/${d.getDate()}`
  } catch { return '' }
}

const statusLabel: Record<string, string> = {
  'AI进行中': 'AI',
  '待客服接手': '等待客服',
  '待客服确认': '待审批',
  '客服处理中': '人工',
  '已关闭': '已结束',
}
</script>

<template>
  <div class="list-page">
    <!-- ═══ Header ═══ -->
    <div class="list-header">
      <button class="list-back" @click="router.push('/home')">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
      </button>
      <span class="list-header-title">咨询记录</span>
      <span style="width:36px;"></span>
    </div>

    <van-loading v-if="loading" type="spinner" style="display:flex;justify-content:center;padding:40px;" />

    <template v-else>
      <van-swipe-cell v-for="s in sessions" :key="s.id">
        <div class="session-card" @click="goChat(s)">
          <div class="session-avatar">
            <span class="session-avatar-text">{{ (s.product_name || '咨询').charAt(0) }}</span>
            <span class="session-dot" :class="s.status === '客服处理中' || s.status === '待客服接手' ? 'dot-human' : s.status === '已关闭' ? 'dot-off' : 'dot-ai'"></span>
          </div>
          <div class="session-body">
            <div class="session-top">
              <span class="session-name">{{ s.product_name || '售后咨询' }}</span>
              <span class="session-time">{{ formatTime(s.updated_at) }}</span>
            </div>
            <div class="session-bottom">
              <span class="session-preview text-ellipsis">{{ s.last_message || '暂无消息' }}</span>
              <span class="session-tag">{{ statusLabel[s.status] || s.status }}</span>
            </div>
          </div>
        </div>
        <template #right>
          <div class="session-swipe-delete" @click="handleDelete(s)">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
            </svg>
            <span>删除</span>
          </div>
        </template>
      </van-swipe-cell>

      <div v-if="sessions.length === 0" class="empty-state">
        <span class="empty-state-icon">💬</span>
        <p>暂无咨询记录</p>
        <p style="font-size:var(--text-xs);color:var(--text-tertiary);">从订单页点击「咨询客服」发起首次咨询</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.list-page { min-height: 100dvh; background: var(--bg-page); }

/* ═══ Header ═══ */
.list-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px var(--space-md); background: rgba(255,255,255,0.82);
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border-bottom: 1px solid var(--border-light); position: sticky; top: 0; z-index: 10;
}
.list-back {
  width: 36px; height: 36px; border-radius: 50%;
  border: none; background: transparent;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: var(--text-secondary); transition: all 0.2s ease;
}
.list-back:active { background: rgba(0,0,0,0.04); color: var(--text); }
.list-header-title { font-size: var(--text-base); font-weight: 700; color: var(--text); }

/* ═══ Session Card ═══ */
.session-card {
  display: flex; align-items: center; gap: 12px; padding: 16px var(--space-md);
  cursor: pointer; background: #fff;
  border-bottom: 1px solid rgba(0,0,0,0.03);
  transition: background 0.2s ease;
}
.session-card:active { background: rgba(0,0,0,0.015); }
.session-avatar {
  width: 52px; height: 52px; border-radius: 16px; flex-shrink: 0;
  background: var(--bg-input); display: flex; align-items: center; justify-content: center;
  position: relative;
}
.session-avatar-text { font-size: 20px; font-weight: 700; color: var(--text-secondary); }
.session-dot {
  position: absolute; bottom: 2px; right: 2px;
  width: 10px; height: 10px; border-radius: 50%; border: 2px solid #fff;
}
.dot-ai    { background: var(--primary); }
.dot-human { background: var(--green); }
.dot-off   { background: rgba(0,0,0,0.18); }

.session-body { flex: 1; min-width: 0; }
.session-top {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 4px;
}
.session-name { font-size: var(--text-base); font-weight: 600; color: var(--text); letter-spacing: -0.01em; }
.session-time { font-size: 11px; color: var(--text-tertiary); flex-shrink: 0; }
.session-bottom {
  display: flex; justify-content: space-between; align-items: center;
}
.session-preview { font-size: var(--text-sm); color: var(--text-secondary); flex: 1; }
.session-tag {
  font-size: 10px; color: var(--text-tertiary); background: rgba(0,0,0,0.04);
  padding: 2px 8px; border-radius: 8px; font-weight: 500; flex-shrink: 0; margin-left: 8px;
}

/* Swipe delete */
.session-swipe-delete {
  background: var(--red); color: #fff; display: flex;
  flex-direction: column; align-items: center; justify-content: center; gap: 4px;
  width: 72px; font-size: 12px; font-weight: 600; cursor: pointer;
}
</style>

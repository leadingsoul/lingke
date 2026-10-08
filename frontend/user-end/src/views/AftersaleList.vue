<script setup lang="ts">
import { ref, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { aftersaleApi } from '@/api'
import type { AftersaleTicket } from '@/types'
import { showToast } from 'vant'

const router = useRouter()
const userStore = useUserStore()

const tickets = ref<AftersaleTicket[]>([])
const loading = ref(false)

onMounted(() => {
  if (!userStore.isLoggedIn) { router.replace('/login'); return }
  loadTickets()
})

onActivated(() => {
  if (userStore.isLoggedIn) loadTickets()
})

async function loadTickets() {
  loading.value = true
  try {
    const res = await aftersaleApi.list()
    tickets.value = res.items
  } catch { showToast('加载失败') }
  finally { loading.value = false }
}

function goDetail(ticket: AftersaleTicket) { router.push(`/aftersale/${ticket.id}`) }

function getStepIndex(status: string): number {
  const map: Record<string, number> = { '待审核': 0, '审核通过': 1, '处理中': 2, '已完成': 3, '已拒绝': -1 }
  return map[status] ?? 0
}

function statusDotColor(status: string): string {
  const map: Record<string, string> = {
    '待审核': '#EA580C', '审核通过': '#0D9488', '处理中': '#0D9488', '已完成': '#16A34A', '已拒绝': '#DC2626',
  }
  return map[status] || '#999'
}

function statusClass(status: string): string {
  const map: Record<string, string> = {
    '待审核': 'tag-orange', '审核通过': 'tag-blue', '处理中': 'tag-blue', '已完成': 'tag-green', '已拒绝': 'tag-red',
  }
  return map[status] || 'tag-grey'
}
</script>

<template>
  <div class="aftersale-page">
    <!-- ═══ Header ═══ -->
    <div class="page-header">
      <h1 class="section-title" style="margin:0;">我的售后</h1>
    </div>

    <div class="page" style="padding-top:4px;">
      <van-loading v-if="loading" type="spinner" style="display:flex;justify-content:center;padding:40px;" />

      <!-- Empty -->
      <div v-if="!loading && tickets.length === 0" class="empty-state">
        <span class="empty-state-icon">📭</span>
        <p>暂无售后工单</p>
      </div>

      <!-- Ticket Cards -->
      <div
        v-for="ticket in tickets"
        :key="ticket.id"
        class="ticket-card"
        @click="goDetail(ticket)"
      >
        <!-- Left color bar -->
        <div class="ticket-bar" :style="{ background: statusDotColor(ticket.aso_status) }"></div>

        <!-- Body -->
        <div class="ticket-body">
          <div class="ticket-top">
            <div class="ticket-type text-ellipsis">{{ ticket.order_info?.product_name || '商品' }}</div>
            <span class="tag" :class="statusClass(ticket.aso_status)">
              <span class="status-dot" :style="{ background: statusDotColor(ticket.aso_status) }"></span>
              {{ ticket.aso_status }}
            </span>
          </div>
          <div class="ticket-meta">
            {{ ticket.aso_type }} · {{ ticket.aso_reason }} · {{ ticket.created_at?.slice(0, 10) }}
          </div>

          <!-- Step indicator -->
          <div v-if="ticket.aso_status !== '已拒绝'" class="ticket-steps">
            <template v-for="(label, i) in ['提交','审核','处理','完成']" :key="i">
              <div class="ticket-step" :class="{ done: i < getStepIndex(ticket.aso_status), active: i === getStepIndex(ticket.aso_status) }">
                <div class="ticket-step-dot">{{ i < getStepIndex(ticket.aso_status) ? '✓' : (i + 1) }}</div>
              </div>
              <div v-if="i < 3" class="ticket-step-line" :class="{ filled: i < getStepIndex(ticket.aso_status) }"></div>
            </template>
          </div>

          <div v-if="ticket.aso_status === '已拒绝'" class="ticket-reject-reason">
            拒绝原因: {{ ticket.handle_opinion || '不符合售后条件' }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.aftersale-page { min-height: 100dvh; background: var(--bg-page); }

/* ═══ Ticket card ═══ */
.ticket-card {
  display: flex; gap: 0; margin-bottom: var(--space-md);
  background: #fff; border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs); border: 1px solid var(--border-light);
  overflow: hidden; cursor: pointer;
  transition: all 0.3s var(--ease-out-expo);
}
.ticket-card:active { transform: scale(0.985); box-shadow: var(--shadow-sm); }
.ticket-bar {
  width: 4px; flex-shrink: 0; border-radius: 0;
}
.ticket-body {
  flex: 1; padding: 16px; min-width: 0;
}
.ticket-top {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 10px;
}
.ticket-type {
  font-size: var(--text-base); font-weight: 600; color: var(--text);
}
.ticket-meta {
  font-size: var(--text-xs); color: var(--text-tertiary); margin-top: 6px;
}

/* Steps */
.ticket-steps {
  display: flex; align-items: center; gap: 0; margin-top: 14px;
}
.ticket-step { display: flex; align-items: center; }
.ticket-step-dot {
  width: 22px; height: 22px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; font-weight: 700; flex-shrink: 0;
  background: rgba(0,0,0,0.04); color: var(--text-tertiary);
  transition: all 0.3s ease;
}
.ticket-step.done .ticket-step-dot,
.ticket-step.active .ticket-step-dot {
  background: var(--primary); color: #fff;
}
.ticket-step-line {
  width: 28px; height: 2px; background: rgba(0,0,0,0.06);
  margin: 0 4px; transition: background 0.3s ease;
}
.ticket-step-line.filled { background: var(--primary); }
.ticket-reject-reason {
  font-size: var(--text-xs); color: var(--red); margin-top: 8px;
}
</style>

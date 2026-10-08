<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { aftersaleApi } from '@/api'
import type { AftersaleTicket } from '@/types'
import { showToast, showConfirmDialog } from 'vant'

const route = useRoute()
const router = useRouter()
const ticketId = route.params.id as string

const ticket = ref<AftersaleTicket | null>(null)
const loading = ref(true)

onMounted(async () => {
  try { ticket.value = await aftersaleApi.detail(ticketId) }
  catch { showToast('加载失败') }
  finally { loading.value = false }
})

function statusDotColor(status: string): string {
  const map: Record<string, string> = {
    '待审核': '#EA580C', '审核通过': '#0D9488', '处理中': '#0D9488', '已完成': '#16A34A', '已拒绝': '#DC2626',
  }
  return map[status] || '#999'
}

function getStepIndex(status: string): number {
  const map: Record<string, number> = { '待审核': 0, '审核通过': 1, '处理中': 2, '已完成': 3, '已拒绝': -1 }
  return map[status] ?? 0
}

const steps = ['提交', '审核', '处理', '完成']

async function handleCancel() {
  try {
    await showConfirmDialog({
      title: '撤销申请',
      message: '确定要撤销此次售后申请吗？',
      confirmButtonColor: '#DC2626',
    })
    await aftersaleApi.cancel(ticketId)
    showToast('已撤销')
    router.push('/aftersale/list')
  } catch { /* canceled */ }
}
</script>

<template>
  <div class="detail-page">
    <!-- ═══ Header ═══ -->
    <div class="detail-header">
      <button class="detail-back" @click="router.push('/aftersale/list')">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
      </button>
      <span class="detail-header-title">售后详情</span>
      <span style="width:36px;"></span>
    </div>

    <van-loading v-if="loading" type="spinner" style="display:flex;justify-content:center;padding:40px;" />

    <template v-if="ticket">
      <div class="page" style="padding-bottom:100px;">
        <!-- ═══ Status Banner ═══ -->
        <div class="status-banner" :style="{ '--accent': statusDotColor(ticket.aso_status) }">
          <div class="status-banner-dot" :style="{ background: statusDotColor(ticket.aso_status) }"></div>
          <div class="status-banner-text">{{ ticket.aso_status }}</div>
          <div class="status-banner-meta">{{ ticket.aso_type }} · {{ ticket.aso_reason }}</div>
        </div>

        <!-- ═══ Timeline ═══ -->
        <div v-if="ticket.aso_status !== '已拒绝'" class="info-card">
          <div class="info-card-title">处理进度</div>
          <div class="stepper">
            <div
              v-for="(label, i) in steps"
              :key="i"
              class="stepper-node"
              :class="{
                'stepper-done': i < getStepIndex(ticket.aso_status),
                'stepper-active': i === getStepIndex(ticket.aso_status),
              }"
            >
              <div class="stepper-circle">
                <svg v-if="i < getStepIndex(ticket.aso_status)" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span v-else>{{ i + 1 }}</span>
              </div>
              <div class="stepper-label">{{ label }}</div>
              <div v-if="i < steps.length - 1" class="stepper-line" :class="{ 'stepper-line-done': i < getStepIndex(ticket.aso_status) }"></div>
            </div>
          </div>
        </div>

        <!-- ═══ Ticket Info ═══ -->
        <div class="info-card">
          <div class="info-card-title">工单信息</div>
          <div class="info-card-body">
            <div class="info-row">
              <span class="info-row-key">售后类型</span>
              <span class="info-row-val">{{ ticket.aso_type }}</span>
            </div>
            <div class="info-row">
              <span class="info-row-key">售后原因</span>
              <span class="info-row-val">{{ ticket.aso_reason }}</span>
            </div>
            <div class="info-row">
              <span class="info-row-key">紧急程度</span>
              <span class="tag" :class="ticket.urgency === '紧急' ? 'tag-red' : 'tag-grey'">
                {{ ticket.urgency || '普通' }}
              </span>
            </div>
            <div class="info-row">
              <span class="info-row-key">责任归属</span>
              <span class="info-row-val">{{ ticket.responsibility || '待定' }}</span>
            </div>
            <div class="info-row" v-if="ticket.description">
              <span class="info-row-key">问题描述</span>
              <span class="info-row-val" style="text-align:left;white-space:pre-wrap;">{{ ticket.description }}</span>
            </div>
          </div>
        </div>

        <!-- Evidence -->
        <div v-if="ticket.evidence_urls?.length" class="info-card">
          <div class="info-card-title">凭证图片</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;padding:0 18px 16px;">
            <van-image v-for="(url, i) in ticket.evidence_urls" :key="i" :src="url" width="64" height="64" fit="cover" :radius="10" />
          </div>
        </div>

        <!-- Handle opinion -->
        <div v-if="ticket.handle_opinion" class="info-card" style="border-color:rgba(13,148,136,0.15);background:rgba(13,148,136,0.02);">
          <div class="info-card-title">处理意见</div>
          <div style="font-size:var(--text-base);color:var(--text);line-height:1.6;padding:0 18px 16px;">{{ ticket.handle_opinion }}</div>
        </div>
        <div v-if="ticket.suggested_action" class="info-card" style="border-color:rgba(13,148,136,0.15);">
          <div class="info-card-title">建议方案</div>
          <div style="font-size:var(--text-base);color:var(--primary);line-height:1.6;padding:0 18px 16px;">{{ ticket.suggested_action }}</div>
        </div>

        <!-- Cancel -->
        <div v-if="ticket.aso_status === '待审核'" style="padding:var(--space-md) 0;">
          <button class="btn btn-danger btn-block" @click="handleCancel">撤销售后申请</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.detail-page { min-height: 100dvh; background: var(--bg-page); }

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

/* ═══ Status Banner ═══ */
.status-banner {
  text-align: center; padding: 28px 0 20px;
}
.status-banner-dot {
  width: 14px; height: 14px; border-radius: 50%;
  margin: 0 auto 12px;
  box-shadow: 0 0 0 6px color-mix(in srgb, var(--accent) 12%, transparent);
}
.status-banner-text {
  font-size: var(--text-2xl); font-weight: 800; color: var(--text);
  letter-spacing: -0.02em;
}
.status-banner-meta {
  font-size: var(--text-sm); color: var(--text-tertiary); margin-top: 4px;
}

/* ═══ Info Cards ═══ */
.info-card {
  background: #fff; border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xs); border: 1px solid var(--border-light);
  margin-bottom: var(--space-md); overflow: hidden;
}
.info-card-title {
  font-size: var(--text-xs); font-weight: 600; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: 0.06em;
  padding: 16px 18px 0;
}
.info-card-body { padding: 12px 18px 16px; }
.info-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 9px 0; border-bottom: 1px solid rgba(0,0,0,0.03);
}
.info-row:last-child { border-bottom: none; }
.info-row-key { font-size: var(--text-sm); color: var(--text-secondary); flex-shrink: 0; }
.info-row-val { font-size: var(--text-sm); color: var(--text); font-weight: 500; max-width: 60%; text-align: right; }

/* ═══ Progress Stepper (Horizontal) ═══ */
.stepper {
  display: flex; align-items: flex-start; justify-content: center;
  padding: 8px 18px 20px; gap: 0;
}
.stepper-node {
  display: flex; flex-direction: column; align-items: center;
  flex: 1; position: relative; gap: 8px;
}
.stepper-circle {
  width: 28px; height: 28px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 600;
  border: 2px solid rgba(0,0,0,0.12);
  color: var(--text-tertiary);
  background: #fff;
  transition: all 0.35s cubic-bezier(0.32,0.72,0,1);
  flex-shrink: 0; position: relative; z-index: 1;
}
.stepper-done .stepper-circle {
  background: var(--primary); border-color: var(--primary); color: #fff;
}
.stepper-active .stepper-circle {
  border-color: var(--primary); color: var(--primary);
  box-shadow: 0 0 0 5px rgba(13,148,136,0.1);
}
.stepper-label {
  font-size: 11px; font-weight: 500; color: var(--text-tertiary);
  letter-spacing: 0.03em; white-space: nowrap;
  transition: color 0.35s ease;
}
.stepper-done .stepper-label { color: var(--primary); }
.stepper-active .stepper-label { color: var(--text); font-weight: 600; }
.stepper-line {
  position: absolute; top: 14px; left: calc(50% + 20px);
  width: calc(100% - 40px); height: 1.5px;
  background: rgba(0,0,0,0.08);
  transition: background 0.5s ease;
}
.stepper-line-done { background: var(--primary); }
</style>

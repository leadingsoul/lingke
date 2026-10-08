<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { aftersaleApi } from '@/api'
import { showToast, showLoadingToast, closeToast } from 'vant'

const route = useRoute()
const router = useRouter()
const orderId = route.params.orderId as string

const asoType = ref('换货')
const asoReason = ref('')
const description = ref('')
const evidenceFiles = ref<any[]>([])

const typeOptions = ['仅退款', '退货退款', '换货', '维修']
const reasonOptions: Record<string, string[]> = {
  '仅退款': ['未收到货', '描述不符', '质量问题', '其他'],
  '退货退款': ['质量问题', '发错货', '七天无理由', '描述不符', '其他'],
  '换货': ['尺码不合适', '质量问题', '发错货', '描述不符', '其他'],
  '维修': ['质量问题', '意外损坏', '其他'],
}

const currentReasons = computed(() => reasonOptions[asoType.value] || [])

async function handleSubmit() {
  if (!asoReason.value) { showToast('请选择售后原因'); return }

  showLoadingToast({ message: '提交中...', forbidClick: true })
  try {
    const urls = evidenceFiles.value.map((f: any) => f.url || f.content || '')
    const res = await aftersaleApi.apply({
      order_id: orderId,
      aso_type: asoType.value,
      aso_reason: asoReason.value,
      description: description.value,
      evidence_urls: urls,
    })
    closeToast()
    showToast('售后申请已提交！')
    router.replace(`/aftersale/${res.id}`)
  } catch { closeToast() }
}
</script>

<template>
  <div class="apply-page">
    <!-- ═══ Header ═══ -->
    <div class="detail-header">
      <button class="detail-back" @click="router.push('/home')">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
      </button>
      <span class="detail-header-title">售后申请</span>
      <span style="width:36px;"></span>
    </div>

    <div class="page" style="padding-bottom:40px;">
      <!-- ═══ Intro ═══ -->
      <div class="apply-intro">
        <div class="apply-intro-title">需要什么帮助？</div>
        <div class="apply-intro-desc">请选择售后类型并描述问题，我们会尽快为您处理</div>
        <div class="apply-order-chip">
          <span class="apply-order-label">关联订单</span>
          <span class="apply-order-id">{{ orderId }}</span>
        </div>
      </div>

      <!-- ═══ Type Pills ═══ -->
      <div class="apply-section">
        <div class="apply-section-label">售后类型</div>
        <div class="type-grid">
          <div
            v-for="t in typeOptions"
            :key="t"
            class="type-card"
            :class="{ selected: asoType === t }"
            @click="asoType = t; asoReason = ''"
          >
            <span class="type-card-emoji">
              {{ t === '仅退款' ? '💰' : t === '退货退款' ? '📦' : t === '换货' ? '🔄' : '🔧' }}
            </span>
            <span class="type-card-label">{{ t }}</span>
          </div>
        </div>
      </div>

      <!-- ═══ Reason ═══ -->
      <div class="apply-section">
        <div class="apply-section-label">售后原因</div>
        <div class="pill-row">
          <span
            v-for="r in currentReasons"
            :key="r"
            class="pill"
            :class="{ active: asoReason === r }"
            @click="asoReason = r"
          >{{ r }}</span>
        </div>
      </div>

      <!-- ═══ Description ═══ -->
      <div class="apply-section">
        <div class="apply-section-label">问题描述</div>
        <textarea
          v-model="description"
          class="apply-textarea"
          placeholder="请详细描述您遇到的问题..."
          maxlength="500"
        ></textarea>
        <div class="apply-charcount">{{ description.length }}/500</div>
      </div>

      <!-- ═══ Evidence ═══ -->
      <div class="apply-section">
        <div class="apply-section-label">上传凭证</div>
        <van-uploader
          v-model="evidenceFiles"
          :max-count="9"
          :max-size="5 * 1024 * 1024"
          accept="image/*"
          multiple
          style="margin-top:4px;"
        />
      </div>

      <!-- ═══ Submit ═══ -->
      <button class="btn btn-primary btn-block" style="margin-top:var(--space-lg);" @click="handleSubmit">提交申请</button>
    </div>
  </div>
</template>

<style scoped>
.apply-page { min-height: 100dvh; background: var(--bg-page); }

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

/* ═══ Intro ═══ */
.apply-intro { text-align: center; padding: var(--space-lg) 0 var(--space-md); }
.apply-intro-title { font-size: var(--text-2xl); font-weight: 800; color: var(--text); letter-spacing: -0.02em; }
.apply-intro-desc { font-size: var(--text-sm); color: var(--text-tertiary); margin-top: 6px; }
.apply-order-chip {
  display: inline-flex; align-items: center; gap: 8px; margin-top: 14px;
  padding: 8px 16px; background: rgba(13,148,136,0.06); border-radius: var(--radius-pill);
}
.apply-order-label { font-size: var(--text-xs); color: var(--text-tertiary); }
.apply-order-id { font-size: var(--text-sm); font-weight: 600; color: var(--primary); font-family: monospace; }

/* ═══ Sections ═══ */
.apply-section { margin-bottom: var(--space-lg); }
.apply-section-label {
  font-size: var(--text-xs); font-weight: 600; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px;
}

/* Type cards */
.type-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.type-card {
  background: #fff; border-radius: var(--radius-lg);
  border: 1.5px solid var(--border-light);
  padding: 22px 16px; text-align: center; cursor: pointer;
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  transition: all 0.3s var(--ease-out-expo);
}
.type-card.selected {
  border-color: var(--primary); background: rgba(13,148,136,0.04);
  box-shadow: 0 0 0 3px rgba(13,148,136,0.06);
}
.type-card:active { transform: scale(0.96); }
.type-card-emoji { font-size: 28px; }
.type-card-label { font-size: var(--text-sm); font-weight: 600; color: var(--text); }

/* Reason pills */
.pill-row { display: flex; flex-wrap: wrap; gap: 8px; }
.pill-row .pill {
  background: #fff; border: 1px solid var(--border-light);
  color: var(--text-secondary); cursor: pointer; font-size: var(--text-sm);
  padding: 8px 16px; border-radius: var(--radius-pill);
  transition: all 0.25s ease;
}
.pill-row .pill.active {
  background: rgba(13,148,136,0.08); border-color: var(--primary);
  color: var(--primary); font-weight: 600;
}

/* Textarea */
.apply-textarea {
  width: 100%; min-height: 120px; border: 1px solid var(--border-light);
  border-radius: var(--radius-md); padding: 14px 16px;
  font-size: var(--text-base); line-height: 1.6; resize: vertical;
  font-family: inherit; background: #fff; outline: none;
  transition: border-color 0.3s ease; box-sizing: border-box;
}
.apply-textarea:focus { border-color: var(--border-focus); }
.apply-charcount {
  text-align: right; font-size: var(--text-xs); color: var(--text-tertiary);
  margin-top: 4px;
}
</style>

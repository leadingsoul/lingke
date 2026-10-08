<script setup lang="ts">
import { ref, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { evaluateApi } from '@/api'
import type { PendingEval, Evaluation } from '@/types'
import { showToast, showLoadingToast, closeToast } from 'vant'

const router = useRouter()
const userStore = useUserStore()

const pendingOrders = ref<PendingEval[]>([])
const myEvaluations = ref<Evaluation[]>([])
const loading = ref(false)
const activeTab = ref(0)
const selectedEvaluation = ref<Evaluation | null>(null)
const showDetail = ref(false)

// ====== 编辑模式 ======
const isEditing = ref(false)
const editProductRating = ref(5)
const editServiceRating = ref(5)
const editLogisticsRating = ref(5)
const editContent = ref('')
const editSubmitting = ref(false)

onMounted(() => {
  if (!userStore.isLoggedIn) { router.replace('/login'); return }
  loadPending()
})

onActivated(() => {
  if (userStore.isLoggedIn) loadPending()
})

async function loadPending() {
  loading.value = true
  try { const res = await evaluateApi.pendingList(); pendingOrders.value = res.items }
  catch { showToast('加载失败') }
  finally { loading.value = false }
}

async function loadMine() {
  loading.value = true
  try { const res = await evaluateApi.myList(); myEvaluations.value = res.items }
  catch { showToast('加载失败') }
  finally { loading.value = false }
}

function switchTab(index: number) {
  activeTab.value = index
  index === 0 ? loadPending() : loadMine()
}

function goEvaluate(order: PendingEval) { router.push(`/evaluate/${order.order_id}`) }

function openDetail(ev: Evaluation) {
  selectedEvaluation.value = ev
  showDetail.value = true
}

// ====== 编辑入口 ======
function startEdit() {
  if (!selectedEvaluation.value) return
  editProductRating.value = selectedEvaluation.value.product_rating
  editServiceRating.value = selectedEvaluation.value.service_rating
  editLogisticsRating.value = selectedEvaluation.value.logistics_rating
  editContent.value = selectedEvaluation.value.content || ''
  isEditing.value = true
}

function cancelEdit() { isEditing.value = false }

async function submitEdit() {
  if (!selectedEvaluation.value) return
  editSubmitting.value = true
  showLoadingToast({ message: '更新中...', forbidClick: true })
  try {
    await evaluateApi.update(
      selectedEvaluation.value.id,
      editProductRating.value,
      editServiceRating.value,
      editLogisticsRating.value,
      editContent.value,
    )
    closeToast()
    showToast('评价已更新 ✅')
    if (selectedEvaluation.value) {
      selectedEvaluation.value.product_rating = editProductRating.value
      selectedEvaluation.value.service_rating = editServiceRating.value
      selectedEvaluation.value.logistics_rating = editLogisticsRating.value
      selectedEvaluation.value.content = editContent.value
    }
    const idx = myEvaluations.value.findIndex(e => e.id === selectedEvaluation.value!.id)
    if (idx > -1) myEvaluations.value[idx] = { ...myEvaluations.value[idx], ...selectedEvaluation.value }
    isEditing.value = false
  } catch { closeToast() }
  finally { editSubmitting.value = false }
}

function setEditRating(which: 'product' | 'service' | 'logistics', val: number) {
  if (which === 'product') editProductRating.value = val
  else if (which === 'service') editServiceRating.value = val
  else editLogisticsRating.value = val
}

function getEffectiveSentiment(ev: Evaluation): string {
  const avg = (ev.product_rating + ev.service_rating + ev.logistics_rating) / 3
  if (avg >= 4) return 'positive'
  if (avg <= 2) return 'negative'
  return ev.sentiment || 'neutral'
}

function getSentimentLabel(s?: string) {
  const map: Record<string, string> = { positive: '好评', neutral: '中评', negative: '差评' }
  return map[s || ''] || '未分析'
}

function getSentimentColor(s?: string) {
  const map: Record<string, string> = { positive: 'var(--green)', neutral: 'var(--orange)', negative: 'var(--red)' }
  return map[s || ''] || 'var(--text-secondary)'
}

function getAvgRating(ev: Evaluation): number {
  return Math.round((ev.product_rating + ev.logistics_rating + ev.service_rating) / 3)
}
</script>

<template>
  <div class="evaluate-page">
    <!-- ═══ Header ═══ -->
    <div class="page-header">
      <h1 class="section-title" style="margin:0;">我的评价</h1>
    </div>

    <!-- ═══ Pill Tabs ═══ -->
    <div class="eval-tabs">
      <span class="pill" :class="{ active: activeTab === 0 }" @click="switchTab(0)">待评价</span>
      <span class="pill" :class="{ active: activeTab === 1 }" @click="switchTab(1)">已评价</span>
    </div>

    <div class="page" style="padding-top:4px;">
      <van-loading v-if="loading" type="spinner" style="display:flex;justify-content:center;padding:40px;" />

      <!-- ═══ 待评价 ═══ -->
      <template v-if="activeTab === 0 && !loading">
        <div v-if="pendingOrders.length === 0" class="empty-state">
          <span class="empty-state-icon">🌟</span>
          <p>暂无待评价订单</p>
        </div>
        <div v-for="order in pendingOrders" :key="order.order_id" class="card eval-card-row" @click="goEvaluate(order)">
          <div class="eval-card-img">
            <img v-if="order.product_image" :src="order.product_image" alt="" />
            <span v-else class="eval-card-fallback">📦</span>
          </div>
          <div class="eval-card-body">
            <div class="eval-card-name text-ellipsis">{{ order.product_name || '商品' }}</div>
            <div class="eval-card-price">¥{{ Number(order.total_amount).toFixed(2) }}</div>
            <div class="eval-card-meta">订单号: {{ order.order_sn?.slice(0, 8) || '' }}...</div>
          </div>
          <button class="btn btn-primary btn-sm" style="flex-shrink:0;">去评价</button>
        </div>
      </template>

      <!-- ═══ 已评价 ═══ -->
      <template v-if="activeTab === 1 && !loading">
        <div v-if="myEvaluations.length === 0" class="empty-state">
          <span class="empty-state-icon">📝</span>
          <p>还没有评价过</p>
        </div>
        <div v-for="ev in myEvaluations" :key="ev.id" class="card eval-card-row" style="flex-wrap:wrap;" @click="openDetail(ev)">
          <div class="eval-card-img">
            <img v-if="ev.order_info?.product_image" :src="ev.order_info.product_image" alt="" />
            <span v-else class="eval-card-fallback">📦</span>
          </div>
          <div class="eval-card-body">
            <div class="eval-card-name text-ellipsis">{{ ev.order_info?.product_name || ev.order_id?.slice(0, 12) || '商品' }}</div>
            <div class="eval-card-stars">
              <span class="star-gold">★</span>
              <span style="font-size:var(--text-sm);font-weight:600;color:var(--text);margin-left:4px;">{{ getAvgRating(ev) }}</span>
            </div>
            <div class="eval-card-content" v-if="ev.content">{{ ev.content.slice(0, 60) }}{{ ev.content.length > 60 ? '...' : '' }}</div>
          </div>
          <div style="display:flex;align-items:center;gap:6px;width:100%;margin-top:8px;">
            <span :style="{ color: getSentimentColor(getEffectiveSentiment(ev)), fontSize: '11px', fontWeight: 600 }">
              {{ getSentimentLabel(getEffectiveSentiment(ev)) }}
            </span>
            <span v-for="t in (ev.themes || [])" :key="t" class="pill" style="font-size:10px;padding:2px 10px;">{{ t }}</span>
          </div>
        </div>
      </template>
    </div>

    <!-- ═══ Detail/Edit Popup ═══ -->
    <van-popup v-model:show="showDetail" position="bottom" round :style="{ height: '80%' }" safe-area-inset-bottom @closed="isEditing = false">
      <div v-if="selectedEvaluation" class="popup-container">
        <!-- Header -->
        <div class="popup-header">
          <span class="popup-title">{{ isEditing ? '修改评价' : '评价详情' }}</span>
          <button class="popup-close" @click="showDetail = false">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div class="popup-scroll">
          <!-- Product mini -->
          <div class="popup-product" v-if="selectedEvaluation.order_info?.product_name">
            <img v-if="selectedEvaluation.order_info.product_image" :src="selectedEvaluation.order_info.product_image" class="popup-pimg" />
            <span v-else class="popup-pfallback">📦</span>
            <div>
              <div class="popup-pname">{{ selectedEvaluation.order_info.product_name || '未知商品' }}</div>
              <div class="popup-pprice">¥{{ Number(selectedEvaluation.order_info.total_amount || 0).toFixed(2) }}</div>
            </div>
          </div>

          <!-- View mode -->
          <template v-if="!isEditing">
            <div class="eval-dim-section">
              <div class="eval-dim-label">评分详情</div>
              <div class="eval-dim-list">
                <div class="eval-dim-row" v-for="dim in [
                  { label: '商品质量', val: selectedEvaluation.product_rating },
                  { label: '服务质量', val: selectedEvaluation.service_rating },
                  { label: '物流速度', val: selectedEvaluation.logistics_rating },
                ]" :key="dim.label">
                  <span class="eval-dim-name">{{ dim.label }}</span>
                  <span class="eval-dim-stars">
                    <span class="star-gold">{{ '★'.repeat(dim.val) }}</span>
                    <span class="star-empty">{{ '★'.repeat(5 - dim.val) }}</span>
                  </span>
                </div>
              </div>
            </div>
            <div v-if="selectedEvaluation.content" class="eval-text-block">
              <div class="eval-dim-label">评价内容</div>
              <div class="eval-text-content">{{ selectedEvaluation.content }}</div>
            </div>
            <div v-if="selectedEvaluation.image_urls?.length" class="eval-text-block">
              <div class="eval-dim-label">评价图片</div>
              <div style="display:flex;gap:8px;flex-wrap:wrap;">
                <img v-for="(url, i) in selectedEvaluation.image_urls" :key="i" :src="url" class="eval-thumb" />
              </div>
            </div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
              <span class="eval-dim-label" style="margin-bottom:0;">AI 分析：</span>
              <span :style="{ color: getSentimentColor(getEffectiveSentiment(selectedEvaluation)), fontSize: '13px', fontWeight: 600 }">
                {{ getSentimentLabel(getEffectiveSentiment(selectedEvaluation)) }}
              </span>
              <span v-for="t in (selectedEvaluation.themes || [])" :key="t" class="pill" style="font-size:10px;padding:2px 10px;">{{ t }}</span>
            </div>
            <div style="font-size:12px;color:var(--text-tertiary);margin-bottom:16px;">{{ selectedEvaluation.created_at }}</div>
            <button class="btn btn-outline btn-block" @click="startEdit">修改评价</button>
          </template>

          <!-- Edit mode -->
          <template v-if="isEditing">
            <div class="eval-dim-section">
              <div class="eval-dim-label">修改评分</div>
              <div class="eval-dim-list">
                <div class="eval-dim-row" v-for="dim in [
                  { label: '商品质量', which: 'product' as const, val: editProductRating },
                  { label: '服务质量', which: 'service' as const, val: editServiceRating },
                  { label: '物流速度', which: 'logistics' as const, val: editLogisticsRating },
                ]" :key="dim.which">
                  <span class="eval-dim-name">{{ dim.label }}</span>
                  <div class="eval-dim-interactive">
                    <span v-for="n in 5" :key="n"
                      :class="['star-interactive', { on: n <= dim.val }]"
                      @click="setEditRating(dim.which, n)"
                    >{{ n <= dim.val ? '★' : '☆' }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="eval-text-block">
              <div class="eval-dim-label">修改内容</div>
              <textarea v-model="editContent" class="popup-textarea" placeholder="分享您的使用体验..." rows="4"></textarea>
            </div>
            <div style="display:flex;gap:10px;">
              <button class="btn btn-outline" style="flex:1;" @click="cancelEdit">取消</button>
              <button class="btn btn-primary" style="flex:1;" @click="submitEdit" :disabled="editSubmitting">
                {{ editSubmitting ? '保存中...' : '保存修改' }}
              </button>
            </div>
          </template>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.evaluate-page { min-height: 100dvh; background: var(--bg-page); }

/* ═══ Tabs ═══ */
.eval-tabs {
  display: flex; justify-content: center; gap: 8px; padding: var(--space-md);
}
.eval-tabs .pill {
  font-size: var(--text-sm); font-weight: 500;
  padding: 8px 20px; border-radius: var(--radius-pill);
  background: #fff; color: var(--text-secondary);
  border: 1px solid var(--border-light); cursor: pointer;
  transition: all 0.3s var(--ease-out-expo);
}
.eval-tabs .pill.active {
  background: var(--primary); color: #fff; border-color: var(--primary);
}

/* ═══ Card Row ═══ */
.eval-card-row {
  display: flex; gap: 12px; align-items: center;
  cursor: pointer; margin-bottom: var(--space-md);
}
.eval-card-row:active { transform: scale(0.985); }
.eval-card-img {
  width: 68px; height: 68px; border-radius: var(--radius-md);
  background: var(--bg-input); flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; overflow: hidden;
}
.eval-card-img img { width: 100%; height: 100%; object-fit: cover; }
.eval-card-fallback { font-size: 28px; }
.eval-card-body { flex: 1; min-width: 0; }
.eval-card-name { font-size: var(--text-base); font-weight: 600; color: var(--text); }
.eval-card-price { font-size: var(--text-lg); font-weight: 800; color: var(--text); letter-spacing: -0.02em; }
.eval-card-meta { font-size: var(--text-xs); color: var(--text-tertiary); margin-top: 2px; }
.eval-card-stars { display: flex; align-items: center; margin-top: 4px; }
.eval-card-content {
  font-size: var(--text-xs); color: var(--text-secondary);
  margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ═══ Popup ═══ */
.popup-container {
  height: 100%; display: flex; flex-direction: column; padding: 20px 16px 0;
}
.popup-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px; flex-shrink: 0;
}
.popup-title { font-size: 18px; font-weight: 700; color: var(--text); }
.popup-close {
  width: 36px; height: 36px; border-radius: 50%; border: none; background: rgba(0,0,0,0.04);
  display: flex; align-items: center; justify-content: center; cursor: pointer;
  color: var(--text-secondary); transition: all 0.2s ease;
}
.popup-close:active { background: rgba(0,0,0,0.08); }
.popup-scroll { flex: 1; overflow-y: auto; padding-bottom: 20px; }

.popup-product {
  display: flex; gap: 12px; align-items: center;
  padding: 12px; background: var(--bg-input); border-radius: var(--radius-md);
  margin-bottom: 16px;
}
.popup-pimg { width: 56px; height: 56px; border-radius: var(--radius-sm); object-fit: cover; }
.popup-pfallback {
  width: 56px; height: 56px; border-radius: var(--radius-sm);
  background: rgba(0,0,0,0.05); display: flex; align-items: center; justify-content: center; font-size: 24px;
}
.popup-pname { font-size: var(--text-sm); font-weight: 600; color: var(--text); }
.popup-pprice { font-size: var(--text-xs); color: var(--text-tertiary); margin-top: 2px; }

/* Dimensions */
.eval-dim-section { margin-bottom: 16px; }
.eval-dim-label { font-size: var(--text-xs); font-weight: 600; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px; }
.eval-dim-list { display: flex; flex-direction: column; gap: 8px; }
.eval-dim-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 14px; background: var(--bg-input); border-radius: var(--radius-md);
}
.eval-dim-name { font-size: var(--text-sm); color: var(--text); min-width: 70px; }
.eval-dim-stars { font-size: 18px; }
.eval-dim-interactive { display: flex; gap: 2px; cursor: pointer; font-size: 24px; }

.eval-text-block { margin-bottom: 16px; }
.eval-text-content {
  padding: 12px; background: var(--bg-input); border-radius: var(--radius-md);
  font-size: var(--text-sm); line-height: 1.8; white-space: pre-wrap; color: var(--text);
}
.eval-thumb { width: 80px; height: 80px; border-radius: var(--radius-sm); object-fit: cover; }

.popup-textarea {
  width: 100%; padding: 12px; border: 1px solid var(--border-light); border-radius: var(--radius-md);
  font-size: var(--text-sm); line-height: 1.6; resize: vertical; font-family: inherit;
  outline: none; background: #fff; box-sizing: border-box;
  transition: border-color 0.3s ease;
}
.popup-textarea:focus { border-color: var(--border-focus); }
</style>

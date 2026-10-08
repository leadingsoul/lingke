<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { orderApi, chatApi } from '@/api'
import type { OrderDetail, ChatSession } from '@/types'
import { showToast } from 'vant'

const route = useRoute()
const router = useRouter()
const orderId = route.params.id as string

const order = ref<OrderDetail | null>(null)
const loading = ref(true)

onMounted(async () => {
  try { order.value = await orderApi.detail(orderId) }
  catch { showToast('加载失败') }
  finally { loading.value = false }
})

const consulting = ref(false)
async function goConsult() {
  if (consulting.value || !orderId) return
  consulting.value = true
  try {
    const sessions = await chatApi.getSessions(1, 50)
    const existing = (sessions.items as ChatSession[])?.find(
      s => s.order_id === orderId && s.status !== '已关闭' && s.status !== '已删除',
    )
    if (existing) { router.push(`/consult/${existing.id}?orderId=${orderId}`); return }
    const { session_id } = await chatApi.createConversation(orderId)
    router.push(`/consult/${session_id}?orderId=${orderId}`)
  } catch { showToast('创建会话失败，请重试') }
  finally { consulting.value = false }
}
</script>

<template>
  <div class="detail-page">
    <!-- ═══ Header ═══ -->
    <div class="detail-header">
      <button class="detail-back" @click="router.push('/home')">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
      </button>
      <span class="detail-header-title">订单详情</span>
      <span style="width:36px;"></span>
    </div>

    <van-loading v-if="loading" type="spinner" style="display:flex;justify-content:center;padding:40px;" />

    <template v-if="order">
      <div class="page" style="padding-bottom:120px;">
        <!-- ═══ Product Hero ═══ -->
        <div class="product-hero">
          <div class="product-hero-img">
            <img v-if="(order as any).product_image" :src="(order as any).product_image" alt="" />
            <span v-else class="product-hero-fallback">📦</span>
          </div>
          <div class="product-hero-info">
            <div class="product-hero-name">{{ order.product_name }}</div>
            <div class="product-hero-spec" v-if="order.product_spec">{{ order.product_spec }} · 数量: {{ order.quantity }}</div>
            <div class="product-hero-price">¥{{ Number(order.total_amount).toFixed(2) }}</div>
            <span class="tag" :class="order.status === '已完成' ? 'tag-green' : order.status === '已取消' ? 'tag-grey' : 'tag-blue'">
              <span class="status-dot" :class="order.status === '已完成' ? 'green' : order.status === '已取消' ? 'grey' : 'blue'"></span>
              {{ order.status }}
            </span>
          </div>
        </div>

        <!-- ═══ Logistics ═══ -->
        <div v-if="order.logistics_info" class="info-card">
          <div class="info-card-title">📦 物流信息</div>
          <div class="info-card-body">
            <div class="info-row">
              <span class="info-row-key">快递</span>
              <span class="info-row-val">{{ order.logistics_info.company }} {{ order.logistics_info.tracking_no }}</span>
            </div>
            <div v-if="order.logistics_info.traces?.[0]" style="margin-top:6px;font-size:var(--text-sm);color:var(--primary);">
              {{ order.logistics_info.traces[0].description }}
            </div>
            <div v-if="order.logistics_info.traces?.[0]?.time" style="font-size:var(--text-xs);color:var(--text-tertiary);margin-top:2px;">
              {{ order.logistics_info.traces[0].time }}
            </div>
          </div>
        </div>

        <!-- ═══ Order Info ═══ -->
        <div class="info-card">
          <div class="info-card-title">订单信息</div>
          <div class="info-card-body">
            <div class="info-row">
              <span class="info-row-key">订单编号</span>
              <span class="info-row-val">{{ order.order_sn }}</span>
            </div>
            <div class="info-row">
              <span class="info-row-key">下单时间</span>
              <span class="info-row-val">{{ order.created_at }}</span>
            </div>
            <div class="info-row" v-if="order.finished_at">
              <span class="info-row-key">完成时间</span>
              <span class="info-row-val">{{ order.finished_at }}</span>
            </div>
          </div>
        </div>

        <!-- ═══ Amount Summary ═══ -->
        <div class="info-card">
          <div class="info-card-title">金额明细</div>
          <div class="info-card-body">
            <div class="info-row">
              <span class="info-row-key">商品金额</span>
              <span class="info-row-val">¥{{ Number(order.total_amount).toFixed(2) }}</span>
            </div>
            <div class="info-row info-row-total">
              <span class="info-row-key">实付金额</span>
              <span class="info-row-val" style="font-weight:800;">¥{{ Number(order.total_amount).toFixed(2) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ Bottom Actions ═══ -->
      <div class="detail-bottom-bar">
        <button class="btn btn-outline" style="flex:1;" @click="goConsult">咨询客服</button>
        <button
          v-if="order.status === '已完成'"
          class="btn btn-primary"
          style="flex:1;"
          @click="router.push(`/aftersale/apply/${orderId}`)"
        >申请售后</button>
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

/* ═══ Product Hero ═══ */
.product-hero {
  display: flex; gap: 16px; padding: var(--space-md) 0;
}
.product-hero-img {
  width: 110px; height: 110px; border-radius: var(--radius-lg);
  background: var(--bg-input); flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; overflow: hidden;
}
.product-hero-img img { width: 100%; height: 100%; object-fit: cover; }
.product-hero-fallback { font-size: 40px; }
.product-hero-info {
  flex: 1; min-width: 0;
  display: flex; flex-direction: column; gap: 6px;
}
.product-hero-name {
  font-size: var(--text-lg); font-weight: 700; color: var(--text);
  line-height: 1.35; letter-spacing: -0.01em;
}
.product-hero-spec { font-size: var(--text-sm); color: var(--text-tertiary); }
.product-hero-price {
  font-size: var(--text-xl); font-weight: 800; color: var(--red);
  letter-spacing: -0.02em;
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
.info-row-key { font-size: var(--text-sm); color: var(--text-secondary); }
.info-row-val { font-size: var(--text-sm); color: var(--text); font-weight: 500; max-width: 60%; text-align: right; }
.info-row-total { border-top: 1px solid var(--border-light); padding-top: 12px; margin-top: 4px; border-bottom: none; }

/* ═══ Bottom Bar ═══ */
.detail-bottom-bar {
  position: fixed; bottom: 0; left: 0; right: 0; padding: 12px var(--space-md);
  display: flex; gap: 10px;
  background: rgba(255,255,255,0.88);
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  box-shadow: 0 -1px 0 var(--border-light);
}
</style>

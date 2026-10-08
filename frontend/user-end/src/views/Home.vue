<script setup lang="ts">
import { ref, computed, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { orderApi, chatApi } from '@/api'
import type { Order, ChatSession } from '@/types'
import { showToast, showLoadingToast, closeToast } from 'vant'

const router = useRouter()
const userStore = useUserStore()

const orders = ref<Order[]>([])
const refreshing = ref(false)
const loading = ref(true)
const statusFilter = ref('全部')

const STATUS_TABS = ['全部', '已完成', '待收货', '待付款']

function statusClass(status: string) {
  const map: Record<string, string> = { '已完成': 'green', '待收货': 'blue', '待付款': 'orange' }
  return map[status] || 'grey'
}

function getProductImage(order: Order): string {
  return (order as any).product_image || ''
}

onMounted(() => {
  if (!userStore.isLoggedIn) { router.replace('/login'); return }
  loadOrders()
})

onActivated(() => {
  if (userStore.isLoggedIn) loadOrders()
})

async function loadOrders() {
  loading.value = true
  try {
    const res = await orderApi.list(undefined, undefined, 1, 50)
    orders.value = res.items
    refreshing.value = false
  } catch { showToast('加载失败') }
  finally { loading.value = false }
}

const filteredOrders = computed(() => {
  return orders.value
    .filter(o => o.status !== '已关闭')
    .filter(o => statusFilter.value === '全部' || o.status === statusFilter.value)
})

const activeCount = computed(() => filteredOrders.value.length)

function onRefresh() { refreshing.value = true; loadOrders() }
function goOrder(order: Order) { router.push(`/order/${order.id}`) }

// ====== 咨询客服 ======
const consulting = ref(false)
const sessionCache = new Map<string, string>()
async function goConsult(order: Order, e: Event) {
  e.stopPropagation()
  if (consulting.value) return
  consulting.value = true
  try {
    let sid = sessionCache.get(order.id)
    if (sid) { router.push(`/consult/${sid}?orderId=${order.id}`); return }
    const sessions = await chatApi.getSessions(1, 50)
    const existing = (sessions.items as ChatSession[])?.find(
      s => s.order_id === order.id && s.status !== '已关闭' && s.status !== '已删除',
    )
    if (existing) { sid = existing.id; sessionCache.set(order.id, sid); router.push(`/consult/${sid}?orderId=${order.id}`); return }
    const { session_id } = await chatApi.createConversation(order.id)
    sessionCache.set(order.id, session_id)
    router.push(`/consult/${session_id}?orderId=${order.id}`)
  } catch { showToast('创建会话失败') }
  finally { consulting.value = false }
}

function goAftersale(order: Order, e: Event) {
  e.stopPropagation()
  router.push(`/aftersale/apply/${order.id}`)
}
</script>

<template>
  <div class="home-page">
    <!-- ── Header ── -->
    <div class="home-header">
      <div class="home-greeting">
        <h1 class="section-title" style="margin:0;">我的订单</h1>
        <span class="home-count">{{ activeCount }} 笔</span>
      </div>
    </div>

    <!-- ── Filter Pills ── -->
    <div class="filter-scroll">
      <span
        v-for="tab in STATUS_TABS"
        :key="tab"
        class="pill"
        :class="{ active: statusFilter === tab }"
        @click="statusFilter = tab"
      >{{ tab }}</span>
    </div>

    <!-- ── Content ── -->
    <div class="page" style="padding-top:8px;">
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <!-- Empty -->
        <div v-if="!loading && filteredOrders.length === 0" class="empty-state">
          <span class="empty-state-icon">📭</span>
          <p>{{ orders.length === 0 ? '还没有订单' : '该状态下暂无订单' }}</p>
        </div>

        <!-- Order Cards -->
        <div
          v-for="order in filteredOrders"
          :key="order.id"
          class="card order-row"
          @click="goOrder(order)"
        >
          <!-- Product Image -->
          <div class="order-img-box">
            <img
              v-if="getProductImage(order)"
              :src="getProductImage(order)"
              class="order-img"
            />
            <span v-else class="order-img-fallback">📦</span>
          </div>

          <!-- Info -->
          <div class="order-body">
            <div class="order-name text-ellipsis">{{ order.product_name || '商品' }}</div>
            <div class="order-price">¥{{ Number(order.total_amount).toFixed(2) }}</div>
            <div class="order-footer">
              <span class="tag" :class="'tag-' + statusClass(order.status)">
                <span class="status-dot" :class="statusClass(order.status)"></span>
                {{ order.status }}
              </span>
              <span class="order-time">{{ (order as any).created_at?.slice(0, 10) || '' }}</span>
            </div>
          </div>

          <!-- Actions -->
          <div class="order-actions-col">
            <button
              v-if="order.status === '已完成'"
              class="btn btn-outline btn-sm"
              @click="goAftersale(order, $event)"
            >售后</button>
            <button
              class="btn btn-ghost btn-sm"
              @click="goConsult(order, $event)"
            >咨询</button>
          </div>
        </div>
      </van-pull-refresh>
    </div>
  </div>
</template>

<style scoped>
.home-page { min-height: 100vh; background: var(--bg-page); }

/* ── Header ── */
.home-header {
  padding: var(--space-lg) var(--space-md) 0;
}
.home-greeting {
  display: flex; align-items: baseline; gap: 10px;
}
.home-count {
  font-size: var(--text-sm); font-weight: 500;
  color: var(--text-tertiary);
}

/* ── Filter ── */
.filter-scroll {
  display: flex; gap: 6px; padding: var(--space-md);
  overflow-x: auto; -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.filter-scroll::-webkit-scrollbar { display: none; }

/* ── Order Row ── */
.order-row {
  display: flex; gap: 14px; align-items: center;
  padding: 14px; border-radius: var(--radius-lg);
  cursor: pointer;
}
.order-row:hover { box-shadow: var(--shadow-sm); }

.order-img-box {
  width: 80px; height: 80px; border-radius: var(--radius-md);
  background: var(--bg-input); flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
}
.order-img {
  width: 100%; height: 100%; object-fit: cover;
}
.order-img-fallback {
  font-size: 32px;
}

.order-body {
  flex: 1; min-width: 0;
  display: flex; flex-direction: column; gap: 4px;
}
.order-name {
  font-size: var(--text-base); font-weight: 600;
  color: var(--text); letter-spacing: -0.01em;
}
.order-price {
  font-size: var(--text-lg); font-weight: 800;
  color: var(--text); letter-spacing: -0.02em;
}
.order-footer {
  display: flex; align-items: center; gap: 8px;
}
.order-time {
  font-size: var(--text-xs); color: var(--text-tertiary);
}

/* ── Actions ── */
.order-actions-col {
  display: flex; flex-direction: column; gap: 6px;
  flex-shrink: 0;
}
</style>

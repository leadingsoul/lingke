<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { evaluateApi, orderApi } from '@/api'
import type { OrderDetail } from '@/types'
import { showToast, showLoadingToast, closeToast } from 'vant'

const route = useRoute()
const router = useRouter()
const orderId = route.params.orderId as string

const productRating = ref(5)
const logisticsRating = ref(4)
const serviceRating = ref(5)
const content = ref('')
const isAnonymous = ref(false)
const imageFiles = ref<any[]>([])

const order = ref<OrderDetail | null>(null)

onMounted(async () => {
  try { order.value = await orderApi.detail(orderId) }
  catch { /* ignore */ }
})

const dimensions = [
  { label: '商品质量', key: 'product', ref: productRating },
  { label: '物流速度', key: 'logistics', ref: logisticsRating },
  { label: '客服态度', key: 'service', ref: serviceRating },
]

async function handleSubmit() {
  showLoadingToast({ message: '提交中...', forbidClick: true })
  try {
    const urls = imageFiles.value.map((f: any) => f.url || f.content || '')
    await evaluateApi.submit({
      order_id: orderId,
      product_rating: productRating.value,
      logistics_rating: logisticsRating.value,
      service_rating: serviceRating.value,
      content: content.value,
      image_urls: urls,
      is_anonymous: isAnonymous.value,
    })
    closeToast()
    showToast('评价提交成功！感谢您的反馈 ❤️')
    router.replace('/evaluate')
  } catch { closeToast() }
}
</script>

<template>
  <div class="submit-page">
    <!-- ═══ Header ═══ -->
    <div class="detail-header">
      <button class="detail-back" @click="router.push('/evaluate')">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
      </button>
      <span class="detail-header-title">发布评价</span>
      <span style="width:36px;"></span>
    </div>

    <div class="page" style="padding-bottom:40px;">
      <!-- ═══ Product Card ═══ -->
      <div v-if="order" class="submit-product-card">
        <img v-if="(order as any).product_image" :src="(order as any).product_image" class="submit-pimg" alt="" />
        <span v-else class="submit-pfallback">📦</span>
        <div class="submit-pinfo">
          <div class="submit-pname text-ellipsis">{{ order.product_name }}</div>
          <div class="submit-pspec" v-if="order.product_spec">{{ order.product_spec }}</div>
          <div class="submit-pprice">¥{{ Number(order.total_amount).toFixed(2) }}</div>
        </div>
      </div>

      <!-- ═══ Rating Dimensions ═══ -->
      <div class="rate-card">
        <div class="rate-card-title">评分</div>
        <div class="rate-dims">
          <div class="rate-dim" v-for="dim in dimensions" :key="dim.key">
            <div class="rate-dim-label">{{ dim.label }}</div>
            <div class="rate-dim-stars">
              <span
                v-for="n in 5"
                :key="n"
                class="star-interactive"
                :class="{ on: n <= dim.ref.value }"
                @click="dim.ref.value = n"
              >{{ n <= dim.ref.value ? '★' : '☆' }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ Content ═══ -->
      <div class="rate-card">
        <div class="rate-card-title">评价内容</div>
        <textarea
          v-model="content"
          class="submit-textarea"
          placeholder="分享您的使用体验，帮助更多小伙伴..."
          maxlength="300"
        ></textarea>
        <div class="submit-charcount">{{ content.length }}/300</div>
      </div>

      <!-- ═══ Upload ═══ -->
      <div class="rate-card">
        <div class="rate-card-title">实拍图片</div>
        <van-uploader
          v-model="imageFiles"
          :max-count="9"
          :max-size="5 * 1024 * 1024"
          accept="image/*"
          multiple
        />
      </div>

      <!-- ═══ Anonymous ═══ -->
      <div class="anon-toggle" @click="isAnonymous = !isAnonymous">
        <div class="anon-check" :class="{ on: isAnonymous }">
          <svg v-if="isAnonymous" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
        </div>
        <span class="anon-label">匿名发布评价</span>
      </div>

      <!-- ═══ Submit ═══ -->
      <button class="btn btn-primary btn-block" style="margin-top:var(--space-lg);" @click="handleSubmit">发布评价</button>
    </div>
  </div>
</template>

<style scoped>
.submit-page { min-height: 100dvh; background: var(--bg-page); }

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

/* ═══ Product ═══ */
.submit-product-card {
  display: flex; gap: 12px; align-items: center;
  padding: 14px; background: #fff; border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs); border: 1px solid var(--border-light);
  margin-bottom: var(--space-md);
}
.submit-pimg {
  width: 72px; height: 72px; border-radius: var(--radius-md); object-fit: cover; flex-shrink: 0;
}
.submit-pfallback {
  width: 72px; height: 72px; border-radius: var(--radius-md); flex-shrink: 0;
  background: var(--bg-input); display: flex; align-items: center; justify-content: center; font-size: 28px;
}
.submit-pinfo { flex: 1; min-width: 0; }
.submit-pname { font-size: var(--text-base); font-weight: 600; color: var(--text); }
.submit-pspec { font-size: var(--text-xs); color: var(--text-tertiary); margin-top: 2px; }
.submit-pprice { font-size: var(--text-lg); font-weight: 800; color: var(--red); letter-spacing: -0.02em; }

/* ═══ Rate Card ═══ */
.rate-card {
  background: #fff; border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xs); border: 1px solid var(--border-light);
  padding: 18px; margin-bottom: var(--space-md);
}
.rate-card-title {
  font-size: var(--text-xs); font-weight: 600; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 14px;
}

/* Dimensions */
.rate-dims { display: flex; flex-direction: column; gap: 12px; }
.rate-dim {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 14px; background: var(--bg-input); border-radius: var(--radius-md);
}
.rate-dim-label { font-size: var(--text-sm); font-weight: 500; color: var(--text); min-width: 70px; }
.rate-dim-stars { display: flex; gap: 2px; font-size: 30px; }

/* Textarea */
.submit-textarea {
  width: 100%; min-height: 120px; border: 1px solid var(--border-light);
  border-radius: var(--radius-md); padding: 14px 16px;
  font-size: var(--text-base); line-height: 1.6; resize: vertical;
  font-family: inherit; background: #fff; outline: none; box-sizing: border-box;
  transition: border-color 0.3s ease;
}
.submit-textarea:focus { border-color: var(--border-focus); }
.submit-charcount {
  text-align: right; font-size: var(--text-xs); color: var(--text-tertiary);
  margin-top: 4px;
}

/* Anonymous toggle */
.anon-toggle {
  display: flex; align-items: center; gap: 10px; cursor: pointer; padding: 4px 0;
}
.anon-check {
  width: 22px; height: 22px; border-radius: 6px;
  border: 1.5px solid var(--border); display: flex;
  align-items: center; justify-content: center;
  transition: all 0.2s ease; color: transparent;
}
.anon-check.on { background: var(--primary); border-color: var(--primary); color: #fff; }
.anon-label { font-size: var(--text-sm); color: var(--text-secondary); }
</style>

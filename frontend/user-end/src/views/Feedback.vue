<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { feedbackApi } from '@/api'
import { showToast, showLoadingToast, closeToast } from 'vant'

const router = useRouter()

const content = ref('')
const satisfaction = ref(0)
const canSubmit = computed(() => content.value.trim().length >= 5)

const emojis = [
  { val: 1, emoji: '😫', label: '很差' },
  { val: 2, emoji: '😕', label: '较差' },
  { val: 3, emoji: '😐', label: '一般' },
  { val: 4, emoji: '😊', label: '满意' },
  { val: 5, emoji: '🥰', label: '很棒' },
]

async function handleSubmit() {
  if (!canSubmit.value) return
  showLoadingToast({ message: '提交中...', forbidClick: true })
  try { await feedbackApi.submit(content.value); closeToast(); showToast('感谢您的反馈！'); router.push('/profile') }
  catch { closeToast() }
}
</script>

<template>
  <div class="feedback-page">
    <!-- ═══ Header ═══ -->
    <div class="detail-header">
      <button class="detail-back" @click="router.push('/profile')">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
      </button>
      <span class="detail-header-title">意见反馈</span>
      <span style="width:36px;"></span>
    </div>

    <div class="page" style="padding-bottom:40px;">
      <!-- ═══ Hero ═══ -->
      <div class="feedback-hero">
        <div class="feedback-hero-icon">💬</div>
        <div class="feedback-hero-title">我们倾听每一个声音</div>
        <div class="feedback-hero-sub">您的反馈将帮助我们变得更好</div>
      </div>

      <!-- ═══ Satisfaction ═══ -->
      <div class="feedback-section">
        <div class="feedback-section-label">整体满意度</div>
        <div class="satisfaction-row">
          <div
            v-for="e in emojis"
            :key="e.val"
            class="satisfaction-item"
            :class="{ active: satisfaction === e.val }"
            @click="satisfaction = e.val"
          >
            <span class="satisfaction-emoji">{{ e.emoji }}</span>
            <span class="satisfaction-label">{{ e.label }}</span>
          </div>
        </div>
      </div>

      <!-- ═══ Text input ═══ -->
      <div class="feedback-section">
        <div class="feedback-section-label">问题或建议</div>
        <textarea
          v-model="content"
          class="feedback-textarea"
          placeholder="请详细描述您遇到的问题或建议（至少5个字）"
          maxlength="500"
        ></textarea>
        <div class="feedback-charcount">{{ content.length }}/500</div>
      </div>

      <!-- ═══ Submit ═══ -->
      <button
        class="btn btn-primary btn-block"
        :disabled="!canSubmit"
        @click="handleSubmit"
      >提交反馈</button>
    </div>
  </div>
</template>

<style scoped>
.feedback-page { min-height: 100dvh; background: var(--bg-page); }

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

/* ═══ Hero ═══ */
.feedback-hero { text-align: center; padding: 32px 0 24px; }
.feedback-hero-icon { font-size: 48px; margin-bottom: 12px; }
.feedback-hero-title { font-size: var(--text-2xl); font-weight: 800; color: var(--text); letter-spacing: -0.02em; }
.feedback-hero-sub { font-size: var(--text-sm); color: var(--text-tertiary); margin-top: 6px; }

/* ═══ Section ═══ */
.feedback-section { margin-bottom: var(--space-lg); }
.feedback-section-label {
  font-size: var(--text-xs); font-weight: 600; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px;
}

/* Satisfaction */
.satisfaction-row { display: flex; gap: 8px; justify-content: center; }
.satisfaction-item {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  cursor: pointer; padding: 12px 16px; border-radius: var(--radius-md);
  background: #fff; border: 1.5px solid var(--border-light);
  transition: all 0.3s var(--ease-out-expo);
}
.satisfaction-item.active {
  border-color: var(--primary); background: rgba(13,148,136,0.04);
  box-shadow: 0 0 0 3px rgba(13,148,136,0.06);
}
.satisfaction-item:active { transform: scale(0.93); }
.satisfaction-emoji { font-size: 28px; }
.satisfaction-label { font-size: 10px; color: var(--text-tertiary); font-weight: 500; }

/* Textarea */
.feedback-textarea {
  width: 100%; min-height: 140px; border: 1px solid var(--border-light);
  border-radius: var(--radius-md); padding: 14px 16px;
  font-size: var(--text-base); line-height: 1.7; resize: vertical;
  font-family: inherit; background: #fff; outline: none; box-sizing: border-box;
  transition: border-color 0.3s ease;
}
.feedback-textarea:focus { border-color: var(--border-focus); }
.feedback-charcount { text-align: right; font-size: var(--text-xs); color: var(--text-tertiary); margin-top: 4px; }
</style>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { userApi } from '@/api'
import { showToast } from 'vant'

const router = useRouter()
const userStore = useUserStore()
const nickname = ref('')
const submitting = ref(false)

onMounted(() => {
  if (userStore.userInfo) nickname.value = userStore.userInfo.nickname || ''
})

async function handleSave() {
  if (!nickname.value.trim()) { showToast('请输入昵称'); return }
  submitting.value = true
  try {
    await userApi.updateProfile({ nickname: nickname.value.trim() })
    await userStore.fetchMe()
    showToast('保存成功')
    router.push('/profile')
  } catch { /* */ }
  finally { submitting.value = false }
}

function avatarChar(): string {
  const name = userStore.userInfo?.nickname || '用'
  return name.charAt(0)
}
</script>

<template>
  <div class="edit-page">
    <!-- ═══ Header ═══ -->
    <div class="detail-header">
      <button class="detail-back" @click="router.push('/profile')">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
      </button>
      <span class="detail-header-title">编辑资料</span>
      <button class="detail-save" :disabled="submitting" @click="handleSave">
        {{ submitting ? '保存中...' : '保存' }}
      </button>
    </div>

    <div class="page" style="padding-bottom:40px;">
      <!-- ═══ Avatar ═══ -->
      <div class="edit-avatar-section">
        <div class="edit-avatar" @click="showToast('暂不支持更换头像')">
          <span class="edit-avatar-char">{{ avatarChar() }}</span>
          <div class="edit-avatar-overlay">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
              <circle cx="12" cy="13" r="4"></circle>
            </svg>
          </div>
        </div>
        <div class="edit-avatar-label">点击更换头像</div>
      </div>

      <!-- ═══ Form ═══ -->
      <div class="info-card">
        <div class="info-card-title">基本信息</div>
        <div class="info-card-body">
          <div class="info-row edit-row">
            <span class="info-row-key">昵称</span>
            <input
              v-model="nickname"
              type="text"
              placeholder="请输入昵称"
              maxlength="16"
              class="edit-input"
            />
          </div>
          <div class="info-row">
            <span class="info-row-key">手机号</span>
            <span class="info-row-val">
              {{ userStore.userInfo?.phone ? userStore.userInfo.phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2') : '未绑定' }}
            </span>
          </div>
        </div>
      </div>

      <div class="info-card">
        <div class="info-card-title">平台关联</div>
        <div class="info-card-body">
          <div class="info-row">
            <span class="info-row-key">淘宝账号</span>
            <span class="info-row-val" :class="{ bound: userStore.userInfo?.platform_account }">
              {{ userStore.userInfo?.platform_account || '未关联' }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.edit-page { min-height: 100dvh; background: var(--bg-page); }

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
.detail-save {
  border: none; background: none; font-size: var(--text-sm); font-weight: 700;
  color: var(--primary); cursor: pointer; padding: 8px 4px; font-family: inherit;
  transition: opacity 0.2s ease;
}
.detail-save:disabled { opacity: 0.4; cursor: not-allowed; }
.detail-save:active:not(:disabled) { opacity: 0.6; }

/* ═══ Avatar ═══ */
.edit-avatar-section {
  display: flex; flex-direction: column; align-items: center;
  padding: 28px 0 24px; gap: 10px;
}
.edit-avatar {
  width: 88px; height: 88px; border-radius: 50%;
  background: var(--brand-gradient); position: relative; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 20px rgba(13,148,136,0.25);
  transition: transform 0.3s var(--ease-out-expo);
}
.edit-avatar:active { transform: scale(0.94); }
.edit-avatar-char { font-size: 38px; font-weight: 800; color: #fff; }
.edit-avatar-overlay {
  position: absolute; inset: 0; border-radius: 50%;
  background: rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;
  opacity: 0; transition: opacity 0.3s ease; color: #fff;
}
.edit-avatar:hover .edit-avatar-overlay { opacity: 1; }
.edit-avatar-label { font-size: var(--text-xs); color: var(--text-tertiary); }

/* ═══ Info Card ═══ */
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
  padding: 10px 0; border-bottom: 1px solid rgba(0,0,0,0.03);
}
.info-row:last-child { border-bottom: none; }
.info-row-key { font-size: var(--text-sm); color: var(--text-secondary); flex-shrink: 0; }
.info-row-val { font-size: var(--text-sm); color: var(--text); font-weight: 500; }
.info-row-val.bound { color: var(--green); }

.edit-row { padding: 10px 0; }
.edit-input {
  border: none; text-align: right; font-size: var(--text-sm); color: var(--text);
  outline: none; background: transparent; font-family: inherit;
  width: 200px; font-weight: 500;
}
.edit-input::placeholder { color: var(--text-tertiary); font-weight: 400; }
</style>

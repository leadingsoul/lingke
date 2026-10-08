<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { showToast, showLoadingToast, closeToast } from 'vant'

const router = useRouter()
const userStore = useUserStore()

const loginMode = ref<'password' | 'wechat'>('password')
const username = ref('')
const password = ref('')
const loading = ref(false)
const mounted = ref(false)

onMounted(() => {
  requestAnimationFrame(() => { mounted.value = true })
})

async function handlePasswordLogin() {
  if (!username.value.trim()) { showToast('请输入用户名'); return }
  if (!password.value) { showToast('请输入密码'); return }

  loading.value = true
  showLoadingToast({ message: '登录中...', forbidClick: true })
  try {
    await userStore.login(username.value.trim(), password.value)
    closeToast()
    showToast('登录成功')
    router.replace('/home')
  } catch {
    closeToast()
    showToast('用户名或密码错误')
  } finally {
    loading.value = false
  }
}

async function handleWechatLogin() {
  showLoadingToast({ message: '授权登录中...', forbidClick: true })
  try {
    await userStore.wechatLogin('mock_wx_code')
    closeToast()
    showToast('登录成功')
    router.replace('/home')
  } catch {
    closeToast()
    showToast('授权失败，请重试')
  }
}
</script>

<template>
  <div class="login-page" :class="{ mounted }">
    <!-- Soft ambient glows -->
    <div class="bg-orb bg-orb-1" />
    <div class="bg-orb bg-orb-2" />

    <!-- Double-Bezel card -->
    <div class="card-shell">
      <div class="card-core">
        <!-- Logo mark -->
        <div class="logo-mark">
          <span class="logo-icon">🎧</span>
        </div>

        <h1 class="brand-title">聆客</h1>
        <p class="brand-sub">AI 驱动 · 智能售后 · 聆听每一份声音</p>

        <!-- Tab switcher -->
        <div class="tab-row">
          <button
            :class="['tab-pill', { active: loginMode === 'password' }]"
            @click="loginMode = 'password'"
          >账号登录</button>
          <button
            :class="['tab-pill', { active: loginMode === 'wechat' }]"
            @click="loginMode = 'wechat'"
          >微信登录</button>
        </div>

        <!-- Password form -->
        <form v-if="loginMode === 'password'" class="login-form" @submit.prevent="handlePasswordLogin">
          <div class="input-shell">
            <input
              v-model="username"
              type="text"
              placeholder="用户名"
              class="glass-input"
              autocomplete="username"
            />
          </div>
          <div class="input-shell">
            <input
              v-model="password"
              type="password"
              placeholder="密码"
              class="glass-input"
              autocomplete="current-password"
            />
          </div>
          <button
            type="submit"
            class="btn-primary"
            :disabled="loading"
          >
            <span>{{ loading ? '登录中...' : '登 录' }}</span>
            <span class="btn-arrow-nest">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
            </span>
          </button>
        </form>

        <!-- Wechat login -->
        <button v-else class="wechat-btn" @click="handleWechatLogin">
          <span class="wechat-icon">💬</span>
          <span>微信一键登录</span>
        </button>

        <p class="agreement">
          登录即表示同意 <a href="javascript:;">《用户协议》</a>和<a href="javascript:;">《隐私政策》</a>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ═══════════ RESET & BASE ═══════════ */
.login-page {
  min-height: 100dvh;
  background: #FDFBF7;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  font-family: "Plus Jakarta Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
}

/* ── Subtle grain ── */
.login-page::after {
  content: '';
  position: fixed; inset: 0; z-index: 100; pointer-events: none; opacity: 0.025;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-size: 256px 256px;
}

/* ── Soft ambient orbs ── */
.bg-orb { position: fixed; border-radius: 50%; filter: blur(140px); pointer-events: none; z-index: 0; }
.bg-orb-1 { width: 420px; height: 420px; top: -160px; right: -100px; background: radial-gradient(circle, rgba(20,184,166,0.12), transparent 70%); }
.bg-orb-2 { width: 360px; height: 360px; bottom: -140px; left: -100px; background: radial-gradient(circle, rgba(59,130,246,0.08), transparent 70%); }

/* ═══════════ DOUBLE-BEZEL CARD ═══════════ */
.card-shell {
  position: relative; z-index: 1;
  width: 86vw; max-width: 340px;
  border-radius: 28px;
  padding: 1px;
  background: linear-gradient(135deg, rgba(0,0,0,0.06), rgba(0,0,0,0.02));
  box-shadow: 0 8px 60px rgba(0,0,0,0.06), 0 2px 12px rgba(0,0,0,0.04);
  opacity: 0; transform: translateY(24px); filter: blur(4px);
  transition: all 0.9s cubic-bezier(0.32,0.72,0,1);
}
.mounted .card-shell { opacity: 1; transform: translateY(0); filter: blur(0); }

.card-core {
  border-radius: 24px;
  padding: 2.4rem 1.6rem 2rem;
  background: rgba(255,255,255,0.88);
  backdrop-filter: blur(40px);
  -webkit-backdrop-filter: blur(40px);
  border: 1px solid rgba(0,0,0,0.05);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.8);
  display: flex; flex-direction: column; align-items: center;
}

/* ═══════════ LOGO ═══════════ */
.logo-mark {
  width: 64px; height: 64px; margin-bottom: 1rem;
  border-radius: 18px; display: flex; align-items: center; justify-content: center;
  background: rgba(20,184,166,0.08);
  border: 1px solid rgba(20,184,166,0.15);
  opacity: 0; transform: scale(0.8);
  transition: all 0.7s cubic-bezier(0.32,0.72,0,1) 0.15s;
}
.mounted .logo-mark { opacity: 1; transform: scale(1); }
.logo-icon { font-size: 28px; }

/* ═══════════ TYPOGRAPHY ═══════════ */
.brand-title {
  font-size: 1.5rem; font-weight: 800; letter-spacing: -0.02em;
  background: linear-gradient(135deg, #0D9488, #2563EB);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  margin: 0 0 0.3rem;
  opacity: 0; transform: translateY(8px);
  transition: all 0.7s cubic-bezier(0.32,0.72,0,1) 0.25s;
}
.mounted .brand-title { opacity: 1; transform: translateY(0); }

.brand-sub {
  font-size: 0.78rem; color: rgba(0,0,0,0.35); margin: 0 0 1.5rem;
  opacity: 0; transition: opacity 0.7s ease 0.35s;
}
.mounted .brand-sub { opacity: 1; }

/* ═══════════ TAB SWITCHER ═══════════ */
.tab-row {
  display: flex; gap: 4px; margin-bottom: 1.25rem;
  background: rgba(0,0,0,0.04); border-radius: 9999px; padding: 3px;
  opacity: 0; transition: opacity 0.7s ease 0.45s;
}
.mounted .tab-row { opacity: 1; }

.tab-pill {
  border: none; background: transparent; color: rgba(0,0,0,0.4);
  font-size: 0.8rem; font-weight: 500; padding: 7px 18px; border-radius: 9999px;
  cursor: pointer; transition: all 0.6s cubic-bezier(0.32,0.72,0,1);
  font-family: inherit;
}
.tab-pill.active {
  background: #fff; color: #1a1a1a; font-weight: 600;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
.tab-pill:active { transform: scale(0.96); }

/* ═══════════ FORM INPUTS ═══════════ */
.login-form {
  width: 100%; display: flex; flex-direction: column; gap: 10px;
  opacity: 0; transition: opacity 0.7s ease 0.55s;
}
.mounted .login-form { opacity: 1; }

.input-shell {
  border-radius: 14px; padding: 1px;
  background: linear-gradient(135deg, rgba(0,0,0,0.06), rgba(0,0,0,0.02));
  transition: all 0.5s cubic-bezier(0.32,0.72,0,1);
}
.input-shell:focus-within {
  background: linear-gradient(135deg, rgba(20,184,166,0.35), rgba(59,130,246,0.25));
  box-shadow: 0 0 0 4px rgba(20,184,166,0.06);
}

.glass-input {
  width: 100%; padding: 12px 16px; border: none; border-radius: 13px;
  background: rgba(0,0,0,0.03); color: #1a1a1a; font-size: 0.9rem;
  outline: none; box-sizing: border-box; font-family: inherit;
  transition: background 0.4s ease;
}
.glass-input::placeholder { color: rgba(0,0,0,0.25); }
.glass-input:-webkit-autofill {
  -webkit-box-shadow: 0 0 0 30px #fff inset !important;
  -webkit-text-fill-color: #1a1a1a !important;
}

/* ═══════════ BUTTON-IN-BUTTON CTA ═══════════ */
.btn-primary {
  display: inline-flex; align-items: center; justify-content: center; gap: 10px;
  width: 100%; padding: 13px 20px; border-radius: 9999px; border: none;
  background: linear-gradient(135deg, #0D9488, #2563EB);
  color: #fff; font-size: 0.95rem; font-weight: 700; cursor: pointer;
  font-family: inherit; margin-top: 4px;
  box-shadow: 0 4px 20px rgba(13,148,136,0.25);
  transition: all 0.7s cubic-bezier(0.32,0.72,0,1);
}
.btn-primary:active:not(:disabled) { transform: scale(0.97); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; animation: btn-pulse 1.5s ease-in-out infinite; }
@keyframes btn-pulse { 0%,100%{opacity:0.6} 50%{opacity:0.4} }

.btn-arrow-nest {
  width: 26px; height: 26px; border-radius: 50%;
  background: rgba(255,255,255,0.25); display: inline-flex; align-items: center; justify-content: center;
  transition: transform 0.5s cubic-bezier(0.32,0.72,0,1);
  flex-shrink: 0; color: #fff;
}
.btn-primary:active:not(:disabled) .btn-arrow-nest {
  transform: translateX(3px) translateY(-1px) scale(1.05);
}

/* ═══════════ WECHAT BUTTON ═══════════ */
.wechat-btn {
  width: 100%; display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 14px; border-radius: 9999px; border: 1px solid rgba(7,193,96,0.25);
  background: rgba(7,193,96,0.06); color: #07C160; font-size: 0.95rem; font-weight: 600;
  cursor: pointer; transition: all 0.7s cubic-bezier(0.32,0.72,0,1);
  font-family: inherit;
  opacity: 0; transition: opacity 0.7s ease 0.55s, background 0.7s cubic-bezier(0.32,0.72,0,1);
}
.mounted .wechat-btn { opacity: 1; }
.wechat-btn:active { transform: scale(0.97); background: rgba(7,193,96,0.14); }
.wechat-icon { font-size: 1.2rem; }

/* ═══════════ AGREEMENT ═══════════ */
.agreement {
  font-size: 0.68rem; color: rgba(0,0,0,0.25); text-align: center;
  margin: 1rem 0 0;
  opacity: 0; transition: opacity 0.7s ease 0.65s;
}
.mounted .agreement { opacity: 1; }
.agreement a { color: #0D9488; text-decoration: none; }
</style>

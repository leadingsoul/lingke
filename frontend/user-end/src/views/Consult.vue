<script setup lang="ts">
import { ref, computed, onMounted, onActivated, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { chatApi, orderApi } from '@/api'
import type { ChatMessage, Order } from '@/types'
import { showToast, showLoadingToast, closeToast } from 'vant'
import { useWebSocket } from '@/composables/useWebSocket'
import { marked } from 'marked'

// ====== 扩展消息类型（UI 状态） ======
interface UIMessage extends ChatMessage {
  _status?: 'sent' | 'sending' | 'error'
  _retryContent?: string
}

// ====== 文件预览条目（选择后未发送） ======
interface PendingFile {
  file: File
  objectUrl: string    // 本地 blob URL 供预览
  type: 'image' | 'video' | 'document'
  ext: string
}

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const sessionIdParam = computed(() => (route.params.sessionId as string) || '')
const orderId = computed(() => (route.query.orderId as string) || '')
const ws = useWebSocket()

// ====== 响应式状态 ======
const order = ref<Order | null>(null)
const messages = ref<UIMessage[]>([])
const inputText = ref('')
const sending = ref(false)
const chatBody = ref<HTMLElement>()
const sessionId = ref('')
const suggestions = ref<string[]>([])
const showRating = ref(false)
const starRating = ref(0)
const ratingFeedback = ref('')
const ratingSubmitting = ref(false)
const ratingDone = ref(false)

// ====== 文件上传相关 ======
const pendingFiles = ref<PendingFile[]>([])
const uploadingFiles = ref(false)
const fileInput = ref<HTMLInputElement>()

/** 根据扩展名判断文件类型大类 */
function classifyFile(ext: string): 'image' | 'video' | 'document' {
  const images = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'])
  const videos = new Set(['mp4', 'mov', 'webm', 'avi'])
  if (images.has(ext)) return 'image'
  if (videos.has(ext)) return 'video'
  return 'document'
}

/** 获取文件类型图标 */
function fileIcon(ext: string): string {
  const map: Record<string, string> = {
    pdf: '📄', doc: '📝', docx: '📝', xls: '📊', xlsx: '📊',
    ppt: '📽️', pptx: '📽️', txt: '📃', md: '📃', csv: '📊',
    zip: '📦', rar: '📦',
  }
  return map[ext] || '📎'
}

/** 从 URL 判断是否为图片 */
function isImageUrl(url: string): boolean {
  const ext = url.split('.').pop()?.split('?')[0]?.toLowerCase() || ''
  return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'].includes(ext)
}

/** 从 URL 判断是否为视频 */
function isVideoUrl(url: string): boolean {
  const ext = url.split('.').pop()?.split('?')[0]?.toLowerCase() || ''
  return ['mp4', 'mov', 'webm', 'avi'].includes(ext)
}

/** 打开文件选择器 */
function triggerFilePicker() { fileInput.value?.click() }

/** 文件被选中后加入待发送列表 */
function handleFilesSelected(e: Event) {
  const input = e.target as HTMLInputElement
  const files = input.files
  if (!files || files.length === 0) return
  for (let i = 0; i < files.length; i++) {
    const f = files[i]
    const ext = f.name.split('.').pop()?.toLowerCase() || ''
    const type = classifyFile(ext)
    const objectUrl = URL.createObjectURL(f)
    pendingFiles.value.push({ file: f, objectUrl, type, ext })
  }
  input.value = '' // 允许重复选同一文件
}

/** 移除待发送文件 */
function removePendingFile(index: number) {
  const pf = pendingFiles.value[index]
  if (pf) URL.revokeObjectURL(pf.objectUrl)
  pendingFiles.value.splice(index, 1)
}

/** 在新标签页打开 URL */
function openUrl(url: string) { window.open(url, '_blank') }

// ====== 持久化 ======
function saveSessionId(id: string) {
  sessionId.value = id
}

// ====== Markdown 渲染 ======
function renderMarkdown(text: string): string {
  if (!text) return ''
  try {
    return marked.parse(text, { breaks: true, gfm: true }) as string
  } catch {
    return text
  }
}

// ====== 时间格式化 ======
function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return `${hh}:${mm}`
  } catch { return '' }
}

// ====== 滚动到底部 ======
async function scrollToBottom() {
  await nextTick()
  if (chatBody.value) {
    chatBody.value.scrollTop = chatBody.value.scrollHeight
  }
}

// ====== WebSocket: 实时接收 CS 消息 ======
ws.on('new_message', (data: any) => {
  if (data.conversation_id && data.conversation_id !== sessionId.value) return
  if (!data.sender_type || !data.content) return
  if (data.sender_type === 'consumer') return
  const newMsg: UIMessage = {
    id: data.id || `ws_${Date.now()}`,
    conversation_id: data.conversation_id || sessionId.value,
    sender_type: data.sender_type,
    content: data.content,
    created_at: data.created_at || new Date().toISOString(),
    _status: 'sent',
  }
  const dup = messages.value.some(
    (m) => m.sender_type === newMsg.sender_type && m.content === newMsg.content
      && Math.abs(Date.now() - new Date(m.created_at).getTime()) < 5000,
  )
  if (!dup) {
    messages.value.push(newMsg)
    scrollToBottom()
  }
})

// ====== WebSocket: 会话状态变更 ======
ws.on('conversation_update', (data: any) => {
  if (data.conversation_id !== sessionId.value) return
  if (data.status === '已关闭') {
    messages.value.push({
      id: `sys_${Date.now()}`,
      conversation_id: sessionId.value,
      sender_type: 'system',
      content: '客服已关闭本次会话，如有其他问题请重新发起咨询。',
      created_at: new Date().toISOString(),
      _status: 'sent',
    })
    scrollToBottom()
    if (!ratingDone.value) { showRating.value = true }
  }
})

// ====== 发送消息 ======
async function doSend(content: string) {
  const hasFiles = pendingFiles.value.length > 0
  if ((!content.trim() && !hasFiles) || sending.value) return

  // 先上传所有待发送文件
  let uploadedUrls: string[] = []
  if (hasFiles) {
    uploadingFiles.value = true
    try {
      for (const pf of pendingFiles.value) {
        const res = await chatApi.uploadFile(pf.file)
        uploadedUrls.push(res.url)
      }
    } catch (err) {
      console.error('[Consult] 文件上传失败:', err)
      // 响应拦截器已弹 toast，这里不再重复弹，只重置状态
      uploadingFiles.value = false
      return
    }
    uploadingFiles.value = false
  }

  const tempId = `u_${Date.now()}`
  const userMsg: UIMessage = {
    id: tempId,
    conversation_id: sessionId.value,
    sender_type: 'consumer',
    content: content || '',
    image_urls: uploadedUrls.length > 0 ? uploadedUrls : undefined,
    created_at: new Date().toISOString(),
    _status: 'sending',
    _retryContent: content,
  }
  messages.value.push(userMsg)

  // 清理待发送文件列表
  pendingFiles.value.forEach(pf => URL.revokeObjectURL(pf.objectUrl))
  pendingFiles.value = []
  inputText.value = ''
  suggestions.value = []
  sending.value = true
  scrollToBottom()
  try {
    const res = await chatApi.sendMessage(
      sessionId.value || undefined, content || '', orderId.value || undefined,
      uploadedUrls.length > 0 ? uploadedUrls : undefined,
    )
    if (!sessionId.value && res.session_id) {
      saveSessionId(res.session_id)
      userMsg.conversation_id = res.session_id
    }
    userMsg._status = 'sent'
    if (res.message_id) userMsg.id = res.message_id
    if (res.ai_reply) {
      messages.value.push({
        id: `ai_${Date.now()}`,
        conversation_id: sessionId.value,
        sender_type: res.is_transferred ? 'system' : 'ai',
        content: res.ai_reply,
        created_at: new Date().toISOString(),
        _status: 'sent',
      })
    }
    if (res.suggestions && res.suggestions.length > 0) {
      suggestions.value = res.suggestions
    }
  } catch (err) {
    console.error('[Consult] 发送消息失败:', err)
    userMsg._status = 'error'
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

function handleSend() { doSend(inputText.value) }

async function handleRetry(msg: UIMessage) {
  const content = msg._retryContent || msg.content
  const idx = messages.value.indexOf(msg)
  if (idx > -1) messages.value.splice(idx, 1)
  await doSend(content)
}

function handleSuggestion(text: string) { inputText.value = text; doSend(text) }

async function handleTransfer() {
  if (!sessionId.value) { showToast('请先发送消息'); return }
  try {
    await chatApi.transferToHuman(sessionId.value)
    messages.value.push({
      id: `sys_${Date.now()}`,
      conversation_id: sessionId.value,
      sender_type: 'system',
      content: '正在为您转接人工客服，请稍候...⏳',
      created_at: new Date().toISOString(),
      _status: 'sent',
    })
    suggestions.value = []
    scrollToBottom()
  } catch { showToast('转接失败，请重试') }
}

// ====== 删除会话 ======
const showDeleteDialog = ref(false)
const deleting = ref(false)
function openDeleteDialog() { if (!sessionId.value) return; showDeleteDialog.value = true }
async function confirmDelete() {
  if (!sessionId.value) return
  deleting.value = true
  try {
    await chatApi.deleteSession(sessionId.value)
    showDeleteDialog.value = false; showToast('已删除'); router.back()
  } catch { showDeleteDialog.value = false; showToast('删除失败，请重试') }
  finally { deleting.value = false }
}

// ====== 满意度评分 ======
function handleSetRating(n: number) { starRating.value = n }
async function submitRating() {
  if (starRating.value < 1 || starRating.value > 5) { showToast('请先选择星级'); return }
  ratingSubmitting.value = true
  try {
    await chatApi.rateConversation(sessionId.value, starRating.value, ratingFeedback.value || undefined)
    showToast('感谢您的评价！')
    ratingDone.value = true; showRating.value = false
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '评分失败，请稍后重试'
    showToast(msg)
  } finally { ratingSubmitting.value = false }
}

// ====== 初始化 ======
onMounted(async () => {
  if (!userStore.isLoggedIn) { router.replace('/login'); return }
  userStore.restoreLogin()
  if (orderId.value) {
    try { order.value = await orderApi.detail(orderId.value) } catch { /* ignore */ }
  }
  if (sessionIdParam.value === 'new') {
    const oid = orderId.value
    try {
      const result = await chatApi.createConversation(oid || undefined)
      router.replace(`/consult/${result.session_id}${oid ? `?orderId=${oid}` : ''}`)
    } catch { showToast('创建会话失败') }
    return
  }
  if (sessionIdParam.value) {
    sessionId.value = sessionIdParam.value
    _lastKey.value = `${sessionIdParam.value}_${orderId.value || ''}`
    try {
      const res = await chatApi.getHistory(sessionIdParam.value, 1, 50)
      if (res.items && res.items.length > 0) {
        messages.value = res.items.map((m: ChatMessage) => ({ ...m, _status: 'sent' as const }))
        const alreadyClosed = messages.value.some(
          m => m.sender_type === 'system' && m.content.includes('客服已关闭'),
        )
        if (alreadyClosed && !ratingDone.value) { showRating.value = true }
      }
    } catch { showToast('会话不存在或已过期') }
  }
  scrollToBottom()
})

// ====== keep-alive 激活 ======
const _lastKey = ref('')
onActivated(async () => {
  const sid = (route.params.sessionId as string) || ''
  const oid = (route.query.orderId as string) || ''
  if (sid === 'new') {
    try {
      const result = await chatApi.createConversation(oid || undefined)
      router.replace(`/consult/${result.session_id}${oid ? `?orderId=${oid}` : ''}`)
    } catch { /* ignore */ }
    return
  }
  const currentKey = `${sid}_${oid}`
  if (currentKey !== _lastKey.value) {
    _lastKey.value = currentKey
    messages.value = []; suggestions.value = []; sessionId.value = sid
    if (oid) { try { order.value = await orderApi.detail(oid) } catch { /* ignore */ } }
    if (sid) {
      try {
        const res = await chatApi.getHistory(sid, 1, 50)
        if (res.items && res.items.length > 0) {
          messages.value = res.items.map((m: ChatMessage) => ({ ...m, _status: 'sent' as const }))
        }
      } catch { /* ignore */ }
    }
  } else if (sessionId.value) {
    try {
      const res = await chatApi.getHistory(sessionId.value, 1, 50)
      if (res.items && res.items.length > 0) {
        const existingIds = new Set(messages.value.map((m) => m.id))
        for (const m of res.items) {
          if (!existingIds.has(m.id)) { messages.value.push({ ...m, _status: 'sent' as const }) }
        }
      }
    } catch { /* ignore */ }
  }
  scrollToBottom()
})
</script>

<template>
  <div class="consult-page">
    <!-- ── Header ── -->
    <div class="chat-header">
      <button class="chat-back" @click="router.back()">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
      </button>
      <div class="chat-header-center">
        <span class="chat-header-name">
          {{ order?.product_name ? order.product_name.slice(0, 12) + (order.product_name.length > 12 ? '...' : '') : '智能咨询' }}
        </span>
        <span class="chat-header-status" :class="{ online: ws.isConnected.value }">
          <span class="status-dot" :class="ws.isConnected.value ? 'teal' : 'grey'"></span>
          {{ ws.isConnected.value ? '在线' : '离线' }}
        </span>
      </div>
      <button class="chat-header-action" @click="openDeleteDialog">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
          <path d="M10 11v6"></path><path d="M14 11v6"></path>
        </svg>
      </button>
    </div>

    <!-- ── Chat body ── -->
    <div ref="chatBody" class="chat-body">
      <template v-for="msg in messages" :key="msg.id">
        <!-- System message -->
        <div v-if="msg.sender_type === 'system'" class="chat-system-msg">
          <span>{{ msg.content }}</span>
        </div>

        <!-- User / AI / Staff bubble -->
        <div
          v-else
          :class="['chat-msg', msg.sender_type === 'consumer' ? 'msg-out' : 'msg-in']"
        >
          <!-- Avatar -->
          <div class="msg-avatar" :class="msg.sender_type === 'consumer' ? 'avatar-user' : 'avatar-ai'">
            {{ msg.sender_type === 'consumer' ? '我' : (msg.sender_type === 'staff' ? '服' : 'AI') }}
          </div>

          <!-- Bubble -->
          <div class="msg-bubble" :class="msg.sender_type === 'consumer' ? 'bubble-out' : 'bubble-in'">
            <div
              v-if="msg.sender_type === 'consumer'"
              class="bubble-text"
            >{{ msg.content }}</div>
            <div
              v-else
              class="bubble-text bubble-markdown"
              v-html="renderMarkdown(msg.content)"
            ></div>

            <!-- File attachments -->
            <div v-if="msg.image_urls && msg.image_urls.length > 0" class="bubble-files">
              <div v-for="(url, i) in msg.image_urls" :key="i" class="bubble-file-item">
                <!-- Image -->
                <img
                  v-if="isImageUrl(url)"
                  :src="url"
                  class="bubble-img"
                  @click="openUrl(url)"
                />
                <!-- Video -->
                <video
                  v-else-if="isVideoUrl(url)"
                  :src="url"
                  class="bubble-video"
                  controls
                  preload="metadata"
                ></video>
                <!-- Document -->
                <a v-else :href="url" target="_blank" class="bubble-doc-link">
                  <span class="bubble-doc-icon">{{ fileIcon(url.split('.').pop()?.split('?')[0] || '') }}</span>
                  <span class="bubble-doc-name">{{ decodeURIComponent(url.split('/').pop()?.split('?')[0] || url.split('/').pop() || '文件') }}</span>
                </a>
              </div>
            </div>

            <!-- Footer: time + status -->
            <div class="bubble-foot">
              <span class="bubble-time">{{ formatTime(msg.created_at) }}</span>
              <span v-if="msg._status === 'sending'" class="bubble-dot-pulse"></span>
              <template v-if="msg._status === 'error'">
                <span class="bubble-error-text">发送失败</span>
                <button class="bubble-retry" @click="handleRetry(msg)">重发</button>
              </template>
            </div>
          </div>
        </div>
      </template>

      <!-- Typing indicator -->
      <div v-if="sending" class="chat-msg msg-in">
        <div class="msg-avatar avatar-ai">AI</div>
        <div class="msg-bubble bubble-in typing-indicator">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      </div>
    </div>

    <!-- ── Rating card ── -->
    <div v-if="showRating" class="rating-sheet">
      <div class="rating-sheet-title">对本次服务满意吗？</div>
      <div class="rating-stars-row">
        <span
          v-for="n in 5" :key="n"
          class="star-interactive"
          :class="{ on: n <= starRating }"
          @click="handleSetRating(n)"
        >{{ n <= starRating ? '★' : '☆' }}</span>
      </div>
      <input
        v-model="ratingFeedback"
        class="rating-sheet-input"
        placeholder="说点什么吧（选填）"
        maxlength="200"
      />
      <button
        class="btn btn-primary btn-block"
        :disabled="ratingSubmitting || starRating < 1"
        @click="submitRating"
      >{{ ratingSubmitting ? '提交中...' : '提交评价' }}</button>
    </div>

    <!-- ── Suggestions ── -->
    <div v-if="suggestions.length > 0" class="suggest-strip">
      <span
        v-for="(s, i) in suggestions" :key="i"
        class="pill" style="cursor:pointer;"
        @click="handleSuggestion(s)"
      >{{ s }}</span>
    </div>

    <!-- ── File Preview ── -->
    <div v-if="pendingFiles.length > 0" class="file-preview-strip">
      <div
        v-for="(pf, i) in pendingFiles"
        :key="i"
        class="file-preview-item"
      >
        <!-- Image preview -->
        <img v-if="pf.type === 'image'" :src="pf.objectUrl" class="file-preview-thumb" />
        <!-- Video preview -->
        <video v-else-if="pf.type === 'video'" :src="pf.objectUrl" class="file-preview-thumb" muted />
        <!-- Document preview -->
        <span v-else class="file-preview-doc">
          <span class="file-preview-doc-icon">{{ fileIcon(pf.ext) }}</span>
          <span class="file-preview-doc-ext">.{{ pf.ext }}</span>
        </span>
        <span class="file-preview-remove" @click="removePendingFile(i)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10 10-4.47 10-10S17.53 2 12 2zm5 13.59L15.59 17 12 13.41 8.41 17 7 15.59 10.59 12 7 8.41 8.41 7 12 10.59 15.59 7 17 8.41 13.41 12 17 15.59z"/></svg>
        </span>
      </div>
      <!-- Uploading spinner -->
      <div v-if="uploadingFiles" class="file-preview-item file-uploading-overlay">
        <span class="file-uploading-spinner"></span>
      </div>
    </div>

    <!-- ── Transfer bar ── -->
    <div class="transfer-strip" v-if="!suggestions.length">
      <button class="btn btn-ghost btn-sm" @click="handleTransfer">转人工客服</button>
    </div>

    <!-- ── Input bar ── -->
    <div class="input-bar">
      <!-- File picker button -->
      <button
        class="attach-btn"
        :disabled="sending"
        @click="triggerFilePicker"
        title="添加文件"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/>
        </svg>
      </button>
      <div class="input-pill">
        <input
          v-model="inputText"
          type="text"
          placeholder="输入消息..."
          :disabled="sending"
          @keypress.enter="handleSend"
        />
      </div>
      <button
        class="send-btn"
        :disabled="sending || (!inputText.trim() && pendingFiles.length === 0)"
        @click="handleSend"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="22" y1="2" x2="11" y2="13"></line>
          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
        </svg>
      </button>
    </div>

    <!-- Hidden file input -->
    <input
      ref="fileInput"
      type="file"
      accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.md,.csv"
      multiple
      style="display:none"
      @change="handleFilesSelected"
    />
  </div>

  <!-- ── Delete Dialog ── -->
  <Teleport to="body">
    <Transition name="dialog-fade">
      <div v-if="showDeleteDialog" class="dialog-overlay" @click.self="showDeleteDialog = false">
        <div class="dialog-card">
          <div class="dialog-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#DC2626" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
          </div>
          <div class="dialog-title">删除会话</div>
          <div class="dialog-desc">确定要删除本次对话记录吗？<br/>删除后将无法恢复。</div>
          <div class="dialog-actions">
            <button class="dialog-btn dialog-btn-cancel" @click="showDeleteDialog = false">取消</button>
            <button class="dialog-btn dialog-btn-danger" :disabled="deleting" @click="confirmDelete">
              {{ deleting ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.consult-page {
  display: flex; flex-direction: column;
  height: 100dvh; background: linear-gradient(180deg, #FDFBF7 0%, #F8F6F0 100%);
}

/* ═══ Header ═══ */
.chat-header {
  display: flex; align-items: center; gap: 10px;
  padding: 10px var(--space-md); flex-shrink: 0;
  background: rgba(255,255,255,0.82);
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border-bottom: 1px solid var(--border-light);
  min-height: 54px;
}
.chat-back {
  width: 36px; height: 36px; border-radius: 50%;
  border: none; background: transparent;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: var(--text-secondary);
  transition: all 0.2s ease;
}
.chat-back:active { background: rgba(0,0,0,0.04); color: var(--text); }
.chat-header-center {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  min-width: 0;
}
.chat-header-name {
  font-size: var(--text-base); font-weight: 700; letter-spacing: -0.01em;
  color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  max-width: 200px;
}
.chat-header-status {
  font-size: 11px; color: var(--text-tertiary);
  display: flex; align-items: center; gap: 4px;
}
.chat-header-status.online { color: var(--primary); }
.chat-header-action {
  width: 36px; height: 36px; border-radius: 50%;
  border: none; background: transparent;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: var(--text-tertiary);
  transition: all 0.2s ease;
}
.chat-header-action:active { background: rgba(220,38,38,0.06); color: var(--red); }

/* ═══ Chat body ═══ */
.chat-body {
  flex: 1; overflow-y: auto; padding: var(--space-md);
  display: flex; flex-direction: column; gap: 14px;
}

/* System message */
.chat-system-msg {
  text-align: center; padding: 4px 0;
}
.chat-system-msg span {
  display: inline-block; font-size: var(--text-xs); color: var(--text-tertiary);
  background: rgba(0,0,0,0.04); padding: 4px 14px; border-radius: var(--radius-pill);
}

/* Message row */
.chat-msg {
  display: flex; gap: 8px; max-width: 88%;
}
.msg-in  { align-self: flex-start; }
.msg-out { align-self: flex-end; flex-direction: row-reverse; }

/* Avatars */
.msg-avatar {
  width: 34px; height: 34px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: var(--text-xs); font-weight: 700;
}
.avatar-ai   { background: rgba(0,0,0,0.05); color: var(--text-secondary); }
.avatar-user { background: var(--brand-gradient); color: #fff; }

/* Bubbles */
.msg-bubble {
  padding: 10px 14px; border-radius: var(--radius-lg);
  font-size: var(--text-base); line-height: 1.55;
  word-break: break-word; position: relative;
}
.bubble-in {
  background: #fff; color: var(--text);
  border-bottom-left-radius: 4px;
  box-shadow: var(--shadow-xs);
  border: 1px solid var(--border-light);
}
.bubble-out {
  background: var(--brand-gradient); color: #fff;
  border-bottom-right-radius: 4px;
}
.bubble-text { white-space: pre-wrap; }
.bubble-out .bubble-text { color: #fff; }

/* Markdown inside in-bubbles */
.bubble-markdown p { margin: 0 0 4px 0; }
.bubble-markdown p:last-child { margin-bottom: 0; }
.bubble-markdown strong { font-weight: 600; }
.bubble-markdown ul, .bubble-markdown ol { margin: 4px 0; padding-left: 18px; }
.bubble-markdown li { margin-bottom: 2px; }
.bubble-markdown a { color: var(--primary); text-decoration: underline; }
.bubble-markdown code { background: rgba(0,0,0,0.05); padding: 1px 4px; border-radius: 4px; font-size: 0.95em; }
.bubble-markdown blockquote {
  border-left: 3px solid var(--primary-light); margin: 4px 0;
  padding-left: 10px; color: var(--text-secondary);
}

/* Bubble footer */
.bubble-foot {
  display: flex; align-items: center; justify-content: flex-end; gap: 6px; margin-top: 3px;
}
.bubble-time { font-size: 10px; opacity: 0.35; }
.bubble-out .bubble-time { opacity: 0.55; }
.bubble-dot-pulse {
  width: 4px; height: 4px; border-radius: 50%;
  background: rgba(0,0,0,0.25); animation: pulse-dot 1s ease-in-out infinite;
}
.bubble-out .bubble-dot-pulse { background: rgba(255,255,255,0.5); }
@keyframes pulse-dot { 0%,100%{opacity:0.2} 50%{opacity:1} }
.bubble-error-text { font-size: 10px; color: var(--red); }
.bubble-retry {
  font-size: 10px; background: none; border: none; color: var(--red);
  cursor: pointer; text-decoration: underline; padding: 0;
}

/* Typing indicator */
.typing-indicator {
  display: flex; align-items: center; gap: 4px; padding: 12px 16px;
}
.typing-dot {
  width: 6px; height: 6px; border-radius: 50%; background: rgba(0,0,0,0.2);
  animation: bounce-dot 1.4s ease-in-out infinite;
}
.typing-dot:nth-child(1) { animation-delay: 0s; }
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce-dot {
  0%,80%,100% { transform: translateY(0); }
  40% { transform: translateY(-6px); }
}

/* ═══ Rating sheet ═══ */
.rating-sheet {
  margin: 0 12px 8px; padding: 22px 20px;
  background: #fff; border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md); border: 1px solid var(--border-light);
  display: flex; flex-direction: column; gap: 14px;
}
.rating-sheet-title {
  text-align: center; font-size: var(--text-base); font-weight: 700; color: var(--text);
}
.rating-stars-row {
  display: flex; justify-content: center; gap: 6px;
}
.rating-sheet-input {
  padding: 10px 14px; border: 1px solid var(--border); border-radius: var(--radius-md);
  font-size: var(--text-sm); outline: none; background: var(--bg-input);
  font-family: inherit; transition: border-color 0.3s ease;
}
.rating-sheet-input:focus { border-color: var(--border-focus); }

/* ═══ Suggestions ─═��═ */
.suggest-strip {
  display: flex; gap: 6px; padding: 8px 12px;
  overflow-x: auto; scrollbar-width: none;
}
.suggest-strip::-webkit-scrollbar { display: none; }

/* ═══ Transfer strip ═══ */
.transfer-strip {
  text-align: center; padding: 4px 0;
}

/* ═══ Input bar ═══ */
.input-bar {
  display: flex; gap: 8px; padding: 10px 12px;
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border-top: none; align-items: center;
  box-shadow: var(--shadow-input-bar);
}
.input-pill {
  flex: 1;
  background: var(--bg-input); border-radius: var(--radius-pill);
  border: 1px solid transparent;
  transition: all 0.3s var(--ease-out-expo);
}
.input-pill:focus-within {
  background: #fff; border-color: var(--border-focus);
  box-shadow: 0 0 0 3px rgba(13,148,136,0.06);
}
.input-pill input {
  width: 100%; border: none; background: transparent;
  padding: 11px 18px; font-size: var(--text-base); outline: none;
  font-family: inherit;
}
.attach-btn {
  width: 40px; height: 40px; border-radius: 50%;
  border: none; background: transparent; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary); flex-shrink: 0;
  transition: all 0.25s var(--ease-out-expo);
}
.attach-btn:active { background: rgba(0,0,0,0.06); color: var(--primary); transform: scale(0.92); }
.attach-btn:disabled { opacity: 0.3; cursor: not-allowed; }

.send-btn {
  width: 44px; height: 44px; border-radius: 50%;
  background: var(--brand-gradient); border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  color: #fff; box-shadow: var(--shadow-button);
  transition: all 0.3s var(--ease-out-expo);
  flex-shrink: 0;
}
.send-btn:active { transform: scale(0.9); }
.send-btn:disabled { opacity: 0.3; cursor: not-allowed; box-shadow: none; }

/* ═══ File Preview Strip ═══ */
.file-preview-strip {
  display: flex; gap: 8px; padding: 6px 12px 4px;
  overflow-x: auto; scrollbar-width: none;
}
.file-preview-strip::-webkit-scrollbar { display: none; }
.file-preview-item {
  position: relative; flex-shrink: 0;
  width: 64px; height: 64px; border-radius: 12px;
  overflow: hidden; background: rgba(0,0,0,0.04);
  border: 1px solid var(--border-light);
}
.file-preview-thumb {
  width: 100%; height: 100%; object-fit: cover;
}
.file-preview-doc {
  width: 100%; height: 100%; display: flex;
  flex-direction: column; align-items: center; justify-content: center; gap: 2px;
}
.file-preview-doc-icon { font-size: 22px; }
.file-preview-doc-ext {
  font-size: 9px; font-weight: 600; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: 0.04em;
}
.file-preview-remove {
  position: absolute; top: 2px; right: 2px;
  width: 16px; height: 16px; border-radius: 50%;
  background: rgba(0,0,0,0.45); color: #fff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: transform 0.2s ease;
}
.file-preview-remove:active { transform: scale(1.2); }
.file-uploading-overlay {
  display: flex; align-items: center; justify-content: center;
  background: rgba(255,255,255,0.7); backdrop-filter: blur(4px);
}
.file-uploading-spinner {
  width: 20px; height: 20px; border-radius: 50%;
  border: 2px solid rgba(0,0,0,0.1);
  border-top-color: var(--primary);
  animation: spin-file 0.8s linear infinite;
}
@keyframes spin-file { to { transform: rotate(360deg); } }

/* ═══ Bubble File Attachments ═══ */
.bubble-files {
  display: flex; flex-direction: column; gap: 6px; margin-top: 6px;
}
.bubble-file-item {
  border-radius: 10px; overflow: hidden; max-width: 240px;
}
.bubble-img {
  width: 100%; max-height: 200px; object-fit: cover;
  border-radius: 10px; cursor: pointer;
  transition: opacity 0.2s ease;
}
.bubble-img:active { opacity: 0.8; }
.bubble-video {
  width: 100%; max-height: 200px; border-radius: 10px;
  background: #000;
}
.bubble-doc-link {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; border-radius: 10px;
  background: rgba(0,0,0,0.04); text-decoration: none;
  transition: background 0.2s ease;
}
.bubble-doc-link:active { background: rgba(0,0,0,0.08); }
.bubble-doc-icon { font-size: 24px; flex-shrink: 0; }
.bubble-doc-name {
  font-size: 12px; color: var(--text-secondary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.bubble-out .bubble-doc-link { background: rgba(255,255,255,0.15); }
.bubble-out .bubble-doc-name { color: rgba(255,255,255,0.85); }
.bubble-out .bubble-doc-link:active { background: rgba(255,255,255,0.25); }
</style>

<style>
/* ═══ Delete Dialog (global) ═══ */
.dialog-overlay {
  position: fixed; inset: 0; z-index: 3000;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.35);
  -webkit-backdrop-filter: blur(4px); backdrop-filter: blur(4px);
}
.dialog-card {
  width: 300px; background: #fff; border-radius: 24px;
  padding: 32px 24px 20px; text-align: center;
  box-shadow: 0 16px 48px rgba(0,0,0,0.12);
  animation: dialogPopIn 0.35s cubic-bezier(0.32,0.72,0,1);
}
@keyframes dialogPopIn {
  from { opacity: 0; transform: scale(0.85) translateY(16px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}
.dialog-icon { margin-bottom: 16px; }
.dialog-title { font-size: 18px; font-weight: 700; color: var(--text); margin-bottom: 8px; }
.dialog-desc { font-size: 14px; color: var(--text-secondary); line-height: 1.6; margin-bottom: 28px; }
.dialog-actions { display: flex; gap: 12px; }
.dialog-btn {
  flex: 1; height: 46px; border: none; border-radius: 14px;
  font-size: 15px; font-weight: 600; cursor: pointer;
  transition: all 0.3s ease; font-family: inherit;
}
.dialog-btn:active { transform: scale(0.95); }
.dialog-btn-cancel { background: rgba(0,0,0,0.05); color: var(--text-secondary); }
.dialog-btn-danger { background: var(--red); color: #fff; }
.dialog-btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }
.dialog-fade-enter-active { transition: opacity 0.25s ease; }
.dialog-fade-leave-active { transition: opacity 0.15s ease; }
.dialog-fade-enter-from, .dialog-fade-leave-to { opacity: 0; }
</style>

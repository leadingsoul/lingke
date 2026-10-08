/**
 * WebSocket 客户端 — 全局单例
 *
 * 连接后端 ws://host/api/ws/connect?token=JWT
 * 支持心跳检测、断线自动重连、事件订阅/发送
 *
 * 【心跳机制】：
 *   - 服务端每 30s 发送 ping，客户端回复 pong
 *   - 客户端监控：超过 90s 未收到 ping → 判定连接假死 → 主动断开重连
 *
 * 用法：
 *   App.vue onMounted: useGlobalWS()  // 全局初始化一次
 *   任意组件: const { on, off, emit, isConnected } = useWebSocket()
 */
import { ref } from 'vue'

type EventHandler = (data: any) => void

// ====== 模块级单例状态 ======
let _ws: WebSocket | null = null
const isConnected = ref(false)
let _reconnectTimer: ReturnType<typeof setTimeout> | null = null
let _pingTimer: ReturnType<typeof setTimeout> | null = null
const _handlers = new Map<string, EventHandler[]>()
let _initCalled = false
let _reconnectDelay = 3000
const MAX_RECONNECT_DELAY = 30000
const PING_TIMEOUT_MS = 90_000  // 90s 内收不到 ping 则判定假死

// ── Ping 超时检测辅助 ──

function _resetPingTimer() {
  if (_pingTimer) clearTimeout(_pingTimer)
  _pingTimer = setTimeout(() => {
    console.warn('[WS] Ping 超时 (90s)，判定连接假死，主动断开重连...')
    _cleanup(false)
    _scheduleReconnect()
  }, PING_TIMEOUT_MS)
}

function _clearPingTimer() {
  if (_pingTimer) {
    clearTimeout(_pingTimer)
    _pingTimer = null
  }
}

function _cleanup(permanent: boolean) {
  if (permanent && _reconnectTimer) {
    clearTimeout(_reconnectTimer)
    _reconnectTimer = null
  }
  _clearPingTimer()
  if (_ws) {
    _ws.onclose = null
    _ws.onerror = null
    _ws.close()
    _ws = null
    isConnected.value = false
  }
}

// ── 连接 & 重连 ──

function buildUrl(): string | null {
  const token = localStorage.getItem('token')
  if (!token) return null
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/ws/connect?token=${encodeURIComponent(token)}`
}

function _scheduleReconnect() {
  if (_reconnectTimer) return
  _reconnectTimer = setTimeout(() => {
    _reconnectTimer = null
    if (!isConnected.value) _connect()
  }, _reconnectDelay)
}

function _connect() {
  const url = buildUrl()
  if (!url) return
  if (_ws && (_ws.readyState === WebSocket.OPEN || _ws.readyState === WebSocket.CONNECTING)) return

  const ws = new WebSocket(url)
  _ws = ws

  ws.onopen = () => {
    isConnected.value = true
    _reconnectDelay = 3000  // 重置重连延迟
    _resetPingTimer()        // 启动 ping 超时监控
    console.log('[WS] 全局连接已建立')
    // 通知订阅者
    ;(_handlers.get('connected') || []).forEach((h) => h({}))
  }

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      const eventType = msg.event

      if (eventType === 'ping') {
        // 收到服务端心跳 → 重置超时 + 回复 pong
        _resetPingTimer()
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ event: 'pong', data: {}, timestamp: null }))
        }
        return
      }

      // 任何非 ping 消息也视为连接活跃
      _resetPingTimer()

      const payload = msg.data || msg
      ;(_handlers.get(eventType) || []).forEach((h) => h(payload))
      ;(_handlers.get('*') || []).forEach((h) => h(msg))
    } catch (e) {
      console.error('[WS] 消息解析失败:', e)
    }
  }

  ws.onclose = (e) => {
    isConnected.value = false
    _ws = null
    _clearPingTimer()
    console.log(`[WS] 断开 (code=${e.code}), ${_reconnectDelay / 1000}s 后重连...`)
    _scheduleReconnect()
    // 指数退避
    _reconnectDelay = Math.min(_reconnectDelay * 1.5, MAX_RECONNECT_DELAY)
  }

  ws.onerror = (e) => {
    console.error('[WS] 连接错误:', e)
    ws.close()
  }
}

function _disconnect() {
  _cleanup(true)
}

/**
 * 全局初始化 — 在 App.vue onMounted 中调用一次
 * 幂等：重复调用不会创建新连接
 */
export function useGlobalWS() {
  if (_initCalled) return
  _initCalled = true
  const token = localStorage.getItem('token')
  if (token) _connect()

  // 页面关闭时主动断开
  window.addEventListener('beforeunload', () => _disconnect())
}

/**
 * 获取全局 WebSocket 单例
 * 返回 on / off / emit / isConnected，向后兼容原接口
 */
export function useWebSocket() {
  function on(event: string, handler: EventHandler) {
    if (!_handlers.has(event)) _handlers.set(event, [])
    _handlers.get(event)!.push(handler)
  }

  function off(event: string, handler: EventHandler) {
    const handlers = _handlers.get(event)
    if (handlers) {
      const idx = handlers.indexOf(handler)
      if (idx > -1) handlers.splice(idx, 1)
    }
  }

  function emit(event: string, data: any = {}) {
    if (_ws && _ws.readyState === WebSocket.OPEN) {
      _ws.send(JSON.stringify({ event, data, timestamp: null }))
    }
  }

  return { isConnected, on, off, emit, connect: _connect, disconnect: _disconnect }
}

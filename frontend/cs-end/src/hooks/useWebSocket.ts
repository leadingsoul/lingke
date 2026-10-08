/**
 * WebSocket 客户端 — React Hook (客服端)
 *
 * 【架构】全局单例模式：
 *   - 整个应用只维持一条 WebSocket 连接
 *   - 各组件共享同一个连接，通过 on/off 订阅事件
 *   - 避免多组件同时创建多条连接导致资源浪费和消息路由混乱
 *
 * 【心跳机制】：
 *   - 服务端每 30s 发送 ping，客户端回复 pong
 *   - 客户端监控：超过 90s 未收到 ping → 判定连接假死 → 主动断开重连
 *
 * 【断线重连】：
 *   - 3s 后自动重连，指数退避上限 30s
 *   - 页面关闭时主动断开
 *
 * 用法：
 *   const { isConnected, on, off } = useWebSocket()
 *   useEffect(() => {
 *     on('new_message', handler)
 *     return () => off('new_message', handler)  // 组件卸载时清理
 *   }, [])
 */
import { useState, useEffect, useCallback } from 'react'

type EventHandler = (data: any) => void

interface UseWebSocketReturn {
  isConnected: boolean
  on: (event: string, handler: EventHandler) => void
  off: (event: string, handler: EventHandler) => void
}

// ====== 模块级单例状态 ======
let _ws: WebSocket | null = null
let _reconnectTimer: ReturnType<typeof setTimeout> | null = null
let _pingTimer: ReturnType<typeof setTimeout> | null = null
let _reconnectDelay = 3000
const MAX_RECONNECT_DELAY = 30000
const PING_TIMEOUT_MS = 90_000 // 90s 内收不到 ping 则认为假死
const _handlers = new Map<string, EventHandler[]>()
let _isConnected = false
let _initCalled = false

// 订阅者列表：每个调用 useWebSocket() 的组件在这里注册 setState
const _subscribers = new Set<(connected: boolean) => void>()

function _notifySubscribers(connected: boolean) {
  _isConnected = connected
  _subscribers.forEach((setState) => setState(connected))
}

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

function _buildUrl(): string | null {
  const token = localStorage.getItem('token')
  if (!token) return null
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/ws/connect?token=${encodeURIComponent(token)}`
}

function _scheduleReconnect() {
  if (_reconnectTimer) return
  _reconnectTimer = setTimeout(() => {
    _reconnectTimer = null
    _connect()
  }, _reconnectDelay)
}

function _connect() {
  const url = _buildUrl()
  if (!url) return
  if (_ws && (_ws.readyState === WebSocket.OPEN || _ws.readyState === WebSocket.CONNECTING)) return

  const ws = new WebSocket(url)
  _ws = ws

  ws.onopen = () => {
    _notifySubscribers(true)
    _reconnectDelay = 3000 // 重置重连延迟
    _resetPingTimer()       // 启动 ping 超时监控
    console.log('[WS] 客服端已连接')
    // 通知 connected 事件订阅者
    ;(_handlers.get('connected') || []).forEach((h) => h({}))
  }

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      const eventType = msg.event

      if (eventType === 'ping') {
        // 收到服务端心跳 → 重置超时计时器 + 回复 pong
        _resetPingTimer()
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ event: 'pong', data: {}, timestamp: null }))
        }
        return
      }

      // 任何非 ping 消息也视为连接活跃，刷新超时
      _resetPingTimer()

      const payload = msg.data || msg
      ;(_handlers.get(eventType) || []).forEach((h) => h(payload))
      ;(_handlers.get('*') || []).forEach((h) => h(msg))
    } catch (e) {
      console.error('[WS] 消息解析失败:', e)
    }
  }

  ws.onclose = (e) => {
    _notifySubscribers(false)
    _ws = null
    _clearPingTimer()
    console.log(`[WS] 断开连接 (code=${e.code}), ${_reconnectDelay / 1000}s 后重连...`)
    _scheduleReconnect()
    // 指数退避
    _reconnectDelay = Math.min(_reconnectDelay * 1.5, MAX_RECONNECT_DELAY)
  }

  ws.onerror = (e) => {
    console.error('[WS] 连接错误:', e)
    ws.close() // 触发 onclose → 自动重连
  }
}

function _disconnect() {
  _cleanup(true)
}

function _cleanup(permanent: boolean) {
  if (permanent && _reconnectTimer) {
    clearTimeout(_reconnectTimer)
    _reconnectTimer = null
  }
  _clearPingTimer()
  if (_ws) {
    _ws.onclose = null // 防止触发重连
    _ws.onerror = null
    _ws.close()
    _ws = null
    _notifySubscribers(false)
  }
}

/**
 * 全局初始化 — 在 App.tsx 中调用一次
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
 * 组件级使用：返回 on / off / isConnected
 * 首次调用时自动发起连接（延迟到有 token 时）
 */
export function useWebSocket(): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(_isConnected)

  // 首次调用时自动连接（如果尚未连接且有 token）
  useEffect(() => {
    if (!_ws || _ws.readyState === WebSocket.CLOSED) {
      const token = localStorage.getItem('token')
      if (token) _connect()
    }

    // 订阅连接状态变化
    _subscribers.add(setIsConnected)
    return () => {
      _subscribers.delete(setIsConnected)
    }
  }, [])

  const on = useCallback((event: string, handler: EventHandler) => {
    if (!_handlers.has(event)) _handlers.set(event, [])
    _handlers.get(event)!.push(handler)
  }, [])

  const off = useCallback((event: string, handler: EventHandler) => {
    const handlers = _handlers.get(event)
    if (handlers) {
      const idx = handlers.indexOf(handler)
      if (idx > -1) handlers.splice(idx, 1)
    }
  }, [])

  return { isConnected, on, off }
}

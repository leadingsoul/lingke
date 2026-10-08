/**
 * WebSocket 客户端 — React Hook (管理端)
 *
 * 连接后端 ws://localhost:8000/api/ws/connect?token=JWT
 * 管理端使用 admin_token 而非 token
 */
import { useRef, useState, useEffect, useCallback } from 'react'

type EventHandler = (data: any) => void

interface UseWebSocketReturn {
  isConnected: boolean
  on: (event: string, handler: EventHandler) => void
  off: (event: string, handler: EventHandler) => void
  emit: (event: string, data?: any) => void
  connect: () => void
  disconnect: () => void
}

export function useWebSocket(): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const handlersRef = useRef<Map<string, EventHandler[]>>(new Map())
  const [isConnected, setIsConnected] = useState(false)

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimerRef.current) return
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null
      const token = localStorage.getItem('admin_token')
      if (token && !isConnected) {
        connect()
      }
    }, 3000)
  }, [])

  const connect = useCallback(() => {
    const token = localStorage.getItem('admin_token')
    if (!token) return

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/api/ws/connect?token=${encodeURIComponent(token)}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      console.log('[WS] 管理端已连接')
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        const eventType = msg.event

        if (eventType === 'ping') {
          ws.send(JSON.stringify({ event: 'pong', data: {}, timestamp: null }))
          return
        }

        const payload = msg.data || msg
        const handlers = handlersRef.current.get(eventType) || []
        handlers.forEach((h) => h(payload))

        const wildcard = handlersRef.current.get('*') || []
        wildcard.forEach((h) => h(msg))
      } catch (e) {
        console.error('[WS] 消息解析失败:', e)
      }
    }

    ws.onclose = (e) => {
      setIsConnected(false)
      wsRef.current = null
      console.log(`[WS] 断开连接 (code=${e.code}), 3秒后重连...`)
      scheduleReconnect()
    }

    ws.onerror = (e) => {
      console.error('[WS] 连接错误:', e)
      ws.close()
    }
  }, [scheduleReconnect])

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.close()
      wsRef.current = null
      setIsConnected(false)
    }
  }, [])

  const on = useCallback((event: string, handler: EventHandler) => {
    const handlers = handlersRef.current.get(event) || []
    handlers.push(handler)
    handlersRef.current.set(event, handlers)
  }, [])

  const off = useCallback((event: string, handler: EventHandler) => {
    const handlers = handlersRef.current.get(event)
    if (handlers) {
      const idx = handlers.indexOf(handler)
      if (idx > -1) handlers.splice(idx, 1)
    }
  }, [])

  const emit = useCallback((event: string, data: any = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ event, data, timestamp: null }))
    }
  }, [])

  useEffect(() => {
    const token = localStorage.getItem('admin_token')
    if (token) connect()
    return () => disconnect()
  }, [connect, disconnect])

  return { isConnected, on, off, emit, connect, disconnect }
}

"""WebSocket 路由 — 实时消息推送 / 心跳保活"""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.core.security import decode_token

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器 — 维护 user_id -> WebSocket 映射 + 角色追踪
    支持：精准推送、按角色广播、心跳 ping-pong + 超时断开
    """

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self._roles: dict[str, str] = {}          # user_id -> role
        self._heartbeat_tasks: dict[str, asyncio.Task] = {}
        self._pong_received: dict[str, asyncio.Event] = {}  # 追踪 pong 应答

    async def connect(self, websocket: WebSocket, user_id: str, role: str = ""):
        """接受 WebSocket 连接并注册到连接池"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self._roles[user_id] = role
        self._pong_received[user_id] = asyncio.Event()
        # 启动心跳检测循环
        self._heartbeat_tasks[user_id] = asyncio.create_task(
            self._heartbeat_loop(user_id)
        )

    async def disconnect(self, user_id: str):
        """从连接池移除并取消心跳"""
        websocket = self.active_connections.pop(user_id, None)
        self._roles.pop(user_id, None)
        self._pong_received.pop(user_id, None)
        task = self._heartbeat_tasks.pop(user_id, None)
        if task:
            task.cancel()
        if websocket:
            try:
                await websocket.close()
            except Exception:
                pass

    async def send_personal(self, message: dict, user_id: str):
        """向指定用户发送消息"""
        websocket = self.active_connections.get(user_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception:
                await self.disconnect(user_id)

    async def broadcast(self, message: dict, user_ids: Optional[list[str]] = None):
        """向指定用户列表广播消息，若未指定则广播给全部连接"""
        targets = user_ids or list(self.active_connections.keys())
        for uid in targets:
            await self.send_personal(message, uid)

    async def broadcast_to_role(self, message: dict, role: str):
        """向指定角色的所有在线用户广播消息"""
        targets = [uid for uid, r in self._roles.items() if r == role]
        for uid in targets:
            await self.send_personal(message, uid)

    def get_role(self, user_id: str) -> str:
        """查询用户的角色"""
        return self._roles.get(user_id, "")

    def mark_pong(self, user_id: str):
        """标记收到 pong（由 onmessage 回调调用）"""
        event = self._pong_received.get(user_id)
        if event:
            event.set()

    async def _heartbeat_loop(self, user_id: str):
        """每 30s 发送 ping，等待 15s 内收到 pong，否则断开"""
        while True:
            await asyncio.sleep(30)
            websocket = self.active_connections.get(user_id)
            if not websocket:
                return

            # 清除上次 pong 标记
            pong_event = self._pong_received.get(user_id)
            if pong_event:
                pong_event.clear()

            # 发送 ping
            try:
                await websocket.send_json({"event": "ping", "data": {}, "timestamp": None})
            except Exception:
                await self.disconnect(user_id)
                return

            # 等待 15s 内收到 pong
            if pong_event:
                try:
                    await asyncio.wait_for(pong_event.wait(), timeout=15.0)
                except asyncio.TimeoutError:
                    # 15s 内未收到 pong → 断开
                    await self.disconnect(user_id)
                    return


manager = ConnectionManager()


@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """WebSocket 连接端点 — 通过 query param 传递 JWT 进行认证"""
    # 认证
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001, reason="无效的 Token 类型")
            return
        user_id = payload.get("sub")
        role = payload.get("role")
        if not user_id or not role:
            await websocket.close(code=4001, reason="Token 无效")
            return
    except Exception:
        await websocket.close(code=4001, reason="Token 无效或已过期")
        return

    await manager.connect(websocket, user_id, role)

    # 发送连接成功通知
    await manager.send_personal(
        {"event": "connected", "data": {"user_id": user_id, "role": role}, "timestamp": None},
        user_id,
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send_personal(
                    {"event": "error", "data": {"message": "消息格式无效"}, "timestamp": None},
                    user_id,
                )
                continue

            event = msg.get("event", "")

            if event == "pong":
                # 心跳回复 → 通知 ConnectionManager 收到了 pong
                manager.mark_pong(user_id)

            elif event == "new_message":
                # 消费者发送消息 -> 广播给相关客服
                data = msg.get("data", {})
                target_user_id = data.get("target_user_id")
                if target_user_id:
                    await manager.send_personal(
                        {
                            "event": "new_message",
                            "data": data,
                            "timestamp": None,
                        },
                        target_user_id,
                    )
                else:
                    # 未指定目标，广播给所有客服/管理员
                    await manager.broadcast(
                        {
                            "event": "new_message",
                            "data": data,
                            "timestamp": None,
                        }
                    )

            elif event == "conversation_update":
                # 会话状态更新 -> 通知相关用户
                data = msg.get("data", {})
                affected_users = data.get("affected_users", [])
                await manager.broadcast(
                    {
                        "event": "conversation_update",
                        "data": data,
                        "timestamp": None,
                    },
                    user_ids=affected_users if affected_users else None,
                )

            elif event == "ticket_update":
                # 工单状态变更 -> 通知相关用户
                data = msg.get("data", {})
                affected_users = data.get("affected_users", [])
                await manager.broadcast(
                    {
                        "event": "ticket_update",
                        "data": data,
                        "timestamp": None,
                    },
                    user_ids=affected_users if affected_users else None,
                )

            elif event == "system_notice":
                # 系统通知 -> 全局广播
                data = msg.get("data", {})
                await manager.broadcast(
                    {
                        "event": "system_notice",
                        "data": data,
                        "timestamp": None,
                    }
                )

            else:
                await manager.send_personal(
                    {
                        "event": "error",
                        "data": {"message": f"未知事件类型: {event}"},
                        "timestamp": None,
                    },
                    user_id,
                )

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await manager.disconnect(user_id)

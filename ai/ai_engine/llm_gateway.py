"""
LLM Gateway — 统一 LLM 调用入口（DeepSeek）

功能：
- chat_sync：同步调用（引擎层默认使用）
- chat：异步调用（流式等场景）
- 指数退避重试（最多 3 次）
- 从环境变量加载配置
"""
import os
import time
import asyncio
from typing import Optional, AsyncGenerator

import httpx
from pydantic import BaseModel


class LLMConfig(BaseModel):
    """单个 LLM 模型配置"""
    api_key: str = ""
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 30


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: dict
    finish_reason: str


class LLMGateway:
    """统一 LLM 调用入口（仅 DeepSeek）"""

    # 类级共享 embedding 模型（所有实例复用，避免重复加载）
    _embedding_model = None

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._client: Optional[httpx.AsyncClient] = None

    # ── 同步调用（引擎层主入口）──────────────────────────

    def chat_sync(
        self,
        messages: str | list[dict],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        同步调用 LLM，返回纯文本回复。

        Args:
            messages: 字符串（自动包装为单条 user 消息）或 [{"role":"user","content":"..."}]
            temperature: 温度（None 则用 config 默认值）
            max_tokens: 最大 token 数（None 则用 config 默认值）

        Returns:
            LLM 生成的纯文本内容
        """
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
        }

        for attempt in range(3):
            try:
                with httpx.Client(timeout=self.config.timeout) as client:
                    response = client.post(
                        f"{self.config.base_url}/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.config.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    raise RuntimeError(f"LLM 调用失败（已重试 3 次）: {e}") from e

    # ── Embedding 向量化 ──────────────────────────────────

    @classmethod
    def _load_embedding_model(cls):
        """懒加载中文 embedding 模型（类级单例，所有实例共享）"""
        if cls._embedding_model is None:
            # 国内优先走 HF 镜像，避免 HuggingFace 被墙
            import os as _os
            if "HF_ENDPOINT" not in _os.environ:
                _os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
            from sentence_transformers import SentenceTransformer
            # bge-small-zh 轻量中文模型，~100MB，语义检索效果优秀
            cls._embedding_model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
        return cls._embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        将文本列表转为归一化 embedding 向量。

        Args:
            texts: 待向量化的文本列表

        Returns:
            等长的向量列表，每个向量为 512 维 float 列表（L2 归一化后）
        """
        model = self._load_embedding_model()
        # normalize_embeddings=True → L2 归一化，直接点积即 cosine 相似度
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()

    # ── 异步调用（流式等场景）────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.config.timeout)
        return self._client

    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """异步调用 LLM"""
        client = await self._get_client()
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
        }
        for attempt in range(3):
            try:
                response = await client.post(
                    f"{self.config.base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return LLMResponse(
                    content=data["choices"][0]["message"]["content"],
                    model=data.get("model", self.config.model),
                    usage=data.get("usage", {}),
                    finish_reason=data["choices"][0].get("finish_reason", "stop"),
                )
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise RuntimeError(f"LLM 调用失败（已重试 3 次）: {e}") from e

    async def chat_stream(
        self,
        messages: list[dict],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """流式调用 LLM"""
        client = await self._get_client()
        async with client.stream(
            "POST",
            f"{self.config.base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.config.model,
                "messages": messages,
                "temperature": temperature if temperature is not None else self.config.temperature,
                "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
                "stream": True,
            },
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    import json
                    data = json.loads(data_str)
                    delta = data["choices"][0].get("delta", {})
                    if content := delta.get("content"):
                        yield content

    # ── 工厂方法 ─────────────────────────────────────────

    @classmethod
    def from_env(cls) -> "LLMGateway":
        """从环境变量创建 Gateway（仅 DeepSeek）"""
        config = LLMConfig(
            api_key=os.getenv("LLM_API_KEY", ""),
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2000")),
        )
        return cls(config)

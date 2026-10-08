"""group22-ai Python 包配置"""
from setuptools import setup, find_packages

setup(
    name="group22-ai",
    version="1.0.0",
    description="电商售后客服 AI 引擎 — 8 大 AI 能力模块（全量 DeepSeek LLM）",
    author="Group 22",
    python_requires=">=3.11",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        "langchain>=0.1.0",
        "httpx>=0.25.0",
        "pydantic>=2.5.0",
        "numpy>=1.24.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.23.0",
        ],
    },
)

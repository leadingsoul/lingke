"""工具函数"""

from datetime import datetime, timezone, timedelta

# MySQL func.now() 返回本地时间（中国 +08:00），naive datetime 时应使用此时区
_CHINA_TZ = timezone(timedelta(hours=8))


def format_dt(dt: datetime | None) -> str | None:
    """将 datetime 格式化为 ISO 8601 字符串（带时区）。

    规则：
    - naive datetime（无 tzinfo）→ 假定为东八区，补 +08:00
    - aware datetime → 统一转换为东八区 (+08:00) 后输出
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_CHINA_TZ)
    else:
        dt = dt.astimezone(_CHINA_TZ)
    return dt.isoformat()

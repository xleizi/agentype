#!/usr/bin/env python3
"""
agentype - 会话配置管理模块
Author: cuilei
Version: 1.0
"""

from datetime import datetime
from typing import Optional

# 模块级私有变量（每个进程独立）
_SESSION_ID: Optional[str] = None


def create_session_id() -> str:
    """生成基于时间戳的会话ID（增强版：微秒精度 + UUID）

    格式: session_YYYYMMDD_HHMMSS_microseconds_uuid4
    例如: session_20251024_162305_123456_a3f2

    设计考虑：
    - 时间戳（秒级）：保留可读性，方便人工查找
    - 微秒：6位数字，精度到百万分之一秒
    - 短UUID：4位十六进制，随机性补充
    - 总长度：约40字符（原来24字符）

    并发安全性：
    - 同一微秒内启动：通过UUID区分（1/65536冲突概率）
    - 跨微秒启动：完全不冲突
    - 理论最大QPS：1,000,000 * 65,536 = 655亿/秒

    适用场景：
    - 同一台机器上并行处理多个数据集
    - 快速连续启动多个分析任务
    - 批量任务队列调度

    Returns:
        str: 唯一的会话ID
    """
    import uuid
    now = datetime.now()
    # 时间部分：年月日_时分秒
    time_part = now.strftime("%Y%m%d_%H%M%S")
    # 微秒部分：6位数字
    microsecond = now.strftime("%f")  # 自动补齐到6位
    # UUID部分：取4位十六进制
    uuid_part = uuid.uuid4().hex[:4]

    return f"session_{time_part}_{microsecond}_{uuid_part}"


def set_session_id(session_id: str) -> None:
    """设置当前会话ID

    由mcp_server在启动时调用，设置当前进程的会话ID。

    Args:
        session_id: 会话ID字符串
    """
    global _SESSION_ID
    _SESSION_ID = session_id
    print(f"✅ 会话ID已设置: {session_id}")


def get_session_id() -> str:
    """获取当前会话ID

    被cluster_tools等模块调用，自动获取当前进程的会话ID。
    如果会话ID未初始化，会自动生成一个新的（兼容直接调用的情况）。

    Returns:
        str: 当前会话ID
    """
    global _SESSION_ID
    if _SESSION_ID is None:
        # 如果未设置，自动生成一个（兼容直接调用的情况）
        _SESSION_ID = create_session_id()
        print(f"⚠️  会话ID未初始化，自动生成: {_SESSION_ID}")
    return _SESSION_ID


def reset_session_id() -> str:
    """重置会话ID

    生成新的会话ID并设置为当前会话ID。
    用于测试或需要重新开始新会话的场景。

    Returns:
        str: 新生成的会话ID
    """
    global _SESSION_ID
    _SESSION_ID = create_session_id()
    print(f"🔄 会话ID已重置: {_SESSION_ID}")
    return _SESSION_ID


def get_session_id_for_filename() -> str:
    """获取用于文件命名的会话ID（完整格式）

    返回完整的 session_id，包含 session_ 前缀，确保所有文件命名统一。
    新格式支持高并发场景，避免文件名冲突。

    格式示例: session_20251024_162305_123456_a3f2

    Returns:
        str: 完整的 session_id 字符串，包含时间戳、微秒和UUID
    """
    return get_session_id()


def get_session_info() -> dict:
    """获取当前会话的详细信息

    Returns:
        dict: 包含会话ID和相关元数据的字典
    """
    session_id = get_session_id()

    # 从会话ID解析时间戳（兼容新旧格式）
    timestamp_str = None
    microsecond = None
    uuid_part = None

    if session_id.startswith("session_"):
        try:
            # 移除 session_ 前缀
            parts = session_id.replace("session_", "").split("_")

            # 新格式: 20251024_162305_123456_a3f2 (4个部分)
            # 旧格式: 20251019_162302 (2个部分)
            if len(parts) >= 2:
                date_part = parts[0]  # 20251024
                time_part = parts[1]  # 162305

                # 解析基本时间戳
                dt = datetime.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S")
                timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")

                # 如果是新格式，提取微秒和UUID
                if len(parts) >= 3:
                    microsecond = parts[2]  # 123456
                    timestamp_str += f".{microsecond}"
                if len(parts) >= 4:
                    uuid_part = parts[3]  # a3f2

        except (ValueError, IndexError):
            pass

    return {
        "session_id": session_id,
        "created_at": timestamp_str,
        "microsecond": microsecond,
        "uuid": uuid_part,
        "format": "enhanced" if microsecond else "legacy",
        "is_auto_generated": _SESSION_ID is None or session_id.startswith("session_")
    }

# client_protocol.py - DEPRECATED
# 已迁移到 E:/pyproject/PythonProject/shared/protocol.py
# 此文件仅为向后兼容保留，请使用 from shared.protocol import MsgType, build_packet

import warnings
warnings.warn(
    "client_protocol.py 已废弃，请使用 'from shared.protocol import MsgType, build_packet'",
    DeprecationWarning,
    stacklevel=2
)
from shared.protocol import MsgType, build_packet  # noqa: F401

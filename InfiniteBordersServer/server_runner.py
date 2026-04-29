# server_runner.py - 服务器启动线程封装
# 独立模块，避免 server.py 和 gm_console 之间的循环引用
import asyncio
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

# 全局 uvicorn.Server 实例引用，用于停止/重启
_uvicorn_server = None


def create_app():
    """创建并返回 FastAPI 应用实例。"""
    import os
    _server_root = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.dirname(_server_root)
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    from server import app
    return app


def start_server_thread():
    """在后台线程中启动 uvicorn 服务器。"""
    global _uvicorn_server
    app = create_app()
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    _uvicorn_server = uvicorn.Server(config)
    _uvicorn_server.install_signal_handlers = lambda: None
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_uvicorn_server.serve())
    _uvicorn_server = None  # 服务停止后清除引用


def stop_server():
    """通知 uvicorn 服务器优雅退出。"""
    global _uvicorn_server
    if _uvicorn_server is not None:
        _uvicorn_server.should_exit = True

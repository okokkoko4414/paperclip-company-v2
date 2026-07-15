"""验证 keepalive 插件的接口契约。

测试三项：register 调用、hook 回调签名兼容、_trigger_reload 调的是 discover_mcp_tools。
"""
import sys, inspect, importlib.util
from unittest.mock import patch

PLUGIN_INIT = "/home/ok2049/.hermes/plugins/observability/geo119_keepalive/__init__.py"

def _load():
    spec = importlib.util.spec_from_file_location("geo119_keepalive", PLUGIN_INIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_register_calls_register_hook():
    """register(ctx) 必须调用 ctx.register_hook('on_session_start', cb)。"""
    mod = _load()
    assert hasattr(mod, 'register'), "缺少 register(ctx) 入口"
    hooks = {}
    class MockCtx:
        def register_hook(self, name, callback): hooks[name] = callback
    mod.register(MockCtx())
    assert 'on_session_start' in hooks, f"未注册 on_session_start，已注册: {list(hooks.keys())}"
    assert callable(hooks['on_session_start']), "回调不可调用"

def test_callback_signature_compatible():
    """回调必须兼容 (session_id, model, platform, **kwargs) 签名。"""
    mod = _load()
    hooks = {}
    class MockCtx:
        def register_hook(self, name, callback): hooks[name] = callback
    mod.register(MockCtx())
    cb = hooks['on_session_start']
    sig = inspect.signature(cb)
    params = list(sig.parameters.keys())
    has_var_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    has_session_id = 'session_id' in params
    assert has_var_kwargs or has_session_id, \
        f"签名不兼容: {params}（需 session_id 或 **kwargs）"

def test_trigger_reload_calls_discover_mcp_tools():
    """_trigger_reload() 必须调用 discover_mcp_tools()（主进程内，非 subprocess）。"""
    mod = _load()
    assert hasattr(mod, '_trigger_reload'), "缺少 _trigger_reload()"
    assert callable(mod._trigger_reload), "_trigger_reload 不可调用"

    # 验证 _trigger_reload 调用的是 tools.mcp_tool.discover_mcp_tools，
    # 而非 subprocess 或其他错误路径
    with patch.object(mod, 'discover_mcp_tools') as mock_discover:
        mod._trigger_reload()
        mock_discover.assert_called_once()

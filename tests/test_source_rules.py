"""源码约定（静态检查）：不跑应用、只读源码 —— 用 AST 查「写路由必须自己 commit」（#86）"""

import ast
from pathlib import Path

# 【注意】：这是源码检查，不是行为测试 —— 它拦的是「四道门都看不见的那类错」
#   （忘了 commit 时，get_db 的收尾提交会悄悄救回来，见决策 38）
_APP_PY = Path(__file__).resolve().parents[1] / "src" / "app" / "api" / "app.py"

# 会改库的 HTTP 方法（GET 不算：只读路由不需要提交）
_WRITE_METHODS = {"post", "patch", "put", "delete"}

# 允许「不 commit」的写路由白名单：它们确实不写库
_READ_ONLY_ROUTES = {"/v1/chat"}


def _write_routes(tree: ast.Module) -> dict[tuple[str, str], ast.AST]:
    """收集 @app.<post|patch|put|delete>("路径") 装饰的函数：(方法, 路径) -> 函数节点

    【注意】：键必须含方法 —— DELETE 与 PATCH 用的是【同一个路径】，
        只按路径做键会让后一个覆盖前一个，漏掉其中一个的检查（实测踩到）
    """
    routes: dict[tuple[str, str], ast.AST] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            # 只认 app.post / app.patch / … 这种形态（不认 app.router.post）
            if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)):
                continue
            if func.value.id != "app" or func.attr not in _WRITE_METHODS:
                continue
            if not dec.args:
                continue
            first = dec.args[0]
            # 路径必须是字面量，否则这里看不懂（本项目全部是字面量）
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                routes[(func.attr, first.value)] = node
    return routes


def _awaits_commit(node: ast.AST) -> bool:
    """函数体（含内部嵌套的生成器 / 局部函数）里有没有 await <x>.commit()"""
    for child in ast.walk(node):
        if not isinstance(child, ast.Await):
            continue
        call = child.value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute):
            if call.func.attr == "commit":
                return True
    return False


def test_every_write_route_commits_before_returning() -> None:
    """回归 #86：写路由必须自己 commit —— 否则 #54 的「报 201 但没落盘」会悄悄回来"""
    tree = ast.parse(_APP_PY.read_text(encoding="utf-8"))
    routes = _write_routes(tree)
    # 【注意】：先断言「找得到路由」—— 否则匹配规则失效时这条用例会假绿
    assert routes, "没解析到任何写路由：AST 匹配规则可能已过时（先修这条用例本身）"

    missing = [
        f"{method.upper()} {path}"
        for (method, path), node in routes.items()
        if path not in _READ_ONLY_ROUTES and not _awaits_commit(node)
    ]
    assert missing == [], f"这些写路由没有 await db.commit()：{sorted(missing)}"


def test_read_only_whitelist_has_no_stale_entry() -> None:
    """白名单本身也会过期：路由改名 / 删掉之后，白名单必须跟着清"""
    routes = _write_routes(ast.parse(_APP_PY.read_text(encoding="utf-8")))
    stale = _READ_ONLY_ROUTES - {path for _, path in routes}
    assert stale == set(), f"白名单里的这些路由已经不存在了：{sorted(stale)}"

"""
程序入口：把 config / schemas 串起来的"组合层"

职责边界（重要）：
  定义配置   -> config.py
  定义数据形状 -> schemas.py
  决定执行流程 -> 本文件
"""

# asyncio：标准库，提供"事件循环"——把协程真正跑起来的那个调度员
import asyncio

# sys：标准库，和解释器/系统打交道；本文件只用它的 sys.argv（命令行参数列表）
import sys

# from 包.模块 import 名字：只把 settings 这一个名字拿进来
# settings 在 config.py 里已实例化好（模块级单例），这里不能也不该再 Settings() 一次，
# 否则会出现"两份配置"，改了 .env 只有一份会生效
from app.config import settings

# 只 import 用得到的 3 个名字，而不是 import 整个 app.schemas
# 好处：一眼看出本文件依赖了哪几个契约，也没有多余名字占用命名空间
from app.schemas import ChatRequest, ChatResponse, Message


# 函数名 build_demo_request 用 snake_case，动词开头 = "它做什么"
# 空括号 () = 不接收任何参数
# -> ChatRequest 是返回类型注解：写给人和 mypy 看，运行时不强制转换
def build_demo_request() -> ChatRequest:
    """造一个演示请求：离线、不联网、不花钱。"""
    # return 后面直接构造对象：调用 Pydantic 模型的 __init__ 会顺手做校验，
    # 字段不合法（比如 role 拼错）会抛 ValidationError，不用自己写 if 判断
    return ChatRequest(
        # messages= 是【关键字参数】：左边是 schemas.py 里的字段名，拼错会报错
        # 右边 [...] 是列表字面量，元素是两条 Message 实例
        messages=[
            Message(role="system", content="你是一个简洁的中文助手。"),
            Message(role="user", content="用一句话解释什么是 FastAPI。"),
        ]
        # 末尾这个逗号叫"尾随逗号"：多行写法里加上它，
        # 以后增删一行只改一行，diff 干净（ruff format 也会保留它）
    )


def echo(request: ChatRequest) -> ChatResponse:
    """占位实现：把最后一条消息原样回显（真实的模型调用留给阶段 1）。"""
    # request.messages 是属性访问：Pydantic 实例的字段就是普通属性
    # [-1] 是负索引 = 从后往前数第 1 个 = 最后一条（真实对话里最后一条就是用户当前的问题）
    last = request.messages[-1]
    # 两个关键字参数对应 ChatResponse 的字段（写的顺序和字段定义顺序无关）
    # model=request.model：请求用了哪个模型，响应就如实回报哪个模型
    return ChatResponse(content=last.content, model=request.model)


# async def 定义的是【协程函数】：调用它不会执行函数体，只返回一个协程对象
# list[str] 是"字符串列表"注解（Python 3.9+ 可直接这样写，不必写 List[str]）
# -> int：返回整数，这里当【退出码】用 —— 0 = 成功，非 0 = 失败
async def main(argv: list[str]) -> int:
    """异步入口。argv 现在用不上，0.28b 的 ping 分支会用到它。"""
    request = build_demo_request()  # 同步函数：直接调用，不需要 await
    response = echo(request)  # 同上，纯计算、没有 IO 等待

    # f"" 是 f-string：{} 里的表达式会被求值并替换成文本
    # settings.app_name 是属性链：settings 对象的 app_name 字段（值来自 .env 或默认值）
    print(f"应用={settings.app_name} 环境={settings.app_env} 调试={settings.debug}")
    print(f"收到 {len(request.messages)} 条消息，模型={request.model}")
    print(f"响应内容：{response.content}")

    # 只是把数字交还给调用者 cli()，并不是"在这里结束程序"
    return 0


def cli() -> None:
    """命令行入口：把控制权交给 asyncio.run。"""
    # -> None 表示"没有返回值"；它本身是同步函数，才能被 __main__ 直接调用
    # 这一行从里往外读三层：
    #   ① sys.argv -> 形如 ['C:\\...\\main.py'] 的列表（argv[0] 是程序名，后面是用户参数）
    #   ② main(sys.argv) -> 只是"造出协程对象"，还没执行
    #   ③ asyncio.run(...) -> 建事件循环 / 跑协程 / 关闭循环，拿到那个 int 退出码
    # raise SystemExit(退出码) = 带着退出码结束程序，等价于 sys.exit(退出码)
    raise SystemExit(asyncio.run(main(sys.argv)))


# __name__ 是解释器自动给的变量：
#   直接运行本文件时它等于 "__main__"；被别人 import 时它等于 "app.main"
# 所以下面这句保证："被 import 时不会把程序跑一遍"
if __name__ == "__main__":
    cli()

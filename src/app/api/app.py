"""
FastAPI 应用对象：本项目对外的 HTTP 服务入口

为什么不写进 main.py:
    main.py 是工程基础阶段的【命令行程序】（跑完即退出）；
    本文件是【常驻服务】的应用对象，两者生命周期与职责都不同
"""

from fastapi import FastAPI

# app 就是 uvicorn 要托管的那个对象
# 命令行里写 app.api.app:app 的读法：包 app -> 子包 api -> 模块 app -> 里面的变量 app
app = FastAPI(
    title="llm-service",
    description="LLM 应用后端（学习项目，阶段 1）",
    version="0.1.0",
)


# @ 开头的是 Python 【装饰器】（Decorator）语法
# 装饰器本质上是一个函数，它接收一个函数作为参数，并返回一个新的函数或者原函数
# 用来在不修改原函数代码的情况下，给函数增强或者注册功能
#
# 具体地，@app.get("/health") 把下面的函数【注册】为一条路由
# 本处含义：把下面的函数【注册】成"当有人用 GET 请求 /health 时就调用它"
# 装饰器在这里起的作用：往路由表里登记一行
@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查：最轻的接口，用来确认【服务活着】"""
    # 部署后 Docker / 负载均衡 会定期打这个接口来判断实例是否可用
    return {"status": "ok"}

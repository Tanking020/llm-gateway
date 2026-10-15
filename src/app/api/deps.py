"""
依赖注入的集中地：把 [接口需要用到的资源] 做成可复用、可替换的依赖

依赖注入：接口函数不自己去拿它需要的东西，而是在参数里"声明"我需要一个配置对象，
然后由框架负责把它送进来。deps.py 就是所有这类"声明"的集中存放处

为什么单独一个文件：
    依赖会被多个路由共用：全写在 app.py 里会让路由文件越来越臃肿
"""

from typing import Annotated

from fastapi import Depends

from app.config import Settings, settings


def get_settings() -> Settings:
    """
    提供全局配置对象

    做成依赖的意义：测试时可以用 app.dependency_overrides 把它替换成
    假配置，不必去改 .env，也不必 mock 模块
    """
    return settings


# 类型别名
SettingsDep = Annotated[Settings, Depends(get_settings)]

# -*- coding: utf-8 -*-


import operator
import traceback
from collections.abc import Callable
from typing import Any
from typing import Optional
from typing import overload

from mcdreforged.command.builder.common import CommandContext
from mcdreforged.command.command_source import CommandSource
from mcdreforged.command.command_source import PlayerCommandSource
from mcdreforged.minecraft.rtext.text import RTextBase
from mcdreforged.permission.permission_level import PermissionLevel
from mcdreforged.permission.permission_level import PermissionLevelItem
from mcdreforged.permission.permission_level import PermissionParam

from .cost_strategy import Command
from .cost_strategy import InsufficientExperienceError
from .cost_strategy import QuantitativeInsufficientResourcesError
from .helper import h


@overload
def suppress(
        *,
        exception: type[BaseException] | tuple[type[BaseException], ...] = Exception
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    ...


@overload
def suppress(
        func: Optional[Callable[..., Any]],
        *,
        exception: type[BaseException] | tuple[type[BaseException], ...] = Exception
) -> Callable[..., Any]:
    ...


def suppress(
        func: Optional[Callable[..., Any]] = None,
        *,
        exception: type[BaseException] | tuple[type[BaseException], ...] = Exception
) -> Callable[[Callable[..., Any]], Callable[..., Any]] | Callable[..., Any]:
    """
    捕获意料内的错误并提供合理的反馈

    :param func: 待包装函数
    :type func: Optional[Callable[..., Any]]
    :param exception: 意料内的错误类型
    :type exception: type[BaseException] | tuple[type[BaseException], ...]
    """

    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(source: CommandSource, context: CommandContext, *args: Any, **kwargs: Any) -> Any:
            try:
                return f(source, context, *args, **kwargs)
            except QuantitativeInsufficientResourcesError as err:
                fmt_kwargs: dict[str, Any] = {
                    "available": err.available,
                    "required": err.required,
                }
                if isinstance(err, InsufficientExperienceError):
                    fmt_kwargs["strategy"] = h.crtr(f"unit.{err.resource_type}.{err.strategy}")

                source.reply(h.prtr(f"message.failure.cost.{err.resource_type}", **fmt_kwargs))
            except exception as err:
                traceback.print_exception(err)
                source.reply(h.prtr("message.failure.unknown"))
            return None

        return wrapper

    return decorator if func is None else decorator(func)


def execute_commands(player: str, commands: list[Command]) -> None:
    """
    以任意身份批量执行命令

    .. note::
       此函数默认采用 ``execute as <player> at @s run`` 形式执行命令，因此命令中可以放心使用 ``@s`` 和 ``~``

    :param player: 玩家名/选择器
    :type player: str
    :param commands: 命令
    :type commands: list[Command]
    """
    for cmd in commands:
        h.server.execute(f"execute as {player} at @s run {cmd}")


type AnyPermission = PermissionParam | PermissionLevelItem


def permission_checker(
        permission: AnyPermission,
        comparator: Callable[[int, int], bool] = operator.ge
) -> tuple[Callable[[CommandSource], bool], Callable[[], RTextBase]]:
    permission = permission if isinstance(permission, PermissionLevelItem) else PermissionLevel.from_value(permission)

    def checker(src: CommandSource) -> bool:
        return comparator(
            src.get_permission_level(),
            permission.level  # type: ignore[union-attr]
        )

    return checker, lambda: h.prtr("message.failure.no_permission")


type AnyPermissionGetter = Callable[[], AnyPermission]


def permission_check_wrapper(
        permission: AnyPermissionGetter | tuple[AnyPermissionGetter, ...],
        comparator: Callable[[int, int], bool] = operator.ge
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    权限检查装饰器

    :param permission: 权限获取函数，用于动态获取权限
    :type permission:
       Callable[[], PermissionParam | PermissionLevelItem]
       | tuple[Callable[[], PermissionParam | PermissionLevelItem], ...]
    :param comparator: 比较器
    :type comparator: Callable[[int, int], bool]
    """
    permissions: tuple[AnyPermissionGetter, ...] = permission if isinstance(permission, tuple) else (permission,)

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(source: CommandSource, context: CommandContext, *args: Any, **kwargs: Any) -> Any:
            if not any((check_result := permission_checker(perm(), comparator))[0](source) for perm in permissions):
                source.reply(check_result[1]())
                return None
            return func(source, context, *args, **kwargs)

        return wrapper

    return decorator


def player_only(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    执行来源限制为玩家
    """

    def wrapper(source: CommandSource, context: CommandContext, *args: Any, **kwargs: Any) -> Any:
        if not isinstance(source, PlayerCommandSource):
            source.reply(h.prtr("message.failure.not_player"))
            return None
        return func(source, context, *args, **kwargs)

    return wrapper


def get_labels(
        labels: dict[str | None, dict[str, Any]],
        player_name: Optional[str] = None
) -> tuple[set[str], set[str]]:
    """
    获取标签

    :param labels: 标签表
    :type labels: dict[str | None, dict[str, Any]]
    :param player_name: 玩家名
    :type player_name: Optional[str]

    :return: 全局标签，玩家标签
    :rtype: tuple[set[str], set[str]]
    """
    return set(labels.get(None, {})), set() if player_name is None else set(labels.get(player_name, {}))


def get_label_value[T](
        labels: dict[str | None, dict[str, T]],
        label_name: str,
        player_name: Optional[str] = None,
) -> T | None:
    """
    获取标签值

    :param labels: 标签表
    :type labels: dict[str | None, dict[str, T]]
    :param label_name: 标签名
    :type label_name: str
    :param player_name: 玩家名
    :type player_name: Optional[str]

    :return: 标签值
    :rtype: T | None
    """
    return labels.get(player_name, {}).get(label_name)


__all__ = (
    "suppress",
    "execute_commands",
    "AnyPermission",
    "permission_checker",
    "AnyPermissionGetter",
    "permission_check_wrapper",
    "player_only",
    "get_labels",
    "get_label_value",
)

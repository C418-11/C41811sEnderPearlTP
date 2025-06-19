# -*- coding: utf-8 -*-


import operator
import traceback
from collections.abc import Callable
from collections.abc import Iterator
from dataclasses import dataclass
from functools import wraps
from typing import Any
from typing import Optional
from typing import TypedDict
from typing import cast
from typing import overload

from mcdreforged.command.builder.common import CommandContext
from mcdreforged.command.command_source import CommandSource
from mcdreforged.command.command_source import PlayerCommandSource
from mcdreforged.minecraft.rtext.text import RTextBase
from mcdreforged.permission.permission_level import PermissionLevel
from mcdreforged.permission.permission_level import PermissionLevelItem
from mcdreforged.permission.permission_level import PermissionParam
from mcdreforged.utils import misc_utils
from mypy_extensions import VarArg

from .cost_strategy import Command
from .cost_strategy import CostStrategy
from .cost_strategy import InsufficientExperienceError
from .cost_strategy import QuantitativeInsufficientResourcesError
from .helper import h
from .plugins_api import minecraft_data_api


@overload
def suppress[T, **P](
        *,
        exception: type[BaseException] | tuple[type[BaseException], ...] = Exception
) -> Callable[[Callable[P, T]], Callable[P, T | None]]:
    ...


@overload
def suppress[T, **P](
        func: Callable[P, T],
        *,
        exception: type[BaseException] | tuple[type[BaseException], ...] = Exception
) -> Callable[P, T | None]:
    ...


def suppress[T, **P](
        func: Optional[Callable[P, T]] = None,
        *,
        exception: type[BaseException] | tuple[type[BaseException], ...] = Exception
) -> Callable[[Callable[P, T]], Callable[P, T | None]] | Callable[P, T | None]:
    """
    捕获意料内的错误并提供合理的反馈

    :param func: 待包装函数
    :type func: Optional[Callable[..., Any]]
    :param exception: 意料内的错误类型
    :type exception: type[BaseException] | tuple[type[BaseException], ...]
    """

    def decorator(f: Callable[P, T | None]) -> Callable[P, T | None]:
        @wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            source: CommandSource = args[0]  # type: ignore[assignment]
            try:
                return f(*args, **kwargs)
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

        return misc_utils.copy_signature(wrapper, f)

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
type PermissionChecker = Callable[[CommandSource], bool]
type CheckFailureMessageGetter = Callable[[], RTextBase]


def permission_checker(
        permission: AnyPermission,
        comparator: Callable[[int, int], bool] = operator.ge
) -> tuple[PermissionChecker, CheckFailureMessageGetter]:
    permission = permission if isinstance(permission, PermissionLevelItem) else PermissionLevel.from_value(permission)

    def checker(src: CommandSource) -> bool:
        return comparator(
            src.get_permission_level(),
            permission.level  # type: ignore[union-attr]
        )

    return checker, lambda: h.prtr("message.failure.no_permission")


type AnyPermissionGetter = Callable[[], AnyPermission]
type TaskFuncWithPermission = Callable[[CommandSource, CommandContext, dict[str, bool], VarArg(Any)], None]
type TaskFunc = Callable[[CommandSource, CommandContext], None]


@overload
def permission_check_wrapper[T, **P](
        permission: AnyPermissionGetter | tuple[AnyPermissionGetter, ...],
        comparator: Callable[[int, int], bool] = operator.ge
) -> Callable[[Callable[P, T]], Callable[P, T | None]]:
    ...


@overload
def permission_check_wrapper(
        permission: dict[str, AnyPermissionGetter],
        comparator: Callable[[int, int], bool] = operator.ge
) -> Callable[[TaskFuncWithPermission], TaskFunc]:
    ...


def permission_check_wrapper(
        permission: AnyPermissionGetter | tuple[AnyPermissionGetter, ...] | dict[str, AnyPermissionGetter],
        comparator: Callable[[int, int], bool] = operator.ge
) -> Callable[[TaskFunc | TaskFuncWithPermission], TaskFunc]:
    """
    权限检查装饰器

    :param permission: 权限获取函数，用于动态获取权限
    :type permission:
       Callable[[], PermissionParam | PermissionLevelItem]
       | tuple[Callable[[], PermissionParam | PermissionLevelItem], ...]
    :param comparator: 比较器
    :type comparator: Callable[[int, int], bool]
    """
    permissions: dict[str, AnyPermissionGetter]
    if isinstance(permission, dict):
        permissions = permission
    elif isinstance(permission, tuple):
        permissions = {str(i): getter for i, getter in enumerate(permission)}
    else:
        permissions = {'': permission}

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(source: CommandSource, context: CommandContext, *args: Any, **kwargs: Any) -> Any:
            checkers: dict[str, tuple[PermissionChecker, CheckFailureMessageGetter]] = {
                perm: permission_checker(permissions[perm](), comparator) for perm in permissions
            }
            check_result: dict[str, bool] = {perm: checkers[perm][0](source) for perm in permissions}
            check_failures: Iterator[RTextBase] = iter(
                checkers[perm][1]() for perm in permissions if not check_result[perm]
            )
            if not any(check_result.values()):
                source.reply(next(check_failures))
                return None

            if isinstance(permission, dict):
                args = (check_result, *args)
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


class Permission(TypedDict):
    without_arg: bool
    with_arg: bool


def muti_permission(without_arg: AnyPermissionGetter, with_arg: AnyPermissionGetter) -> dict[str, AnyPermissionGetter]:
    return dict(without_arg=without_arg, with_arg=with_arg)


def check_optional_arg_permission(optional_arg: str) -> Callable[[TaskFunc], TaskFuncWithPermission]:
    def decorator(func: TaskFunc) -> TaskFuncWithPermission:
        @wraps(func)
        def wrapper(
                source: CommandSource,
                context: CommandContext,
                permission: dict[str, bool],
                *args: Any, **kwargs: Any
        ) -> None:
            permission = cast(Permission, permission)
            with_arg = context.get(optional_arg) is not None
            if with_arg and not permission["with_arg"]:
                source.reply(h.prtr("message.failure.no_permission"))
                return
            elif not (with_arg or permission["without_arg"]):
                source.reply(h.prtr("message.failure.no_permission"))
                return
            # noinspection PyArgumentList
            func(source, context, *args, **kwargs)

        return wrapper

    return decorator


def tp_player2player(
        reply: Callable[[str | RTextBase], None],
        cost_strategy: CostStrategy,
        player: str,
        target: str
) -> None:
    """
    玩家传送到玩家

    :param reply: 回复函数
    :type reply: Callable[[str | RTextBase], None]
    :param cost_strategy: 扣费策略
    :type cost_strategy: CostStrategy
    :param player: 玩家
    :type player: str
    :param target: 目标玩家
    :type target: str
    """
    if player == target:
        reply(h.prtr("message.failure.tp_self"))
        return

    # 获取玩家信息
    end = minecraft_data_api.get_resource_state(target)
    resources = minecraft_data_api.get_resource_state(player)
    if end is None or resources is None:
        reply(h.prtr("message.failure.unknown"))
        return

    # 计算消耗命令
    commands = cost_strategy(resources.position, end.position, resources)
    execute_commands(player, commands)

    # 执行传送
    h.server.execute(f"tp {player} {target}")
    reply(h.prtr("message.success.to_player", target=target))


@dataclass(eq=False)
class TeleportRequest:
    from_player: str
    to_player: str
    cost_strategy: CostStrategy
    timeout: float

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, type(self)):
            return self.from_player == other.from_player and self.to_player == other.to_player
        if isinstance(other, tuple):
            return self.from_player == other[0] and self.to_player == other[1]
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.from_player, self.to_player))


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
    "Permission",
    "muti_permission",
    "check_optional_arg_permission",
    "tp_player2player",
    "TeleportRequest",
)

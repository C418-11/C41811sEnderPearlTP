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
from mcdreforged.permission.permission_level import PermissionLevelItem
from mcdreforged.permission.permission_level import PermissionParam

from .command_nodes import permission_checker
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
    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(server: CommandSource, context: CommandContext, *args: Any, **kwargs: Any) -> Any:
            try:
                return f(server, context, *args, **kwargs)
            except QuantitativeInsufficientResourcesError as err:
                fmt_kwargs: dict[str, Any] = {
                    "available": err.available,
                    "required": err.required,
                }
                if isinstance(err, InsufficientExperienceError):
                    fmt_kwargs["strategy"] = h.crtr(f"unit.{err.resource_type}.{err.strategy}")

                server.reply(h.prtr(f"message.failure.cost.{err.resource_type}", **fmt_kwargs))
            except exception as err:
                traceback.print_exception(err)
                server.reply(h.prtr("message.failure.unknown"))
            return None

        return wrapper

    return decorator if func is None else decorator(func)


def execute_commands(player: str, commands: list[Command]) -> None:
    for cmd in commands:
        h.server.execute(f"execute as {player} at @s run {cmd}")


def permission_check_wrapper(
        permission: Callable[[], PermissionParam | PermissionLevelItem],
        comparator: Callable[[int, int], bool] = operator.ge
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(server: CommandSource, context: CommandContext, *args: Any, **kwargs: Any) -> Any:
            if not (check_result := permission_checker(permission(), comparator))[0](server):
                server.reply(check_result[1]())
                return None
            return func(server, context, *args, **kwargs)

        return wrapper

    return decorator


def player_only(func: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(server: CommandSource, context: CommandContext, *args: Any, **kwargs: Any) -> Any:
        if not isinstance(server, PlayerCommandSource):
            server.reply(h.prtr("message.failure.not_player"))
            return None
        return func(server, context, *args, **kwargs)

    return wrapper


__all__ = (
    "suppress",
    "execute_commands",
    "permission_check_wrapper",
    "player_only",
)

# -*- coding: utf-8 -*-


import contextlib
import operator
import traceback
from collections.abc import Callable
from collections.abc import Generator
from types import ModuleType
from typing import Any

from C41811.Config.utils import Ref  # type: ignore[attr-defined]
from mcdreforged.api.decorator import new_thread
from mcdreforged.command.builder.common import CommandContext
from mcdreforged.command.builder.tools import SimpleCommandBuilder
from mcdreforged.command.command_source import CommandSource
from mcdreforged.command.command_source import PlayerCommandSource
from mcdreforged.permission.permission_level import PermissionLevelItem
from mcdreforged.permission.permission_level import PermissionParam
from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface

from .command_nodes import HomeName
from .command_nodes import PlayerName
from .command_nodes import WaypointName
from .command_nodes import permission_checker
from .config import Config
from .cost_strategy import Command
from .cost_strategy import CostStrategy
from .cost_strategy import InsufficientExperienceError
from .cost_strategy import QuantitativeInsufficientResourcesError
from .cost_strategy import Vec3
from .helper import h
from .helper import initialize as init_helper
from .plugins_api import initialize as init_api
from .plugins_api import minecraft_data_api


def _permission_getter(getter: Callable[[], PermissionLevelItem | None]) -> Callable[[], PermissionLevelItem]:
    return lambda: (getter() or Config.Permission)


TP2PLAYER_PERM = _permission_getter(lambda: Config.TeleportToPlayer.Permission)
TP2HOME_PERM = _permission_getter(lambda: Config.TeleportToHome.Permission)
TP2WAYPOINT_PERM = _permission_getter(lambda: Config.TeleportToWaypoint.Permission)


@contextlib.contextmanager
def suppress(
        server: CommandSource,
        exception: type[BaseException] | tuple[type[BaseException], ...] = Exception
) -> Generator[None, Any, None]:
    try:
        yield
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


def _execute_commands(player: str, commands: list[Command]) -> None:
    for cmd in commands:
        h.server.execute(f"execute as {player} at @s run {cmd}")


def _permission_check_wrapper(
        permission: Callable[[], PermissionParam | PermissionLevelItem],
        comparator: Callable[[int, int], bool] = operator.ge
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(server: CommandSource, *args: Any, **kwargs: Any) -> Any:
            if not (check_result := permission_checker(permission(), comparator))[0](server):
                server.reply(check_result[1]())
                return None
            return func(server, *args, **kwargs)

        return wrapper

    return decorator


def _player_only(func: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(server: CommandSource, *args: Any, **kwargs: Any) -> Any:
        if not isinstance(server, PlayerCommandSource):
            server.reply(h.prtr("message.failure.not_player"))
            return None
        return func(server, *args, **kwargs)

    return wrapper


@new_thread("tp2player")  # type: ignore[misc]
@_permission_check_wrapper(TP2PLAYER_PERM)
@_player_only
def tp2player(server: PlayerCommandSource, context: CommandContext) -> None:
    player = server.player
    target = context["player"]

    if player == target:
        server.reply(h.prtr("message.failure.tp_self"))
        return

    with suppress(server):
        # 获取玩家坐标
        start = minecraft_data_api.get_player_coordinate(player)
        end = minecraft_data_api.get_player_coordinate(target)
        resources = minecraft_data_api.get_resource_state(player)

        if start is None or end is None or resources is None:
            server.reply(h.prtr("message.failure.unknown"))
            return

        # 计算消耗命令
        player_cost_strategy: CostStrategy = (Config.TeleportToPlayer.CostStrategy or Config.CostStrategy)
        commands = player_cost_strategy(start, end, resources)
        _execute_commands(player, commands)

        # 执行传送
        h.server.execute(f"tp {player} {target}")
        server.reply(h.prtr("message.success.to_player", target=target))


HOMES: dict[str | None, dict[str, Vec3]] = {}
WAYPOINTS: dict[str | None, dict[str, Vec3]] = {}


@new_thread("tp2home")  # type: ignore[misc]
@_permission_check_wrapper(TP2HOME_PERM)
@_player_only
def tp2home(server: PlayerCommandSource, context: CommandContext) -> None:
    ...  # todo implement


@new_thread("tp2waypoint")  # type: ignore[misc]
@_permission_check_wrapper(TP2WAYPOINT_PERM)
@_player_only
def tp2waypoint(server: PlayerCommandSource, context: CommandContext) -> None:
    ...  # todo implement


def _register_commands() -> None:
    def _help(src: CommandSource) -> None:
        src.reply(h.prtr("help.teleport"))

        if permission_checker(TP2PLAYER_PERM())[0](src):
            src.reply(h.prtr("help.usage.to_player"))
        if permission_checker(TP2HOME_PERM())[0](src):
            src.reply(h.prtr("help.usage.to_home"))
        if permission_checker(TP2WAYPOINT_PERM())[0](src):
            src.reply(h.prtr("help.usage.to_waypoint"))

    builder = SimpleCommandBuilder()  # type: ignore[no-untyped-call]
    builder.arg("player", PlayerName)
    builder.arg("home", lambda name: HomeName(name, labels=Ref(HOMES)))
    builder.arg("waypoint", lambda name: WaypointName(name, labels=Ref(WAYPOINTS)))

    builder.command("!!tp", _help)
    if Config.TeleportToPlayer.Enabled:
        builder.command(Config.TeleportToPlayer.Syntax, tp2player)
    if Config.TeleportToHome.Enabled:
        builder.command(Config.TeleportToHome.Syntax, tp2home)
    if Config.TeleportToWaypoint.Enabled:
        builder.command(Config.TeleportToWaypoint.Syntax, tp2waypoint)

    for cmd in builder.build():
        h.register_command("help.help", cmd)  # type: ignore[arg-type]


def on_load(server: PluginServerInterface, _prev_module: ModuleType) -> None:
    init_helper(server)
    h.translate_prefix = h.crtr("prefix")
    init_api(server)
    Config.initialize()

    _register_commands()

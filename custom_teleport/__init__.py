# -*- coding: utf-8 -*-


import contextlib
import traceback
from collections.abc import Generator
from functools import partial
from types import ModuleType
from typing import Any

from mcdreforged.api.decorator import new_thread
from mcdreforged.command.builder.common import CommandContext
from mcdreforged.command.builder.tools import SimpleCommandBuilder
from mcdreforged.command.command_source import CommandSource
from mcdreforged.command.command_source import PlayerCommandSource
from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface

from .command_nodes import PermissionLiteral as PermLiteral
from .command_nodes import PlayerName
from .command_nodes import permission_checker
from .config import Config
from .cost_strategy import Command
from .cost_strategy import CostStrategy
from .cost_strategy import InsufficientExperienceError
from .cost_strategy import QuantitativeInsufficientResourcesError
from .helper import h
from .helper import initialize as init_helper
from .plugins_api import initialize as init_api
from .plugins_api import minecraft_data_api


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


@new_thread("tp2player")  # type: ignore
def tp2player(server: CommandSource, context: CommandContext) -> None:
    if not isinstance(server, PlayerCommandSource):
        server.reply(h.prtr("message.failure.not_player"))
        return

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


def on_load(server: PluginServerInterface, _prev_module: ModuleType) -> None:
    init_helper(server)
    h.translate_prefix = h.crtr("prefix")
    init_api(server)
    Config.initialize()

    def _help(src: CommandSource) -> None:
        src.reply(h.prtr("help.teleport"))

        tp2player_perm = Config.TeleportToPlayer.Permission or Config.Permission
        if permission_checker(tp2player_perm)[0](src):
            src.reply(h.prtr("help.usage.to_player"))

    builder = SimpleCommandBuilder()  # type: ignore[no-untyped-call]  # todo configable commands
    builder.literal("!!tp", partial(PermLiteral, permission=Config.Permission))
    builder.command("!!tp", _help)
    builder.command("!!tp <player>", tp2player)
    builder.arg("player", PlayerName)

    for cmd in builder.build():
        h.register_command("help.help", cmd)  # type: ignore[arg-type]

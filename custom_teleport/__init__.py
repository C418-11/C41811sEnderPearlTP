# -*- coding: utf-8 -*-


import contextlib
import traceback
from types import ModuleType

from mcdreforged.api.decorator import new_thread
from mcdreforged.command.builder.common import CommandContext
from mcdreforged.command.command_source import CommandSource
from mcdreforged.command.command_source import PlayerCommandSource
from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface

from .command_nodes import PermissionLiteral as PermLiteral
from .command_nodes import PlayerName
from .config import Config
from .cost_strategy import Command
from .cost_strategy import CostStrategy
from .cost_strategy import InsufficientExperienceError
from .cost_strategy import InsufficientItemsError
from .helper import h
from .helper import initialize as init_helper
from .plugins_api import initialize as init_api
from .plugins_api import minecraft_data_api


@contextlib.contextmanager
def suppress(server: CommandSource, exception: BaseException = Exception):
    try:
        yield
    except InsufficientItemsError as err:
        server.reply(h.crtr("message.failure.cost.items", available=err.available, required=err.required))
    except InsufficientExperienceError as err:
        server.reply(h.crtr(
            "message.failure.cost.experience",
            available=err.available, required=err.required, strategy=err.strategy
        ))
    except exception as err:
        traceback.print_exception(err)
        server.reply(h.crtr("message.failure.unknown"))


def _execute_commands(player: str, commands: list[Command]) -> None:
    for cmd in commands:
        h.server.execute(f"execute as {player} at @s run {cmd}")


@new_thread("tp2player")
def tp2player(server: CommandSource, context: CommandContext) -> None:
    if not isinstance(server, PlayerCommandSource):
        server.reply(h.crtr("message.failure.not_player"))
        return

    player = server.player
    target = context["target"]

    if player == target:
        server.reply(h.crtr("message.failure.tp_self"))
        return

    with suppress(server):
        # 获取玩家坐标
        start = minecraft_data_api.get_player_coordinate(player)
        end = minecraft_data_api.get_player_coordinate(target)

        # 计算消耗命令
        player_cost_strategy: CostStrategy = (Config.TeleportToPlayer.CostStrategy or Config.CostStrategy)
        commands = player_cost_strategy(start, end, minecraft_data_api.get_resource_state(player))
        _execute_commands(player, commands)

        # 执行传送
        h.server.execute(f"tp {player} {target}")
        server.reply(h.crtr("message.success.to_player", target=target))


def on_load(server: PluginServerInterface, _prev_module: ModuleType):
    init_helper(server)
    init_api(server)
    Config.initialize()

        runs(lambda src: src.reply(h.crtr("help.teleport")))
    root_cmd = PermLiteral("!!tp", permission=Config.Permission). \

    root_cmd.then(PlayerName("target").runs(tp2player))

    h.register_command("help.help", root_cmd)

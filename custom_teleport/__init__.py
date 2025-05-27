# -*- coding: utf-8 -*-


import itertools
from types import ModuleType

from C41811.Config.utils import Ref  # type: ignore[attr-defined]
from mcdreforged.api.decorator import new_thread
from mcdreforged.command.builder.common import CommandContext
from mcdreforged.command.builder.nodes.arguments import Text
from mcdreforged.command.builder.tools import SimpleCommandBuilder
from mcdreforged.command.command_source import CommandSource
from mcdreforged.command.command_source import PlayerCommandSource
from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface

from .command_nodes import HomeName
from .command_nodes import PlayerName
from .command_nodes import WaypointName
from .config import Config
from .config import SET_HOME_PERM
from .config import SET_HOME_STRATEGY
from .config import SET_HOME_USE_OPTIONAL_USAGE
from .config import SET_HOME_WITH_NAME_PERM
from .config import SET_HOME_WITH_NAME_STRATEGY
from .config import SET_WAYPOINT_PERM
from .config import TP2HOME_PERM
from .config import TP2HOME_STRATEGY
from .config import TP2HOME_USE_OPTIONAL_USAGE
from .config import TP2HOME_WITH_NAME_PERM
from .config import TP2HOME_WITH_NAME_STRATEGY
from .config import TP2PLAYER_PERM
from .config import TP2PLAYER_STRATEGY
from .config import TP2WAYPOINT_PERM
from .cost_strategy import Vec3
from .helper import h
from .helper import initialize as init_helper
from .plugins_api import initialize as init_api
from .plugins_api import minecraft_data_api
from .utils import execute_commands
from .utils import get_label_value
from .utils import get_labels
from .utils import permission_check_wrapper
from .utils import permission_checker
from .utils import player_only
from .utils import suppress


@new_thread("tp2player")  # type: ignore[misc]
@permission_check_wrapper(TP2PLAYER_PERM)
@player_only
@suppress
def tp2player(server: PlayerCommandSource, context: CommandContext) -> None:
    player = server.player
    target = context["player"]

    if player == target:
        server.reply(h.prtr("message.failure.tp_self"))
        return

    # 获取玩家信息
    start = minecraft_data_api.get_player_coordinate(player)
    end = minecraft_data_api.get_player_coordinate(target)
    resources = minecraft_data_api.get_resource_state(player)

    if start is None or end is None or resources is None:
        server.reply(h.prtr("message.failure.unknown"))
        return

    # 计算消耗命令
    player_cost_strategy = TP2PLAYER_STRATEGY()
    commands = player_cost_strategy(start, end, resources)
    execute_commands(player, commands)

    # 执行传送
    h.server.execute(f"tp {player} {target}")
    server.reply(h.prtr("message.success.to_player", target=target))


HOMES: dict[str | None, dict[str, Vec3]] = {}
WAYPOINTS: dict[str | None, dict[str, Vec3]] = {}


@new_thread("tp2home")  # type: ignore[misc]
@permission_check_wrapper(TP2HOME_PERM)
@player_only
@suppress
def tp2home(server: PlayerCommandSource, context: CommandContext) -> None:
    is_with_name = context.get("new-home") is not None

    homes = set(itertools.chain(*get_labels(HOMES, server.player)))
    try:
        home_name = next(iter(homes))
    except StopIteration:
        server.reply(h.prtr("message.failure.argument.not_found.home"))
        return
    if not is_with_name and Config.SetHome.DefaultHomeName in homes:
        home_name = Config.SetHome.DefaultHomeName

    # 获取玩家信息
    start = minecraft_data_api.get_player_coordinate(server.player)
    target = get_label_value(HOMES, home_name, server.player)
    resources = minecraft_data_api.get_resource_state(server.player)

    if target is None:
        server.reply(h.prtr("message.failure.argument.not_found.home"))
        return
    if start is None or resources is None:
        server.reply(h.prtr("message.failure.unknown"))
        return

    # 计算传送费用
    player_cost_strategy = TP2HOME_WITH_NAME_STRATEGY() if is_with_name else TP2HOME_STRATEGY()
    commands = player_cost_strategy(start, target, resources)
    execute_commands(server.player, commands)

    # 传送
    h.server.execute(f"tp {server.player} {target.x} {target.y} {target.z}")
    server.reply(h.prtr("message.success.to_home", home_name=home_name))


@new_thread("tp2waypoint")  # type: ignore[misc]
@permission_check_wrapper(TP2WAYPOINT_PERM)
@player_only
@suppress
def tp2waypoint(server: PlayerCommandSource, context: CommandContext) -> None:
    ...  # todo implement


@new_thread("set-home")  # type: ignore[misc]
@permission_check_wrapper(SET_HOME_PERM)
@player_only
@suppress
def set_home(server: PlayerCommandSource, context: CommandContext) -> None:
    is_with_name = context.get("new-home", None) is not None
    home_name = context.get("new-home", Config.SetHome.DefaultHomeName)

    has_home = home_name in set(itertools.chain(*get_labels(HOMES, server.player)))
    is_maximum = len(HOMES.get(server.player, {})) >= Config.SetHomeWithName.MaximumHomes
    if is_with_name and is_maximum and not has_home:
        server.reply(h.prtr("message.failure.too_many_homes"))
        return

    # 获取玩家信息
    start = Config.SpawnPoint
    target = minecraft_data_api.get_player_coordinate(server.player)
    resources = minecraft_data_api.get_resource_state(server.player)

    if target is None or resources is None:
        server.reply(h.prtr("message.failure.unknown"))
        return

    # 计算消耗命令
    player_cost_strategy = SET_HOME_WITH_NAME_STRATEGY() if is_with_name else SET_HOME_STRATEGY()
    commands = player_cost_strategy(start, target, resources)
    execute_commands(server.player, commands)

    # 设置家
    HOMES.setdefault(server.player, {})[home_name] = target
    server.reply(h.prtr("message.success.set_home", home_name=home_name))


@new_thread("set-waypoint")  # type: ignore[misc]
@permission_check_wrapper(SET_WAYPOINT_PERM)
@player_only
@suppress
def set_waypoint(server: PlayerCommandSource, context: CommandContext) -> None:
    ...  # todo implement


def _help(src: CommandSource) -> None:
    src.reply(h.prtr("help.teleport"))

    # ---- Player -------------------------------
    if permission_checker(TP2PLAYER_PERM())[0](src):
        src.reply(h.prtr("help.usage.to_player"))

    # ---- Home ---------------------------------
    allow_tp2home = permission_checker(TP2HOME_PERM())[0](src)
    allow_tp2home_with_name = permission_checker(TP2HOME_WITH_NAME_PERM())[0](src)

    if TP2HOME_USE_OPTIONAL_USAGE() and allow_tp2home and allow_tp2home_with_name:
        src.reply(h.prtr("help.usage.to_home_optional_name"))
    elif allow_tp2home:
        src.reply(h.prtr("help.usage.to_home"))
    elif allow_tp2home_with_name:
        src.reply(h.prtr("help.usage.to_home_with_name"))

    # ---- Set Home -----------------------------
    allow_set_home = permission_checker(SET_HOME_PERM())[0](src)
    allow_set_home_with_name = permission_checker(SET_HOME_WITH_NAME_PERM())[0](src)

    if SET_HOME_USE_OPTIONAL_USAGE() and allow_set_home and allow_set_home_with_name:
        src.reply(h.prtr("help.usage.set_home_optional_name"))
    elif allow_set_home:
        src.reply(h.prtr("help.usage.set_home"))
    elif allow_set_home_with_name:
        src.reply(h.prtr("help.usage.set_home_with_name"))

    # --- Waypoint ------------------------------
    if permission_checker(TP2WAYPOINT_PERM())[0](src):
        src.reply(h.prtr("help.usage.to_waypoint"))
    if permission_checker(SET_WAYPOINT_PERM())[0](src):
        src.reply(h.prtr("help.usage.set_waypoint"))


def _register_commands() -> None:
    builder = SimpleCommandBuilder()  # type: ignore[no-untyped-call]
    builder.arg("player", PlayerName)
    builder.arg("home", lambda name: HomeName(name, labels=Ref(HOMES)))
    builder.arg("waypoint", lambda name: WaypointName(name, labels=Ref(WAYPOINTS)))

    builder.arg("new-home", Text)
    builder.arg("new-waypoint", Text)

    builder.command("!!tp", _help)
    if Config.TeleportToPlayer.Enabled:
        builder.command(Config.TeleportToPlayer.Syntax, tp2player)
    if Config.TeleportToHome.Enabled:
        builder.command(Config.TeleportToHome.Syntax, tp2home)
    if Config.TeleportToHomeWithName.Enabled:
        builder.command(Config.TeleportToHomeWithName.Syntax, tp2home)
    if Config.TeleportToWaypoint.Enabled:
        builder.command(Config.TeleportToWaypoint.Syntax, tp2waypoint)

    if Config.SetHome.Enabled:
        builder.command(Config.SetHome.Syntax, set_home)
    if Config.SetHomeWithName.Enabled:
        builder.command(Config.SetHomeWithName.Syntax, set_home)
    if Config.SetWaypoint.Enabled:
        builder.command(Config.SetWaypoint.Syntax, set_waypoint)

    for cmd in builder.build():
        h.register_command("help.help", cmd)  # type: ignore[arg-type]


def on_load(server: PluginServerInterface, _prev_module: ModuleType) -> None:
    init_helper(server)
    h.translate_prefix = h.crtr("prefix")
    init_api(server)
    Config.initialize()

    _register_commands()

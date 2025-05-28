# -*- coding: utf-8 -*-


import dataclasses
import itertools
from collections.abc import Callable
from functools import partial
from types import ModuleType
from typing import Any

from C41811.Config.utils import Ref  # type: ignore[attr-defined]
from mcdreforged.api.decorator import new_thread
from mcdreforged.command.builder.common import CommandContext
from mcdreforged.command.builder.tools import SimpleCommandBuilder
from mcdreforged.command.command_source import CommandSource
from mcdreforged.command.command_source import PlayerCommandSource
from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface

from .command_nodes import HomeName
from .command_nodes import PlayerName
from .command_nodes import WaypointName
from .config import CommandConfig
from .config import Config
from .config import LIST_HOME_PERM
from .config import LIST_HOME_USE_OPTIONAL_USAGE
from .config import LIST_HOME_WITH_PLAYER_PERM
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
from .cost_strategy import Position
from .helper import h
from .helper import initialize as init_helper
from .plugins_api import initialize as init_api
from .plugins_api import minecraft_data_api
from .utils import AnyPermissionGetter
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
def tp2player(source: PlayerCommandSource, context: CommandContext) -> None:
    player = source.player
    target = context["player"]

    if player == target:
        source.reply(h.prtr("message.failure.tp_self"))
        return

    # 获取玩家信息
    end = minecraft_data_api.get_player_coordinate(target)
    resources = minecraft_data_api.get_resource_state(player)
    if end is None or resources is None:
        source.reply(h.prtr("message.failure.unknown"))
        return
    start = resources.position.coordinate

    # 计算消耗命令
    player_cost_strategy = TP2PLAYER_STRATEGY()
    commands = player_cost_strategy(start, end, resources)
    execute_commands(player, commands)

    # 执行传送
    h.server.execute(f"tp {player} {target}")
    source.reply(h.prtr("message.success.to_player", target=target))


HOMES: dict[str | None, dict[str, Position]] = {}
WAYPOINTS: dict[str | None, dict[str, Position]] = {}


@new_thread("tp2home")  # type: ignore[misc]
@permission_check_wrapper((TP2HOME_PERM, TP2HOME_WITH_NAME_PERM))
@player_only
@suppress
def tp2home(source: PlayerCommandSource, context: CommandContext) -> None:
    is_with_name: bool = context.get("new-home") is not None
    homes: set[str] = set(itertools.chain(*get_labels(HOMES, source.player)))

    # 检查是否有家
    try:
        home_name = next(iter(homes))
    except StopIteration:
        source.reply(h.prtr("message.failure.argument.not_found.home"))
        return
    if not is_with_name and Config.SetHome.DefaultHomeName in homes:
        home_name = Config.SetHome.DefaultHomeName

    # 获取家位置
    position = get_label_value(HOMES, home_name, source.player)
    if position is None:
        source.reply(h.prtr("message.failure.argument.not_found.home"))
        return

    # 获取玩家信息
    target = position.coordinate
    resources = minecraft_data_api.get_resource_state(source.player)
    if resources is None:
        source.reply(h.prtr("message.failure.unknown"))
        return
    start = resources.position.coordinate

    # 计算传送费用
    player_cost_strategy = TP2HOME_WITH_NAME_STRATEGY() if is_with_name else TP2HOME_STRATEGY()
    commands = player_cost_strategy(start, target, resources)
    execute_commands(source.player, commands)

    # 传送
    h.server.execute(
        f"execute in {position.dimension} run"
        f" tp {source.player} {target.x} {target.y} {target.z} {position.rotation.yaw} {position.rotation.pitch}"
    )
    source.reply(h.prtr("message.success.to_home", home=home_name))


@new_thread("tp2waypoint")  # type: ignore[misc]
@permission_check_wrapper(TP2WAYPOINT_PERM)
@player_only
@suppress
def tp2waypoint(source: PlayerCommandSource, context: CommandContext) -> None:
    ...  # todo implement


@new_thread("set-home")  # type: ignore[misc]
@permission_check_wrapper((SET_HOME_PERM, SET_HOME_WITH_NAME_PERM))
@player_only  # todo not player only
@suppress
def set_home(source: PlayerCommandSource, context: CommandContext) -> None:
    is_with_name: bool = context.get("new-home") is not None
    home_name = context.get("new-home", Config.SetHome.DefaultHomeName)

    has_home = home_name in set(itertools.chain(*get_labels(HOMES, source.player)))
    is_maximum = len(HOMES.get(source.player, {})) >= Config.SetHomeWithName.MaximumHomes
    if is_with_name and is_maximum and not has_home:
        source.reply(h.prtr("message.failure.too_many_homes"))
        return

    # 获取玩家信息
    start = Config.SpawnPoint
    resources = minecraft_data_api.get_resource_state(source.player)
    if resources is None:
        source.reply(h.prtr("message.failure.unknown"))
        return
    target = resources.position.coordinate

    # 计算消耗命令
    player_cost_strategy = SET_HOME_WITH_NAME_STRATEGY() if is_with_name else SET_HOME_STRATEGY()
    commands = player_cost_strategy(start, target, resources)
    execute_commands(source.player, commands)

    # 设置家
    HOMES.setdefault(source.player, {})[home_name] = resources.position
    source.reply(h.prtr("message.success.set_home", home=home_name))


@new_thread("set-waypoint")  # type: ignore[misc]
@permission_check_wrapper(SET_WAYPOINT_PERM)
@player_only
@suppress
def set_waypoint(source: PlayerCommandSource, context: CommandContext) -> None:
    ...  # todo implement


@new_thread("list-home")  # type: ignore[misc]
@permission_check_wrapper((LIST_HOME_PERM, LIST_HOME_WITH_PLAYER_PERM))
@suppress
def list_homes(source: CommandSource, context: CommandContext) -> None:
    is_with_player: bool = context.get("player") is not None
    player: str | None = context.get("player", getattr(source, "player", None))

    public: set[str]
    private: set[str]
    public, private = get_labels(HOMES, player)
    if not (is_with_player or public or private):  # 如果是列出自己的且自己一个家都没
        source.reply(h.prtr("message.success.list_homes.empty"))
        return
    elif is_with_player and not private:  # 如果列出别人的且别人没自己的家
        source.reply(h.prtr("message.success.list_homes.empty", player=player))
        return

    source.reply(h.prtr("message.success.list_homes.header", player=player))
    if not is_with_player:
        for home in public:
            kwargs: dict[str, Any] = {"home": home}
            position = get_label_value(HOMES, home, player)
            if position is None:
                source.reply(h.prtr("message.failure.unknown"))  # todo error message
                continue
            kwargs |= dataclasses.asdict(position.coordinate)
            kwargs |= dataclasses.asdict(position.rotation)
            kwargs["dimension"] = position.dimension
            source.reply(h.prtr("message.success.list_homes.entry.public", **kwargs))

    for home in private:
        kwargs: dict[str, Any] = {"home": home}
        position = get_label_value(HOMES, home, player)
        if position is None:
            source.reply(h.prtr("message.failure.unknown"))  # todo error message
            continue
        kwargs |= dataclasses.asdict(position.coordinate)
        kwargs |= dataclasses.asdict(position.rotation)
        kwargs["dimension"] = position.dimension
        source.reply(h.prtr("message.success.list_homes.entry.private", **kwargs))
    source.reply(h.prtr("message.success.list_homes.footer"))


def _help(source: CommandSource, _: CommandContext) -> None:
    source.reply(h.prtr("help.teleport"))

    def _show(perm: AnyPermissionGetter, translate_key: str) -> bool:
        if permission_checker(perm())[0](source):
            source.reply(h.prtr(translate_key))
            return True
        return False

    def _show_optional_usage(
            use_optional_usage: AnyPermissionGetter,
            translate_key_with_optional_usage: str,
            perm: AnyPermissionGetter,
            translate_key: str,
            perm_with_name: AnyPermissionGetter,
            translate_key_with_name: str
    ) -> bool:
        has_perm = permission_checker(perm())[0](source)
        has_perm_with_name = permission_checker(perm_with_name())[0](source)

        if use_optional_usage() and has_perm and has_perm_with_name:
            source.reply(h.prtr(translate_key_with_optional_usage))
        elif has_perm or has_perm_with_name:
            if has_perm:
                source.reply(h.prtr(translate_key))
            if has_perm_with_name:
                source.reply(h.prtr(translate_key_with_name))
        else:
            return False
        return True

    # ---- Player -------------------------------
    _show(TP2PLAYER_PERM, "help.usage.to_player")

    # ---- Home ---------------------------------
    _show_optional_usage(
        TP2HOME_USE_OPTIONAL_USAGE, "help.usage.to_home_optional_name",
        TP2HOME_PERM, "help.usage.to_home",
        TP2HOME_WITH_NAME_PERM, "help.usage.to_home_with_name",
    )

    # ---- Set Home -----------------------------
    _show_optional_usage(
        SET_HOME_USE_OPTIONAL_USAGE, "help.usage.set_home_optional_name",
        SET_HOME_PERM, "help.usage.set_home",
        SET_HOME_WITH_NAME_PERM, "help.usage.set_home_with_name",
    )

    # ---- List Homes ----------------------------
    _show_optional_usage(
        LIST_HOME_USE_OPTIONAL_USAGE, "help.usage.list_homes_optional_name",
        LIST_HOME_PERM, "help.usage.list_homes",
        LIST_HOME_WITH_PLAYER_PERM, "help.usage.list_homes_with_player",
    )

    # --- Waypoint ------------------------------
    _show(TP2WAYPOINT_PERM, "help.usage.to_waypoint")
    _show(SET_WAYPOINT_PERM, "help.usage.set_waypoint")


def _register_commands() -> None:
    builder = SimpleCommandBuilder()  # type: ignore[no-untyped-call]
    builder.arg("player", PlayerName)
    builder.arg("online-player", partial(PlayerName, require_online=True))
    builder.arg("home", partial(HomeName, labels=Ref(HOMES), require_exists=True))
    builder.arg("waypoint", partial(WaypointName, labels=Ref(WAYPOINTS), require_exists=True))

    builder.arg("new-home", partial(HomeName, labels=Ref(HOMES)))
    builder.arg("new-waypoint", partial(WaypointName, labels=Ref(WAYPOINTS)))

    def _reg(cfg: type[CommandConfig], handler: Callable[[CommandSource, CommandContext], None]) -> None:
        if cfg.Enabled:
            builder.command(cfg.Syntax, handler)

    _reg(Config.Help, _help)

    _reg(Config.TeleportToPlayer, tp2player)
    _reg(Config.TeleportToHome, tp2home)
    _reg(Config.TeleportToHomeWithName, tp2home)
    _reg(Config.TeleportToWaypoint, tp2waypoint)

    _reg(Config.SetHome, set_home)
    _reg(Config.SetHomeWithName, set_home)
    _reg(Config.SetWaypoint, set_waypoint)

    _reg(Config.ListHome, list_homes)
    _reg(Config.ListHomeWithPlayer, list_homes)

    for cmd in builder.build():
        h.register_command("help.help", cmd)  # type: ignore[arg-type]


def on_load(server: PluginServerInterface, _prev_module: ModuleType) -> None:
    init_helper(server)
    h.translate_prefix = h.crtr("prefix")
    init_api(server)
    Config.initialize()

    _register_commands()

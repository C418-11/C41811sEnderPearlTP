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
from .config import ACCEPT_TP_REQUEST_PERM
from .config import CommandConfig
from .config import Config
from .config import DENY_TP_REQUEST_PERM
from .config import HELP_PERM
from .config import LIST_HOME_PERM
from .config import LIST_HOME_USE_OPTIONAL_USAGE
from .config import LIST_HOME_WITH_PLAYER_PERM
from .config import SEND_TP_REQUEST_PERM
from .config import SEND_TP_REQUEST_STRATEGY
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
from .utils import TeleportRequest
from .utils import check_optional_arg_permission
from .utils import execute_commands
from .utils import get_label_value
from .utils import get_labels
from .utils import muti_permission as muti_perm
from .utils import permission_check_wrapper
from .utils import permission_checker
from .utils import player_only
from .utils import suppress
from .utils import tp_player2player

HOMES: dict[str | None, dict[str, Position]] = {}
"""
dict[玩家/None, dict[家名, 位置]]
"""
WAYPOINTS: dict[str | None, dict[str, Position]] = {}
TELEPORT_REQUESTS: dict[str, set[TeleportRequest]] = {}
"""
dict[被请求的玩家, 传送请求]
"""


@new_thread("tp2player")  # type: ignore[misc]
@permission_check_wrapper(TP2PLAYER_PERM)
@player_only
@suppress
def tp2player(source: PlayerCommandSource, context: CommandContext) -> None:
    player = source.player
    target = context["online-player"]

    tp_player2player(source.reply, TP2PLAYER_STRATEGY(), player, target)


@new_thread("send-tp-request")  # type: ignore[misc]
@permission_check_wrapper(SEND_TP_REQUEST_PERM)
@player_only
@suppress
def send_tp_request(source: PlayerCommandSource, context: CommandContext) -> None:
    player = source.player
    target = context["online-player"]
    if player == target:
        source.reply(h.prtr("message.failure.tp_self"))
        return
    if (player, target) in TELEPORT_REQUESTS.get(target, []):
        source.reply(h.prtr("message.failure.request_already_sent", target=target))
        return
    TELEPORT_REQUESTS.setdefault(target, set()).add(
        TeleportRequest(player, target, SEND_TP_REQUEST_STRATEGY(), Config.SendTeleportRequest.Timeout)
    )
    source.reply(h.prtr("message.success.request_sent", target=target, timeout=Config.SendTeleportRequest.Timeout))
    # noinspection SpellCheckingInspection
    h.server.execute(
        f"tellraw {player} {h.prtr("message.success.request_received", target=player).to_json_str()}",
    )


@new_thread("tp2home")  # type: ignore[misc]
@permission_check_wrapper(muti_perm(TP2HOME_PERM, TP2HOME_WITH_NAME_PERM))
@check_optional_arg_permission("home")
@player_only
@suppress
def tp2home(source: PlayerCommandSource, context: CommandContext) -> None:
    is_with_name: bool = context.get("home") is not None
    homes: set[str] = set(itertools.chain(*get_labels(HOMES, source.player)))

    # 检查是否有家
    try:
        home_name = next(iter(homes))
    except StopIteration:
        source.reply(h.prtr("message.failure.argument.not_found.home"))
        return
    if not is_with_name and Config.SetHome.DefaultHomeName in homes:
        home_name = Config.SetHome.DefaultHomeName
    elif is_with_name:
        home_name = context["home"]

    # 获取家位置
    position = get_label_value(HOMES, home_name, source.player)
    if position is None:
        source.reply(h.prtr("message.failure.argument.not_found.home"))
        return

    # 获取玩家信息
    resources = minecraft_data_api.get_resource_state(source.player)
    if resources is None:
        source.reply(h.prtr("message.failure.unknown"))
        return

    # 计算传送费用
    player_cost_strategy = TP2HOME_WITH_NAME_STRATEGY() if is_with_name else TP2HOME_STRATEGY()
    commands = player_cost_strategy(resources.position, position, resources)
    execute_commands(source.player, commands)

    # 传送
    coordinate = position.coordinate
    rotation = position.rotation
    h.server.execute(
        f"execute in {position.dimension} run"
        f" tp {source.player} {coordinate.x} {coordinate.y} {coordinate.z} {rotation.yaw} {rotation.pitch}"
    )
    translate_key = "message.success.to_home_with_name" if is_with_name else "message.success.to_home"
    source.reply(h.prtr(translate_key, home=home_name))


@new_thread("tp2waypoint")  # type: ignore[misc]
@permission_check_wrapper(TP2WAYPOINT_PERM)
@player_only
@suppress
def tp2waypoint(source: PlayerCommandSource, context: CommandContext) -> None:
    ...  # todo implement


@new_thread("set-home")  # type: ignore[misc]
@permission_check_wrapper(muti_perm(SET_HOME_PERM, SET_HOME_WITH_NAME_PERM))
@check_optional_arg_permission("new-home")
@player_only
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

    # 计算消耗命令
    player_cost_strategy = SET_HOME_WITH_NAME_STRATEGY() if is_with_name else SET_HOME_STRATEGY()
    commands = player_cost_strategy(start, resources.position, resources)
    execute_commands(source.player, commands)

    # 设置家
    HOMES.setdefault(source.player, {})[home_name] = resources.position
    translate_key = "message.success.set_home_with_name" if is_with_name else "message.success.set_home"
    source.reply(h.prtr(translate_key, home=home_name))


@new_thread("set-waypoint")  # type: ignore[misc]
@permission_check_wrapper(SET_WAYPOINT_PERM)
@player_only
@suppress
def set_waypoint(source: PlayerCommandSource, context: CommandContext) -> None:
    ...  # todo implement


@new_thread("list-home")  # type: ignore[misc]
@permission_check_wrapper(muti_perm(LIST_HOME_PERM, LIST_HOME_WITH_PLAYER_PERM))
@check_optional_arg_permission("player")
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
                source.reply(h.prtr("message.failure.unknown"))
                continue
            kwargs |= dataclasses.asdict(position.coordinate)
            kwargs |= dataclasses.asdict(position.rotation)
            kwargs["dimension"] = position.dimension
            source.reply(h.prtr("message.success.list_homes.entry.public", **kwargs))

    for home in private:
        kwargs = {"home": home}
        position = get_label_value(HOMES, home, player)
        if position is None:
            source.reply(h.prtr("message.failure.unknown"))
            continue
        kwargs |= dataclasses.asdict(position.coordinate)
        kwargs |= dataclasses.asdict(position.rotation)
        kwargs["dimension"] = position.dimension
        source.reply(h.prtr("message.success.list_homes.entry.private", **kwargs))
    source.reply(h.prtr("message.success.list_homes.footer"))


@permission_check_wrapper(HELP_PERM)
def _help(source: CommandSource, _: CommandContext, *__: Any) -> None:
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
    _show(SEND_TP_REQUEST_PERM, "help.usage.send_request")
    _show(ACCEPT_TP_REQUEST_PERM, "help.usage.accept_request")
    _show(DENY_TP_REQUEST_PERM, "help.usage.deny_request")

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
        LIST_HOME_USE_OPTIONAL_USAGE, "help.usage.list_homes_optional_player",
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
    _reg(Config.SendTeleportRequest, send_tp_request)
    _reg(Config.AcceptTeleportRequest, _help)  # todo
    _reg(Config.DenyTeleportRequest, _help)  # todo
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

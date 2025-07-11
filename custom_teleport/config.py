# -*- coding: utf-8 -*-


from collections.abc import Callable
from typing import Any
from typing import Optional

from C41811.Config import ConfigPool
from C41811.Config import FieldDefinition as FieldDef
from C41811.Config import MappingConfigData
from C41811.Config.processor.RuamelYaml import RuamelYamlSL
from mcdreforged.permission.permission_level import PermissionLevel
from mcdreforged.permission.permission_level import PermissionLevelItem

from .cost_strategy import Rotation
from .cost_strategy import CheckStrategy
from .cost_strategy import CostStrategy
from .cost_strategy import ItemConsumeStrategy
from .cost_strategy import PassStrategy
from .cost_strategy import Position
from .cost_strategy import Vec3
from .cost_strategy import create_cost_strategy
from .helper import h

type OptionalPermission = Optional[str | int]
type Real = int | float

PluginConfigPool = ConfigPool(root_path="./config")

UserPermission: str = PermissionLevel.NAMES[1]
AdminPermission: str = PermissionLevel.NAMES[2]


def _build_default_tp_cmd_cfg(
        syntax: str,
        *,
        perm: OptionalPermission = None,
        cost_strategy: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return {
        "enabled": True,
        "syntax": syntax,
        "permission": FieldDef(OptionalPermission, perm),
        "cost_strategy": FieldDef(Optional[dict[str, Any]], cost_strategy),
    }


def _build_default_cmd_cfg(syntax: str, *, perm: OptionalPermission = None) -> dict[str, Any]:
    return {
        "enabled": True,
        "syntax": syntax,
        "permission": FieldDef(OptionalPermission, perm),
    }


DEFAULT_CONFIG: dict[str, Any] = {
    "global": {
        "spawn_point": {
            "coordinate": {"x": 0, "y": 64, "z": 0},
            "rotation": {"yaw": 0, "pitch": 0},
            "dimension": "minecraft:overworld",
        },
        "permission": FieldDef(str | int, UserPermission),
        "cost_strategy": {
            "distance": {"type": "euclidean"},
            "cost": {
                "type": "linear",
                "base": FieldDef(Real, 0),
                "scale": FieldDef(Real, 1),
            },
            "consumption": {
                "type": "composite",
                "costs": [
                    {
                        "type": "hunger",
                        "pass_strategy": PassStrategy.PROPAGATE.value,
                        "check_strategy": CheckStrategy.LENIENT.value,
                    },
                    {
                        "type": "items",
                        "rate": 1 / 70,
                        "items": {
                            # 水果
                            "minecraft:apple": 6.4,
                            "minecraft:melon_slice": 3.2,

                            # 蔬菜
                            "minecraft:baked_potato": 11,
                            "minecraft:beetroot_soup": 13.2,
                            "minecraft:dried_kelp": 1.6,
                            "minecraft:mushroom_stew": 13.2,
                            # 肉类
                            "minecraft:cooked_chicken": 13.2,
                            "minecraft:cooked_cod": 11,
                            "minecraft:cooked_mutton": 15.6,
                            "minecraft:cooked_porkchop": 20.8,
                            "minecraft:cooked_rabbit": 11,
                            "minecraft:cooked_salmon": 15.6,
                            "minecraft:cooked_beef": 20.8,

                            # 甜点
                            "minecraft:bread": 11,
                            "minecraft:cake": 16.8,
                            "minecraft:cookie": 2.4,
                            "minecraft:honey_bottle": 7.2,
                            "minecraft:pumpkin_pie": 12.8,
                            "minecraft:golden_carrot": 20.4,
                        },
                        "strategy": ItemConsumeStrategy.HIGHER_FIRST.value,
                    },
                ],
            },
        },
    },
    "commands": {
        "help": _build_default_cmd_cfg("!!tp"),

        "teleport-to-player": _build_default_tp_cmd_cfg(
            "!!tp f2 <online-player>",
            perm=AdminPermission,
            cost_strategy={}
        ),
        "send-teleport-request": {
            "timeout": FieldDef(Real, 60),  # 秒
            **_build_default_tp_cmd_cfg("!!tp 2 <online-player>"),
        },
        "accept-teleport-request": _build_default_cmd_cfg("!!tp accept"),
        "deny-teleport-request": _build_default_cmd_cfg("!!tp deny"),
        "teleport-to-home": _build_default_tp_cmd_cfg("!!tp home"),
        "teleport-to-home-with-name": {
            "use-optional-usage": True,
            **_build_default_tp_cmd_cfg("!!tp home <home>"),
        },
        "teleport-to-waypoint": _build_default_tp_cmd_cfg("!!tp wp <waypoint>"),

        "set-home": {
            "default-home-name": "家",
            **_build_default_tp_cmd_cfg("!!tp set home"),
        },
        "set-home-with-name": {
            "maximum-homes": FieldDef(Real, float("inf")),
            "use-optional-usage": True,
            **_build_default_tp_cmd_cfg("!!tp set home <new-home>"),
        },
        "set-waypoint": _build_default_tp_cmd_cfg("!!tp set wp <new-waypoint>"),

        "list-home": _build_default_cmd_cfg("!!tp homes"),
        "list-home-with-player": {
            "use-optional-usage": True,
            **_build_default_cmd_cfg("!!tp homes <player>", perm=AdminPermission),
        },
    },
}

type MCD = MappingConfigData[dict[str, Any]]


class CommandConfig:
    Config: MCD

    Enabled: bool
    Syntax: str
    Permission: Optional[PermissionLevelItem] = None

    @classmethod
    def initialize(cls, config: MCD) -> None:
        cls.Config = config

        cls.Enabled = config.retrieve("enabled")
        cls.Syntax = config.retrieve("syntax")
        cls.Permission = None if (perm := config.get("permission")) is None else PermissionLevel.from_value(perm)


class CommandConfigWithCost(CommandConfig):
    CostStrategy: Optional[CostStrategy] = None

    @classmethod
    def initialize(cls, config: MCD) -> None:
        super().initialize(config)
        cls.CostStrategy = None if (strategy := config.get("cost_strategy")) is None else create_cost_strategy(strategy)


class CommandConfigWithOptionalUsage(CommandConfig):
    UseOptionalUsage: bool

    @classmethod
    def initialize(cls, config: MCD) -> None:
        super().initialize(config)
        cls.UseOptionalUsage = config.retrieve("use-optional-usage")


class Config:
    Config: MCD

    SpawnPoint: Position
    Permission: PermissionLevelItem
    CostStrategy: CostStrategy

    class Help(CommandConfig):
        ...

    class TeleportToPlayer(CommandConfigWithCost):
        ...

    class SendTeleportRequest(CommandConfigWithCost):
        Timeout: float

        @classmethod
        def initialize(cls, config: MCD) -> None:
            super().initialize(config)
            cls.Timeout = float(config.retrieve("timeout"))

    class AcceptTeleportRequest(CommandConfig):
        ...

    class DenyTeleportRequest(CommandConfig):
        ...

    class TeleportToHome(CommandConfigWithCost):
        ...

    class TeleportToHomeWithName(CommandConfigWithCost, CommandConfigWithOptionalUsage):
        ...

    class TeleportToWaypoint(CommandConfigWithCost):
        ...

    class SetHome(CommandConfigWithCost):
        DefaultHomeName: str

        @classmethod
        def initialize(cls, config: MCD) -> None:
            super().initialize(config)
            cls.DefaultHomeName = config.retrieve("default-home-name")

    class SetHomeWithName(CommandConfigWithCost, CommandConfigWithOptionalUsage):
        MaximumHomes: float  # 采用float，因为整数没有 Infinity

        @classmethod
        def initialize(cls, config: MCD) -> None:
            super().initialize(config)
            cls.MaximumHomes = float(config.retrieve("maximum-homes"))

    class SetWaypoint(CommandConfigWithCost):
        ...

    class ListHome(CommandConfig):
        ...

    class ListHomeWithPlayer(CommandConfigWithOptionalUsage):
        ...

    @classmethod
    def initialize(cls) -> None:
        RuamelYamlSL().register_to(PluginConfigPool)
        cls.Config = PluginConfigPool.require('', f"{h.pkg_name}.yaml", DEFAULT_CONFIG).check()
        # PluginConfigPool.save_all()  # todo save

        sp_rotation = Rotation(**cls.Config.retrieve("global\\.spawn_point\\.rotation"))
        sp_dimension = cls.Config.retrieve("global\\.spawn_point\\.dimension")
        sp_coordinate = Vec3(**cls.Config.retrieve("global\\.spawn_point\\.coordinate"))
        cls.SpawnPoint = Position(sp_coordinate, sp_rotation, sp_dimension)
        cls.Permission = cls.Config.retrieve("global\\.permission")
        cls.CostStrategy = create_cost_strategy(cls.Config.retrieve("global\\.cost_strategy"))

        cls.Help.initialize(cls.Config.retrieve("commands\\.help"))

        cls.TeleportToPlayer.initialize(cls.Config.retrieve("commands\\.teleport-to-player"))
        cls.SendTeleportRequest.initialize(cls.Config.retrieve("commands\\.send-teleport-request"))
        cls.AcceptTeleportRequest.initialize(cls.Config.retrieve("commands\\.accept-teleport-request"))
        cls.DenyTeleportRequest.initialize(cls.Config.retrieve("commands\\.deny-teleport-request"))
        cls.TeleportToHome.initialize(cls.Config.retrieve("commands\\.teleport-to-home"))
        cls.TeleportToHomeWithName.initialize(cls.Config.retrieve("commands\\.teleport-to-home-with-name"))
        cls.TeleportToWaypoint.initialize(cls.Config.retrieve("commands\\.teleport-to-waypoint"))

        cls.SetHome.initialize(cls.Config.retrieve("commands\\.set-home"))
        cls.SetHomeWithName.initialize(cls.Config.retrieve("commands\\.set-home-with-name"))
        cls.SetWaypoint.initialize(cls.Config.retrieve("commands\\.set-waypoint"))

        cls.ListHome.initialize(cls.Config.retrieve("commands\\.list-home"))
        cls.ListHomeWithPlayer.initialize(cls.Config.retrieve("commands\\.list-home-with-player"))


def _permission_getter(getter: Callable[[], PermissionLevelItem | None]) -> Callable[[], PermissionLevelItem]:
    return lambda: (getter() or Config.Permission)


def _strategy_getter(getter: Callable[[], CostStrategy | None]) -> Callable[[], CostStrategy]:
    return lambda: (getter() or Config.CostStrategy)


def _use_optional_usage(
        cfg_cls: type[CommandConfig],
        with_name_cfg: type[CommandConfigWithOptionalUsage],
) -> Callable[[], bool]:
    return lambda: (cfg_cls.Enabled and with_name_cfg.Enabled and with_name_cfg.UseOptionalUsage)


# ---- 权限 -------------------------------------------------
HELP_PERM = _permission_getter(lambda: Config.Help.Permission)

TP2PLAYER_PERM = _permission_getter(lambda: Config.TeleportToPlayer.Permission)
SEND_TP_REQUEST_PERM = _permission_getter(lambda: Config.SendTeleportRequest.Permission)
ACCEPT_TP_REQUEST_PERM = _permission_getter(lambda: Config.AcceptTeleportRequest.Permission)
DENY_TP_REQUEST_PERM = _permission_getter(lambda: Config.DenyTeleportRequest.Permission)
TP2HOME_PERM = _permission_getter(lambda: Config.TeleportToHome.Permission)
TP2HOME_WITH_NAME_PERM = _permission_getter(lambda: Config.TeleportToHomeWithName.Permission)
TP2WAYPOINT_PERM = _permission_getter(lambda: Config.TeleportToWaypoint.Permission)

SET_HOME_PERM = _permission_getter(lambda: Config.SetHome.Permission)
SET_HOME_WITH_NAME_PERM = _permission_getter(lambda: Config.SetHomeWithName.Permission)
SET_WAYPOINT_PERM = _permission_getter(lambda: Config.SetWaypoint.Permission)

LIST_HOME_PERM = _permission_getter(lambda: Config.ListHome.Permission)
LIST_HOME_WITH_PLAYER_PERM = _permission_getter(lambda: Config.ListHomeWithPlayer.Permission)

# ---- 成本策略 -----------------------------------------------
TP2PLAYER_STRATEGY = _strategy_getter(lambda: Config.TeleportToPlayer.CostStrategy)
SEND_TP_REQUEST_STRATEGY = _strategy_getter(lambda: Config.SendTeleportRequest.CostStrategy)
TP2HOME_STRATEGY = _strategy_getter(lambda: Config.TeleportToHome.CostStrategy)
TP2HOME_WITH_NAME_STRATEGY = _strategy_getter(lambda: Config.TeleportToHomeWithName.CostStrategy)
SET_HOME_WITH_NAME_STRATEGY = _strategy_getter(lambda: Config.SetHomeWithName.CostStrategy)
TP2WAYPOINT_STRATEGY = _strategy_getter(lambda: Config.TeleportToWaypoint.CostStrategy)

SET_HOME_STRATEGY = _strategy_getter(lambda: Config.SetHome.CostStrategy)
SET_WAYPOINT_STRATEGY = _strategy_getter(lambda: Config.SetWaypoint.CostStrategy)

# ---- 翻译 -------------------------------------------------
TP2HOME_USE_OPTIONAL_USAGE = _use_optional_usage(Config.TeleportToHome, Config.TeleportToHomeWithName)
SET_HOME_USE_OPTIONAL_USAGE = _use_optional_usage(Config.SetHome, Config.SetHomeWithName)
LIST_HOME_USE_OPTIONAL_USAGE = _use_optional_usage(Config.ListHome, Config.ListHomeWithPlayer)

__all__ = (
    # 权限
    "HELP_PERM",

    "TP2PLAYER_PERM",
    "SEND_TP_REQUEST_PERM",
    "ACCEPT_TP_REQUEST_PERM",
    "DENY_TP_REQUEST_PERM",
    "TP2HOME_PERM",
    "TP2HOME_WITH_NAME_PERM",
    "TP2WAYPOINT_PERM",

    "SET_HOME_PERM",
    "SET_HOME_WITH_NAME_PERM",
    "SET_WAYPOINT_PERM",

    "LIST_HOME_PERM",
    "LIST_HOME_WITH_PLAYER_PERM",

    # 成本策略
    "TP2PLAYER_STRATEGY",
    "SEND_TP_REQUEST_STRATEGY",
    "TP2HOME_STRATEGY",
    "TP2HOME_WITH_NAME_STRATEGY",
    "TP2WAYPOINT_STRATEGY",

    "SET_HOME_STRATEGY",
    "SET_HOME_WITH_NAME_STRATEGY",
    "SET_WAYPOINT_STRATEGY",

    # 翻译
    "TP2HOME_USE_OPTIONAL_USAGE",
    "SET_HOME_USE_OPTIONAL_USAGE",
    "LIST_HOME_USE_OPTIONAL_USAGE",

    "CommandConfig",
    "CommandConfigWithCost",
    "CommandConfigWithOptionalUsage",
    "Config",
)

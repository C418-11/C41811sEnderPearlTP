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

from .cost_strategy import CheckStrategy
from .cost_strategy import CostStrategy
from .cost_strategy import ItemConsumeStrategy
from .cost_strategy import PassStrategy
from .cost_strategy import Vec3
from .cost_strategy import create_cost_strategy
from .helper import h

type OptionalPermission = Optional[str | int]
type Real = int | float

PluginConfigPool = ConfigPool(root_path="./config")

UserPermission: str | int = PermissionLevel.NAMES[1]


def _build_default_tp_cmd_cfg(syntax: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "syntax": syntax,
        "permission": FieldDef(OptionalPermission, None),
        "cost_strategy": FieldDef(Optional[dict[str, Any]], None),
    }


DEFAULT_CONFIG: dict[str, Any] = {
    "$global": {
        "spawn_point": {"x": 0, "y": 64, "z": 0},
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
        "teleport-to-player": _build_default_tp_cmd_cfg("!!tp 2 <player>"),
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
            "maximum-homes": 1,
            "use-optional-usage": True,
            **_build_default_tp_cmd_cfg("!!tp set home <new-home>"),
        },
        "set-waypoint": _build_default_tp_cmd_cfg("!!tp set wp <new-waypoint>"),
    },
}

type MCD = MappingConfigData[dict[str, Any]]


class CommandConfig:
    Config: MCD

    Enabled: bool
    Syntax: str
    Permission: Optional[PermissionLevelItem] = None
    CostStrategy: Optional[CostStrategy] = None

    @classmethod
    def initialize(cls, config: MCD) -> None:
        cls.Config = config

        cls.Enabled = config.retrieve("enabled")
        cls.Syntax = config.retrieve("syntax")
        cls.Permission = None if (perm := config.get("permission")) is None else PermissionLevel.from_value(perm)
        cls.CostStrategy = None if (strategy := config.get("cost_strategy")) is None else create_cost_strategy(strategy)


class Config:
    Config: MCD

    SpawnPoint: Vec3
    Permission: PermissionLevelItem
    CostStrategy: CostStrategy

    class TeleportToPlayer(CommandConfig):
        ...

    class TeleportToHome(CommandConfig):
        ...

    class TeleportToHomeWithName(CommandConfig):
        UseOptionalUsage: bool

        @classmethod
        def initialize(cls, config: MCD) -> None:
            super().initialize(config)
            cls.UseOptionalUsage = config.retrieve("use-optional-usage")

    class TeleportToWaypoint(CommandConfig):
        ...

    class SetHome(CommandConfig):
        DefaultHomeName: str

        @classmethod
        def initialize(cls, config: MCD) -> None:
            super().initialize(config)
            cls.DefaultHomeName = config.retrieve("default-home-name")

    class SetHomeWithName(CommandConfig):
        MaximumHomes: float  # 采用float，因为整数没有 Infinity
        UseOptionalUsage: bool

        @classmethod
        def initialize(cls, config: MCD) -> None:
            super().initialize(config)
            cls.MaximumHomes = float(config.retrieve("maximum-homes"))
            cls.UseOptionalUsage = config.retrieve("use-optional-usage")

    class SetWaypoint(CommandConfig):
        ...

    @classmethod
    def initialize(cls) -> None:
        RuamelYamlSL().register_to(PluginConfigPool)
        cls.Config = PluginConfigPool.require('', f"{h.pkg_name}.yaml", DEFAULT_CONFIG).check()
        # PluginConfigPool.save_all()  # todo save

        cls.SpawnPoint = Vec3(**cls.Config.retrieve("$global\\.spawn_point"))
        cls.Permission = cls.Config.retrieve("$global\\.permission")
        cls.CostStrategy = create_cost_strategy(cls.Config.retrieve("$global\\.cost_strategy"))

        cls.TeleportToPlayer.initialize(cls.Config.retrieve("commands\\.teleport-to-player"))
        cls.TeleportToHome.initialize(cls.Config.retrieve("commands\\.teleport-to-home"))
        cls.TeleportToHomeWithName.initialize(cls.Config.retrieve("commands\\.teleport-to-home-with-name"))
        cls.TeleportToWaypoint.initialize(cls.Config.retrieve("commands\\.teleport-to-waypoint"))

        cls.SetHome.initialize(cls.Config.retrieve("commands\\.set-home"))
        cls.SetHomeWithName.initialize(cls.Config.retrieve("commands\\.set-home-with-name"))
        cls.SetWaypoint.initialize(cls.Config.retrieve("commands\\.set-waypoint"))


def _permission_getter(getter: Callable[[], PermissionLevelItem | None]) -> Callable[[], PermissionLevelItem]:
    return lambda: (getter() or Config.Permission)


def _strategy_getter(getter: Callable[[], CostStrategy | None]) -> Callable[[], CostStrategy]:
    return lambda: (getter() or Config.CostStrategy)


def _use_optional_usage(
        cfg_cls: type[CommandConfig],
        with_name_cfg: type[Config.TeleportToHomeWithName] | type[Config.SetHomeWithName],
) -> Callable[[], bool]:
    return lambda: (cfg_cls.Enabled and with_name_cfg.Enabled and with_name_cfg.UseOptionalUsage)


# ---- 权限 -------------------------------------------------
TP2PLAYER_PERM = _permission_getter(lambda: Config.TeleportToPlayer.Permission)
TP2HOME_PERM = _permission_getter(lambda: Config.TeleportToHome.Permission)
TP2HOME_WITH_NAME_PERM = _permission_getter(lambda: Config.TeleportToHomeWithName.Permission)
TP2WAYPOINT_PERM = _permission_getter(lambda: Config.TeleportToWaypoint.Permission)

SET_HOME_PERM = _permission_getter(lambda: Config.SetHome.Permission)
SET_HOME_WITH_NAME_PERM = _permission_getter(lambda: Config.SetHomeWithName.Permission)
SET_WAYPOINT_PERM = _permission_getter(lambda: Config.SetWaypoint.Permission)

# ---- 成本策略 -----------------------------------------------
TP2PLAYER_STRATEGY = _strategy_getter(lambda: Config.TeleportToPlayer.CostStrategy)
TP2HOME_STRATEGY = _strategy_getter(lambda: Config.TeleportToHome.CostStrategy)
TP2HOME_WITH_NAME_STRATEGY = _strategy_getter(lambda: Config.TeleportToHomeWithName.CostStrategy)
SET_HOME_WITH_NAME_STRATEGY = _strategy_getter(lambda: Config.SetHomeWithName.CostStrategy)
TP2WAYPOINT_STRATEGY = _strategy_getter(lambda: Config.TeleportToWaypoint.CostStrategy)

SET_HOME_STRATEGY = _strategy_getter(lambda: Config.SetHome.CostStrategy)
SET_WAYPOINT_STRATEGY = _strategy_getter(lambda: Config.SetWaypoint.CostStrategy)

# ---- 翻译 -------------------------------------------------
TP2HOME_USE_OPTIONAL_USAGE = _use_optional_usage(Config.TeleportToHome, Config.TeleportToHomeWithName)
SET_HOME_USE_OPTIONAL_USAGE = _use_optional_usage(Config.SetHome, Config.SetHomeWithName)

__all__ = (
    # 权限
    "TP2PLAYER_PERM",
    "TP2HOME_PERM",
    "TP2HOME_WITH_NAME_PERM",
    "TP2WAYPOINT_PERM",

    "SET_HOME_PERM",
    "SET_HOME_WITH_NAME_PERM",
    "SET_WAYPOINT_PERM",

    # 成本策略
    "TP2PLAYER_STRATEGY",
    "TP2HOME_STRATEGY",
    "TP2HOME_WITH_NAME_STRATEGY",
    "TP2WAYPOINT_STRATEGY",

    "SET_HOME_STRATEGY",
    "SET_HOME_WITH_NAME_STRATEGY",
    "SET_WAYPOINT_STRATEGY",

    # 翻译
    "TP2HOME_USE_OPTIONAL_USAGE",
    "SET_HOME_USE_OPTIONAL_USAGE",

    "Config",
)

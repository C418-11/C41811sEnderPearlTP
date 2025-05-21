# -*- coding: utf-8 -*-


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
from .cost_strategy import create_cost_strategy
from .helper import h

type OptionalPermission = Optional[str | int]
type Real = int | float

PluginConfigPool = ConfigPool(root_path=f"./config")

DEFAULT_CONFIG: dict[str, Any] = {
    "$global": {
        "permission": FieldDef(str | int, PermissionLevel.NAMES[1]),
        "cost_strategy": {
            "distance": {"type": "euclidean"},
            "cost": {
                "type": "linear",
                "base": FieldDef(Real, 1.0),
                "scale": FieldDef(Real, .05),
            },
            "consumption": {
                "type": "composite",
                "costs": [
                    {
                        "type": "experience",
                        "rate": 1,
                        "pass_strategy": PassStrategy.PROPAGATE,
                        "check_strategy": CheckStrategy.LENIENT,
                    },
                    {
                        "type": "items",
                        "items": {"minecraft:diamond": 100, "minecraft:stone": 1, "minecraft:sand": 2},
                        "strategy": ItemConsumeStrategy.HIGHER_FIRST,
                    },
                ],
            },
        },
    },
    "commands": {
        "teleport-to-player": {
            "permission": FieldDef(OptionalPermission, None),
            "cost_strategy": FieldDef(Optional[dict[str, Any]], None),
        }
    }
}

type MCD = MappingConfigData[dict[str, Any]]


class Config:
    Config: MCD

    Permission: PermissionLevelItem
    CostStrategy: CostStrategy

    class TeleportToPlayer:
        Config: MCD

        Permission: Optional[PermissionLevelItem] = None
        CostStrategy: Optional[CostStrategy] = None

        @classmethod
        def initialize(cls, config: MCD) -> None:
            cls.Config = config

            if (permission := cls.Config.retrieve("permission")) is not None:
                cls.Permission = PermissionLevel.from_value(permission)
            if (cost_strategy := cls.Config.retrieve("cost_strategy")) is not None:
                cls.CostStrategy = create_cost_strategy(cost_strategy)

    @classmethod
    def initialize(cls) -> None:
        RuamelYamlSL().register_to(PluginConfigPool)
        cls.Config = PluginConfigPool.require('', f"{h.pkg_name}.yaml", DEFAULT_CONFIG).check()
        # PluginConfigPool.save_all()  # todo save

        cls.Permission = cls.Config.retrieve("$global\\.permission")
        cls.CostStrategy = create_cost_strategy(cls.Config.retrieve("$global\\.cost_strategy"))
        cls.TeleportToPlayer.initialize(cls.Config.retrieve("commands\\.teleport-to-player"))

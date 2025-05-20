# -*- coding: utf-8 -*-


import itertools
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from typing import Optional
from typing import Self

import wrapt
from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface


class OnlinePlayerAPI:
    """
    包装OnlinePlayerAPI插件
    """

    plugin_instance: Any

    def initialize(self, server: PluginServerInterface) -> None:
        """
        延迟初始化方法

        :param server: 插件服务器接口
        :type server: PluginServerInterface
        """
        self.plugin_instance = server.get_plugin_instance("online_player_api")

    def get_player_list(self) -> list[str]:
        """
        获取玩家列表

        :return: 玩家列表
        :rtype: list[str]
        """
        return self.plugin_instance.get_player_list()

    def check_online(self, player: str) -> bool:
        """
        检查玩家是否在线

        :param player: 玩家名
        :type player: str

        :return: 玩家是否在线
        :rtype: bool
        """
        return self.plugin_instance.check_online(player)


@dataclass
class Vec3:
    x: float
    y: float
    z: float


@dataclass
class Item:
    count: int
    id: str
    components: dict[str, Any]

    def can_stack_with(self, other: Self) -> bool:
        return self.id == other.id and self.components == other.components

    @classmethod
    def from_json(cls, json_obj: dict[str, Any]) -> Self:
        return cls(json_obj["count"], json_obj["id"], json_obj.get("components", {}))

    def to_json(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "id": self.id,
            **({"components": self.components} if self.components else {}),
        }

    def to_component(self) -> str:
        components = ",".join(f"{key}={json.dumps(value)}" for key, value in self.components.items())
        if not components:
            return self.id
        return f"{self.id}[{components}]"

    def stack(self, other: Self) -> Self:
        if self.can_stack_with(other):
            return Item(self.count + other.count, self.id, self.components)
        raise ValueError("Cannot stack items with different id or components")


def _convert_other[F: Callable[[...], Any]](func: F) -> F:
    @wrapt.decorator
    def decorator(wrapped: F, instance: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        if instance is None:
            raise TypeError("Cannot call method without instance")

        cls = type(instance)
        if not isinstance(args[0], cls):
            args = (cls(args[0]), *args[1:])
        return wrapped(*args, **kwargs)

    return decorator(func)


@dataclass(order=True)
class Experience:
    points: int

    @classmethod
    def from_level(cls, level: int | float) -> Self:
        sign = -1 if level < 0 else 1
        level = abs(level)
        if level <= 16:
            points = level * level + 6 * level
        elif level <= 31:
            points = 2.5 * level ** 2 - 40.5 * level + 360
        else:
            points = 4.5 * level ** 2 - 162.5 * level + 2220

        points *= sign
        return cls(int(points))

    def to_level(self) -> tuple[int, int]:
        experience = abs(self)

        low = 0
        high = 1
        # 扩展high直到超过points
        while self.from_level(high) <= experience:
            high *= 2

        best = 0
        while low <= high:
            mid = (low + high) // 2
            current_xp = self.from_level(mid)
            if current_xp <= experience:
                best = mid
                low = mid + 1
            else:
                high = mid - 1

        xp_needed = self.from_level(best)
        remaining = experience - xp_needed

        if self.points < 0:
            best, remaining = -best, -remaining
        return best, remaining.points

    def __abs__(self) -> Self:
        # noinspection PyArgumentList
        return type(self)(abs(self.points))

    def __neg__(self) -> Self:
        # noinspection PyArgumentList
        return type(self)(-self.points)

    @_convert_other
    def __add__(self, other: Any) -> Self:
        # noinspection PyArgumentList
        return type(self)(self.points + other.points)

    @_convert_other
    def __iadd__(self, other: Any) -> Self:
        self.points += other.points
        return self

    @_convert_other
    def __sub__(self, other: Any) -> Self:
        # noinspection PyArgumentList
        return type(self)(self.points - other.points)

    @_convert_other
    def __isub__(self, other: Any) -> Self:
        self.points -= other.points
        return self

    @_convert_other
    def __mul__(self, other: Any) -> Self:
        # noinspection PyArgumentList
        return type(self)(self.points * other.points)

    @_convert_other
    def __imul__(self, other: Any) -> Self:
        self.points *= other.points
        return self

    @_convert_other
    def __pow__(self, power: Any, modulo: Any = None) -> Self:
        # noinspection PyArgumentList
        return type(self)(self.points ** power.points)

    # noinspection SpellCheckingInspection
    @_convert_other
    def __ipow__(self, other: Any) -> Self:
        self.points **= other.points
        return self

    @_convert_other
    def __mod__(self, other: Any) -> Self:
        # noinspection PyArgumentList
        return type(self)(self.points % other.points)

    # noinspection SpellCheckingInspection
    @_convert_other
    def __imod__(self, other: Any) -> Self:
        self.points %= other.points
        return self

    @_convert_other
    def __floordiv__(self, other: Any) -> Self:
        # noinspection PyArgumentList
        return type(self)(self.points // other.points)

    # noinspection SpellCheckingInspection
    @_convert_other
    def __ifloordiv__(self, other: Any) -> Self:
        self.points //= other.points
        return self

    @_convert_other
    def __truediv__(self, other: Any) -> Self:
        # noinspection PyArgumentList
        return type(self)(self.points / other.points)

    # noinspection SpellCheckingInspection
    @_convert_other
    def __itruediv__(self, other: Any) -> Self:
        self.points /= other.points
        return self

    __radd__ = __add__
    __rsub__ = __sub__
    __rmul__ = __mul__
    __rpow__ = __pow__
    __rmod__ = __mod__
    __rfloordiv__ = __floordiv__
    __rtruediv__ = __truediv__


@dataclass
class ResourceState:
    items: list[Item]
    experience: Experience


class MinecraftDataAPI:
    """
    包装MinecraftDataAPI插件
    """

    plugin_instance: Any

    def initialize(self, server: PluginServerInterface) -> None:
        """
        延迟初始化方法

        :param server: 插件服务器接口
        :type server: PluginServerInterface
        """
        self.plugin_instance = server.get_plugin_instance("minecraft_data_api")

    def get_player_coordinate(
            self,
            player: str,
            *,
            timeout: Optional[float] = None
    ) -> Vec3 | None:
        """
        获取玩家坐标

        :param player: 玩家名
        :type player: str

        :param timeout: 超时时间
        :type timeout: Optional[float]

        :return: 玩家坐标
        :rtype: tuple[float, float, float]
        """
        return Vec3(*self.plugin_instance.get_player_coordinate(player, timeout=timeout))

    def get_server_player_list(self, *, timeout: Optional[float] = None) -> Optional[tuple[int, int, list[str]]]:
        """
        获取服务器玩家列表

        :param timeout: 超时时间
        :type timeout: Optional[float]

        :return: 玩家列表
        :rtype: Optional[tuple[int, int, list[str]]]
        """
        return self.plugin_instance.get_server_player_list(timeout=timeout)

    def get_player_info(self, player: str, data_path: str = "", *,
                        timeout: Optional[float] = None) -> dict[str, Any] | list[Any] | int | str | None:
        """
        获取玩家信息

        :param player: 玩家名
        :type player: str

        :param data_path: 数据路径
        :type data_path: str

        :param timeout: 超时时间
        :type timeout: Optional[float]
        """
        return self.plugin_instance.get_player_info(player, data_path, timeout=timeout)

    def get_resource_state(self, player: str, *, timeout: Optional[float] = None) -> ResourceState | None:
        """
        获取玩家物品栏

        :param player: 玩家名
        :type player: str

        :param timeout: 超时时间
        :type timeout: Optional[float]

        :return: 物品栏
        :rtype: dict
        """
        items: dict[str, dict[str, Item]] = {}
        """
        数据结构：{id: {components: item}}

        从id和components获取唯一的Item，确保是stackable
        """

        player_data: dict[str, Any] | None = self.get_player_info(player, timeout=timeout)

        if player_data is None:
            return None

        def _get_items() -> list[Item]:
            for item in itertools.chain(player_data["Inventory"], player_data.get("equipment", {}).values()):
                item = Item.from_json(item)
                frozen_components = json.dumps(item.components)
                if (found_id := item.id in items) and frozen_components in items[item.id]:
                    items[item.id][frozen_components] = items[item.id][frozen_components].stack(item)
                elif found_id:
                    items[item.id][frozen_components] = item
                else:
                    items[item.id] = {frozen_components: item}

            return [item for item_id in items for item in items[item_id].values()]

        def _get_experience() -> Experience:
            return Experience(player_data["XpTotal"])

        return ResourceState(_get_items(), _get_experience())


online_player_api = OnlinePlayerAPI()
minecraft_data_api = MinecraftDataAPI()


def initialize(server: PluginServerInterface) -> None:
    """
    延迟初始化方法

    :param server: 插件服务器接口
    :type server: PluginServerInterface
    """
    online_player_api.initialize(server)
    minecraft_data_api.initialize(server)


__all__ = (
    "OnlinePlayerAPI",
    "Vec3",
    "Item",
    "Experience",
    "ResourceState",
    "MinecraftDataAPI",

    "online_player_api",
    "minecraft_data_api",

    "initialize",
)

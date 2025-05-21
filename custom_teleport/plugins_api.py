# -*- coding: utf-8 -*-


import itertools
import json
from typing import Any
from typing import Optional

from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface

from .cost_strategy import Experience
from .cost_strategy import Item
from .cost_strategy import ResourceState
from .cost_strategy import Vec3


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

        :return: 玩家信息
        :rtype: dict[str, Any] | list[Any] | int | str | None
        """
        return self.plugin_instance.get_player_info(player, data_path, timeout=timeout)

    def get_resource_state(self, player: str, *, timeout: Optional[float] = None) -> ResourceState | None:
        """
        获取玩家资源状态

        :param player: 玩家名
        :type player: str
        :param timeout: 超时时间
        :type timeout: Optional[float]

        :return: 玩家资源状态
        :rtype: ResourceState | None
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

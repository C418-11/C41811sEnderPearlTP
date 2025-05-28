# -*- coding: utf-8 -*-


from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .consumption import CONSUMPTION_TYPES
from .cost_calculation import COST_TYPES
from .distance import DISTANCE_TYPES
from .utils import Command
from .utils import CostStrategy
from .utils import ResourceState
from .utils import Vec3
from .utils import get_params


def create_cost_strategy(config: Mapping[str, Any]) -> CostStrategy:
    """
    创建成本策略

    :param config: 配置信息
    :type config: Mapping[str, Any]

    :return: 成本策略
    :rtype: CostStrategy
    """
    # 初始化距离计算器
    distance_cfg = config.get("distance", {"type": "euclidean"})
    # noinspection PyArgumentList
    distance_calculator = DISTANCE_TYPES[distance_cfg["type"]](**get_params(distance_cfg))

    # 初始化消耗计算器
    cost_cfg = config.get("cost", {"type": "linear"})
    # noinspection PyArgumentList
    cost_calculator = COST_TYPES[cost_cfg["type"]](**get_params(cost_cfg))

    # 初始化消耗处理器
    consumption_cfg = config.get("consumption", {"type": "items"})
    # noinspection PyArgumentList
    composite_cost = CONSUMPTION_TYPES[consumption_cfg["type"]](**get_params(consumption_cfg))

    # 构建处理函数  # todo use Position instead of Vec3
    def calculate_commands(start: Vec3, end: Vec3, resource_state: ResourceState) -> list[Command]:
        """
        计算命令

        :param start: 起始位置
        :type start: Vec3
        :param end: 终止位置
        :type end: Vec3
        :param resource_state: 资源状态，默认深拷贝防止意外更改
        :type resource_state: ResourceState

        :return: 命令列表
        :rtype: list[Command]
        """
        distance = distance_calculator.calculate(start, end)
        cost_value = cost_calculator.compute(distance)
        return composite_cost.apply_cost(cost_value, deepcopy(resource_state))[1]

    return calculate_commands


# 示例配置
SAMPLE_CONFIG = {
    "distance": {
        "type": "euclidean",
    },
    "cost": {
        "type": "exponential",
        "base": 2.0,
        "scale": 0.5
    },
    "consumption": {
        "type": "experience",
        "rate": 1.2
    },
}


__all__ = (
    "create_cost_strategy",
)

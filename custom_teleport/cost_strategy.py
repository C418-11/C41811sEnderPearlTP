# -*- coding: utf-8 -*-


import math
import random
from abc import ABC
from abc import abstractmethod
from collections import defaultdict
from collections.abc import Callable
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field
from decimal import Decimal
from decimal import ROUND_CEILING
from enum import StrEnum
from functools import partial
from typing import Any

from .plugins_api import Item
from .plugins_api import ResourceState
from .plugins_api import Vec3

type Command = str


# --------------------------
# 距离计算模块
# --------------------------
@dataclass
class DistanceCalculator(ABC):
    """
    距离计算器
    """

    min_distance: float = field(default=float("-inf"))
    """
    最小距离
    """
    max_distance: float = field(default=float("inf"))
    """
    最大距离
    """
    scale: float = field(default=1)
    """
    缩放比例
    """

    @abstractmethod
    def calculate(self, from_coordinate: Vec3, to_coordinate: Vec3) -> float:
        """
        计算距离

        :param from_coordinate: 起点
        :type from_coordinate: Vec3
        :param to_coordinate: 终点
        :type to_coordinate: Vec3

        :return: 距离
        :rtype: float
        """


def _limit_value(val: float, min_val: float, max_val: float, scale: float = 1) -> float:
    """
    限制值的范围

    :param val: 值
    :type val: float
    :param min_val: 最小值
    :type min_val: float
    :param max_val: 最大值
    :type max_val: float
    :param scale: 缩放比例
    :type scale: float

    :return: 限制后的值
    :rtype: float
    """
    return max(min_val, min(max_val, val * scale))


class EuclideanDistance(DistanceCalculator):
    """
    欧几里得距离计算器
    """

    def calculate(self, from_coordinate: Vec3, to_coordinate: Vec3) -> float:
        return _limit_value(math.sqrt(
            (from_coordinate.x - to_coordinate.x) ** 2 +
            (from_coordinate.y - to_coordinate.y) ** 2 +
            (from_coordinate.z - to_coordinate.z) ** 2
        ), self.min_distance, self.max_distance, self.scale)


class ManhattanDistance(DistanceCalculator):
    """
    曼哈顿距离计算器
    """

    def calculate(self, from_coordinate: Vec3, to_coordinate: Vec3) -> float:
        return _limit_value((
                abs(from_coordinate.x - to_coordinate.x) +
                abs(from_coordinate.y - to_coordinate.y) +
                abs(from_coordinate.z - to_coordinate.z)
        ), self.min_distance, self.max_distance, self.scale)


class ChebyshevDistance(DistanceCalculator):
    """
    切比雪夫距离计算器
    """

    def calculate(self, from_coordinate: Vec3, to_coordinate: Vec3) -> float:
        return _limit_value(max(
            abs(from_coordinate.x - to_coordinate.x),
            abs(from_coordinate.y - to_coordinate.y),
            abs(from_coordinate.z - to_coordinate.z)
        ), self.min_distance, self.max_distance, self.scale)


DISTANCE_TYPES: dict[str, type[DistanceCalculator]] = {
    "euclidean": EuclideanDistance,
    "manhattan": ManhattanDistance,
    "chebyshev": ChebyshevDistance
}


# --------------------------
# 消耗计算模块
# --------------------------
@dataclass
class CostCalculator(ABC):
    """
    消耗计算器
    """

    min_cost: float = field(default=float("-inf"))
    """
    最低消耗
    """
    max_cost: float = field(default=float("inf"))
    """
    最高消耗
    """
    scale: float = field(default=1)
    """
    消耗缩放
    """

    @abstractmethod
    def compute(self, distance: float) -> float:
        """
        计算消耗

        :param distance: 距离
        :type distance: float

        :return: 消耗
        :rtype: float
        """


@dataclass
class LinearCost(CostCalculator):
    """
    线性消耗计算器
    """
    base: float = field(default=1)

    def compute(self, distance: float) -> float:
        return _limit_value(self.base + distance * self.scale, self.min_cost, self.max_cost)


@dataclass
class ExponentialCost(CostCalculator):
    """
    指数消耗计算器
    """
    base: float = field(default=1.0025)

    def compute(self, distance: float) -> float:
        return _limit_value(self.base ** distance, self.min_cost, self.max_cost, self.scale)


COST_TYPES: dict[str, type[CostCalculator]] = {
    "linear": LinearCost,
    "exponential": ExponentialCost
}


# --------------------------
# 消耗处理模块
# --------------------------
class ExperienceConsumeStrategy(StrEnum):
    """
    经验消耗策略
    """
    POINTS = "points"
    LEVEL = "level"
    RANDOM = "random"


class ItemConsumeStrategy(StrEnum):
    """
    物品消耗策略
    """
    LOWER_FIRST = "lower-first"
    HIGHER_FIRST = "higher-first"
    RANDOM = "random"


class InsufficientResourcesError(Exception):
    """
    资源不足
    """

    def __str__(self):
        return "Insufficient resources"


class InsufficientExperienceError(InsufficientResourcesError):
    """
    经验不足
    """

    def __init__(self, available: float, required: float, strategy: ExperienceConsumeStrategy):
        self.available = available
        self.required = required
        self.strategy = strategy

    def __str__(self):
        return f"Insufficient experience. Available: {self.available}, Required: {self.required} {self.strategy}"


class InsufficientItemsError(InsufficientResourcesError):
    """
    物品不足
    """

    def __init__(self, available: float, required: float):
        self.available = available
        self.required = required

    def __str__(self):
        return f"Insufficient items. Available: {self.available}, Required: {self.required}"


class PassStrategy(StrEnum):
    PASSTHROUGH = "pass_through"
    PROPAGATE = "propagate"


class CheckStrategy(StrEnum):
    STRICT = "strict"
    LENIENT = "lenient"


@dataclass
class Cost(ABC):
    """
    消耗
    """

    pass_strategy: PassStrategy = field(default=PassStrategy.PASSTHROUGH)
    check_strategy: CheckStrategy = field(default=CheckStrategy.STRICT)

    @abstractmethod
    def apply_cost(self, cost_value: float, resources: ResourceState) -> tuple[float, list[Command]]:
        """
        应用消耗

        .. important::
           参数 ``resources`` 会在内部更新其值为消耗后的值，若不依赖此行为应考虑使用 :py:func:`deepcopy` 深拷贝后传参

           实现子类时需要注意该参数的更改一定要放在 :py:attr:`Cost.pass_strategy` 和 :py:attr:`Cost.check_strategy`
           的判断之后，否则可能导致预期之外的行为

        :param cost_value: 消耗值
        :type cost_value: float
        :param resources: 资源状态
        :type resources: ResourceState
        :return: 剩余消耗值, 命令列表
        :rtype: tuple[float, list[Command]]
        """


@dataclass
class ExperienceCost(Cost):
    """
    经验消耗
    """
    rate: float = field(default=1)
    strategy: ExperienceConsumeStrategy = field(default=ExperienceConsumeStrategy.POINTS)
    probability: dict[str, float] = field(default_factory=lambda: {"points": 0.5, "level": 0.5})

    def __post_init__(self) -> None:
        if self.strategy == ExperienceConsumeStrategy.RANDOM:
            total = sum(self.probability.values())
            if total <= 0:
                self.probability = {"points": 0.5, "level": 0.5}
            else:
                # 归一化概率
                self.probability = {k: v / total for k, v in self.probability.items()}

    def _select_strategy(self) -> ExperienceConsumeStrategy:
        if self.strategy != ExperienceConsumeStrategy.RANDOM:
            return self.strategy
        choices = list(self.probability.keys())
        probs = list(self.probability.values())
        return ExperienceConsumeStrategy(random.choices(choices, weights=probs)[0])

    def apply_cost(self, cost_value: float, resources: ResourceState) -> tuple[float, list[Command]]:
        selected_strategy = self._select_strategy()

        if selected_strategy == ExperienceConsumeStrategy.POINTS:
            required_experience = math.ceil(cost_value * self.rate)
            resource_experience = resources.experience.points
            commands = [f"xp add @s -{required_experience} points"]
        else:
            required_experience = cost_value * self.rate
            resource_experience = (
                    (level := resources.experience.to_level())[0]
                    + resources.experience.from_level(level[0] + 1)
            )
            commands = [f"xp add @s -{required_experience} levels"]

        if resource_experience < required_experience and self.check_strategy == CheckStrategy.STRICT:
            raise InsufficientExperienceError(resource_experience, required_experience, selected_strategy)
        if self.pass_strategy == PassStrategy.PROPAGATE:
            cost_value -= resource_experience

        resources.experience -= required_experience
        return cost_value, commands


def calculate_combination(
        items_dict: dict[str, float],
        id_counts: defaultdict[str, int],
        cost_value: float,
        strategy: ItemConsumeStrategy
) -> dict[str, int]:
    # 将所有浮点数转换为 Decimal 以保持高精度
    cost_value_dec = Decimal(str(cost_value))
    items = [(item_id, Decimal(str(value))) for item_id, value in items_dict.items()]

    if strategy == ItemConsumeStrategy.RANDOM:
        strategy = random.choice([ItemConsumeStrategy.LOWER_FIRST, ItemConsumeStrategy.HIGHER_FIRST])

    # 根据策略排序物品
    reverse_sort = (strategy == ItemConsumeStrategy.HIGHER_FIRST)
    sorted_items = sorted(items, key=lambda x: x[1], reverse=reverse_sort)
    item_ids = [item[0] for item in sorted_items]
    values = {item[0]: item[1] for item in sorted_items}

    result = {item_id: 0 for item_id in item_ids}
    remaining = cost_value_dec

    # 步骤1: 贪心算法优先取最大可能数量
    for item_id in item_ids:
        if remaining <= 0:
            break
        value = values[item_id]
        if value <= 0:
            continue
        # noinspection PyTypeChecker
        max_possible = min(id_counts[item_id], (remaining // value).to_integral_value())
        if max_possible > 0:
            result[item_id] = max_possible
            remaining -= max_possible * value

    # 步骤2: 如果还有剩余，逆序尝试补充
    if remaining > 0:
        # 确定逆序策略：原策略为更高优先则按升序检查，反之降序
        reverse_strategy = not reverse_sort
        reverse_sorted = sorted(items, key=lambda x: x[1], reverse=reverse_strategy)

        for item in reverse_sorted:
            item_id, value = item
            if remaining <= 0:
                break
            if value <= 0:
                continue
            current_taken = result[item_id]
            available = id_counts[item_id] - current_taken
            if available <= 0:
                continue
            # 使用 Decimal 的天花板除法计算所需数量
            needed = (remaining / value).to_integral(rounding=ROUND_CEILING)
            # noinspection PyTypeChecker
            take = min(needed, available)
            result[item_id] += take
            remaining -= take * value

    # 移除数量为0的条目
    return {k: v for k, v in result.items() if v > 0}


@dataclass
class ItemValueCost(Cost):
    """
    物品消耗
    """
    items: dict[str, float] = field(default_factory=dict)
    strategy: ItemConsumeStrategy = field(default=ItemConsumeStrategy.HIGHER_FIRST)

    strategy_registry: dict[
        ItemConsumeStrategy, Callable[[dict[str, float], defaultdict[str, int], float], dict[str, int]]
    ] = field(
        default_factory=lambda: dict({
            ItemConsumeStrategy.HIGHER_FIRST: partial(calculate_combination, strategy=ItemConsumeStrategy.HIGHER_FIRST),
            ItemConsumeStrategy.LOWER_FIRST: partial(calculate_combination, strategy=ItemConsumeStrategy.LOWER_FIRST),
            ItemConsumeStrategy.RANDOM: partial(calculate_combination, strategy=ItemConsumeStrategy.RANDOM),
        })
    )

    def apply_cost(self, cost_value: float, resources: ResourceState) -> tuple[float, list[Command]]:
        id_counts: defaultdict[str, int] = defaultdict(int)
        id_items: defaultdict[str, list[Item]] = defaultdict(list)
        for item in resources.items:
            if item.id in self.items:
                id_counts[item.id] += item.count
                id_items[item.id].append(item)

        strategy_func = self.strategy_registry.get(self.strategy)
        if not strategy_func:
            raise ValueError(f"Unsupported strategy: {self.strategy}")

        consumed = strategy_func(self.items, id_counts, cost_value)

        total_paid = sum(count * self.items[item_id] for item_id, count in consumed.items())
        if total_paid < cost_value and self.check_strategy == CheckStrategy.STRICT:
            raise InsufficientItemsError(total_paid, cost_value)
        if self.pass_strategy == PassStrategy.PROPAGATE:
            cost_value -= total_paid

        commands = []
        for item_id, count in consumed.items():
            remaining_count = count
            for item in id_items[item_id]:
                if remaining_count <= 0:
                    break
                take = min(remaining_count, item.count)
                commands.append(f"clear @s {item.to_component()} {take}")
                item.count -= take
                remaining_count -= take
                if item.count == 0:
                    resources.items.remove(item)

        return cost_value, commands


def _get_params[C: dict[str, Any]](cfg: C) -> C:
    return {k: v for k, v in cfg.items() if k != "type"}


@dataclass
class CompositeCost(Cost):
    """
    计算综合成本
    """
    costs: list[dict[str, Any]] = field(default_factory=list)

    def apply_cost(self, cost_value: float, resources: ResourceState) -> tuple[float, list[Command]]:
        remaining = cost_value
        costs = []
        for cost_cfg in self.costs:
            # noinspection PyArgumentList
            costs.append(CONSUMPTION_TYPES[cost_cfg["type"]](**_get_params(cost_cfg)))

        commands = []
        for cost in costs:
            try:
                remaining, cmds = cost.apply_cost(remaining, resources)
            except InsufficientResourcesError:
                if self.check_strategy == CheckStrategy.STRICT:
                    raise
                continue
            commands.extend(cmds)
        if self.pass_strategy == PassStrategy.PROPAGATE:
            cost_value = remaining
        return cost_value, commands


CONSUMPTION_TYPES: dict[str, type[Cost]] = {
    "experience": ExperienceCost,
    "items": ItemValueCost,
    "composite": CompositeCost,
}

# --------------------------
# 工厂函数
# --------------------------
type CostStrategy = Callable[[Vec3, Vec3, ResourceState], list[Command]]


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
    distance_calculator = DISTANCE_TYPES[distance_cfg["type"]](**_get_params(distance_cfg))

    # 初始化消耗计算器
    cost_cfg = config.get("cost", {"type": "linear"})
    # noinspection PyArgumentList
    cost_calculator = COST_TYPES[cost_cfg["type"]](**_get_params(cost_cfg))

    # 初始化消耗处理器
    consumption_cfg = config.get("consumption", {"type": "items"})
    # noinspection PyArgumentList
    composite_cost = CONSUMPTION_TYPES[consumption_cfg["type"]](**_get_params(consumption_cfg))

    # 构建处理函数（保持不变）
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

# -*- coding: utf-8 -*-


import math
import random
from abc import ABC
from abc import abstractmethod
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from decimal import Decimal
from decimal import ROUND_CEILING
from enum import StrEnum
from functools import partial
from typing import Any

from .utils import Command
from .utils import Item
from .utils import ResourceState
from .utils import get_params


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

    strategy_handlers: dict[
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

        strategy_func = self.strategy_handlers.get(self.strategy)
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
            costs.append(CONSUMPTION_TYPES[cost_cfg["type"]](**get_params(cost_cfg)))

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

__all__ = (
    "ExperienceConsumeStrategy",
    "ItemConsumeStrategy",

    "InsufficientResourcesError",
    "InsufficientExperienceError",
    "InsufficientItemsError",

    "PassStrategy",
    "CheckStrategy",

    "Cost",
    "ExperienceCost",
    "ItemValueCost",

    "CompositeCost",

    "CONSUMPTION_TYPES",
)

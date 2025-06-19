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


class ResourceType(StrEnum):
    """
    资源类型
    """
    EXPERIENCE = "experience"
    ITEMS = "items"
    HUNGER = "hunger"
    HEALTH = "health"


class InsufficientResourcesError(Exception):
    """
    资源不足
    """

    def __init__(self, resource_type: ResourceType):
        self.resource_type = resource_type

    def __str__(self) -> str:
        return f"Insufficient {self.resource_type}"


class QuantitativeInsufficientResourcesError(InsufficientResourcesError):
    """
    定量资源不足
    """

    def __init__(self, resource_type: ResourceType, available: float, required: float):
        super().__init__(resource_type)
        self.available = available
        self.required = required

    def __str__(self) -> str:
        return f"Insufficient {self.resource_type}. Available: {self.available}, Required: {self.required}"


class InsufficientExperienceError(QuantitativeInsufficientResourcesError):
    """
    经验不足
    """

    def __init__(self, available: float, required: float, strategy: ExperienceConsumeStrategy):
        super().__init__(ResourceType.EXPERIENCE, available, required)
        self.strategy = strategy

    def __str__(self) -> str:
        return f"{super().__str__()} {self.strategy}"


class InsufficientItemsError(QuantitativeInsufficientResourcesError):
    """
    物品不足
    """

    def __init__(self, available: float, required: float):
        super().__init__(ResourceType.ITEMS, available, required)


class InsufficientHungerError(QuantitativeInsufficientResourcesError):
    """
    饥饿值不足
    """

    def __init__(self, available: float, required: float):
        super().__init__(ResourceType.HUNGER, available, required)


class InsufficientHealthError(QuantitativeInsufficientResourcesError):
    """
    生命值不足
    """

    def __init__(self, available: float, required: float):
        super().__init__(ResourceType.HEALTH, available, required)


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
           会在内部更新参数 ``resources`` 其值为消耗后的值，若不依赖此行为应考虑使用 :py:func:`deepcopy` 深拷贝后传参

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

        required_experience: int | float
        resource_experience: float
        if selected_strategy == ExperienceConsumeStrategy.POINTS:
            required_experience = math.ceil(cost_value * self.rate)
            resource_experience = resources.experience.points
            commands = [f"xp add @s -{required_experience} points"]
        else:
            required_experience = cost_value * self.rate
            level = resources.experience.to_level()
            resource_experience = level[0] + level[1] / resources.experience.from_level(level[0] + 1).points
            commands = [f"xp add @s -{required_experience} levels"]

        if resource_experience < required_experience and self.check_strategy == CheckStrategy.STRICT:
            raise InsufficientExperienceError(resource_experience, required_experience, selected_strategy)
        if self.pass_strategy == PassStrategy.PROPAGATE:
            cost_value -= resource_experience / self.rate

        resources.experience -= required_experience
        return cost_value, commands


def calculate_combination(  # noqa: C901 (too complex)
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

    result: dict[str, int | Decimal] = {item_id: 0 for item_id in item_ids}
    remaining = cost_value_dec

    # 步骤1: 贪心算法优先取最大可能数量
    for item_id in item_ids:
        if remaining <= 0:
            break
        value = values[item_id]
        if value <= 0:
            continue
        # noinspection PyTypeChecker
        max_possible: int | Decimal = min(  # type: ignore[assignment]
            id_counts[item_id],
            (remaining // value).to_integral_value()
        )
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
            take: Decimal | int = min(needed, available)
            result[item_id] += take
            remaining -= take * value

    # 移除数量为0的条目
    return {k: int(v) for k, v in result.items() if v > 0}


@dataclass
class ItemValueCost(Cost):
    """
    物品消耗
    """
    rate: float = field(default=1)
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

        required_cost_value = cost_value * self.rate
        consumed = strategy_func(self.items, id_counts, required_cost_value)

        total_paid = sum(count * self.items[item_id] for item_id, count in consumed.items())
        if total_paid < required_cost_value and self.check_strategy == CheckStrategy.STRICT:
            raise InsufficientItemsError(total_paid, required_cost_value)
        if self.pass_strategy == PassStrategy.PROPAGATE:
            cost_value -= total_paid / self.rate

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


def calculate_hunger_effect(food_level: float, target_level: float) -> tuple[int, int]:
    delta = food_level - target_level
    if delta <= 0:
        return 0, 0

    d = delta / 0.025
    best_e = 0
    best_s = 0
    min_error = float('inf')

    for e in range(255, 0, -1):
        s = math.ceil(d / e)
        current_total = s * e
        error = current_total - d

        if error < min_error or (error == min_error and e > best_e):
            min_error = error
            best_e = e
            best_s = s
            if min_error == 0:
                break  # 找到零误差的最优解，提前终止

    return best_s, best_e


@dataclass
class HungerEffectCost(Cost):
    """
    消耗饥饿值
    """
    rate: float = field(default=1 / 70)  # 消耗1饥饿值约跑跳70米

    def apply_cost(self, cost_value: float, resources: ResourceState) -> tuple[float, list[Command]]:
        resource_hunger = max(.0, resources.hunger.total)
        target_hunger = max(.0, resource_hunger - cost_value * self.rate)

        if (resource_hunger < target_hunger) and self.check_strategy == CheckStrategy.STRICT:
            raise InsufficientHungerError(resource_hunger, resource_hunger - target_hunger)
        if self.pass_strategy == PassStrategy.PROPAGATE:
            cost_value -= (resource_hunger - target_hunger) / self.rate

        resources.hunger.total -= resource_hunger - target_hunger
        commands = []
        if (effect := calculate_hunger_effect(resource_hunger, target_hunger)) != (0, 0):
            commands.append(f"effect give @s minecraft:hunger {effect[0]} {effect[1]} true")
        return float(round(cost_value, 7)), commands


class HealthCost(Cost):
    """
    消耗生命值
    """
    # 简陋测试没饥饿值时4秒8.4185036275910米
    rate: float = field(default=Decimal("0.11878595"))  # 没饥饿值时4秒消耗1生命值，大概每米需要这么多生命值
    damage_type: str = field(default="void")

    def apply_cost(self, cost_value: float, resources: ResourceState) -> tuple[float, list[Command]]:
        resource_health: float = resources.health
        target_health = resource_health - cost_value * self.rate

        if (resource_health < target_health) and self.check_strategy == CheckStrategy.STRICT:
            raise InsufficientHealthError(resource_health, resource_health - target_health)
        if self.pass_strategy == PassStrategy.PROPAGATE:
            cost_value -= (resource_health - target_health) / self.rate

        resources.health = target_health
        return cost_value, [f"damage @s {resource_health - target_health} {self.damage_type}"]


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
    "hunger": HungerEffectCost,
    "health": HealthCost,
}

__all__ = (
    "ExperienceConsumeStrategy",
    "ItemConsumeStrategy",
    "ResourceType",

    "InsufficientResourcesError",
    "QuantitativeInsufficientResourcesError",
    "InsufficientExperienceError",
    "InsufficientItemsError",
    "InsufficientHungerError",

    "PassStrategy",
    "CheckStrategy",

    "Cost",
    "ExperienceCost",
    "ItemValueCost",
    "HungerEffectCost",
    "HealthCost",

    "CompositeCost",

    "CONSUMPTION_TYPES",
)

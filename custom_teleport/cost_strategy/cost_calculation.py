# -*- coding: utf-8 -*-


from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field

from .utils import limit_value


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
        return limit_value(self.base + distance * self.scale, self.min_cost, self.max_cost)


@dataclass
class ExponentialCost(CostCalculator):
    """
    指数消耗计算器
    """
    base: float = field(default=1.0025)

    def compute(self, distance: float) -> float:
        return limit_value(self.base ** distance, self.min_cost, self.max_cost, self.scale)


COST_TYPES: dict[str, type[CostCalculator]] = {
    "linear": LinearCost,
    "exponential": ExponentialCost
}

__all__ = (
    "CostCalculator",

    "LinearCost",
    "ExponentialCost",

    "COST_TYPES",
)

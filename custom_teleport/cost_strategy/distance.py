# -*- coding: utf-8 -*-


import math
from abc import ABC
from abc import abstractmethod
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field

from .utils import Position
from .utils import Vec3
from .utils import limit_value


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
    cross_dimensional_cost: Mapping[str, float] = field(default_factory=lambda: defaultdict(lambda: 35))
    """
    跨维度成本
    """

    def calculate(self, from_position: Position, to_position: Position) -> float:
        """
        计算距离

        :param from_position: 起点
        :type from_position: Position
        :param to_position: 终点
        :type to_position: Position

        :return: 距离
        :rtype: float
        """
        coordinate_distance = self.coordinate_distance(from_position.coordinate, to_position.coordinate)

        cross_dimensional_cost: float = 0
        if from_position.dimension != to_position.dimension:
            cross_dimensional_cost += self.cross_dimensional_cost[from_position.dimension]
            cross_dimensional_cost += self.cross_dimensional_cost[to_position.dimension]

        return limit_value(
            coordinate_distance,
            self.min_distance, self.max_distance, self.scale
        )

    @abstractmethod
    def coordinate_distance(self, from_coordinate: Vec3, to_coordinate: Vec3) -> float:
        """
        计算坐标距离

        :param from_coordinate: 起点
        :type from_coordinate: Vec3
        :param to_coordinate: 终点
        :type to_coordinate: Vec3

        :return: 距离
        :rtype: float
        """


class EuclideanDistance(DistanceCalculator):
    """
    欧几里得距离计算器
    """

    def coordinate_distance(self, from_coordinate: Vec3, to_coordinate: Vec3) -> float:
        return math.sqrt(
            (from_coordinate.x - to_coordinate.x) ** 2 +
            (from_coordinate.y - to_coordinate.y) ** 2 +
            (from_coordinate.z - to_coordinate.z) ** 2
        )


class ManhattanDistance(DistanceCalculator):
    """
    曼哈顿距离计算器
    """

    def coordinate_distance(self, from_coordinate: Vec3, to_coordinate: Vec3) -> float:
        return (
                abs(from_coordinate.x - to_coordinate.x) +
                abs(from_coordinate.y - to_coordinate.y) +
                abs(from_coordinate.z - to_coordinate.z)
        )


class ChebyshevDistance(DistanceCalculator):
    """
    切比雪夫距离计算器
    """

    def coordinate_distance(self, from_coordinate: Vec3, to_coordinate: Vec3) -> float:
        return max(
            abs(from_coordinate.x - to_coordinate.x),
            abs(from_coordinate.y - to_coordinate.y),
            abs(from_coordinate.z - to_coordinate.z)
        )


@dataclass
class FixedDistance(DistanceCalculator):
    """
    固定距离计算器
    """

    distance: float = field(default=0)

    def coordinate_distance(self, from_coordinate: Vec3, to_coordinate: Vec3) -> float:
        return self.distance


DISTANCE_TYPES: dict[str, type[DistanceCalculator]] = {
    "fixed": FixedDistance,
    "euclidean": EuclideanDistance,
    "manhattan": ManhattanDistance,
    "chebyshev": ChebyshevDistance,
}

__all__ = (
    "DistanceCalculator",

    "EuclideanDistance",
    "ManhattanDistance",
    "ChebyshevDistance",

    "DISTANCE_TYPES",
)

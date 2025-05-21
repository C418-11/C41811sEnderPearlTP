# -*- coding: utf-8 -*-


import math
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field

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


class EuclideanDistance(DistanceCalculator):
    """
    欧几里得距离计算器
    """

    def calculate(self, from_coordinate: Vec3, to_coordinate: Vec3) -> float:
        return limit_value(math.sqrt(
            (from_coordinate.x - to_coordinate.x) ** 2 +
            (from_coordinate.y - to_coordinate.y) ** 2 +
            (from_coordinate.z - to_coordinate.z) ** 2
        ), self.min_distance, self.max_distance, self.scale)


class ManhattanDistance(DistanceCalculator):
    """
    曼哈顿距离计算器
    """

    def calculate(self, from_coordinate: Vec3, to_coordinate: Vec3) -> float:
        return limit_value((
                abs(from_coordinate.x - to_coordinate.x) +
                abs(from_coordinate.y - to_coordinate.y) +
                abs(from_coordinate.z - to_coordinate.z)
        ), self.min_distance, self.max_distance, self.scale)


class ChebyshevDistance(DistanceCalculator):
    """
    切比雪夫距离计算器
    """

    def calculate(self, from_coordinate: Vec3, to_coordinate: Vec3) -> float:
        return limit_value(max(
            abs(from_coordinate.x - to_coordinate.x),
            abs(from_coordinate.y - to_coordinate.y),
            abs(from_coordinate.z - to_coordinate.z)
        ), self.min_distance, self.max_distance, self.scale)


DISTANCE_TYPES: dict[str, type[DistanceCalculator]] = {
    "euclidean": EuclideanDistance,
    "manhattan": ManhattanDistance,
    "chebyshev": ChebyshevDistance
}

__all__ = (
    "DistanceCalculator",

    "EuclideanDistance",
    "ManhattanDistance",
    "ChebyshevDistance",

    "DISTANCE_TYPES",
)

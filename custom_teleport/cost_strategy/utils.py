# -*- coding: utf-8 -*-


from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from typing import Self

import hjson
import wrapt

type Command = str
type CostStrategy = Callable[[Vec3, Vec3, ResourceState], list[Command]]


def limit_value(val: float, min_val: float, max_val: float, scale: float = 1) -> float:
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


def get_params[C: dict[str, Any]](cfg: C) -> C:
    return {k: v for k, v in cfg.items() if k != "type"}


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
        components = ",".join(f"{key}={hjson.dumps(value)}" for key, value in self.components.items())
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


__all__ = (
    "limit_value",
    "get_params",

    "Command",
    "CostStrategy",

    "Vec3",
    "Item",
    "Experience",
    "ResourceState",
)

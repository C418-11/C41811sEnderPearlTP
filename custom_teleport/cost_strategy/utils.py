# -*- coding: utf-8 -*-


from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from typing import Self

import hjson  # type: ignore[import-not-found]
import wrapt  # type: ignore[import-not-found]

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


def get_params(cfg: dict[str, Any]) -> dict[str, Any]:
    """
    从配置获取参数

    :param cfg: 配置
    :type cfg: dict[str, Any]

    :return: 参数
    :rtype: dict[str, Any]
    """
    return {k: v for k, v in cfg.items() if k != "type"}


@dataclass
class Vec3:
    """
    简陋的三维向量
    """
    x: float
    y: float
    z: float


@dataclass
class Item:
    """
    物品
    """
    count: int
    id: str
    components: dict[str, Any]

    def can_stack_with(self, other: Self) -> bool:
        """
        判断两个物品是否可以堆叠

        无视原版堆叠上限，``id`` 和 ``components`` 相同即视为可堆叠/同一物品

        :param other: 另一个物品
        :type other: Self

        :return: 是否可以堆叠
        :rtype: bool
        """
        return self.id == other.id and self.components == other.components

    @classmethod
    def from_json(cls, json_obj: dict[str, Any]) -> Self:
        """
        从 JSON 对象创建物品

        :param json_obj: JSON 对象
        :type json_obj: dict[str, Any]

        :return: 物品
        :rtype: Self
        """
        return cls(json_obj["count"], json_obj["id"], json_obj.get("components", {}))

    def to_json(self) -> dict[str, Any]:
        """
        转换为 JSON 对象

        :return: JSON 对象
        :rtype: dict[str, Any]
        """
        return {
            "count": self.count,
            "id": self.id,
            **({"components": self.components} if self.components else {}),
        }

    def to_component(self) -> str:
        """
        转换为物品组件字符串

        :return: 物品组件字符串
        :rtype: str
        """
        components = ",".join(f"{key}={hjson.dumps(value)}" for key, value in self.components.items())
        if not components:
            return self.id
        return f"{self.id}[{components}]"

    def stack(self, other: Self) -> Self:
        """
        与另一个物品进行堆叠

        :param other: 另一个物品
        :type other: Self

        :return: 堆叠后的物品
        :rtype: Self

        :raise ValueError: 不是可堆叠在一起的物品

        .. seealso::
           :py:meth:`can_stack_with`
        """
        if self.can_stack_with(other):
            # noinspection PyArgumentList
            return type(self)(self.count + other.count, self.id, self.components)
        raise ValueError("Cannot stack items with different id or components")


def _convert_other[F: Callable[..., Any]](func: F) -> F:
    """
    将被装饰方法的第一个非self参数转换为该实例

    :param func: 被装饰的方法
    :type func: Callable[..., Any]

    :return: 装饰后的方法
    :rtype: Callable[..., Any]
    """

    @wrapt.decorator  # type: ignore[misc]
    def decorator(wrapped: F, instance: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        if instance is None:
            raise TypeError("Cannot call method without instance")

        cls = type(instance)
        if not isinstance(args[0], cls):
            args = (cls(args[0]), *args[1:])
        return wrapped(*args, **kwargs)

    return decorator(func)  # type: ignore[no-any-return]


@dataclass(order=True)
class Experience:
    """
    经验值
    """
    points: int

    @classmethod
    def from_level(cls, level: int | float) -> Self:
        """
        从等级计算经验值

        :param level: 等级
        :type level: int | float

        :return: 经验值
        :rtype: Self
        """
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
        """
        转换为等级

        :return: 等级，剩余点数
        :rtype: tuple[int, int]
        """
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
class Hunger:
    """
    饥饿值
    """
    level: float
    saturation_level: float
    exhaustion_level: float

    @property
    def total(self) -> float:
        """
        饥饿值总计

        :return: 总饥饿值
        :rtype: float
        """
        return self.level + self.saturation_level - (self.exhaustion_level / 4)

    @total.setter
    def total(self, value: float) -> None:
        subtract = value - self.total
        if subtract < 0:
            # saturation_level减到0再减level
            self.saturation_level += subtract
            if self.saturation_level < 0:
                self.level += self.saturation_level
                self.saturation_level = 0
        else:
            self.level += subtract
            if self.level > 20:
                self.saturation_level += self.level - 20
                self.level = 20


@dataclass
class ResourceState:
    """
    资源状态
    """
    items: list[Item]
    experience: Experience
    hunger: Hunger
    health: float


__all__ = (
    "limit_value",
    "get_params",

    "Command",
    "CostStrategy",

    "Vec3",
    "Item",
    "Experience",
    "Hunger",
    "ResourceState",
)

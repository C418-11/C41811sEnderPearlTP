# -*- coding: utf-8 -*-


import operator
from abc import ABC
from abc import abstractmethod
from collections.abc import Callable
from collections.abc import Iterable
from typing import Any
from typing import Optional
from typing import override

from C41811.Config.utils import Ref  # type: ignore[attr-defined]
from mcdreforged.command.builder import command_builder_utils
from mcdreforged.command.builder.common import CommandContext
from mcdreforged.command.builder.common import ParseResult
from mcdreforged.command.builder.exception import IllegalArgument
from mcdreforged.command.builder.nodes.basic import ArgumentNode
from mcdreforged.command.command_source import CommandSource
from mcdreforged.command.command_source import PlayerCommandSource
from mcdreforged.minecraft.rtext.text import RTextBase
from mcdreforged.permission.permission_level import PermissionLevel
from mcdreforged.permission.permission_level import PermissionLevelItem
from mcdreforged.permission.permission_level import PermissionParam

from .cost_strategy import Vec3
from .helper import h
from .plugins_api import online_player_api


class InvalidPlayerName(IllegalArgument):
    """
    玩家名无效
    """

    def __init__(self, char_read: int | str, *, player_name: str):
        super().__init__(h.crtr("message.failure.argument.not_found.player", player=player_name), char_read)


class InvalidHomeName(IllegalArgument):
    """
    家名无效
    """

    def __init__(self, char_read: int | str, *, home_name: Optional[str]):
        print(char_read)
        super().__init__(h.crtr("message.failure.argument.not_found.home", home=home_name), char_read)


class InvalidWaypointName(IllegalArgument):
    """
    路径点名无效
    """

    def __init__(self, char_read: int | str, *, waypoint_name: Optional[str]):
        super().__init__(h.crtr("message.failure.argument.not_found.waypoint", waypoint=waypoint_name), char_read)


class DynamicEnumeration(ArgumentNode, ABC):
    """
    动态枚举参数
    """

    def _parse_validate(self, value: str) -> None:
        """`解析时` 验证参数的抽象方法，由子类实现"""

    def _visit_validate(self, context: CommandContext, parse_result: ParseResult) -> None:
        """`访问时` 验证参数的抽象方法，由子类实现"""

    @override
    def parse(self, text: str) -> ParseResult:
        # 提取参数
        arg = command_builder_utils.get_element(text)
        # 调用子类验证逻辑
        self._parse_validate(arg)
        # 返回解析结果
        return ParseResult(arg, len(arg))

    @override
    def _on_visited(self, context: CommandContext, parsed_result: ParseResult) -> None:
        # 调用子类验证逻辑
        self._visit_validate(context, parsed_result)
        super()._on_visited(context, parsed_result)


class PlayerName(DynamicEnumeration):
    """
    玩家名参数
    """

    @override
    def _get_suggestions(self, context: CommandContext) -> Iterable[str]:
        return online_player_api.get_player_list()

    @override
    def _parse_validate(self, value: str) -> None:
        if not online_player_api.check_online(value):
            raise InvalidPlayerName(value, player_name=value)


class LabelName(DynamicEnumeration, ABC):
    """
    标签名参数
    """

    def __init__(self, name: str, labels: Ref[dict[str | None, dict[str, Vec3]]], **kwargs: Any):
        super().__init__(name, **kwargs)
        self.labels = labels

    def _get_labels(self, player_name: Optional[str] = None) -> set[str]:
        labels: set[str] = set(self.labels.value.get(None, {}).keys())
        if player_name is not None:
            labels.update(self.labels.value.get(player_name, {}))
        return labels

    @override
    def _get_suggestions(self, context: CommandContext) -> Iterable[str]:
        # noinspection PyUnresolvedReferences
        return self._get_labels(context.source.player if isinstance(context.source, PlayerCommandSource) else None)

    @abstractmethod
    def _get_exception(self, parse_result: ParseResult) -> IllegalArgument:
        """
        返回一个异常，用于在解析失败时抛出
        """

    @override
    def _visit_validate(self, context: CommandContext, parse_result: ParseResult) -> None:
        # noinspection PyUnresolvedReferences
        labels = self._get_labels(context.source.player if isinstance(context.source, PlayerCommandSource) else None)
        if parse_result.value not in labels:
            raise self._get_exception(parse_result)


class HomeName(LabelName):
    """
    家参数
    """

    def _get_exception(self, parse_result: ParseResult) -> IllegalArgument:
        return InvalidHomeName(parse_result.char_read, home_name=parse_result.value)


class WaypointName(LabelName):
    """
    路径点参数
    """

    def _get_exception(self, parse_result: ParseResult) -> IllegalArgument:
        return InvalidWaypointName(parse_result.char_read, waypoint_name=parse_result.value)


def permission_checker(
        permission: PermissionParam | PermissionLevelItem,
        comparator: Callable[[int, int], bool] = operator.ge
) -> tuple[Callable[[CommandSource], bool], Callable[[], RTextBase]]:
    permission = permission if isinstance(permission, PermissionLevelItem) else PermissionLevel.from_value(permission)

    def checker(src: CommandSource) -> bool:
        return comparator(
            src.get_permission_level(),
            permission.level  # type: ignore[union-attr]
        )

    return checker, lambda: h.prtr("message.failure.no_permission")


__all__ = (
    "InvalidPlayerName",
    "InvalidHomeName",
    "InvalidWaypointName",

    "DynamicEnumeration",

    "PlayerName",
    "LabelName",
    "HomeName",
    "WaypointName",

    "permission_checker",
)

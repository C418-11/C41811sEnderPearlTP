# -*- coding: utf-8 -*-


import operator
from abc import abstractmethod
from collections.abc import Callable
from collections.abc import Iterable
from typing import override

from mcdreforged.command.builder import command_builder_utils
from mcdreforged.command.builder.common import CommandContext
from mcdreforged.command.builder.common import ParseResult
from mcdreforged.command.builder.exception import IllegalArgument
from mcdreforged.command.builder.nodes.basic import ArgumentNode
from mcdreforged.command.builder.nodes.basic import Literal
from mcdreforged.command.command_source import CommandSource
from mcdreforged.permission.permission_level import PermissionLevel
from mcdreforged.permission.permission_level import PermissionParam

from .helper import h
from .plugins_api import online_player_api


class InvalidPlayerName(IllegalArgument):
    """
    玩家名无效
    """

    def __init__(self, char_read: int | str, *, player_name: str):
        super().__init__(h.crtr("message.failure.argument.not_found.player", player_name), char_read)


class DynamicEnumeration(ArgumentNode):
    """
    动态枚举参数
    """

    @abstractmethod
    def _validate(self, value: str) -> None:
        """验证参数的抽象方法，由子类实现"""
        pass

    @override
    def parse(self, text: str) -> ParseResult:
        # 提取参数
        arg = command_builder_utils.get_element(text)
        # 调用子类验证逻辑
        self._validate(arg)
        # 返回解析结果
        return ParseResult(arg, len(arg))


class PlayerName(DynamicEnumeration):
    """
    玩家名参数
    """

    @override
    def _get_suggestions(self, context: CommandContext) -> Iterable[str]:
        return online_player_api.get_player_list()

    @override
    def _validate(self, value: str) -> None:
        if not online_player_api.check_online(value):
            raise InvalidPlayerName(value, player_name=value)


class PermissionLiteral(Literal):
    """
    权限Literal
    """

    def __init__(
            self,
            literal: str | Iterable[str],
            *,
            permission: PermissionParam,
            comparator: Callable[[int, int], bool] = operator.ge
    ):
        super().__init__(literal)
        self.requires(self._check_permission, self._denied_message)

        self.permission = PermissionLevel.from_value(permission)
        self.comparator = comparator

    def _check_permission(self, src: CommandSource) -> bool:
        return self.comparator(src.get_permission_level(), self.permission.level)

    @staticmethod
    def _denied_message() -> str:
        return h.crtr("message.failure.no_permission")


__all__ = (
    "InvalidPlayerName",
    "DynamicEnumeration",
    "PlayerName",
    "PermissionLiteral",
)

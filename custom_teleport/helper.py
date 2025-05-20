# -*- coding: utf-8 -*-


import inspect
from typing import Any

import hjson
from mcdreforged.command.builder.nodes.basic import Literal
from mcdreforged.minecraft.rtext.text import RTextBase
from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface
from mcdreforged.translation.translation_text import RTextMCDRTranslation


class Helper:
    """
    为插件提供更简洁的API
    """

    server: PluginServerInterface
    pkg_name: str | None = None
    translate_key_formatter: str

    def __init__(self):
        self.pkg_name: str | None = inspect.getmodule(inspect.stack()[0][0]).__package__

        self.translate_key_formatter = "{package_name}.{key}"
        self.translate_prefix = ""

    def initialize(self, server: PluginServerInterface) -> None:
        """
        延迟初始化方法

        :param server: 插件服务器接口
        :type server: PluginServerInterface
        """
        self.server = server

    def _translate_key_formatter(self, key: str) -> str:
        """
        格式化翻译键
    
        :param key: 插件内相对翻译键
        :type key: str

        :return: 完整的全局翻译键
        :rtype: str
        """
        return self.translate_key_formatter.format(key=key, package_name=self.pkg_name)

    def rtr(self, translate_key: str, *args: Any, **kwargs: Any) -> RTextMCDRTranslation:
        """
        获取翻译文本

        :param translate_key: 插件内部翻译键
        :type translate_key: str
        :param args: 翻译文本的参数
        :type args: Any
        :param kwargs: 翻译文本的参数
        :type kwargs: Any

        :return: 翻译后的文本
        """
        return self.server.rtr(
            self._translate_key_formatter(translate_key),
            *args, **kwargs
        )

    # noinspection SpellCheckingInspection
    def crtr(self, translate_key: str, *args: Any, **kwargs: Any) -> RTextBase:
        """
        获取支持组件的翻译文本

        :param translate_key: 插件内部翻译键
        :type translate_key: str
        :param args: 翻译文本的参数
        :type args: Any
        :param kwargs: 翻译文本的参数
        :type kwargs: Any

        :return: 翻译后的文本
        """

        translated_text = self.server.rtr(
            self._translate_key_formatter(translate_key),
            *args, **kwargs
        ).to_plain_text()

        try:
            text_object = hjson.loads(translated_text)
        except hjson.HjsonDecodeError:
            print("fail")
            text_object = translated_text

        return RTextBase.from_json_object(text_object)

    # noinspection SpellCheckingInspection
    def prtr(self, translate_key: str, *args: Any, **kwargs: Any) -> RTextBase:
        """
        获取带前缀的翻译文本

        :param translate_key: 插件内部翻译键
        :type translate_key: str
        :param args: 翻译文本的参数
        :type args: Any
        :param kwargs: 翻译文本的参数
        :type kwargs: Any

        :return: 翻译后的文本
        """

        text_obejct = self.crtr(translate_key, *args, **kwargs).to_json_object()
        text_obejct = [self.translate_prefix, text_obejct]
        return RTextBase.from_json_object(text_obejct)

    def register_command(
            self,
            help_message: str,
            root_node: Literal,
            *,
            allow_duplicates: bool = False,
            use_translate_key: bool = True
    ) -> None:
        self.server.register_command(root_node, allow_duplicates=allow_duplicates)
        for literal in root_node.literals:
            self.server.register_help_message(
                literal,
                self.rtr(help_message) if use_translate_key else help_message
            )


h = Helper()


def initialize(server: PluginServerInterface) -> None:
    """
    延迟初始化方法

    :param server: 插件服务器接口
    :type server: PluginServerInterface
    """
    h.initialize(server)


__all__ = (
    "Helper",

    "h",

    "initialize",
)

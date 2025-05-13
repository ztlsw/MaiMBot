import time
import traceback
from ..memory_system.Hippocampus import HippocampusManager
from ...config.config import global_config
from ..chat.message import MessageRecv
from ..storage.storage import MessageStorage
from ..chat.utils import is_mentioned_bot_in_message
from maim_message import Seg
from src.heart_flow.heartflow import heartflow
from src.common.logger_manager import get_logger
from ..chat.chat_stream import chat_manager
from ..chat.message_buffer import message_buffer
from ..utils.timer_calculator import Timer
from src.plugins.person_info.relationship_manager import relationship_manager
from typing import Optional, Tuple

logger = get_logger("chat")


class HeartFCProcessor:
    """心流处理器，负责处理接收到的消息并计算兴趣度"""

    def __init__(self):
        """初始化心流处理器，创建消息存储实例"""
        self.storage = MessageStorage()

    async def _handle_error(self, error: Exception, context: str, message: Optional[MessageRecv] = None) -> None:
        """统一的错误处理函数

        Args:
            error: 捕获到的异常
            context: 错误发生的上下文描述
            message: 可选的消息对象，用于记录相关消息内容
        """
        logger.error(f"{context}: {error}")
        logger.error(traceback.format_exc())
        if message and hasattr(message, "raw_message"):
            logger.error(f"相关消息原始内容: {message.raw_message}")

    async def _process_relationship(self, message: MessageRecv) -> None:
        """处理用户关系逻辑

        Args:
            message: 消息对象，包含用户信息
        """
        platform = message.message_info.platform
        user_id = message.message_info.user_info.user_id
        nickname = message.message_info.user_info.user_nickname
        cardname = message.message_info.user_info.user_cardname or nickname

        is_known = await relationship_manager.is_known_some_one(platform, user_id)

        if not is_known:
            logger.info(f"首次认识用户: {nickname}")
            await relationship_manager.first_knowing_some_one(platform, user_id, nickname, cardname, "")
        elif not await relationship_manager.is_qved_name(platform, user_id):
            logger.info(f"给用户({nickname},{cardname})取名: {nickname}")
            await relationship_manager.first_knowing_some_one(platform, user_id, nickname, cardname, "")

    async def _calculate_interest(self, message: MessageRecv) -> Tuple[float, bool]:
        """计算消息的兴趣度

        Args:
            message: 待处理的消息对象

        Returns:
            Tuple[float, bool]: (兴趣度, 是否被提及)
        """
        is_mentioned, _ = is_mentioned_bot_in_message(message)
        interested_rate = 0.0

        with Timer("记忆激活"):
            interested_rate = await HippocampusManager.get_instance().get_activate_from_text(
                message.processed_plain_text,
                fast_retrieval=True,
            )
            logger.trace(f"记忆激活率: {interested_rate:.2f}")

        if is_mentioned:
            interest_increase_on_mention = 1
            interested_rate += interest_increase_on_mention

        return interested_rate, is_mentioned

    def _get_message_type(self, message: MessageRecv) -> str:
        """获取消息类型

        Args:
            message: 消息对象

        Returns:
            str: 消息类型
        """
        if message.message_segment.type != "seglist":
            return message.message_segment.type

        if (
            isinstance(message.message_segment.data, list)
            and all(isinstance(x, Seg) for x in message.message_segment.data)
            and len(message.message_segment.data) == 1
        ):
            return message.message_segment.data[0].type

        return "seglist"

    async def process_message(self, message_data: str) -> None:
        """处理接收到的原始消息数据

        主要流程:
        1. 消息解析与初始化
        2. 消息缓冲处理
        3. 过滤检查
        4. 兴趣度计算
        5. 关系处理

        Args:
            message_data: 原始消息字符串
        """
        message = None
        try:
            # 1. 消息解析与初始化
            message = MessageRecv(message_data)
            groupinfo = message.message_info.group_info
            userinfo = message.message_info.user_info
            messageinfo = message.message_info

            # 2. 消息缓冲与流程序化
            await message_buffer.start_caching_messages(message)

            chat = await chat_manager.get_or_create_stream(
                platform=messageinfo.platform,
                user_info=userinfo,
                group_info=groupinfo,
            )

            subheartflow = await heartflow.get_or_create_subheartflow(chat.stream_id)
            message.update_chat_stream(chat)
            await message.process()

            # 3. 过滤检查
            if self._check_ban_words(message.processed_plain_text, chat, userinfo) or self._check_ban_regex(
                message.raw_message, chat, userinfo
            ):
                return

            # 4. 缓冲检查
            buffer_result = await message_buffer.query_buffer_result(message)
            if not buffer_result:
                msg_type = self._get_message_type(message)
                type_messages = {
                    "text": f"触发缓冲，消息：{message.processed_plain_text}",
                    "image": "触发缓冲，表情包/图片等待中",
                    "seglist": "触发缓冲，消息列表等待中",
                }
                logger.debug(type_messages.get(msg_type, "触发未知类型缓冲"))
                return

            # 5. 消息存储
            await self.storage.store_message(message, chat)
            logger.trace(f"存储成功: {message.processed_plain_text}")

            # 6. 兴趣度计算与更新
            interested_rate, is_mentioned = await self._calculate_interest(message)
            await subheartflow.interest_chatting.increase_interest(value=interested_rate)
            subheartflow.interest_chatting.add_interest_dict(message, interested_rate, is_mentioned)

            # 7. 日志记录
            mes_name = chat.group_info.group_name if chat.group_info else "私聊"
            current_time = time.strftime("%H点%M分%S秒", time.localtime(message.message_info.time))
            logger.info(
                f"[{current_time}][{mes_name}]"
                f"{userinfo.user_nickname}:"
                f"{message.processed_plain_text}"
                f"[兴趣度: {interested_rate:.2f}]"
            )

            # 8. 关系处理
            await self._process_relationship(message)

        except Exception as e:
            await self._handle_error(e, "消息处理失败", message)

    def _check_ban_words(self, text: str, chat, userinfo) -> bool:
        """检查消息是否包含过滤词

        Args:
            text: 待检查的文本
            chat: 聊天对象
            userinfo: 用户信息

        Returns:
            bool: 是否包含过滤词
        """
        for word in global_config.ban_words:
            if word in text:
                chat_name = chat.group_info.group_name if chat.group_info else "私聊"
                logger.info(f"[{chat_name}]{userinfo.user_nickname}:{text}")
                logger.info(f"[过滤词识别]消息中含有{word}，filtered")
                return True
        return False

    def _check_ban_regex(self, text: str, chat, userinfo) -> bool:
        """检查消息是否匹配过滤正则表达式

        Args:
            text: 待检查的文本
            chat: 聊天对象
            userinfo: 用户信息

        Returns:
            bool: 是否匹配过滤正则
        """
        for pattern in global_config.ban_msgs_regex:
            if pattern.search(text):
                chat_name = chat.group_info.group_name if chat.group_info else "私聊"
                logger.info(f"[{chat_name}]{userinfo.user_nickname}:{text}")
                logger.info(f"[正则表达式过滤]消息匹配到{pattern}，filtered")
                return True
        return False

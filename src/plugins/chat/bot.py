from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message as EventMessage, Bot
from .message import Message,MessageSet
from .config import BotConfig, global_config
from .storage import MessageStorage
from .llm_generator import LLMResponseGenerator
from .message_stream import MessageStream, MessageStreamContainer
from .topic_identifier import topic_identifier
from random import random, choice
from .emoji_manager import emoji_manager  # 导入表情包管理器
import time
import os
from .cq_code import CQCode  # 导入CQCode模块
from .message_send_control import message_sender  # 导入消息发送控制器
from .message import Message_Thinking  # 导入 Message_Thinking 类
from .relationship_manager import relationship_manager
from .willing_manager import willing_manager  # 导入意愿管理器
from .utils import is_mentioned_bot_in_txt, calculate_typing_time
from ..memory_system.memory import memory_graph

class ChatBot:
    def __init__(self, config: BotConfig):
        self.config = config
        self.storage = MessageStorage()
        self.gpt = LLMResponseGenerator(config)
        self.bot = None  # bot 实例引用
        self._started = False
        
        self.emoji_chance = 0.2  # 发送表情包的基础概率
        self.message_streams = MessageStreamContainer()
        self.message_sender = message_sender
        
    async def _ensure_started(self):
        """确保所有任务已启动"""
        if not self._started:
            # 只保留必要的任务
            self._started = True
                

    async def handle_message(self, event: GroupMessageEvent, bot: Bot) -> None:
        """处理收到的群消息"""
        
        if event.group_id not in self.config.talk_allowed_groups:
            return
        self.bot = bot  # 更新 bot 实例
        
        if event.user_id in self.config.ban_user_id:
            return
        
        # 打印原始消息内容
        '''
        print(f"\n\033[1;33m[消息详情]\033[0m")
        # print(f"- 原始消息: {str(event.raw_message)}")
        print(f"- post_type: {event.post_type}")
        print(f"- sub_type: {event.sub_type}")
        print(f"- user_id: {event.user_id}")
        print(f"- message_type: {event.message_type}")
        # print(f"- message_id: {event.message_id}")
        # print(f"- message: {event.message}")
        print(f"- original_message: {event.original_message}")
        print(f"- raw_message: {event.raw_message}")
        # print(f"- font: {event.font}")
        print(f"- sender: {event.sender}")
        # print(f"- to_me: {event.to_me}")
        
        if event.reply:
            print(f"\n\033[1;33m[回复消息详情]\033[0m")
            # print(f"- message_id: {event.reply.message_id}")
            print(f"- message_type: {event.reply.message_type}")
            print(f"- sender: {event.reply.sender}")
            # print(f"- time: {event.reply.time}")
            print(f"- message: {event.reply.message}")
            print(f"- raw_message: {event.reply.raw_message}")
            # print(f"- original_message: {event.reply.original_message}")
        '''

        
        group_info = await bot.get_group_info(group_id=event.group_id)

        
        
        sender_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id, no_cache=True)
        

        await relationship_manager.update_relationship(user_id = event.user_id, data = sender_info)
        await relationship_manager.update_relationship_value(user_id = event.user_id, relationship_value = 0.5)
        # print(f"\033[1;32m[关系管理]\033[0m 更新关系值: {relationship_manager.get_relationship(event.user_id).relationship_value}")
        
        
        message = Message(
            group_id=event.group_id,
            user_id=event.user_id,
            message_id=event.message_id,
            raw_message=str(event.original_message), 
            plain_text=event.get_plaintext(),
            reply_message=event.reply,
        )
        
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(message.time))

        topic = topic_identifier.identify_topic_jieba(message.processed_plain_text)
        print(f"\033[1;32m[主题识别]\033[0m 主题: {topic}")
        
        all_num = 0
        interested_num = 0
        if topic:
            for current_topic in topic:
                all_num += 1
                first_layer_items, second_layer_items = memory_graph.get_related_item(current_topic, depth=2)
                if first_layer_items:
                    interested_num += 1
                    print(f"\033[1;32m[前额叶]\033[0m 对|{current_topic}|有印象")
        interested_rate = interested_num / all_num if all_num > 0 else 0
        
     
        await self.storage.store_message(message, topic[0] if topic else None)
        

        is_mentioned = is_mentioned_bot_in_txt(message.processed_plain_text)
        reply_probability = willing_manager.change_reply_willing_received(
            event.group_id, 
            topic[0] if topic else None,
            is_mentioned,
            self.config,
            event.user_id,
            message.is_emoji,
            interested_rate
        )
        current_willing = willing_manager.get_willing(event.group_id)
        
        
        print(f"\033[1;32m[{current_time}][{message.group_name}]{message.user_nickname}:\033[0m {message.processed_plain_text}\033[1;36m[回复意愿:{current_willing:.2f}][概率:{reply_probability:.1f}]\033[0m")
        response = ""
        # 创建思考消息
        if random() < reply_probability:
            
            tinking_time_point = round(time.time(), 2)
            think_id = 'mt' + str(tinking_time_point)
            thinking_message = Message_Thinking(message=message,message_id=think_id)
            message_sender.send_temp_container.add_message(thinking_message)

            willing_manager.change_reply_willing_sent(thinking_message.group_id)
            
            response, emotion = await self.gpt.generate_response(message)
            
            # 如果生成了回复，发送并记录
            
            
        if response:
            message_set = MessageSet(event.group_id, self.config.BOT_QQ, think_id)
            accu_typing_time = 0
            for msg in response:
                print(f"当前消息: {msg}")
                typing_time = calculate_typing_time(msg)
                accu_typing_time += typing_time
                timepoint = tinking_time_point+accu_typing_time
                # print(f"\033[1;32m[调试]\033[0m 消息: {msg}，添加！, 累计打字时间: {accu_typing_time:.2f}秒")
                
                bot_message = Message(
                    group_id=event.group_id,
                    user_id=self.config.BOT_QQ,
                    message_id=think_id,
                    message_based_id=event.message_id,
                    raw_message=msg,
                    plain_text=msg,
                    processed_plain_text=msg,
                    user_nickname=global_config.BOT_NICKNAME,
                    group_name=message.group_name,
                    time=timepoint
                )
                message_set.add_message(bot_message)
                
            message_sender.send_temp_container.update_thinking_message(message_set)

    
            
            bot_response_time = tinking_time_point
            if random() < self.config.emoji_chance:
                emoji_path = await emoji_manager.get_emoji_for_emotion(emotion)
                if emoji_path:
                    emoji_cq = CQCode.create_emoji_cq(emoji_path)
                    
                    if random() < 0.5:
                        bot_response_time = tinking_time_point - 1
                    else:
                        bot_response_time = bot_response_time + 1
                        
                    bot_message = Message(
                            group_id=event.group_id,
                            user_id=self.config.BOT_QQ,
                            message_id=0,
                            raw_message=emoji_cq,
                            plain_text=emoji_cq,
                            processed_plain_text=emoji_cq,
                            user_nickname=global_config.BOT_NICKNAME,
                            group_name=message.group_name,
                            time=bot_response_time,
                            is_emoji=True,
                            translate_cq=False
                        )
                    message_sender.send_temp_container.add_message(bot_message)
        
        # 如果收到新消息，提高回复意愿
        willing_manager.change_reply_willing_after_sent(event.group_id)
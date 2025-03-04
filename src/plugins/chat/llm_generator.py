from typing import Dict, Any, List, Optional, Union, Tuple
from openai import OpenAI
import asyncio
from functools import partial
from .message import Message
from .config import global_config
from ...common.database import Database
import random
import time
import numpy as np
from .relationship_manager import relationship_manager
from .prompt_builder import prompt_builder
from .config import global_config
from .utils import process_llm_response
from nonebot import get_driver
from ..models.utils_model import LLM_request

driver = get_driver()
config = driver.config


class ResponseGenerator:
    def __init__(self):
        self.model_r1 = LLM_request(model=global_config.llm_reasoning, temperature=0.7)
        self.model_v3 = LLM_request(model=global_config.llm_normal, temperature=0.7)
        self.model_r1_distill = LLM_request(model=global_config.llm_reasoning_minor, temperature=0.7)
        self.db = Database.get_instance()
        self.current_model_type = 'r1'  # 默认使用 R1

    async def generate_response(self, message: Message) -> Optional[Union[str, List[str]]]:
        """根据当前模型类型选择对应的生成函数"""
        # 从global_config中获取模型概率值并选择模型
        rand = random.random()
        if rand < global_config.MODEL_R1_PROBABILITY:
            self.current_model_type = 'r1'
            current_model = self.model_r1
        elif rand < global_config.MODEL_R1_PROBABILITY + global_config.MODEL_V3_PROBABILITY:
            self.current_model_type = 'v3'
            current_model = self.model_v3
        else:
            self.current_model_type = 'r1_distill'
            current_model = self.model_r1_distill

        print(f"+++++++++++++++++{global_config.BOT_NICKNAME}{self.current_model_type}思考中+++++++++++++++++")
        
        model_response = await self._generate_response_with_model(message, current_model)
        
        if model_response:
            print(f'{global_config.BOT_NICKNAME}的回复是：{model_response}')
            model_response, emotion = await self._process_response(model_response)
            if model_response:
                print(f"为 '{model_response}' 获取到的情感标签为：{emotion}")
            return model_response, emotion
        return None, []

    async def _generate_response_with_model(self, message: Message, model: LLM_request) -> Optional[str]:
        """使用指定的模型生成回复"""
        sender_name = message.user_nickname or f"用户{message.user_id}"
        
        # 获取关系值
        relationship_value = relationship_manager.get_relationship(message.user_id).relationship_value if relationship_manager.get_relationship(message.user_id) else 0.0
        if relationship_value != 0.0:
            print(f"\033[1;32m[关系管理]\033[0m 回复中_当前关系值: {relationship_value}")
        
        # 构建prompt
        prompt, prompt_check = prompt_builder._build_prompt(
            message_txt=message.processed_plain_text,
            sender_name=sender_name,
            relationship_value=relationship_value,
            group_id=message.group_id
        )

        # 读空气模块
        if global_config.enable_kuuki_read:
            content_check, reasoning_content_check = await self.model_v3.generate_response(prompt_check)
            print(f"\033[1;32m[读空气]\033[0m 读空气结果为{content_check}")
            if 'yes' not in content_check.lower() and random.random() < 0.3:
                self._save_to_db(
                    message=message,
                    sender_name=sender_name,
                    prompt=prompt,
                    prompt_check=prompt_check,
                    content="",
                    content_check=content_check,
                    reasoning_content="",
                    reasoning_content_check=reasoning_content_check
                )
                return None

        # 生成回复
        content, reasoning_content = await model.generate_response(prompt)
        
        # 保存到数据库
        self._save_to_db(
            message=message,
            sender_name=sender_name,
            prompt=prompt,
            prompt_check=prompt_check,
            content=content,
            content_check=content_check if global_config.enable_kuuki_read else "",
            reasoning_content=reasoning_content,
            reasoning_content_check=reasoning_content_check if global_config.enable_kuuki_read else ""
        )
        
        return content

    def _save_to_db(self, message: Message, sender_name: str, prompt: str, prompt_check: str,
                    content: str, content_check: str, reasoning_content: str, reasoning_content_check: str):
        """保存对话记录到数据库"""
        self.db.db.reasoning_logs.insert_one({
            'time': time.time(),
            'group_id': message.group_id,
            'user': sender_name,
            'message': message.processed_plain_text,
            'model': self.current_model_type,
            'reasoning_check': reasoning_content_check,
            'response_check': content_check,
            'reasoning': reasoning_content,
            'response': content,
            'prompt': prompt,
            'prompt_check': prompt_check
        })

    async def _get_emotion_tags(self, content: str) -> List[str]:
        """提取情感标签"""
        try:
            prompt = f'''请从以下内容中，从"happy,angry,sad,surprised,disgusted,fearful,neutral"中选出最匹配的1个情感标签并输出
            只输出标签就好，不要输出其他内容:
            内容：{content}
            输出：
            '''
            
            content, _ = await self.model_v3.generate_response(prompt)
            return [content.strip()] if content else ["neutral"]
            
        except Exception as e:
            print(f"获取情感标签时出错: {e}")
            return ["neutral"]
    
    async def _process_response(self, content: str) -> Tuple[List[str], List[str]]:
        """处理响应内容，返回处理后的内容和情感标签"""
        if not content:
            return None, []
        
        emotion_tags = await self._get_emotion_tags(content)
        processed_response = process_llm_response(content)
        
        return processed_response, emotion_tags
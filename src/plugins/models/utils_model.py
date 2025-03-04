import aiohttp
import asyncio
import requests
import time
from typing import Tuple, Union
from nonebot import get_driver
from ..chat.config import global_config
driver = get_driver()
config = driver.config

class LLM_request:
    def __init__(self, model = global_config.llm_normal,**kwargs):
        # 将大写的配置键转换为小写并从config中获取实际值
        try:
            self.api_key = getattr(config, model["key"])
            self.base_url = getattr(config, model["base_url"])
        except AttributeError as e:
            raise ValueError(f"配置错误：找不到对应的配置项 - {str(e)}")
        self.model_name = model["name"]
        self.params = kwargs

    async def generate_response(self, prompt: str) -> Tuple[str, str]:
        """根据输入的提示生成模型的异步响应"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 构建请求体
        data = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            **self.params
        }
        
        # 发送请求到完整的chat/completions端点
        api_url = f"{self.base_url.rstrip('/')}/chat/completions"
        
        max_retries = 3
        base_wait_time = 15
        
        for retry in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(api_url, headers=headers, json=data) as response:
                        if response.status == 429:
                            wait_time = base_wait_time * (2 ** retry)  # 指数退避
                            print(f"遇到请求限制(429)，等待{wait_time}秒后重试...")
                            await asyncio.sleep(wait_time)
                            continue
                            
                        response.raise_for_status()  # 检查其他响应状态
                        
                        result = await response.json()
                        if "choices" in result and len(result["choices"]) > 0:
                            content = result["choices"][0]["message"]["content"]
                            reasoning_content = result["choices"][0]["message"].get("reasoning_content", "")
                            return content, reasoning_content
                        return "没有返回结果", ""
                
            except Exception as e:
                if retry < max_retries - 1:  # 如果还有重试机会
                    wait_time = base_wait_time * (2 ** retry)
                    print(f"请求失败，等待{wait_time}秒后重试... 错误: {str(e)}")
                    await asyncio.sleep(wait_time)
                else:
                    return f"请求失败: {str(e)}", ""
        
        return "达到最大重试次数，请求仍然失败", ""

    async def generate_response_for_image(self, prompt: str, image_base64: str) -> Tuple[str, str]:
        """根据输入的提示和图片生成模型的异步响应"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 构建请求体
        data = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            **self.params
        }
        
        # 发送请求到完整的chat/completions端点
        api_url = f"{self.base_url.rstrip('/')}/chat/completions"
        
        max_retries = 3
        base_wait_time = 15
        
        for retry in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(api_url, headers=headers, json=data) as response:
                        if response.status == 429:
                            wait_time = base_wait_time * (2 ** retry)  # 指数退避
                            print(f"遇到请求限制(429)，等待{wait_time}秒后重试...")
                            await asyncio.sleep(wait_time)
                            continue
                            
                        response.raise_for_status()  # 检查其他响应状态
                        
                        result = await response.json()
                        if "choices" in result and len(result["choices"]) > 0:
                            content = result["choices"][0]["message"]["content"]
                            reasoning_content = result["choices"][0]["message"].get("reasoning_content", "")
                            return content, reasoning_content
                        return "没有返回结果", ""
                
            except Exception as e:
                if retry < max_retries - 1:  # 如果还有重试机会
                    wait_time = base_wait_time * (2 ** retry)
                    print(f"请求失败，等待{wait_time}秒后重试... 错误: {str(e)}")
                    await asyncio.sleep(wait_time)
                else:
                    return f"请求失败: {str(e)}", ""
        
        return "达到最大重试次数，请求仍然失败", ""

    def generate_response_for_image_sync(self, prompt: str, image_base64: str) -> Tuple[str, str]:
        """同步方法：根据输入的提示和图片生成模型的响应"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 构建请求体
        data = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            **self.params
        }
        
        # 发送请求到完整的chat/completions端点
        api_url = f"{self.base_url.rstrip('/')}/chat/completions"
        
        max_retries = 2
        base_wait_time = 6
        
        for retry in range(max_retries):
            try:
                response = requests.post(api_url, headers=headers, json=data, timeout=30)
                
                if response.status_code == 429:
                    wait_time = base_wait_time * (2 ** retry)  # 指数退避
                    print(f"遇到请求限制(429)，等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                    
                response.raise_for_status()  # 检查其他响应状态
                
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    reasoning_content = result["choices"][0]["message"].get("reasoning_content", "")
                    return content, reasoning_content
                return "没有返回结果", ""
                
            except Exception as e:
                if retry < max_retries - 1:  # 如果还有重试机会
                    wait_time = base_wait_time * (2 ** retry)
                    print(f"请求失败，等待{wait_time}秒后重试... 错误: {str(e)}")
                    time.sleep(wait_time)
                else:
                    return f"请求失败: {str(e)}", ""
        
        return "达到最大重试次数，请求仍然失败", ""

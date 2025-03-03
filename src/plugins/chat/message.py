from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple, ForwardRef
import time
import jieba.analyse as jieba_analyse
import os
from datetime import datetime
from ...common.database import Database
from PIL import Image
from .config import global_config
import urllib3
from .utils_user import get_user_nickname
from .utils_cq import parse_cq_code
from .cq_code import cq_code_tool,CQCode

Message = ForwardRef('Message')  # 添加这行
# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#这个类是消息数据类，用于存储和管理消息数据。
#它定义了消息的属性，包括群组ID、用户ID、消息ID、原始消息内容、纯文本内容和时间戳。
#它还定义了两个辅助属性：keywords用于提取消息的关键词，is_plain_text用于判断消息是否为纯文本。


@dataclass
class Message:
    """消息数据类"""
    group_id: int = None
    user_id: int = None
    user_nickname: str = None  # 用户昵称
    group_name: str = None  # 群名称    
    
    message_id: int = None
    raw_message: str = None
    plain_text: str = None
    
    message_based_id: int = None
    reply_message: Dict = None  # 存储回复消息
    
    message_segments: List[Dict] = None  # 存储解析后的消息片段
    processed_plain_text: str = None  # 用于存储处理后的plain_text
    detailed_plain_text: str = None  # 用于存储详细可读文本
    
    time: float = None
    
    is_emoji: bool = False # 是否是表情包
    has_emoji: bool = False # 是否包含表情包
    
    translate_cq: bool = True # 是否翻译cq码

    
    reply_benefits: float = 0.0
    
    type: str = 'received' # 消息类型，可以是received或者send
    
    def __post_init__(self):
        if self.time is None:
            self.time = int(time.time())
        
        if not self.user_nickname:
            self.user_nickname = get_user_nickname(self.user_id)
        
        if not self.group_name:
            self.group_name = self.get_groupname(self.group_id)
        
        if not self.processed_plain_text:
            if self.raw_message:
                self.message_segments = self.parse_message_segments(str(self.raw_message))
                self.processed_plain_text = ' '.join(
                    seg.translated_plain_text
                    for seg in self.message_segments
                )
        #将详细翻译为详细可读文本
        time_str = time.strftime("%m-%d %H:%M:%S", time.localtime(self.time))
        name = self.user_nickname or f"用户{self.user_id}"
        content = self.processed_plain_text
        self.detailed_plain_text = f"[{time_str}] {name}: {content}\n"
                
        
    def get_groupname(self, group_id: int) -> str:
        if not group_id:
            return "未知群"
        group_id = int(group_id)    
        # 使用数据库单例
        db = Database.get_instance()
        # 查找用户，打印查询条件和结果
        query = {'group_id': group_id}
        group = db.db.group_info.find_one(query)
        if group:
            return group.get('group_name')
        else:
            return f"群{group_id}"
    
    def parse_message_segments(self, message: str) -> List[CQCode]:
        """
        将消息解析为片段列表，包括纯文本和CQ码
        返回的列表中每个元素都是字典，包含：
        - cq_code_list:分割出的聊天对象，包括文本和CQ码
        - trans_list:翻译后的对象列表
        """
        # print(f"\033[1;34m[调试信息]\033[0m 正在处理消息: {message}")
        cq_code_dict_list = []
        trans_list = []
        
        start = 0
        while True:
            # 查找下一个CQ码的开始位置
            cq_start = message.find('[CQ:', start)
            #如果没有cq码，直接返回文本内容
            if cq_start == -1:
                # 如果没有找到更多CQ码，添加剩余文本
                if start < len(message):
                    text = message[start:].strip()
                    if text:  # 只添加非空文本
                        cq_code_dict_list.append(parse_cq_code(text))
                break
            # 添加CQ码前的文本
            if cq_start > start:
                text = message[start:cq_start].strip()
                if text:  # 只添加非空文本
                    cq_code_dict_list.append(parse_cq_code(text))
            # 查找CQ码的结束位置
            cq_end = message.find(']', cq_start)
            if cq_end == -1:
                # CQ码未闭合，作为普通文本处理
                text = message[cq_start:].strip()
                if text:
                    cq_code_dict_list.append(parse_cq_code(text))
                break
            cq_code = message[cq_start:cq_end + 1]
            
            #将cq_code解析成字典
            cq_code_dict_list.append(parse_cq_code(cq_code))
            # 更新start位置到当前CQ码之后
            start = cq_end + 1
            
        # print(f"\033[1;34m[调试信息]\033[0m 提取的消息对象：列表: {cq_code_dict_list}")
        
        #判定是否是表情包消息，以及是否含有表情包
        if len(cq_code_dict_list) == 1 and cq_code_dict_list[0]['type'] == 'image':
            self.is_emoji = True
            self.has_emoji_emoji = True
        else:
            for segment in cq_code_dict_list:
                if segment['type'] == 'image' and segment['data'].get('sub_type') == '1':
                    self.has_emoji_emoji = True
                    break
                
        
        #翻译作为字典的CQ码  
        for _code_item in cq_code_dict_list:
            message_obj = cq_code_tool.cq_from_dict_to_class(_code_item,reply = self.reply_message)
            trans_list.append(message_obj)       
        return trans_list

class Message_Thinking:
    """消息思考类"""
    def __init__(self, message: Message,message_id: str):
        # 复制原始消息的基本属性
        self.group_id = message.group_id
        self.user_id = message.user_id
        self.user_nickname = message.user_nickname
        self.group_name = message.group_name
        
        self.message_id = message_id
        
        # 思考状态相关属性
        self.thinking_text = "正在思考..."
        self.time = int(time.time())
        self.thinking_time = 0
    
    def update_thinking_time(self):
        self.thinking_time = round(time.time(), 2) - self.time
    
    @property
    def processed_plain_text(self) -> str:
        """获取处理后的文本"""
        return self.thinking_text
    
    def __str__(self) -> str:
        return f"[思考中] 群:{self.group_id} 用户:{self.user_nickname} 时间:{self.time} 消息ID:{self.message_id}"
        
        
class MessageSet:
    """消息集合类，可以存储多个相关的消息"""
    def __init__(self, group_id: int, user_id: int, message_id: str):
        self.group_id = group_id
        self.user_id = user_id
        self.message_id = message_id
        self.messages: List[Message] = []
        self.time = round(time.time(), 2)
        
    def add_message(self, message: Message) -> None:
        """添加消息到集合"""
        self.messages.append(message)
        # 按时间排序
        self.messages.sort(key=lambda x: x.time)
        
    def get_message_by_index(self, index: int) -> Optional[Message]:
        """通过索引获取消息"""
        if 0 <= index < len(self.messages):
            return self.messages[index]
        return None
        
    def get_message_by_time(self, target_time: float) -> Optional[Message]:
        """获取最接近指定时间的消息"""
        if not self.messages:
            return None
            
        # 使用二分查找找到最接近的消息
        left, right = 0, len(self.messages) - 1
        while left < right:
            mid = (left + right) // 2
            if self.messages[mid].time < target_time:
                left = mid + 1
            else:
                right = mid
                
        return self.messages[left]
        
        
    def clear_messages(self) -> None:
        """清空所有消息"""
        self.messages.clear()
        
    def remove_message(self, message: Message) -> bool:
        """移除指定消息"""
        if message in self.messages:
            self.messages.remove(message)
            return True
        return False
        
    def __str__(self) -> str:
        return f"MessageSet(id={self.message_id}, count={len(self.messages)})"
        
    def __len__(self) -> int:
        return len(self.messages)
        

        
        
        
        
    

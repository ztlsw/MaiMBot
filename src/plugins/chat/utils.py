import time
import random
from typing import List
from .message import Message
import requests
import numpy as np
from .config import llm_config, global_config
import re
from typing import Dict
from collections import Counter
import math


def combine_messages(messages: List[Message]) -> str:
    """将消息列表组合成格式化的字符串
    
    Args:
        messages: Message对象列表
        
    Returns:
        str: 格式化后的消息字符串
    """
    result = ""
    for message in messages:
        time_str = time.strftime("%m-%d %H:%M:%S", time.localtime(message.time))
        name = message.user_nickname or f"用户{message.user_id}"
        content = message.processed_plain_text or message.plain_text
        
        result += f"[{time_str}] {name}: {content}\n"
        
    return result

def db_message_to_str (message_dict: Dict) -> str:
    print(f"message_dict: {message_dict}")
    time_str = time.strftime("%m-%d %H:%M:%S", time.localtime(message_dict["time"]))
    name = message_dict.get("user_nickname", "") or f"用户{message_dict['user_id']}"
    content = message_dict.get("processed_plain_text", "")
    result = f"[{time_str}] {name}: {content}\n"
    print(f"result: {result}")
    return result


def is_mentioned_bot_in_message(message: Message) -> bool:
    """检查消息是否提到了机器人"""
    keywords = [global_config.BOT_NICKNAME]
    for keyword in keywords:
        if keyword in message.processed_plain_text:
            return True
    return False

def is_mentioned_bot_in_txt(message: str) -> bool:
    """检查消息是否提到了机器人"""
    keywords = [global_config.BOT_NICKNAME]
    for keyword in keywords:
        if keyword in message:
            return True
    return False

def get_embedding(text):
    url = "https://api.siliconflow.cn/v1/embeddings"
    payload = {
        "model": "BAAI/bge-m3",
        "input": text,
        "encoding_format": "float"
    }
    headers = {
        "Authorization": f"Bearer {llm_config.SILICONFLOW_API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.request("POST", url, json=payload, headers=headers)
    
    if response.status_code != 200:
        print(f"API请求失败: {response.status_code}")
        print(f"错误信息: {response.text}")
        return None
        
    return response.json()['data'][0]['embedding']

def cosine_similarity(v1, v2):
    dot_product = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    return dot_product / (norm1 * norm2)

def calculate_information_content(text):   
    """计算文本的信息量（熵）"""
    # 统计字符频率
    char_count = Counter(text)
    total_chars = len(text)
    
    # 计算熵
    entropy = 0
    for count in char_count.values():
        probability = count / total_chars
        entropy -= probability * math.log2(probability)
    
    return entropy

def get_cloest_chat_from_db(db, length: int, timestamp: str):
    # 从数据库中根据时间戳获取离其最近的聊天记录
    chat_text = ''
    closest_record = db.db.messages.find_one({"time": {"$lte": timestamp}}, sort=[('time', -1)])  # 调试输出
    # print(f"距离time最近的消息时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(closest_record['time'])))}")
    
    if closest_record:
        closest_time = closest_record['time']
        group_id = closest_record['group_id']  # 获取groupid
        # 获取该时间戳之后的length条消息，且groupid相同
        chat_record = list(db.db.messages.find({"time": {"$gt": closest_time}, "group_id": group_id}).sort('time', 1).limit(length))
        for record in chat_record:
            time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(record['time'])))
            chat_text += f'[{time_str}] {record["user_nickname"] or "用户" + str(record["user_id"])}: {record["processed_plain_text"]}\n'  # 添加发送者和时间信息
        return chat_text
    
    return []  # 如果没有找到记录，返回空列表


def get_recent_group_messages(db, group_id: int, limit: int = 12) -> list:
    """从数据库获取群组最近的消息记录
    
    Args:
        db: Database实例
        group_id: 群组ID
        limit: 获取消息数量，默认12条
        
    Returns:
        list: Message对象列表，按时间正序排列
    """

        # 从数据库获取最近消息
    recent_messages = list(db.db.messages.find(
        {"group_id": group_id},
        {
            "time": 1,
            "user_id": 1,
            "user_nickname": 1,
            "message_id": 1,
            "raw_message": 1,
            "processed_text": 1
        }
    ).sort("time", -1).limit(limit))

    if not recent_messages:
        return []
        
    # 转换为 Message对象列表
    from .message import Message
    message_objects = []
    for msg_data in recent_messages:
        msg = Message(
            time=msg_data["time"],
            user_id=msg_data["user_id"],
            user_nickname=msg_data.get("user_nickname", ""),
            message_id=msg_data["message_id"],
            raw_message=msg_data["raw_message"],
            processed_plain_text=msg_data.get("processed_text", ""),
            group_id=group_id
        )
        message_objects.append(msg)
    
    # 按时间正序排列
    message_objects.reverse()
    return message_objects

def get_recent_group_detailed_plain_text(db, group_id: int, limit: int = 12,combine = False):
    recent_messages = list(db.db.messages.find(
        {"group_id": group_id},
        {
            "time": 1,  # 返回时间字段
            "user_id": 1,  # 返回用户ID字段
            "user_nickname": 1,  # 返回用户昵称字段
            "message_id": 1,  # 返回消息ID字段
            "detailed_plain_text": 1  # 返回处理后的文本字段
        }
    ).sort("time", -1).limit(limit))

    if not recent_messages:
        return []
    
    message_detailed_plain_text = ''
    message_detailed_plain_text_list = []
    
    
    if combine:
        for msg_db_data in recent_messages:
            message_detailed_plain_text+=str(msg_db_data["detailed_plain_text"])
        return message_detailed_plain_text
    else:
        for msg_db_data in recent_messages:
            message_detailed_plain_text_list.append(msg_db_data["detailed_plain_text"])
        return message_detailed_plain_text_list



def split_into_sentences_w_remove_punctuation(text: str) -> List[str]:
    """将文本分割成句子，但保持书名号中的内容完整
    Args:
        text: 要分割的文本字符串
    Returns:
        List[str]: 分割后的句子列表
    """
    len_text = len(text)
    if len_text < 5:
        if random.random() < 0.01:
            return list(text)  # 如果文本很短且触发随机条件,直接按字符分割
        else:
            return [text]
    if len_text < 12:
        split_strength = 0.3
    elif len_text < 32:
        split_strength = 0.7
    else:
        split_strength = 0.9
    #先移除换行符
    # print(f"split_strength: {split_strength}")
    
    # print(f"处理前的文本: {text}")
    
    # 统一将英文逗号转换为中文逗号
    text = text.replace(',', '，')
    text = text.replace('\n', ' ')
    
    # print(f"处理前的文本: {text}")
    
    text_no_1 = ''
    for letter in text:
        # print(f"当前字符: {letter}")
        if letter in ['!','！','?','？']:
            # print(f"当前字符: {letter}, 随机数: {random.random()}")
            if random.random() < split_strength:
                letter = ''
        if letter in ['。','…']:
            # print(f"当前字符: {letter}, 随机数: {random.random()}")
            if random.random() < 1 - split_strength:
                letter = ''
        text_no_1 += letter
        
    # 对每个逗号单独判断是否分割
    sentences = [text_no_1]
    new_sentences = []
    for sentence in sentences:
        parts = sentence.split('，')
        current_sentence = parts[0]
        for part in parts[1:]:
            if random.random() < split_strength:
                new_sentences.append(current_sentence.strip())
                current_sentence = part
            else:
                current_sentence += '，' + part
        # 处理空格分割
        space_parts = current_sentence.split(' ')
        current_sentence = space_parts[0]
        for part in space_parts[1:]:
            if random.random() < split_strength:
                new_sentences.append(current_sentence.strip())
                current_sentence = part
            else:
                current_sentence += ' ' + part
        new_sentences.append(current_sentence.strip())
    sentences = [s for s in new_sentences if s]  # 移除空字符串

    # print(f"分割后的句子: {sentences}")
    sentences_done = []
    for sentence in sentences:
        sentence = sentence.rstrip('，,')
        if random.random() < split_strength*0.5:
            sentence = sentence.replace('，', '').replace(',', '')
        elif random.random() < split_strength:
            sentence = sentence.replace('，', ' ').replace(',', ' ')
        sentences_done.append(sentence)
        
    print(f"处理后的句子: {sentences_done}")
    return sentences_done

# 常见的错别字映射
TYPO_DICT = {
    '的': '地得',
    '了': '咯啦勒',
    '吗': '嘛麻',
    '吧': '八把罢',
    '是': '事',
    '在': '再在',
    '和': '合',
    '有': '又',
    '我': '沃窝喔',
    '你': '泥尼拟',
    '他': '它她塔祂',
    '们': '门',
    '啊': '阿哇',
    '呢': '呐捏',
    '都': '豆读毒',
    '很': '狠',
    '会': '回汇',
    '去': '趣取曲',
    '做': '作坐',
    '想': '相像',
    '说': '说税睡',
    '看': '砍堪刊',
    '来': '来莱赖',
    '好': '号毫豪',
    '给': '给既继',
    '过': '锅果裹',
    '能': '嫩',
    '为': '位未',
    '什': '甚深伸',
    '么': '末麽嘛',
    '话': '话花划',
    '知': '织直值',
    '道': '到',
    '听': '听停挺',
    '见': '见件建',
    '觉': '觉脚搅',
    '得': '得德锝',
    '着': '着找招',
    '像': '向象想',
    '等': '等灯登',
    '谢': '谢写卸',
    '对': '对队',
    '里': '里理鲤',
    '啦': '啦拉喇',
    '吃': '吃持迟',
    '哦': '哦喔噢',
    '呀': '呀压',
    '要': '药',
    '太': '太抬台',
    '快': '块',
    '点': '店',
    '以': '以已',
    '因': '因应',
    '啥': '啥沙傻',
    '行': '行型形',
    '哈': '哈蛤铪',
    '嘿': '嘿黑嗨',
    '嗯': '嗯恩摁',
    '哎': '哎爱埃',
    '呜': '呜屋污',
    '喂': '喂位未',
    '嘛': '嘛麻马',
    '嗨': '嗨害亥',
    '哇': '哇娃蛙',
    '咦': '咦意易',
    '嘻': '嘻西希'
}

def random_remove_punctuation(text: str) -> str:
    """随机处理标点符号，模拟人类打字习惯
    
    Args:
        text: 要处理的文本
        
    Returns:
        str: 处理后的文本
    """
    result = ''
    text_len = len(text)
    
    for i, char in enumerate(text):
        if char == '。' and i == text_len - 1:  # 结尾的句号
            if random.random() > 0.4:  # 80%概率删除结尾句号
                continue
        elif char == '，':
            rand = random.random()
            if rand < 0.25:  # 5%概率删除逗号
                continue
            elif rand < 0.25:  # 20%概率把逗号变成空格
                result += ' '
                continue
        result += char
    return result

def add_typos(text: str) -> str:
    TYPO_RATE = 0.02  # 控制错别字出现的概率(2%)
    result = ""
    for char in text:
        if char in TYPO_DICT and random.random() < TYPO_RATE:
            # 从可能的错别字中随机选择一个
            typos = TYPO_DICT[char]
            result += random.choice(typos)
        else:
            result += char
    return result

def process_llm_response(text: str) -> List[str]:
    # processed_response = process_text_with_typos(content)
    if len(text) > 200:
            print(f"回复过长 ({len(text)} 字符)，返回默认回复")
            return ['懒得说']
    # 处理长消息
    sentences = split_into_sentences_w_remove_punctuation(add_typos(text))
    # 检查分割后的消息数量是否过多（超过3条）
    if len(sentences) > 3:
        print(f"分割后消息数量过多 ({len(sentences)} 条)，返回默认回复")
        return [f'{global_config.BOT_NICKNAME}不知道哦']
    
    return sentences

def calculate_typing_time(input_string: str, chinese_time: float = 0.2, english_time: float = 0.1) -> float:
    """
    计算输入字符串所需的时间，中文和英文字符有不同的输入时间
        input_string (str): 输入的字符串
        chinese_time (float): 中文字符的输入时间，默认为0.3秒
        english_time (float): 英文字符的输入时间，默认为0.15秒
    """
    total_time = 0.0
    for char in input_string:
        if '\u4e00' <= char <= '\u9fff':  # 判断是否为中文字符
            total_time += chinese_time
        else:  # 其他字符（如英文）
            total_time += english_time  
    return total_time



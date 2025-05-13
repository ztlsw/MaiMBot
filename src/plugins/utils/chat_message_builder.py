from src.config.config import global_config

# 不再直接使用 db
# from src.common.database import db
# 移除 logger 和 traceback，因为错误处理移至 repository
# from src.common.logger import get_module_logger
# import traceback
from typing import List, Dict, Any, Tuple  # 确保类型提示被导入
import time  # 导入 time 模块以获取当前时间

# 导入新的 repository 函数
from src.common.message_repository import find_messages, count_messages

# 导入 PersonInfoManager 和时间转换工具
from src.plugins.person_info.person_info import person_info_manager
from src.plugins.chat.utils import translate_timestamp_to_human_readable

# 不再需要文件级别的 logger
# logger = get_module_logger(__name__)


def get_raw_msg_by_timestamp(
    timestamp_start: float, timestamp_end: float, limit: int = 0, limit_mode: str = "latest"
) -> List[Dict[str, Any]]:
    """
    获取从指定时间戳到指定时间戳的消息，按时间升序排序，返回消息列表
    limit: 限制返回的消息数量，0为不限制
    limit_mode: 当 limit > 0 时生效。 'earliest' 表示获取最早的记录， 'latest' 表示获取最新的记录。默认为 'latest'。
    """
    filter_query = {"time": {"$gt": timestamp_start, "$lt": timestamp_end}}
    # 只有当 limit 为 0 时才应用外部 sort
    sort_order = [("time", 1)] if limit == 0 else None
    return find_messages(filter=filter_query, sort=sort_order, limit=limit, limit_mode=limit_mode)


def get_raw_msg_by_timestamp_with_chat(
    chat_id: str, timestamp_start: float, timestamp_end: float, limit: int = 0, limit_mode: str = "latest"
) -> List[Dict[str, Any]]:
    """获取在特定聊天从指定时间戳到指定时间戳的消息，按时间升序排序，返回消息列表
    limit: 限制返回的消息数量，0为不限制
    limit_mode: 当 limit > 0 时生效。 'earliest' 表示获取最早的记录， 'latest' 表示获取最新的记录。默认为 'latest'。
    """
    filter_query = {"chat_id": chat_id, "time": {"$gt": timestamp_start, "$lt": timestamp_end}}
    # 只有当 limit 为 0 时才应用外部 sort
    sort_order = [("time", 1)] if limit == 0 else None
    # 直接将 limit_mode 传递给 find_messages
    return find_messages(filter=filter_query, sort=sort_order, limit=limit, limit_mode=limit_mode)


def get_raw_msg_by_timestamp_with_chat_users(
    chat_id: str,
    timestamp_start: float,
    timestamp_end: float,
    person_ids: list,
    limit: int = 0,
    limit_mode: str = "latest",
) -> List[Dict[str, Any]]:
    """获取某些特定用户在特定聊天从指定时间戳到指定时间戳的消息，按时间升序排序，返回消息列表
    limit: 限制返回的消息数量，0为不限制
    limit_mode: 当 limit > 0 时生效。 'earliest' 表示获取最早的记录， 'latest' 表示获取最新的记录。默认为 'latest'。
    """
    filter_query = {
        "chat_id": chat_id,
        "time": {"$gt": timestamp_start, "$lt": timestamp_end},
        "user_id": {"$in": person_ids},
    }
    # 只有当 limit 为 0 时才应用外部 sort
    sort_order = [("time", 1)] if limit == 0 else None
    return find_messages(filter=filter_query, sort=sort_order, limit=limit, limit_mode=limit_mode)


def get_raw_msg_by_timestamp_with_users(
    timestamp_start: float, timestamp_end: float, person_ids: list, limit: int = 0, limit_mode: str = "latest"
) -> List[Dict[str, Any]]:
    """获取某些特定用户在 *所有聊天* 中从指定时间戳到指定时间戳的消息，按时间升序排序，返回消息列表
    limit: 限制返回的消息数量，0为不限制
    limit_mode: 当 limit > 0 时生效。 'earliest' 表示获取最早的记录， 'latest' 表示获取最新的记录。默认为 'latest'。
    """
    filter_query = {"time": {"$gt": timestamp_start, "$lt": timestamp_end}, "user_id": {"$in": person_ids}}
    # 只有当 limit 为 0 时才应用外部 sort
    sort_order = [("time", 1)] if limit == 0 else None
    return find_messages(filter=filter_query, sort=sort_order, limit=limit, limit_mode=limit_mode)


def get_raw_msg_before_timestamp(timestamp: float, limit: int = 0) -> List[Dict[str, Any]]:
    """获取指定时间戳之前的消息，按时间升序排序，返回消息列表
    limit: 限制返回的消息数量，0为不限制
    """
    filter_query = {"time": {"$lt": timestamp}}
    sort_order = [("time", 1)]
    return find_messages(filter=filter_query, sort=sort_order, limit=limit)


def get_raw_msg_before_timestamp_with_chat(chat_id: str, timestamp: float, limit: int = 0) -> List[Dict[str, Any]]:
    """获取指定时间戳之前的消息，按时间升序排序，返回消息列表
    limit: 限制返回的消息数量，0为不限制
    """
    filter_query = {"chat_id": chat_id, "time": {"$lt": timestamp}}
    sort_order = [("time", 1)]
    return find_messages(filter=filter_query, sort=sort_order, limit=limit)


def get_raw_msg_before_timestamp_with_users(timestamp: float, person_ids: list, limit: int = 0) -> List[Dict[str, Any]]:
    """获取指定时间戳之前的消息，按时间升序排序，返回消息列表
    limit: 限制返回的消息数量，0为不限制
    """
    filter_query = {"time": {"$lt": timestamp}, "user_id": {"$in": person_ids}}
    sort_order = [("time", 1)]
    return find_messages(filter=filter_query, sort=sort_order, limit=limit)


def num_new_messages_since(chat_id: str, timestamp_start: float = 0.0, timestamp_end: float = None) -> int:
    """
    检查特定聊天从 timestamp_start (不含) 到 timestamp_end (不含) 之间有多少新消息。
    如果 timestamp_end 为 None，则检查从 timestamp_start (不含) 到当前时间的消息。
    """
    # 确定有效的结束时间戳
    _timestamp_end = timestamp_end if timestamp_end is not None else time.time()

    # 确保 timestamp_start < _timestamp_end
    if timestamp_start >= _timestamp_end:
        # logger.warning(f"timestamp_start ({timestamp_start}) must be less than _timestamp_end ({_timestamp_end}). Returning 0.")
        return 0  # 起始时间大于等于结束时间，没有新消息

    filter_query = {"chat_id": chat_id, "time": {"$gt": timestamp_start, "$lt": _timestamp_end}}
    return count_messages(filter=filter_query)


def num_new_messages_since_with_users(
    chat_id: str, timestamp_start: float, timestamp_end: float, person_ids: list
) -> int:
    """检查某些特定用户在特定聊天在指定时间戳之间有多少新消息"""
    if not person_ids:  # 保持空列表检查
        return 0
    filter_query = {
        "chat_id": chat_id,
        "time": {"$gt": timestamp_start, "$lt": timestamp_end},
        "user_id": {"$in": person_ids},
    }
    return count_messages(filter=filter_query)


async def _build_readable_messages_internal(
    messages: List[Dict[str, Any]],
    replace_bot_name: bool = True,
    merge_messages: bool = False,
    timestamp_mode: str = "relative",
    truncate: bool = False,
) -> Tuple[str, List[Tuple[float, str, str]]]:
    """
    内部辅助函数，构建可读消息字符串和原始消息详情列表。

    Args:
        messages: 消息字典列表。
        replace_bot_name: 是否将机器人的 user_id 替换为 "我"。
        merge_messages: 是否合并来自同一用户的连续消息。
        timestamp_mode: 时间戳的显示模式 ('relative', 'absolute', etc.)。传递给 translate_timestamp_to_human_readable。
        truncate: 是否根据消息的新旧程度截断过长的消息内容。

    Returns:
        包含格式化消息的字符串和原始消息详情列表 (时间戳, 发送者名称, 内容) 的元组。
    """
    if not messages:
        return "", []

    message_details_raw: List[Tuple[float, str, str]] = []

    # 1 & 2: 获取发送者信息并提取消息组件
    for msg in messages:
        user_info = msg.get("user_info", {})
        platform = user_info.get("platform")
        user_id = user_info.get("user_id")

        user_nickname = user_info.get("user_nickname")
        user_cardname = user_info.get("user_cardname")

        timestamp = msg.get("time")
        content = msg.get("processed_plain_text", "")  # 默认空字符串

        # 检查必要信息是否存在
        if not all([platform, user_id, timestamp is not None]):
            continue

        person_id = person_info_manager.get_person_id(platform, user_id)
        # 根据 replace_bot_name 参数决定是否替换机器人名称
        if replace_bot_name and user_id == global_config.BOT_QQ:
            person_name = f"{global_config.BOT_NICKNAME}(你)"
        else:
            person_name = await person_info_manager.get_value(person_id, "person_name")

        # 如果 person_name 未设置，则使用消息中的 nickname 或默认名称
        if not person_name:
            if user_cardname:
                person_name = f"昵称：{user_cardname}"
            elif user_nickname:
                person_name = f"{user_nickname}"
            else:
                person_name = "某人"

        message_details_raw.append((timestamp, person_name, content))

    if not message_details_raw:
        return "", []

    message_details_raw.sort(key=lambda x: x[0])  # 按时间戳(第一个元素)升序排序，越早的消息排在前面

    # 应用截断逻辑 (如果 truncate 为 True)
    message_details: List[Tuple[float, str, str]] = []
    n_messages = len(message_details_raw)
    if truncate and n_messages > 0:
        for i, (timestamp, name, content) in enumerate(message_details_raw):
            percentile = i / n_messages  # 计算消息在列表中的位置百分比 (0 <= percentile < 1)
            original_len = len(content)
            limit = -1  # 默认不截断

            if percentile < 0.2:  # 60% 之前的消息 (即最旧的 60%)
                limit = 50
                replace_content = "......（记不清了）"
            elif percentile < 0.5:  # 60% 之前的消息 (即最旧的 60%)
                limit = 100
                replace_content = "......（有点记不清了）"
            elif percentile < 0.7:  # 60% 到 80% 之前的消息 (即中间的 20%)
                limit = 200
                replace_content = "......（内容太长了）"
            elif percentile < 1.0:  # 80% 到 100% 之前的消息 (即较新的 20%)
                limit = 300
                replace_content = "......（太长了）"

            truncated_content = content
            if limit > 0 and original_len > limit:
                truncated_content = f"{content[:limit]}{replace_content}"

            message_details.append((timestamp, name, truncated_content))
    else:
        # 如果不截断，直接使用原始列表
        message_details = message_details_raw

    # 3: 合并连续消息 (如果 merge_messages 为 True)
    merged_messages = []
    if merge_messages and message_details:
        # 初始化第一个合并块
        current_merge = {
            "name": message_details[0][1],
            "start_time": message_details[0][0],
            "end_time": message_details[0][0],
            "content": [message_details[0][2]],
        }

        for i in range(1, len(message_details)):
            timestamp, name, content = message_details[i]
            # 如果是同一个人发送的连续消息且时间间隔小于等于60秒
            if name == current_merge["name"] and (timestamp - current_merge["end_time"] <= 60):
                current_merge["content"].append(content)
                current_merge["end_time"] = timestamp  # 更新最后消息时间
            else:
                # 保存上一个合并块
                merged_messages.append(current_merge)
                # 开始新的合并块
                current_merge = {"name": name, "start_time": timestamp, "end_time": timestamp, "content": [content]}
        # 添加最后一个合并块
        merged_messages.append(current_merge)
    elif message_details:  # 如果不合并消息，则每个消息都是一个独立的块
        for timestamp, name, content in message_details:
            merged_messages.append(
                {
                    "name": name,
                    "start_time": timestamp,  # 起始和结束时间相同
                    "end_time": timestamp,
                    "content": [content],  # 内容只有一个元素
                }
            )

    # 4 & 5: 格式化为字符串
    output_lines = []
    for _i, merged in enumerate(merged_messages):
        # 使用指定的 timestamp_mode 格式化时间
        readable_time = translate_timestamp_to_human_readable(merged["start_time"], mode=timestamp_mode)

        header = f"{readable_time}{merged['name']} 说:"
        output_lines.append(header)
        # 将内容合并，并添加缩进
        for line in merged["content"]:
            stripped_line = line.strip()
            if stripped_line:  # 过滤空行
                # 移除末尾句号，添加分号 - 这个逻辑似乎有点奇怪，暂时保留
                if stripped_line.endswith("。"):
                    stripped_line = stripped_line[:-1]
                # 如果内容被截断，结尾已经是 ...（内容太长），不再添加分号
                if not stripped_line.endswith("（内容太长）"):
                    output_lines.append(f"{stripped_line};")
                else:
                    output_lines.append(stripped_line)  # 直接添加截断后的内容
        output_lines.append("\n")  # 在每个消息块后添加换行，保持可读性

    # 移除可能的多余换行，然后合并
    formatted_string = "".join(output_lines).strip()

    # 返回格式化后的字符串和 *应用截断后* 的 message_details 列表
    # 注意：如果外部调用者需要原始未截断的内容，可能需要调整返回策略
    return formatted_string, message_details


async def build_readable_messages_with_list(
    messages: List[Dict[str, Any]],
    replace_bot_name: bool = True,
    merge_messages: bool = False,
    timestamp_mode: str = "relative",
    truncate: bool = False,
) -> Tuple[str, List[Tuple[float, str, str]]]:
    """
    将消息列表转换为可读的文本格式，并返回原始(时间戳, 昵称, 内容)列表。
    允许通过参数控制格式化行为。
    """
    formatted_string, details_list = await _build_readable_messages_internal(
        messages, replace_bot_name, merge_messages, timestamp_mode, truncate
    )
    return formatted_string, details_list


async def build_readable_messages(
    messages: List[Dict[str, Any]],
    replace_bot_name: bool = True,
    merge_messages: bool = False,
    timestamp_mode: str = "relative",
    read_mark: float = 0.0,
    truncate: bool = False,
) -> str:
    """
    将消息列表转换为可读的文本格式。
    如果提供了 read_mark，则在相应位置插入已读标记。
    允许通过参数控制格式化行为。
    """
    if read_mark <= 0:
        # 没有有效的 read_mark，直接格式化所有消息
        formatted_string, _ = await _build_readable_messages_internal(
            messages, replace_bot_name, merge_messages, timestamp_mode, truncate
        )
        return formatted_string
    else:
        # 按 read_mark 分割消息
        messages_before_mark = [msg for msg in messages if msg.get("time", 0) <= read_mark]
        messages_after_mark = [msg for msg in messages if msg.get("time", 0) > read_mark]

        # 分别格式化
        # 注意：这里决定对已读和未读部分都应用相同的 truncate 设置
        # 如果需要不同的行为（例如只截断已读部分），需要调整这里的调用
        formatted_before, _ = await _build_readable_messages_internal(
            messages_before_mark, replace_bot_name, merge_messages, timestamp_mode, truncate
        )
        formatted_after, _ = await _build_readable_messages_internal(
            messages_after_mark,
            replace_bot_name,
            merge_messages,
            timestamp_mode,
        )

        readable_read_mark = translate_timestamp_to_human_readable(read_mark, mode=timestamp_mode)
        read_mark_line = f"\n--- 以上消息是你已经思考过的内容已读 (标记时间: {readable_read_mark}) ---\n--- 请关注以下未读的新消息---\n"

        # 组合结果，确保空部分不引入多余的标记或换行
        if formatted_before and formatted_after:
            return f"{formatted_before}{read_mark_line}{formatted_after}"
        elif formatted_before:
            return f"{formatted_before}{read_mark_line}"
        elif formatted_after:
            return f"{read_mark_line}{formatted_after}"
        else:
            # 理论上不应该发生，但作为保险
            return read_mark_line.strip()  # 如果前后都无消息，只返回标记行


async def get_person_id_list(messages: List[Dict[str, Any]]) -> List[str]:
    """
    从消息列表中提取不重复的 person_id 列表 (忽略机器人自身)。

    Args:
        messages: 消息字典列表。

    Returns:
        一个包含唯一 person_id 的列表。
    """
    person_ids_set = set()  # 使用集合来自动去重

    for msg in messages:
        user_info = msg.get("user_info", {})
        platform = user_info.get("platform")
        user_id = user_info.get("user_id")

        # 检查必要信息是否存在 且 不是机器人自己
        if not all([platform, user_id]) or user_id == global_config.BOT_QQ:
            continue

        person_id = person_info_manager.get_person_id(platform, user_id)

        # 只有当获取到有效 person_id 时才添加
        if person_id:
            person_ids_set.add(person_id)

    return list(person_ids_set)  # 将集合转换为列表返回

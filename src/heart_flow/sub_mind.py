from .observation import Observation
from src.plugins.models.utils_model import LLMRequest
from src.config.config import global_config
import time
import traceback
from src.common.logger_manager import get_logger
from src.individuality.individuality import Individuality
import random
from ..plugins.utils.prompt_builder import Prompt, global_prompt_manager
from src.do_tool.tool_use import ToolUser
from src.plugins.utils.json_utils import safe_json_dumps, process_llm_tool_calls
from src.heart_flow.chat_state_info import ChatStateInfo
from src.plugins.chat.chat_stream import chat_manager
from src.plugins.heartFC_chat.heartFC_Cycleinfo import CycleInfo
import difflib
from src.plugins.person_info.relationship_manager import relationship_manager


logger = get_logger("sub_heartflow")


def init_prompt():
    prompt = ""
    prompt += "{extra_info}\n"
    prompt += "{relation_prompt}\n"
    prompt += "你的名字是{bot_name},{prompt_personality}\n"
    prompt += "{last_loop_prompt}\n"
    prompt += "{cycle_info_block}\n"
    prompt += "现在是{time_now}，你正在上网，和qq群里的网友们聊天，以下是正在进行的聊天内容：\n{chat_observe_info}\n"
    prompt += "\n你现在{mood_info}\n"
    prompt += "请仔细阅读当前群聊内容，分析讨论话题和群成员关系，分析你刚刚发言和别人对你的发言的反应，思考你要不要回复。然后思考你是否需要使用函数工具。"
    prompt += "思考并输出你的内心想法\n"
    prompt += "输出要求：\n"
    prompt += "1. 根据聊天内容生成你的想法，{hf_do_next}\n"
    prompt += "2. 不要分点、不要使用表情符号\n"
    prompt += "3. 避免多余符号(冒号、引号、括号等)\n"
    prompt += "4. 语言简洁自然，不要浮夸\n"
    prompt += "5. 如果你刚发言，并且没有人回复你，不要回复\n"
    prompt += "工具使用说明：\n"
    prompt += "1. 输出想法后考虑是否需要使用工具\n"
    prompt += "2. 工具可获取信息或执行操作\n"
    prompt += "3. 如需处理消息或回复，请使用工具\n"

    Prompt(prompt, "sub_heartflow_prompt_before")

    prompt = ""
    prompt += "刚刚你的内心想法是：{current_thinking_info}\n"
    prompt += "{if_replan_prompt}\n"

    Prompt(prompt, "last_loop")


def calculate_similarity(text_a: str, text_b: str) -> float:
    """
    计算两个文本字符串的相似度。
    """
    if not text_a or not text_b:
        return 0.0
    matcher = difflib.SequenceMatcher(None, text_a, text_b)
    return matcher.ratio()


def calculate_replacement_probability(similarity: float) -> float:
    """
    根据相似度计算替换的概率。
    规则：
    - 相似度 <= 0.4: 概率 = 0
    - 相似度 >= 0.9: 概率 = 1
    - 相似度 == 0.6: 概率 = 0.7
    - 0.4 < 相似度 <= 0.6: 线性插值 (0.4, 0) 到 (0.6, 0.7)
    - 0.6 < 相似度 < 0.9: 线性插值 (0.6, 0.7) 到 (0.9, 1.0)
    """
    if similarity <= 0.4:
        return 0.0
    elif similarity >= 0.9:
        return 1.0
    elif 0.4 < similarity <= 0.6:
        # p = 3.5 * s - 1.4
        probability = 3.5 * similarity - 1.4
        return max(0.0, probability)
    elif 0.6 < similarity < 0.9:
        # p = s + 0.1
        probability = similarity + 0.1
        return min(1.0, max(0.0, probability))


class SubMind:
    def __init__(self, subheartflow_id: str, chat_state: ChatStateInfo, observations: Observation):
        self.subheartflow_id = subheartflow_id

        self.llm_model = LLMRequest(
            model=global_config.llm_sub_heartflow,
            temperature=global_config.llm_sub_heartflow["temp"],
            max_tokens=800,
            request_type="sub_heart_flow",
        )

        self.chat_state = chat_state
        self.observations = observations

        self.current_mind = ""
        self.past_mind = []
        self.structured_info = {}

        name = chat_manager.get_stream_name(self.subheartflow_id)
        self.log_prefix = f"[{name}] "

    async def do_thinking_before_reply(self, history_cycle: list[CycleInfo] = None):
        """
        在回复前进行思考，生成内心想法并收集工具调用结果

        返回:
            tuple: (current_mind, past_mind) 当前想法和过去的想法列表
        """
        # 更新活跃时间
        self.last_active_time = time.time()

        # ---------- 1. 准备基础数据 ----------
        # 获取现有想法和情绪状态
        previous_mind = self.current_mind if self.current_mind else ""
        mood_info = self.chat_state.mood

        # 获取观察对象
        observation = self.observations[0]
        if not observation:
            logger.error(f"{self.log_prefix} 无法获取观察对象")
            self.update_current_mind("(我没看到任何聊天内容...)")
            return self.current_mind, self.past_mind

        # 获取观察内容
        chat_observe_info = observation.get_observe_info()
        person_list = observation.person_list

        # ---------- 2. 准备工具和个性化数据 ----------
        # 初始化工具
        tool_instance = ToolUser()
        tools = tool_instance._define_tools()

        # 获取个性化信息
        individuality = Individuality.get_instance()

        relation_prompt = ""
        # print(f"person_list: {person_list}")
        for person in person_list:
            relation_prompt += await relationship_manager.build_relationship_info(person, is_id=True)

        # print(f"relat22222ion_prompt: {relation_prompt}")

        # 构建个性部分
        prompt_personality = individuality.get_prompt(x_person=2, level=2)

        # 获取当前时间
        time_now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        # ---------- 3. 构建思考指导部分 ----------
        # 创建本地随机数生成器，基于分钟数作为种子
        local_random = random.Random()
        current_minute = int(time.strftime("%M"))
        local_random.seed(current_minute)

        # 思考指导选项和权重
        hf_options = [
            ("可以参考之前的想法，在原来想法的基础上继续思考", 0.2),
            ("可以参考之前的想法，在原来的想法上尝试新的话题", 0.4),
            ("不要太深入", 0.2),
            ("进行深入思考", 0.2),
        ]

        last_cycle = history_cycle[-1] if history_cycle else None
        # 上一次决策信息
        if last_cycle != None:
            last_action = last_cycle.action_type
            last_reasoning = last_cycle.reasoning
            is_replan = last_cycle.replanned
            if is_replan:
                if_replan_prompt = f"但是你有了上述想法之后，有了新消息，你决定重新思考后，你做了：{last_action}\n因为：{last_reasoning}\n"
            else:
                if_replan_prompt = f"出于这个想法，你刚才做了：{last_action}\n因为：{last_reasoning}\n"
        else:
            last_action = ""
            last_reasoning = ""
            is_replan = False
            if_replan_prompt = ""
        if previous_mind:
            last_loop_prompt = (await global_prompt_manager.get_prompt_async("last_loop")).format(
                current_thinking_info=previous_mind, if_replan_prompt=if_replan_prompt
            )
        else:
            last_loop_prompt = ""

        # 准备循环信息块 (分析最近的活动循环)
        recent_active_cycles = []
        for cycle in reversed(history_cycle):
            # 只关心实际执行了动作的循环
            if cycle.action_taken:
                recent_active_cycles.append(cycle)
                # 最多找最近的3个活动循环
                if len(recent_active_cycles) == 3:
                    break

        cycle_info_block = ""
        consecutive_text_replies = 0
        responses_for_prompt = []

        # 检查这最近的活动循环中有多少是连续的文本回复 (从最近的开始看)
        for cycle in recent_active_cycles:
            if cycle.action_type == "text_reply":
                consecutive_text_replies += 1
                # 获取回复内容，如果不存在则返回'[空回复]'
                response_text = cycle.response_info.get("response_text", [])
                # 使用简单的 join 来格式化回复内容列表
                formatted_response = "[空回复]" if not response_text else " ".join(response_text)
                responses_for_prompt.append(formatted_response)
            else:
                # 一旦遇到非文本回复，连续性中断
                break

        # 根据连续文本回复的数量构建提示信息
        # 注意: responses_for_prompt 列表是从最近到最远排序的
        if consecutive_text_replies >= 3:  # 如果最近的三个活动都是文本回复
            cycle_info_block = f'你已经连续回复了三条消息（最近: "{responses_for_prompt[0]}"，第二近: "{responses_for_prompt[1]}"，第三近: "{responses_for_prompt[2]}"）。你回复的有点多了，请注意'
        elif consecutive_text_replies == 2:  # 如果最近的两个活动是文本回复
            cycle_info_block = f'你已经连续回复了两条消息（最近: "{responses_for_prompt[0]}"，第二近: "{responses_for_prompt[1]}"），请注意'
        elif consecutive_text_replies == 1:  # 如果最近的一个活动是文本回复
            cycle_info_block = f'你刚刚已经回复一条消息（内容: "{responses_for_prompt[0]}"）'

        # 包装提示块，增加可读性，即使没有连续回复也给个标记
        if cycle_info_block:
            cycle_info_block = f"\n【近期回复历史】\n{cycle_info_block}\n"
        else:
            # 如果最近的活动循环不是文本回复，或者没有活动循环
            cycle_info_block = "\n【近期回复历史】\n(最近没有连续文本回复)\n"

        # 加权随机选择思考指导
        hf_do_next = local_random.choices(
            [option[0] for option in hf_options], weights=[option[1] for option in hf_options], k=1
        )[0]

        # ---------- 4. 构建最终提示词 ----------
        # 获取提示词模板并填充数据
        prompt = (await global_prompt_manager.get_prompt_async("sub_heartflow_prompt_before")).format(
            extra_info="",  # 可以在这里添加额外信息
            prompt_personality=prompt_personality,
            relation_prompt=relation_prompt,
            bot_name=individuality.name,
            time_now=time_now,
            chat_observe_info=chat_observe_info,
            mood_info=mood_info,
            hf_do_next=hf_do_next,
            last_loop_prompt=last_loop_prompt,
            cycle_info_block=cycle_info_block,
        )

        # ---------- 5. 执行LLM请求并处理响应 ----------
        content = ""  # 初始化内容变量
        _reasoning_content = ""  # 初始化推理内容变量

        try:
            # 调用LLM生成响应
            response, _reasoning_content, tool_calls = await self.llm_model.generate_response_tool_async(
                prompt=prompt, tools=tools
            )

            logger.debug(f"{self.log_prefix} 子心流输出的原始LLM响应: {response}")

            # 直接使用LLM返回的文本响应作为 content
            content = response if response else ""

            if tool_calls:
                # 直接将 tool_calls 传递给处理函数
                success, valid_tool_calls, error_msg = process_llm_tool_calls(
                    tool_calls, log_prefix=f"{self.log_prefix} "
                )

                if success and valid_tool_calls:
                    # 记录工具调用信息
                    tool_calls_str = ", ".join(
                        [call.get("function", {}).get("name", "未知工具") for call in valid_tool_calls]
                    )
                    logger.info(f"{self.log_prefix} 模型请求调用{len(valid_tool_calls)}个工具: {tool_calls_str}")

                    # 收集工具执行结果
                    await self._execute_tool_calls(valid_tool_calls, tool_instance)
                elif not success:
                    logger.warning(f"{self.log_prefix} 处理工具调用时出错: {error_msg}")
            else:
                logger.info(f"{self.log_prefix} 心流未使用工具")

        except Exception as e:
            # 处理总体异常
            logger.error(f"{self.log_prefix} 执行LLM请求或处理响应时出错: {e}")
            logger.error(traceback.format_exc())
            content = "思考过程中出现错误"

        # 记录初步思考结果
        logger.debug(f"{self.log_prefix} 初步心流思考结果: {content}\nprompt: {prompt}\n")

        # 处理空响应情况
        if not content:
            content = "(不知道该想些什么...)"
            logger.warning(f"{self.log_prefix} LLM返回空结果，思考失败。")

        # ---------- 6. 应用概率性去重和修饰 ----------
        new_content = content  # 保存 LLM 直接输出的结果
        try:
            similarity = calculate_similarity(previous_mind, new_content)
            replacement_prob = calculate_replacement_probability(similarity)
            logger.debug(f"{self.log_prefix} 新旧想法相似度: {similarity:.2f}, 替换概率: {replacement_prob:.2f}")

            # 定义词语列表 (移到判断之前)
            yu_qi_ci_liebiao = ["嗯", "哦", "啊", "唉", "哈", "唔"]
            zhuan_zhe_liebiao = ["但是", "不过", "然而", "可是", "只是"]
            cheng_jie_liebiao = ["然后", "接着", "此外", "而且", "另外"]
            zhuan_jie_ci_liebiao = zhuan_zhe_liebiao + cheng_jie_liebiao

            if random.random() < replacement_prob:
                # 相似度非常高时，尝试去重或特殊处理
                if similarity == 1.0:
                    logger.debug(f"{self.log_prefix} 想法完全重复 (相似度 1.0)，执行特殊处理...")
                    # 随机截取大约一半内容
                    if len(new_content) > 1:  # 避免内容过短无法截取
                        split_point = max(
                            1, len(new_content) // 2 + random.randint(-len(new_content) // 4, len(new_content) // 4)
                        )
                        truncated_content = new_content[:split_point]
                    else:
                        truncated_content = new_content  # 如果只有一个字符或者为空，就不截取了

                    # 添加语气词和转折/承接词
                    yu_qi_ci = random.choice(yu_qi_ci_liebiao)
                    zhuan_jie_ci = random.choice(zhuan_jie_ci_liebiao)
                    content = f"{yu_qi_ci}{zhuan_jie_ci}，{truncated_content}"
                    logger.debug(f"{self.log_prefix} 想法重复，特殊处理后: {content}")

                else:
                    # 相似度较高但非100%，执行标准去重逻辑
                    logger.debug(f"{self.log_prefix} 执行概率性去重 (概率: {replacement_prob:.2f})...")
                    matcher = difflib.SequenceMatcher(None, previous_mind, new_content)
                    deduplicated_parts = []
                    last_match_end_in_b = 0
                    for _i, j, n in matcher.get_matching_blocks():
                        if last_match_end_in_b < j:
                            deduplicated_parts.append(new_content[last_match_end_in_b:j])
                        last_match_end_in_b = j + n

                    deduplicated_content = "".join(deduplicated_parts).strip()

                    if deduplicated_content:
                        # 根据概率决定是否添加词语
                        prefix_str = ""
                        if random.random() < 0.3:  # 30% 概率添加语气词
                            prefix_str += random.choice(yu_qi_ci_liebiao)
                        if random.random() < 0.7:  # 70% 概率添加转折/承接词
                            prefix_str += random.choice(zhuan_jie_ci_liebiao)

                        # 组合最终结果
                        if prefix_str:
                            content = f"{prefix_str}，{deduplicated_content}"  # 更新 content
                            logger.debug(f"{self.log_prefix} 去重并添加引导词后: {content}")
                        else:
                            content = deduplicated_content  # 更新 content
                            logger.debug(f"{self.log_prefix} 去重后 (未添加引导词): {content}")
                    else:
                        logger.warning(f"{self.log_prefix} 去重后内容为空，保留原始LLM输出: {new_content}")
                        content = new_content  # 保留原始 content
            else:
                logger.debug(f"{self.log_prefix} 未执行概率性去重 (概率: {replacement_prob:.2f})")
                # content 保持 new_content 不变

        except Exception as e:
            logger.error(f"{self.log_prefix} 应用概率性去重或特殊处理时出错: {e}")
            logger.error(traceback.format_exc())
            # 出错时保留原始 content
            content = new_content

        # ---------- 7. 更新思考状态并返回结果 ----------
        logger.info(f"{self.log_prefix} 最终心流思考结果: {content}")
        # 更新当前思考内容
        self.update_current_mind(content)

        return self.current_mind, self.past_mind

    async def _execute_tool_calls(self, tool_calls, tool_instance):
        """
        执行一组工具调用并收集结果

        参数:
            tool_calls: 工具调用列表
            tool_instance: 工具使用器实例
        """
        tool_results = []
        structured_info = {}  # 动态生成键

        # 执行所有工具调用
        for tool_call in tool_calls:
            try:
                result = await tool_instance._execute_tool_call(tool_call)
                if result:
                    tool_results.append(result)

                    # 使用工具名称作为键
                    tool_name = result["name"]
                    if tool_name not in structured_info:
                        structured_info[tool_name] = []

                    structured_info[tool_name].append({"name": result["name"], "content": result["content"]})
            except Exception as tool_e:
                logger.error(f"[{self.subheartflow_id}] 工具执行失败: {tool_e}")

        # 如果有工具结果，记录并更新结构化信息
        if structured_info:
            logger.debug(f"工具调用收集到结构化信息: {safe_json_dumps(structured_info, ensure_ascii=False)}")
            self.structured_info = structured_info

    def update_current_mind(self, response):
        self.past_mind.append(self.current_mind)
        self.current_mind = response


init_prompt()

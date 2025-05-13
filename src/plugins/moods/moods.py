import math
import threading
import time
from dataclasses import dataclass

from ...config.config import global_config
from src.common.logger_manager import get_logger
from ..person_info.relationship_manager import relationship_manager
from src.individuality.individuality import Individuality


logger = get_logger("mood")


@dataclass
class MoodState:
    valence: float  # 愉悦度 (-1.0 到 1.0)，-1表示极度负面，1表示极度正面
    arousal: float  # 唤醒度 (-1.0 到 1.0)，-1表示抑制，1表示兴奋
    text: str  # 心情文本描述


class MoodManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        # 确保初始化代码只运行一次
        if self._initialized:
            return

        self._initialized = True

        # 初始化心情状态
        self.current_mood = MoodState(valence=0.0, arousal=0.0, text="平静")

        # 从配置文件获取衰减率
        self.decay_rate_valence = 1 - global_config.mood_decay_rate  # 愉悦度衰减率
        self.decay_rate_arousal = 1 - global_config.mood_decay_rate  # 唤醒度衰减率

        # 上次更新时间
        self.last_update = time.time()

        # 线程控制
        self._running = False
        self._update_thread = None

        # 情绪词映射表 (valence, arousal)
        self.emotion_map = {
            "开心": (0.21, 0.6),
            "害羞": (0.15, 0.2),
            "愤怒": (-0.24, 0.8),
            "恐惧": (-0.21, 0.7),
            "悲伤": (-0.21, 0.3),
            "厌恶": (-0.12, 0.4),
            "惊讶": (0.06, 0.7),
            "困惑": (0.0, 0.6),
            "平静": (0.03, 0.5),
        }

        # 情绪文本映射表
        self.mood_text_map = {
            # 第一象限：高唤醒，正愉悦
            (0.5, 0.4): "兴奋",
            (0.3, 0.6): "快乐",
            (0.2, 0.3): "满足",
            # 第二象限：高唤醒，负愉悦
            (-0.5, 0.4): "愤怒",
            (-0.3, 0.6): "焦虑",
            (-0.2, 0.3): "烦躁",
            # 第三象限：低唤醒，负愉悦
            (-0.5, -0.4): "悲伤",
            (-0.3, -0.3): "疲倦",
            (-0.4, -0.7): "疲倦",
            # 第四象限：低唤醒，正愉悦
            (0.2, -0.1): "平静",
            (0.3, -0.2): "安宁",
            (0.5, -0.4): "放松",
        }

    @classmethod
    def get_instance(cls) -> "MoodManager":
        """获取MoodManager的单例实例"""
        if cls._instance is None:
            cls._instance = MoodManager()
        return cls._instance

    def start_mood_update(self, update_interval: float = 5.0) -> None:
        """
        启动情绪更新线程
        :param update_interval: 更新间隔（秒）
        """
        if self._running:
            return

        self._running = True
        self._update_thread = threading.Thread(
            target=self._continuous_mood_update, args=(update_interval,), daemon=True
        )
        self._update_thread.start()

    def stop_mood_update(self) -> None:
        """停止情绪更新线程"""
        self._running = False
        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.join()

    def _continuous_mood_update(self, update_interval: float) -> None:
        """
        持续更新情绪状态的线程函数
        :param update_interval: 更新间隔（秒）
        """
        while self._running:
            self._apply_decay()
            self._update_mood_text()
            time.sleep(update_interval)

    def _apply_decay(self) -> None:
        """应用情绪衰减，正向和负向情绪分开计算"""
        current_time = time.time()
        time_diff = current_time - self.last_update
        agreeableness_factor = 1
        agreeableness_bias = 0
        neuroticism_factor = 0.5

        # 获取人格特质
        personality = Individuality.get_instance().personality
        if personality:
            # 神经质：影响情绪变化速度
            neuroticism_factor = 1 + (personality.neuroticism - 0.5) * 0.4
            agreeableness_factor = 1 + (personality.agreeableness - 0.5) * 0.4

            # 宜人性：影响情绪基准线
            if personality.agreeableness < 0.2:
                agreeableness_bias = (personality.agreeableness - 0.2) * 0.5
            elif personality.agreeableness > 0.8:
                agreeableness_bias = (personality.agreeableness - 0.8) * 0.5
            else:
                agreeableness_bias = 0

        # 分别计算正向和负向的衰减率
        if self.current_mood.valence >= 0:
            # 正向情绪衰减
            decay_rate_positive = self.decay_rate_valence * (1 / agreeableness_factor)
            valence_target = 0 + agreeableness_bias
            self.current_mood.valence = valence_target + (self.current_mood.valence - valence_target) * math.exp(
                -decay_rate_positive * time_diff * neuroticism_factor
            )
        else:
            # 负向情绪衰减
            decay_rate_negative = self.decay_rate_valence * agreeableness_factor
            valence_target = 0 + agreeableness_bias
            self.current_mood.valence = valence_target + (self.current_mood.valence - valence_target) * math.exp(
                -decay_rate_negative * time_diff * neuroticism_factor
            )

        # Arousal 向中性（0）回归
        arousal_target = 0
        self.current_mood.arousal = arousal_target + (self.current_mood.arousal - arousal_target) * math.exp(
            -self.decay_rate_arousal * time_diff * neuroticism_factor
        )

        # 确保值在合理范围内
        self.current_mood.valence = max(-1.0, min(1.0, self.current_mood.valence))
        self.current_mood.arousal = max(-1.0, min(1.0, self.current_mood.arousal))

        self.last_update = current_time

    def update_mood_from_text(self, text: str, valence_change: float, arousal_change: float) -> None:
        """根据输入文本更新情绪状态"""

        self.current_mood.valence += valence_change
        self.current_mood.arousal += arousal_change

        # 限制范围
        self.current_mood.valence = max(-1.0, min(1.0, self.current_mood.valence))
        self.current_mood.arousal = max(-1.0, min(1.0, self.current_mood.arousal))

        self._update_mood_text()

    def set_mood_text(self, text: str) -> None:
        """直接设置心情文本"""
        self.current_mood.text = text

    def _update_mood_text(self) -> None:
        """根据当前情绪状态更新文本描述"""
        closest_mood = None
        min_distance = float("inf")

        for (v, a), text in self.mood_text_map.items():
            distance = math.sqrt((self.current_mood.valence - v) ** 2 + (self.current_mood.arousal - a) ** 2)
            if distance < min_distance:
                min_distance = distance
                closest_mood = text

        if closest_mood:
            self.current_mood.text = closest_mood

    def update_mood_by_user(self, user_id: str, valence_change: float, arousal_change: float) -> None:
        """根据用户ID更新情绪状态"""

        # 这里可以根据用户ID添加特定的权重或规则
        weight = 1.0  # 默认权重

        self.current_mood.valence += valence_change * weight
        self.current_mood.arousal += arousal_change * weight

        # 限制范围
        self.current_mood.valence = max(-1.0, min(1.0, self.current_mood.valence))
        self.current_mood.arousal = max(-1.0, min(1.0, self.current_mood.arousal))

        self._update_mood_text()

    def get_prompt(self) -> str:
        """根据当前情绪状态生成提示词"""

        base_prompt = f"当前心情：{self.current_mood.text}。"

        # 根据情绪状态添加额外的提示信息
        if self.current_mood.valence > 0.5:
            base_prompt += "你现在心情很好，"
        elif self.current_mood.valence < -0.5:
            base_prompt += "你现在心情不太好，"

        if self.current_mood.arousal > 0.4:
            base_prompt += "情绪比较激动。"
        elif self.current_mood.arousal < -0.4:
            base_prompt += "情绪比较平静。"

        return base_prompt

    def get_arousal_multiplier(self) -> float:
        """根据当前情绪状态返回唤醒度乘数"""
        if self.current_mood.arousal > 0.4:
            multiplier = 1 + min(0.15, (self.current_mood.arousal - 0.4) / 3)
            return multiplier
        elif self.current_mood.arousal < -0.4:
            multiplier = 1 - min(0.15, ((0 - self.current_mood.arousal) - 0.4) / 3)
            return multiplier
        return 1.0

    def get_current_mood(self) -> MoodState:
        """获取当前情绪状态"""
        return self.current_mood

    def print_mood_status(self) -> None:
        """打印当前情绪状态"""
        logger.info(
            f"愉悦度: {self.current_mood.valence:.2f}, "
            f"唤醒度: {self.current_mood.arousal:.2f}, "
            f"心情: {self.current_mood.text}"
        )

    def update_mood_from_emotion(self, emotion: str, intensity: float = 1.0) -> None:
        """
        根据情绪词更新心情状态
        :param emotion: 情绪词（如'happy', 'sad'等）
        :param intensity: 情绪强度（0.0-1.0）
        """
        if emotion not in self.emotion_map:
            logger.debug(f"[情绪更新] 未知情绪词: {emotion}")
            return

        valence_change, arousal_change = self.emotion_map[emotion]
        old_valence = self.current_mood.valence
        old_arousal = self.current_mood.arousal
        old_mood = self.current_mood.text

        valence_change = relationship_manager.feedback_to_mood(valence_change)

        # 应用情绪强度
        valence_change *= intensity
        arousal_change *= intensity

        # 更新当前情绪状态
        self.current_mood.valence += valence_change
        self.current_mood.arousal += arousal_change

        # 限制范围
        self.current_mood.valence = max(-1.0, min(1.0, self.current_mood.valence))
        self.current_mood.arousal = max(-1.0, min(1.0, self.current_mood.arousal))

        self._update_mood_text()

        logger.info(
            f"[情绪变化] {emotion}(强度:{intensity:.2f}) | 愉悦度:{old_valence:.2f}->{self.current_mood.valence:.2f}, 唤醒度:{old_arousal:.2f}->{self.current_mood.arousal:.2f} | 心情:{old_mood}->{self.current_mood.text}"
        )

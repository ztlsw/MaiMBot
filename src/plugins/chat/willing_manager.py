import asyncio

class WillingManager:
    def __init__(self):
        self.group_reply_willing = {}  # 存储每个群的回复意愿
        self._decay_task = None
        self._started = False
        
    async def _decay_reply_willing(self):
        """定期衰减回复意愿"""
        while True:
            await asyncio.sleep(3)
            for group_id in self.group_reply_willing:
                # 每分钟衰减10%的回复意愿
                self.group_reply_willing[group_id] = max(0, self.group_reply_willing[group_id] * 0.6)
                
    def get_willing(self, group_id: int) -> float:
        """获取指定群组的回复意愿"""
        return self.group_reply_willing.get(group_id, 0)
    
    def set_willing(self, group_id: int, willing: float):
        """设置指定群组的回复意愿"""
        self.group_reply_willing[group_id] = willing
        
    def change_reply_willing_received(self, group_id: int, topic: str, is_mentioned_bot: bool, config, user_id: int = None, is_emoji: bool = False, interested_rate: float = 0) -> float:
        """改变指定群组的回复意愿并返回回复概率"""
        current_willing = self.group_reply_willing.get(group_id, 0)
        
        print(f"初始意愿: {current_willing}")
        
        # if topic and current_willing < 1:
        #     current_willing += 0.2
        # elif topic:
        #     current_willing += 0.05
            
        if is_mentioned_bot and current_willing < 1.0:
            current_willing += 0.9
            print(f"被提及, 当前意愿: {current_willing}")
        elif is_mentioned_bot:
            current_willing += 0.05
            print(f"被重复提及, 当前意愿: {current_willing}")
        
        if is_emoji:
            current_willing *= 0.15
            print(f"表情包, 当前意愿: {current_willing}")
        
        if interested_rate > 0.6:
            print(f"兴趣度: {interested_rate}, 当前意愿: {current_willing}")
            current_willing += interested_rate-0.45
        
        self.group_reply_willing[group_id] = min(current_willing, 3.0)
        
        reply_probability = (current_willing - 0.5) * 2
        if group_id not in config.talk_allowed_groups:
            current_willing = 0
            reply_probability = 0
            
        if group_id in config.talk_frequency_down_groups:
            reply_probability = reply_probability / 3.5
            
        if is_mentioned_bot and user_id == int(1026294844):
            reply_probability = 1
            
        return reply_probability
    
    def change_reply_willing_sent(self, group_id: int):
        """开始思考后降低群组的回复意愿"""
        current_willing = self.group_reply_willing.get(group_id, 0)
        self.group_reply_willing[group_id] = max(0, current_willing - 2)
        
    def change_reply_willing_after_sent(self, group_id: int):
        """发送消息后提高群组的回复意愿"""
        current_willing = self.group_reply_willing.get(group_id, 0)
        if current_willing < 1:
            self.group_reply_willing[group_id] = min(1, current_willing + 0.3)
        
    async def ensure_started(self):
        """确保衰减任务已启动"""
        if not self._started:
            if self._decay_task is None:
                self._decay_task = asyncio.create_task(self._decay_reply_willing())
            self._started = True

# 创建全局实例
willing_manager = WillingManager() 
from .relationship_manager import relationship_manager
from .config import global_config

def get_user_nickname(user_id: int) -> str:
    if int(user_id) == int(global_config.BOT_QQ):
        return global_config.BOT_NICKNAME
#     print(user_id)
    return relationship_manager.get_name(user_id)
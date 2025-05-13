from src.do_tool.tool_can_use.base_tool import BaseTool
from src.common.logger import get_module_logger
from typing import Dict, Any

logger = get_module_logger("compare_numbers_tool")


class CompareNumbersTool(BaseTool):
    """比较两个数大小的工具"""

    name = "compare_numbers"
    description = "比较两个数的大小，返回较大的数"
    parameters = {
        "type": "object",
        "properties": {
            "num1": {"type": "number", "description": "第一个数字"},
            "num2": {"type": "number", "description": "第二个数字"},
        },
        "required": ["num1", "num2"],
    }

    async def execute(self, function_args: Dict[str, Any]) -> Dict[str, Any]:
        """执行比较两个数的大小

        Args:
            function_args: 工具参数
            message_txt: 原始消息文本

        Returns:
            Dict: 工具执行结果
        """
        try:
            num1 = function_args.get("num1")
            num2 = function_args.get("num2")

            if num1 > num2:
                result = f"{num1} 大于 {num2}"
            elif num1 < num2:
                result = f"{num1} 小于 {num2}"
            else:
                result = f"{num1} 等于 {num2}"

            return {"name": self.name, "content": result}
        except Exception as e:
            logger.error(f"比较数字失败: {str(e)}")
            return {"name": self.name, "content": f"比较数字失败: {str(e)}"}


# 注册工具
# register_tool(CompareNumbersTool)

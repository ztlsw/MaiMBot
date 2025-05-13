import shutil
import tomlkit
from pathlib import Path
from datetime import datetime


def update_config():
    print("开始更新配置文件...")
    # 获取根目录路径
    root_dir = Path(__file__).parent.parent.parent.parent
    template_dir = root_dir / "template"
    config_dir = root_dir / "config"
    old_config_dir = config_dir / "old"

    # 创建old目录（如果不存在）
    old_config_dir.mkdir(exist_ok=True)

    # 定义文件路径
    template_path = template_dir / "bot_config_template.toml"
    old_config_path = config_dir / "bot_config.toml"
    new_config_path = config_dir / "bot_config.toml"

    # 读取旧配置文件
    old_config = {}
    if old_config_path.exists():
        print(f"发现旧配置文件: {old_config_path}")
        with open(old_config_path, "r", encoding="utf-8") as f:
            old_config = tomlkit.load(f)

        # 生成带时间戳的新文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        old_backup_path = old_config_dir / f"bot_config_{timestamp}.toml"

        # 移动旧配置文件到old目录
        shutil.move(old_config_path, old_backup_path)
        print(f"已备份旧配置文件到: {old_backup_path}")

    # 复制模板文件到配置目录
    print(f"从模板文件创建新配置: {template_path}")
    shutil.copy2(template_path, new_config_path)

    # 读取新配置文件
    with open(new_config_path, "r", encoding="utf-8") as f:
        new_config = tomlkit.load(f)

    # 检查version是否相同
    if old_config and "inner" in old_config and "inner" in new_config:
        old_version = old_config["inner"].get("version")
        new_version = new_config["inner"].get("version")
        if old_version and new_version and old_version == new_version:
            print(f"检测到版本号相同 (v{old_version})，跳过更新")
            # 如果version相同，恢复旧配置文件并返回
            shutil.move(old_backup_path, old_config_path)
            return
        else:
            print(f"检测到版本号不同: 旧版本 v{old_version} -> 新版本 v{new_version}")

    # 递归更新配置
    def update_dict(target, source):
        for key, value in source.items():
            # 跳过version字段的更新
            if key == "version":
                continue
            if key in target:
                if isinstance(value, dict) and isinstance(target[key], (dict, tomlkit.items.Table)):
                    update_dict(target[key], value)
                else:
                    try:
                        # 对数组类型进行特殊处理
                        if isinstance(value, list):
                            # 如果是空数组，确保它保持为空数组
                            if not value:
                                target[key] = tomlkit.array()
                            else:
                                target[key] = tomlkit.array(value)
                        else:
                            # 其他类型使用item方法创建新值
                            target[key] = tomlkit.item(value)
                    except (TypeError, ValueError):
                        # 如果转换失败，直接赋值
                        target[key] = value

    # 将旧配置的值更新到新配置中
    print("开始合并新旧配置...")
    update_dict(new_config, old_config)

    # 保存更新后的配置（保留注释和格式）
    with open(new_config_path, "w", encoding="utf-8") as f:
        f.write(tomlkit.dumps(new_config))
    print("配置文件更新完成")


if __name__ == "__main__":
    update_config()

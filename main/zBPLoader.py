from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Blueprint 配置文件路径：当前模块所在目录的上级目录
_current_dir = Path(__file__).resolve().parent
_parent_dir = _current_dir.parent
_blueprint_config_path = _parent_dir / "blueprint_config.toml"

# 默认配置
_default_blueprint_config = """# Blueprint 功能开关配置文件
# 默认全部为 false (关闭)

[blueprints]
main_loop_bp = false
ap_bp = false
"""

def _create_default_config():
    """配置文件不存在时创建默认配置"""
    if _blueprint_config_path.exists():
        return

    try:
        with open(_blueprint_config_path, "w", encoding="utf-8") as f:
            f.write(_default_blueprint_config)

        logger.info(
            "已自动创建默认 Blueprint 配置文件: {}",
            _blueprint_config_path
        )

    except Exception as e:
        logger.warning("创建默认 Blueprint 配置文件失败: {}", e)


def _load_config():
    """读取 TOML 配置文件"""
    config_data = {}

    try:
        if not _blueprint_config_path.exists():
            return config_data

        try:
            import tomllib
            with open(_blueprint_config_path, "rb") as f:
                config_data = tomllib.load(f)

        except ImportError:
            try:
                import tomli
                with open(_blueprint_config_path, "rb") as f:
                    config_data = tomli.load(f)

            except ImportError:
                logger.warning(
                    "缺少 TOML 解析库，请安装 tomli 或使用 Python 3.11+"
                )

    except Exception as e:
        logger.warning("读取 Blueprint 配置文件异常: {}", e)

    return config_data


# 初始化配置
_create_default_config()

_bp_config_data = _load_config()
_bp_switches = _bp_config_data.get("blueprints", {})


def _save_config():
    """保存 Blueprint 配置"""
    try:
        lines = [
            "# Blueprint 功能开关配置文件",
            "# 默认全部为 false (关闭)",
            "",
            "[blueprints]"
        ]

        for name, value in _bp_switches.items():
            lines.append(f"{name} = {'true' if bool(value) else 'false'}")

        with open(_blueprint_config_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        return True

    except Exception as e:
        logger.warning("保存 Blueprint 配置失败: {}", e)
        return False


def is_bp_enabled(name: str) -> bool:
    """
    判断 Blueprint 是否开启。
    如果配置项不存在，则自动补充为 false 并保存。
    """

    if name not in _bp_switches:
        logger.info("发现未配置的 Blueprint: {}，自动添加为 false", name)

        _bp_switches[name] = False
        _save_config()

        return False

    val = _bp_switches[name]

    if isinstance(val, bool):
        return val

    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")

    return bool(val)
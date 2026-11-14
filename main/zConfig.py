import os
from pathlib import Path
from typing import Any, Optional

# 尝试导入 tomllib / tomli / ruamel.yaml
HAS_TOML = False
toml_load = None
toml_dump = None

try:
    import tomllib
    toml_load = lambda f: tomllib.load(f)
    HAS_TOML = True
except ImportError:
    try:
        import tomli
        toml_load = lambda f: tomli.load(f)
        HAS_TOML = True
    except ImportError:
        pass

# 同时也保留 ruamel.yaml 作为备选（如果没有 toml 库或者回退到 yaml.yaml）
from ruamel.yaml import YAML
yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

DEFAULT_CONFIG_NAME = "config.toml"
FALLBACK_CONFIG_NAME = "config.yaml"

def _resolve_config_path(filename: str = DEFAULT_CONFIG_NAME, config_path: Optional[Path] = None) -> Path:
    """
    解析配置文件路径：
    优先在当前文件夹查找，若不存在则到上一级目录寻找。
    """
    if config_path is not None:
        target = Path(config_path)
        if target.exists():
            return target
        # 如果指定了路径但不存在，也可以尝试检查上一级
        parent_target = target.parent.resolve().parent / target.name
        if parent_target.exists():
            return parent_target
        return target

    # 1. 当前文件夹下的指定文件名
    curr_path = Path(filename)
    if curr_path.exists():
        return curr_path

    # 2. 上一级文件夹下的指定文件名
    parent_path = curr_path.parent.resolve().parent / curr_path.name
    if parent_path.exists():
        return parent_path

    # 默认返回当前文件夹下的路径（供报错或写入时使用）
    return curr_path

def _load_config(config_path: Optional[Path] = None):
    """
    读取配置文件：
    优先尝试读取 config.toml（当前目录其次上级目录）；
    如果没有找到 toml 文件，则导入 yaml 库尝试读取 config.yaml（当前目录其次上级目录）。
    """
    # 优先寻找 toml
    toml_target = _resolve_config_path(DEFAULT_CONFIG_NAME, config_path)
    if toml_target.exists() and toml_load is not None:
        with open(toml_target, "rb") as f:
            return toml_load(f), "toml", toml_target

    # 如果有自定义传入路径且明确是 yaml 或没有 toml，或者找不到 toml 但有 yaml
    yaml_target = _resolve_config_path(FALLBACK_CONFIG_NAME, config_path)
    if yaml_target.exists():
        with open(yaml_target, "r", encoding="utf-8") as f:
            return yaml.load(f), "yaml", yaml_target

    # 若都找不到，默认抛出详细的 FileNotFoundError
    raise FileNotFoundError(f"未找到配置文件: 尝试了 {DEFAULT_CONFIG_NAME} 和 {FALLBACK_CONFIG_NAME} (当前目录及上级目录)")

def _save_config(data: Any, file_type: str, target_path: Path) -> None:
    """将配置对象写回文件"""
    if file_type == "toml":
        # 如果当前使用 toml 并且安装了 tomli_w 等库可以写回，否则用 toml/yaml 或抛出/用 yaml 存储
        # 通常 zConfig 使用 set_config。为了简单且安全，如果安装了 tomli_w 可写，或者如果原本是 yaml 格式则用 yaml 保持兼容
        # 这里尝试使用 tomli_w 如果有，或者写入 yaml/toml
        try:
            import tomli_w
            with open(target_path, "wb") as f:
                tomli_w.dump(data, f)
            return
        except ImportError:
            # 如果没有 toml 写回库，可降级使用 ruamel.yaml 写入对应文件或提示
            pass
    
    # 默认使用 yaml 格式保存或写回
    with open(target_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)

def get_config(key_path: Optional[str] = None, default: Any = None, config_path: Optional[Path] = None) -> Any:
    """
    读取配置项。
    
    :param key_path: 配置项路径，支持层级路径（如 'server.port'）。若为 None 则返回完整配置字典。
    :param default: 查找失败时的默认返回值
    :param config_path: 配置文件路径
    :return: 配置项的值
    """
    data, _, _ = _load_config(config_path)
    
    if key_path is None:
        return data

    keys = key_path.split(".")
    curr = data
    for k in keys:
        if isinstance(curr, dict) and k in curr:
            curr = curr[k]
        else:
            return default
    return curr

def set_config(key_path: str, value: Any, config_path: Optional[Path] = None) -> None:
    """
    修改或设置配置项，自动写回文件并保留原有的格式。
    
    :param key_path: 配置项路径，支持层级路径（如 'server.port'）
    :param value: 要设置的新值
    :param config_path: 配置文件路径
    """
    data, file_type, target_path = _load_config(config_path)
    
    keys = key_path.split(".")
    curr = data
    
    # 逐层遍历/建树，保证嵌套结构存在
    for k in keys[:-1]:
        if k not in curr or not isinstance(curr[k], dict):
            curr[k] = {}
        curr = curr[k]
    
    # 修改目标 key
    curr[keys[-1]] = value
    
    # 保存修改
    _save_config(data, file_type, target_path)

if __name__ == "__main__":
    try:
        print(f"HAS_TOML{HAS_TOML}")
        ALAS_PATH = get_config("alas.alas_path")
        aaa = get_config("banmumu.file_targets.dir")
        print("ALAS_PATH:", ALAS_PATH)
        print("banmumu.file_targets.dir", aaa)
    except Exception as e:
        print("Error:", e)

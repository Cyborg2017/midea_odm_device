"""设备映射包：按设备类型自动发现和组织映射定义。

每个 T0xXX.py 文件定义一种设备类型的 DEVICE_MAPPING。
新增设备只需创建 T0xXX.py 文件，无需修改其他代码。

协议模式自动推断:
  - 实体配置中有 thing_key -> v2_thing
  - 映射中有 queries/calculate -> v1_luaget
"""
from __future__ import annotations

import logging
import pkgutil
from importlib import import_module
from typing import Any

_LOGGER = logging.getLogger(__name__)

_MODULE_CACHE: dict[int, Any] = {}
_MODULE_REGISTRY: dict[int, str] | None = None


def _parse_device_type(module_name: str) -> int | None:
    """从模块名解析设备类型，如 'T0x58' -> 0x58。"""
    try:
        hex_str = module_name.replace("T0x", "").replace("T0X", "")
        return int(hex_str, 16)
    except (ValueError, TypeError):
        return None


def _infer_protocol(module: Any) -> str:
    """从映射内容推断协议模式。"""
    protocol = getattr(module, "DEVICE_PROTOCOL", "")
    if protocol:
        return protocol
    mapping = getattr(module, "DEVICE_MAPPING", {}) or {}
    default = mapping.get("default", {}) or {}
    entities = default.get("entities", {}) or {}
    # 实体配置中有 thing_key 则为 v2_thing
    for cfg in entities.values():
        if isinstance(cfg, dict):
            for ecfg in cfg.values():
                if isinstance(ecfg, dict) and "thing_key" in ecfg:
                    return "v2_thing"
    # 有 queries/calculate 则为 v1_luaget
    if default.get("queries"):
        return "v1_luaget"
    return "v2_thing"


def _scan_modules() -> dict[int, str]:
    """自动扫描所有 T0x*.py 模块，构建 device_type -> module_name 映射。"""
    global _MODULE_REGISTRY
    if _MODULE_REGISTRY is not None:
        return _MODULE_REGISTRY

    result: dict[int, str] = {}
    for finder, name, ispkg in pkgutil.iter_modules(__path__):
        if not (name.startswith("T0x") or name.startswith("T0X")):
            continue
        device_type = _parse_device_type(name)
        if device_type is None:
            continue
        result[device_type] = name
    _MODULE_REGISTRY = result
    return result


def load_all_modules() -> None:
    """在线程池中调用，预扫描并加载所有设备映射模块。"""
    for device_type in _scan_modules():
        _load_module(device_type)


def _load_module(device_type: int) -> Any | None:
    """加载指定设备类型的映射模块（带缓存）。"""
    if device_type in _MODULE_CACHE:
        return _MODULE_CACHE[device_type]

    registered = _scan_modules()
    module_name = registered.get(device_type)
    if not module_name:
        _LOGGER.debug("设备类型 0x%02X 未注册映射模块", device_type)
        return None

    try:
        module = import_module(f".{module_name}", __package__)
        _MODULE_CACHE[device_type] = module
        return module
    except ModuleNotFoundError:
        _LOGGER.warning("设备类型 0x%02X 的映射模块 %s 未找到", device_type, module_name)
        return None


def load_mapping(
    device_type: int,
    sn8: str = "",
    subtype: int | None = None,
    category: str | None = None,
) -> dict:
    """加载并匹配设备的映射配置。

    匹配优先级: subtype > sn8 > category > default
    """
    import re

    module = _load_module(device_type)
    if not module:
        return {}

    device_mappings: dict = getattr(module, "DEVICE_MAPPING", {}) or {}
    if not device_mappings:
        return {}

    result = None

    # 1. 按 subtype 匹配
    if subtype is not None:
        subtype_str = str(subtype)
        for key, config in device_mappings.items():
            if (
                isinstance(key, tuple)
                and len(key) == 2
                and key[0] == "subtype"
                and str(key[1]) == subtype_str
            ):
                result = config
                break

    # 2. 按 sn8 匹配
    if result is None and sn8:
        for key, config in device_mappings.items():
            if (
                key == sn8
                or (isinstance(key, tuple) and sn8 in key)
                or (isinstance(key, str) and re.match(key, sn8))
            ):
                result = config
                break

    # 3. 按 category 匹配
    if result is None and category:
        category_key = f"default_{category.replace('-', '_')}"
        if category_key in device_mappings:
            result = device_mappings[category_key]

    # 4. 默认配置
    if result is None and "default" in device_mappings:
        result = device_mappings["default"]

    if not result:
        _LOGGER.debug(
            "未找到匹配的映射: sn8=%s subtype=%s category=%s type=0x%02X",
            sn8, subtype, category, device_type,
        )

    return result or {}


def get_specific_endpoints(device_type: int) -> dict:
    """获取设备类型对应的设备专用端点表。"""
    module = _load_module(device_type)
    if not module:
        return {}
    mapping = (getattr(module, "DEVICE_MAPPING", {}) or {}).get("default", {})
    return mapping.get("specific_endpoints", {}) or {}


def get_device_protocol(device_type: int) -> str:
    """获取设备类型的协议模式: 'v2_thing' 或 'v1_luaget'。"""
    module = _load_module(device_type)
    if not module:
        return ""
    return _infer_protocol(module)


def get_all_device_types() -> dict[int, str]:
    """获取所有已注册的设备类型: {device_type: protocol}。"""
    result: dict[int, str] = {}
    for dt in _scan_modules():
        module = _load_module(dt)
        if module:
            result[dt] = _infer_protocol(module)
    return result

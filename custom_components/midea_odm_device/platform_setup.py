"""通用平台初始化框架。

所有平台文件通过本模块统一创建实体，不在平台文件中出现任何设备特有字段名或 API 调用。

两类设备共用同一套调度:
  - 透明协议只读设备（走 MideaDataUpdateCoordinator）- 仅消费 mapping['entities'][platform]
  - Thing Model V2 设备（走 MideaThingDataCoordinator）- 消费 mapping['entities'][platform]

平台只消费通用键（thing_key/section/field/list_index/...）。
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device_mapping import load_mapping
from .midea_entity import (
    MideaDiagnosticBinarySensor,
    MideaDiagnosticSensor,
    MideaThingDiagnosticBinarySensor,
    MideaThingDiagnosticSensor,
    safe_key,
)

# Built-in diagnostic info keys exposed as sensor entities on the device page
DIAGNOSTIC_SENSOR_KEYS = ("sn", "sn8", "device_id")


EntityFactory = Callable[
    [Any, Any, Any, Any, str, dict[str, Any]],
    Any,
]
ThingEntityFactory = Callable[
    [Any, str, dict[str, Any]],
    Any,
]
RestSensorFactory = Callable[
    [Any, str, dict[str, Any]],
    Any,
]


def _set_entity_identity(entity: Any, platform: Platform, device_id: Any, entity_key: str) -> None:
    """按集成约定设置实体唯一 ID 和实体 ID。"""
    platform_name = platform.value
    entity._attr_unique_id = (
        f"{platform_name}.midea_{device_id}_{entity_key}"
        if platform_name
        else f"midea_{device_id}_{entity_key}"
    )
    if platform_name:
        entity.entity_id = f"{platform_name}.midea_{device_id}_{safe_key(entity_key)}"


async def async_setup_platform_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    platform: Platform,
    entity_factory: EntityFactory,
) -> None:
    """为透明协议只读设备创建实体。

    平台实体来自 mapping['entities'][platform]，工厂返回 None 会被自动过滤。
    """
    account_bucket = hass.data.get(DOMAIN, {}).get("accounts", {}).get(config_entry.entry_id)
    if not account_bucket:
        async_add_entities([])
        return

    device_list = account_bucket.get("device_list", {})
    coordinator_map = account_bucket.get("coordinator_map", {})
    thing_coordinators = account_bucket.get("thing_coordinators", {})

    entities: list[Any] = []
    for device_id, info in device_list.items():
        # 跳过 Thing 设备（由 async_setup_thing_entities 单独处理）
        if str(device_id) in thing_coordinators:
            continue
        device_type = info.get("type")
        sn8 = info.get("sn8")
        coordinator = coordinator_map.get(device_id)
        device = coordinator.device if coordinator else None
        subtype = info.get("model_number")
        category = info.get("category")

        config = await _load_mapping_async(device_type, sn8, subtype, category)
        entities_cfg = (config.get("entities") or {}).get(platform, {}) or {}

        for entity_key, ecfg in entities_cfg.items():
            entity = entity_factory(
                coordinator, device,
                config.get("manufacturer"), config.get("rationale"),
                entity_key, ecfg,
            )
            if entity is not None:
                _set_entity_identity(entity, platform, device_id, entity_key)
                entities.append(entity)

        # Built-in diagnostic entities for the device page
        if coordinator is not None:
            if platform == Platform.SENSOR:
                for diag_key in DIAGNOSTIC_SENSOR_KEYS:
                    entity = MideaDiagnosticSensor(coordinator, device, diag_key)
                    _set_entity_identity(entity, platform, device_id, diag_key)
                    entities.append(entity)
            elif platform == Platform.BINARY_SENSOR:
                entity = MideaDiagnosticBinarySensor(coordinator, device)
                _set_entity_identity(entity, platform, device_id, "online")
                entities.append(entity)

    async_add_entities(entities)


async def async_setup_thing_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    platform: Platform,
    thing_entity_factory: ThingEntityFactory,
    *,
    rest_sensor_factory: RestSensorFactory | None = None,
) -> None:
    """为 Thing Model V2 设备创建实体。

    平台实体来自 mapping['entities'][platform]。
    配置中含 section 字段的实体使用 rest_sensor_factory 创建（设备专用端点派生传感器）。
    """
    account_bucket = hass.data.get(DOMAIN, {}).get("accounts", {}).get(config_entry.entry_id)
    if not account_bucket:
        async_add_entities([])
        return

    thing_coordinators = account_bucket.get("thing_coordinators", {})
    for appliance_code, coordinator in thing_coordinators.items():
        info = coordinator._device_info or {}
        device_type = info.get("type") or info.get("device_type")
        sn8 = info.get("sn8")
        subtype = info.get("model_number") or info.get("subtype")
        category = info.get("category")

        mapping = await _load_mapping_async(device_type, sn8, subtype, category)
        platform_entities = (mapping.get("entities") or {}).get(platform, {}) or {}

        entities: list[Any] = []
        for entity_key, ecfg in platform_entities.items():
            # 配置中有 section 字段时使用 REST 传感器工厂
            if "section" in ecfg and rest_sensor_factory is not None:
                entity = rest_sensor_factory(coordinator, entity_key, ecfg)
            else:
                entity = thing_entity_factory(coordinator, entity_key, ecfg)
            if entity is not None:
                _set_entity_identity(entity, platform, appliance_code, entity_key)
                entities.append(entity)

        # Built-in diagnostic entities for the device page
        if platform == Platform.SENSOR:
            for diag_key in DIAGNOSTIC_SENSOR_KEYS:
                entity = MideaThingDiagnosticSensor(coordinator, diag_key)
                _set_entity_identity(entity, platform, appliance_code, diag_key)
                entities.append(entity)
        elif platform == Platform.BINARY_SENSOR:
            entity = MideaThingDiagnosticBinarySensor(coordinator)
            _set_entity_identity(entity, platform, appliance_code, "online")
            entities.append(entity)

        async_add_entities(entities)


async def _load_mapping_async(
    device_type: int | None,
    sn8: str | None,
    subtype: int | None,
    category: str | None,
) -> dict:
    """异步加载设备映射。"""
    if device_type is None:
        return {}
    import asyncio
    return await asyncio.to_thread(
        load_mapping,
        device_type,
        sn8 or "",
        subtype,
        category,
    )

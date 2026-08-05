"""美的慧选设备 - 传感器平台。

支持三类传感器:
  - 透明协议只读设备 (T0xBC):  MideaSensor + mapping['entities'][SENSOR]
  - Thing 设备属性传感器:      MideaThingSensor + mapping['entities'][SENSOR]
  - 设备专用端点派生传感器:     MideaRestSensor（配置中有 section 字段时自动创建）
"""
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .midea_entity import MideaEntity, MideaThingEntity
from .platform_setup import (
    async_setup_platform_entities,
    async_setup_thing_entities,
)

_LOGGER = logging.getLogger(__name__)


class MideaSensor(MideaEntity, SensorEntity):
    """透明协议只读设备传感器实体。"""

    @property
    def native_value(self) -> Any:
        """从设备属性中按 attribute 键提取传感器值。"""
        attribute_key = self._config.get("attribute", self._entity_key)
        return self._get_nested_value(attribute_key)


def _lua_plugin_factory(coordinator, device, manufacturer, rationale, entity_key, config):
    """透明协议传感器工厂函数。"""
    return MideaSensor(coordinator, device, entity_key, config)


class MideaThingSensor(MideaThingEntity, SensorEntity):
    """Thing 设备属性传感器实体，基于 V2 通用 API。"""

    def __init__(self, coordinator, entity_key: str, config: dict):
        super().__init__(coordinator, entity_key, config, unique_id_prefix="tms")
        self._attr_device_class = config.get("device_class")
        self._attr_state_class = config.get("state_class")
        self._attr_native_unit_of_measurement = config.get("unit")

    @property
    def native_value(self) -> Any:
        """从 Thing 属性中获取传感器值。"""
        return self._get_thing_value()


def _thing_sensor_factory(coordinator, entity_key, config):
    """Thing 传感器工厂函数。"""
    return MideaThingSensor(coordinator, entity_key, config)


class MideaRestSensor(MideaThingEntity, SensorEntity):
    """设备专用端点派生传感器，从 REST 接口返回数据中提取字段值。

    支持三种取值方式:
      1. list_match: 在列表中按字段匹配后取值
      2. list_index: 取列表第 N 项的字段
      3. 普通 dict: 直接取字段
    """

    def __init__(self, coordinator, entity_key: str, config: dict):
        super().__init__(coordinator, entity_key, config, unique_id_prefix="tmr")
        self._attr_device_class = config.get("device_class")
        self._attr_state_class = config.get("state_class")
        self._attr_native_unit_of_measurement = config.get("unit")

    def _extract_value(self) -> Any:
        """从 REST section 数据中提取字段值。"""
        section = self._config.get("section")
        field = self._config.get("field")
        if not section or not field:
            return None
        raw = self._get_rest_section(section)
        if raw is None:
            return None

        # 1) list_match: 在 list 中按字段匹配
        if (matcher := self._config.get("list_match")) and isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                if all(item.get(k) == v for k, v in matcher.items()):
                    return item.get(field)
            return None

        # 2) list_index: 取 list 第 N 项的字段
        if (idx := self._config.get("list_index")) is not None and isinstance(raw, list):
            if 0 <= idx < len(raw) and isinstance(raw[idx], dict):
                return raw[idx].get(field)
            return None

        # 3) 普通 dict
        if isinstance(raw, dict):
            return raw.get(field)
        return None

    @property
    def native_value(self) -> Any:
        """返回从 REST 数据中提取的传感器值。"""
        return self._extract_value()


def _rest_sensor_factory(coordinator, entity_key, config):
    """REST 派生传感器工厂函数。"""
    return MideaRestSensor(coordinator, entity_key, config)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """传感器平台入口。"""
    # 透明协议只读设备
    await async_setup_platform_entities(
        hass, config_entry, async_add_entities,
        Platform.SENSOR, _lua_plugin_factory,
    )
    # Thing 设备（含设备专用端点派生传感器）
    await async_setup_thing_entities(
        hass, config_entry, async_add_entities,
        Platform.SENSOR, _thing_sensor_factory,
        rest_sensor_factory=_rest_sensor_factory,
    )

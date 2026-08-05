"""美的慧选设备 - 二元传感器平台。

支持透明协议只读设备和 Thing 设备。
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .midea_entity import MideaThingEntity
from .platform_setup import (
    async_setup_platform_entities,
    async_setup_thing_entities,
)

_LOGGER = logging.getLogger(__name__)


class MideaBinarySensor(MideaThingEntity, BinarySensorEntity):
    """透明协议只读设备二元传感器实体。"""

    def __init__(self, coordinator, device, manufacturer, rationale, entity_key, config):
        super().__init__(coordinator, entity_key, config, unique_id_prefix="mb")

    @property
    def is_on(self) -> bool | None:
        """返回传感器开关状态。"""
        val = self._get_thing_value()
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        try:
            return bool(int(val))
        except (TypeError, ValueError):
            return None


class MideaThingBinarySensor(MideaThingEntity, BinarySensorEntity):
    """Thing 设备二元传感器实体。"""

    def __init__(self, coordinator, entity_key, config):
        super().__init__(coordinator, entity_key, config, unique_id_prefix="tmb")
        self._attr_device_class = config.get("device_class")

    @property
    def is_on(self) -> bool | None:
        """返回传感器开关状态。"""
        val = self._get_thing_value()
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        try:
            return bool(int(val))
        except (TypeError, ValueError):
            return None


def _lua_factory(coordinator, device, manufacturer, rationale, entity_key, config):
    """透明协议二元传感器工厂函数。"""
    return MideaBinarySensor(coordinator, device, manufacturer, rationale, entity_key, config)


def _thing_factory(coordinator, entity_key, config):
    """Thing 二元传感器工厂函数。"""
    return MideaThingBinarySensor(coordinator, entity_key, config)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """二元传感器平台入口。"""
    await async_setup_platform_entities(
        hass, config_entry, async_add_entities,
        Platform.BINARY_SENSOR, _lua_factory,
    )
    await async_setup_thing_entities(
        hass, config_entry, async_add_entities,
        Platform.BINARY_SENSOR, _thing_factory,
    )

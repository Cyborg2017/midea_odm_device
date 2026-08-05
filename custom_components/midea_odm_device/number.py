"""美的慧选设备 - 数值平台。

只服务 Thing 设备（V2 通用 API 控制）。
透明协议只读设备（T0xBC）不支持本平台。
"""
import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
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


class MideaThingNumber(MideaThingEntity, NumberEntity):
    """Thing 设备数值实体，支持标量属性和对象字段两种模式。"""

    def __init__(self, coordinator, entity_key, config):
        super().__init__(coordinator, entity_key, config, unique_id_prefix="tmn")
        self._attr_native_min_value = config.get("min")
        self._attr_native_max_value = config.get("max")
        self._attr_native_step = config.get("step")
        self._attr_native_unit_of_measurement = config.get("unit")
        self._attr_mode = NumberMode.BOX

    @property
    def native_value(self) -> Any:
        """返回当前数值。"""
        return self._get_thing_value()

    async def async_set_native_value(self, value: float) -> None:
        """设置数值。"""
        # REST 写入模式: 从 list item 合并 id 后整体 POST
        rest_write = self._config.get("rest_write")
        if rest_write:
            section = self._config.get("section")
            list_index = self._config.get("list_index")
            list_match = self._config.get("list_match")
            field = self._config.get("field")
            id_field = rest_write.get("id_field", "id")
            endpoint = rest_write.get("endpoint")
            item = self.coordinator.get_rest_list_item(section, list_index, list_match) or {}
            # 只保留 id 和目标字段
            payload = {id_field: item.get(id_field), field: int(value)}
            await self.coordinator.async_rest_write(endpoint, payload)
            return
        # Thing 属性写入模式
        thing_key = self._config.get("thing_key", self._entity_key)
        field = self._config.get("field")
        if field:
            # 对象字段: 合并整个对象后写回
            await self.coordinator.async_set_object_field(thing_key, field, value)
        else:
            # 标量属性: 直接写入
            await self.coordinator.async_set_property(thing_key, value)


def _noop_factory(coordinator, device, manufacturer, rationale, entity_key, config):
    """空操作工厂，透明协议只读设备不支持数值。"""
    return None


def _thing_factory(coordinator, entity_key, config):
    """Thing 数值工厂函数。"""
    return MideaThingNumber(coordinator, entity_key, config)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """数值平台入口。"""
    await async_setup_platform_entities(
        hass, config_entry, async_add_entities,
        Platform.NUMBER, _noop_factory,
    )
    await async_setup_thing_entities(
        hass, config_entry, async_add_entities,
        Platform.NUMBER, _thing_factory,
    )

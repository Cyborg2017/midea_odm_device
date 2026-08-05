"""美的慧选设备 - 开关平台。

只服务 Thing 设备（V2 通用 API 控制）。
透明协议只读设备（T0xBC）不支持本平台。
"""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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


class MideaThingSwitch(MideaThingEntity, SwitchEntity):
    """Thing 设备开关实体。"""

    @property
    def is_on(self) -> bool | None:
        """返回开关状态。"""
        val = self._get_thing_value()
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        try:
            return bool(int(val))
        except (TypeError, ValueError):
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """打开开关。"""
        thing_key = self._config.get("thing_key", self._entity_key)
        await self.coordinator.async_set_property(thing_key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """关闭开关。"""
        thing_key = self._config.get("thing_key", self._entity_key)
        await self.coordinator.async_set_property(thing_key, False)


def _noop_factory(coordinator, device, manufacturer, rationale, entity_key, config):
    """空操作工厂，透明协议只读设备不支持开关。"""
    return None


def _thing_factory(coordinator, entity_key, config):
    """Thing 开关工厂函数。"""
    return MideaThingSwitch(coordinator, entity_key, config)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """开关平台入口。"""
    await async_setup_platform_entities(
        hass, config_entry, async_add_entities,
        Platform.SWITCH, _noop_factory,
    )
    await async_setup_thing_entities(
        hass, config_entry, async_add_entities,
        Platform.SWITCH, _thing_factory,
    )

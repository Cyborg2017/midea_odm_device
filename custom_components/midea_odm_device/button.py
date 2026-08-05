"""美的慧选设备 - 按钮平台。

只服务 Thing 设备（V2 通用 API Action 控制）。
透明协议只读设备（T0xBC）不支持本平台。
"""
import logging

from homeassistant.components.button import ButtonEntity
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


class MideaThingButton(MideaThingEntity, ButtonEntity):
    """Thing 设备按钮实体，按下时通过 V2 API 执行 Action。"""

    async def async_press(self) -> None:
        """处理按钮按下事件，调用云端 Action 接口。"""
        module_code = self._config.get("module_code")
        action_code = self._config.get("action_code")
        body = self._config.get("body") or {}
        if not module_code or not action_code:
            _LOGGER.warning("按钮 %s 缺少 module_code/action_code", self._entity_key)
            return
        await self.coordinator.async_perform_action(
            module_code, action_code, body
        )


def _noop_factory(coordinator, device, manufacturer, rationale, entity_key, config):
    """空操作工厂，透明协议只读设备不支持按钮。"""
    return None


def _thing_factory(coordinator, entity_key, config):
    """Thing 设备按钮实体工厂。"""
    return MideaThingButton(coordinator, entity_key, config)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """按钮平台入口。"""
    await async_setup_platform_entities(
        hass, config_entry, async_add_entities,
        Platform.BUTTON, _noop_factory,
    )
    await async_setup_thing_entities(
        hass, config_entry, async_add_entities,
        Platform.BUTTON, _thing_factory,
    )

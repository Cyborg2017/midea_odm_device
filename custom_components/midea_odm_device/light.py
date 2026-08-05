"""美的慧选设备 - 灯光平台。

只服务 Thing 设备（V2 通用 API 控制）。
透明协议只读设备（T0xBC）不支持本平台。
"""
import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN
from .midea_entity import MideaThingEntity
from .platform_setup import (
    async_setup_platform_entities,
    async_setup_thing_entities,
)

_LOGGER = logging.getLogger(__name__)


class MideaThingLight(MideaThingEntity, LightEntity):
    """Thing 设备灯光实体，支持开关、亮度调节和灯光场景。"""

    def __init__(self, coordinator, entity_key, config):
        super().__init__(coordinator, entity_key, config, unique_id_prefix="tml")
        self._power_key = config.get("power_key")
        self._brightness_key = config.get("brightness_key")
        self._effect_key = config.get("effect_key")
        self._scenes: list = config.get("scenes") or []
        self._scenes_translation_keys: list = config.get("scenes_translation_keys") or []
        # 场景索引 -> 翻译文本的映射
        self._scene_labels: dict = {}

        # 根据是否支持亮度设置颜色模式
        if self._brightness_key:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF
        # 有灯光场景时启用 effect 功能，先用翻译键兜底，async_added_to_hass 中异步替换为翻译文本
        if self._scenes:
            if (
                self._scenes_translation_keys
                and len(self._scenes_translation_keys) == len(self._scenes)
            ):
                self._scene_labels = {
                    idx: key for idx, key in zip(self._scenes, self._scenes_translation_keys)
                }
            else:
                self._scene_labels = {idx: str(idx) for idx in self._scenes}
            self._attr_effect_list = list(self._scene_labels.values())
            self._attr_supported_features = LightEntityFeature.EFFECT

    async def async_added_to_hass(self) -> None:
        """实体加入 HA 后异步加载灯光场景翻译。"""
        await super().async_added_to_hass()
        if not self._scenes or not self._scenes_translation_keys:
            return
        if len(self._scenes_translation_keys) != len(self._scenes):
            return
        translations = await async_get_translations(
            self.hass, self.hass.config.language, "state", {DOMAIN}
        )
        # 翻译键直接对应 state 下的 slug，形如 "component.<domain>.state.<key>"
        prefix = f"component.{DOMAIN}.state."
        mapping = {
            key[len(prefix):]: value
            for key, value in translations.items()
            if key.startswith(prefix)
        }
        if not mapping:
            return
        self._scene_labels = {
            idx: mapping.get(key, key)
            for idx, key in zip(self._scenes, self._scenes_translation_keys)
        }
        self._attr_effect_list = list(self._scene_labels.values())
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """返回灯光开关状态。"""
        if not self._power_key:
            return None
        val = self.thing_properties.get(self._power_key)
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        try:
            return bool(int(val))
        except (TypeError, ValueError):
            return None

    @property
    def brightness(self) -> int | None:
        """返回亮度值（HA 标准 1-255）。"""
        if not self._brightness_key:
            return None
        val = self.thing_properties.get(self._brightness_key)
        if val is None:
            return None
        try:
            # 设备亮度范围 1-100, HA 标准 1-255
            return round(int(val) * 255 / 100)
        except (TypeError, ValueError):
            return None

    @property
    def effect(self) -> str | None:
        """返回当前灯光场景名称。"""
        if not self._effect_key or not self._scenes:
            return None
        val = self.thing_properties.get(self._effect_key)
        if val is None:
            return None
        try:
            idx = int(val)
        except (TypeError, ValueError):
            return None
        return self._scene_labels.get(idx)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """打开灯光，可同时设置亮度和场景。"""
        optimistic: dict = {}
        if self._power_key:
            await self.coordinator.async_set_property(self._power_key, True)
            optimistic[self._power_key] = True
        if self._brightness_key and ATTR_BRIGHTNESS in kwargs:
            # HA 0-255 -> 设备 1-100
            ha_brightness = int(kwargs[ATTR_BRIGHTNESS])
            device_brightness = max(1, min(100, round(ha_brightness * 100 / 255)))
            await self.coordinator.async_set_property(
                self._brightness_key, device_brightness
            )
            optimistic[self._brightness_key] = device_brightness
        if self._effect_key and ATTR_EFFECT in kwargs:
            effect_name = kwargs[ATTR_EFFECT]
            for idx, name in self._scene_labels.items():
                if name == effect_name:
                    await self.coordinator.async_set_property(self._effect_key, idx)
                    optimistic[self._effect_key] = idx
                    break
        # 乐观更新: 立即反映状态变化，不等下次轮询
        if optimistic:
            self.coordinator.apply_optimistic_update(optimistic)
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """关闭灯光。"""
        if self._power_key:
            await self.coordinator.async_set_property(self._power_key, False)
            self.coordinator.apply_optimistic_update({self._power_key: False})
            self.async_write_ha_state()


def _noop_factory(coordinator, device, manufacturer, rationale, entity_key, config):
    """空操作工厂，透明协议只读设备不支持灯光。"""
    return None


def _thing_factory(coordinator, entity_key, config):
    """Thing 灯光工厂函数。"""
    return MideaThingLight(coordinator, entity_key, config)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """灯光平台入口。"""
    await async_setup_platform_entities(
        hass, config_entry, async_add_entities,
        Platform.LIGHT, _noop_factory,
    )
    await async_setup_thing_entities(
        hass, config_entry, async_add_entities,
        Platform.LIGHT, _thing_factory,
    )

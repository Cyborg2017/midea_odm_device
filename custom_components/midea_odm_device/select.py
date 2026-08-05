"""美的慧选设备 - 选择平台。

只服务 Thing 设备（V2 通用 API 控制）。
透明协议只读设备（T0xBC）不支持本平台。
"""
import logging

from homeassistant.components.select import SelectEntity
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


class MideaThingSelect(MideaThingEntity, SelectEntity):
    """Thing 设备选择实体，支持原始值与翻译标签映射。"""

    def __init__(self, coordinator, entity_key, config):
        super().__init__(coordinator, entity_key, config, unique_id_prefix="tmsel")
        self._raw_options = config.get("options", [])
        self._options_translation_keys = config.get("options_translation_keys")
        self._options_labels = config.get("options_labels")

        # 先用兜底值构建显示选项列表，async_added_to_hass 中再异步替换为翻译文本
        if self._options_labels and len(self._options_labels) == len(self._raw_options):
            self._attr_options = [str(o) for o in self._options_labels]
        else:
            self._attr_options = [str(o) for o in self._raw_options]

    async def async_added_to_hass(self) -> None:
        """实体加入 HA 后异步加载翻译并重建 options。"""
        await super().async_added_to_hass()
        if not (
            self._options_translation_keys
            and len(self._options_translation_keys) == len(self._raw_options)
        ):
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
        self._attr_options = [
            mapping.get(key, key) for key in self._options_translation_keys
        ]
        self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        """返回当前选项的显示标签。"""
        val = self._get_thing_value()
        if val is None:
            return None
        try:
            idx = self._raw_options.index(val)
        except (ValueError, TypeError):
            return str(val)
        if 0 <= idx < len(self._attr_options):
            return self._attr_options[idx]
        return str(val)

    async def async_select_option(self, option: str) -> None:
        """选择选项，将显示标签转为原始值后写入。"""
        # REST 写入模式
        rest_write = self._config.get("rest_write")
        if rest_write:
            section = self._config.get("section")
            list_index = self._config.get("list_index")
            list_match = self._config.get("list_match")
            field = self._config.get("field")
            id_field = rest_write.get("id_field", "id")
            endpoint = rest_write.get("endpoint")
            # 显示标签 -> 原始值
            value = self._raw_options[self._attr_options.index(option)] if option in self._attr_options else option
            item = self.coordinator.get_rest_list_item(section, list_index, list_match) or {}
            payload = {id_field: item.get(id_field), field: value}
            await self.coordinator.async_rest_write(endpoint, payload)
            return
        # Thing 属性写入模式
        thing_key = self._config.get("thing_key", self._entity_key)
        if option in self._attr_options:
            idx = self._attr_options.index(option)
            value = self._raw_options[idx]
        else:
            value = option
        await self.coordinator.async_set_property(thing_key, value)


def _noop_factory(coordinator, device, manufacturer, rationale, entity_key, config):
    """空操作工厂，透明协议只读设备不支持选择。"""
    return None


def _thing_factory(coordinator, entity_key, config):
    """Thing 选择工厂函数。"""
    return MideaThingSelect(coordinator, entity_key, config)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """选择平台入口。"""
    await async_setup_platform_entities(
        hass, config_entry, async_add_entities,
        Platform.SELECT, _noop_factory,
    )
    await async_setup_thing_entities(
        hass, config_entry, async_add_entities,
        Platform.SELECT, _thing_factory,
    )

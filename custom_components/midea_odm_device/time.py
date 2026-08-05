"""美的慧选设备 - 时间平台。

只服务 Thing 设备（V2 通用 API 控制）。
透明协议只读设备（T0xBC）不支持本平台。

支持多种时间格式:
  - "HHmm"  整数 HHmm（如 1320 = 13:20，默认）
  - "hh:mm"  字符串 "HH:MM"
  - "minutes" 分钟数整数（如 1320 = 22:00）
"""
import logging
import re
from datetime import time as dt_time
from typing import Any

from homeassistant.components.time import TimeEntity
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

# 时间字符串解析正则
_TIME_PATTERNS = [
    # "HH:MM" 或 "HH:MM:SS"
    (re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$"), lambda m: dt_time(
        int(m.group(1)), int(m.group(2)),
        int(m.group(3)) if m.group(3) else 0)),
    # "HHMM" 字符串（如 "0930" -> 09:30）
    (re.compile(r"^(\d{1,2})(\d{2})$"), lambda m: dt_time(int(m.group(1)), int(m.group(2)))),
]


def _parse_time(value: Any, value_format: str = "HHmm") -> dt_time | None:
    """将设备返回的时间值解析为 datetime.time 对象。"""
    if value is None:
        return None
    if isinstance(value, dt_time):
        return value
    # 整数处理
    if isinstance(value, int):
        # minutes 模式: 纯分钟数（如 1320 -> 22:00）
        if value_format == "minutes":
            try:
                hours = value // 60
                minutes = value % 60
                if 0 <= hours < 24 and 0 <= minutes < 60:
                    return dt_time(hours, minutes)
            except (ValueError, TypeError):
                pass
            return None
        # HHmm 模式: 如 1320 -> 13:20
        if 0 <= value <= 2359 and value % 100 < 60:
            s = f"{value:04d}"
            try:
                return dt_time(int(s[:2]), int(s[2:]))
            except (ValueError, TypeError):
                return None
        return None
    # 字符串处理
    s = str(value).strip()
    for pat, builder in _TIME_PATTERNS:
        m = pat.match(s)
        if m:
            try:
                return builder(m)
            except (ValueError, TypeError):
                return None
    return None


class MideaThingTime(MideaThingEntity, TimeEntity):
    """Thing 设备时间实体。"""

    @property
    def native_value(self) -> dt_time | None:
        """返回当前时间值。"""
        value_format = self._config.get("value_format", "HHmm")
        return _parse_time(self._get_thing_value(), value_format)

    async def async_set_value(self, value: dt_time) -> None:
        """设置时间值，根据 value_format 转换为设备所需格式。"""
        thing_key = self._config.get("thing_key", self._entity_key)
        field = self._config.get("field")
        value_format = self._config.get("value_format", "HHmm")
        if value_format == "hh:mm":
            formatted: int | str = value.strftime("%H:%M")
        elif value_format == "minutes":
            formatted = value.hour * 60 + value.minute
        else:
            formatted = int(value.strftime("%H%M"))

        # REST 写入模式
        rest_write = self._config.get("rest_write")
        if rest_write:
            section = self._config.get("section")
            list_index = self._config.get("list_index")
            list_match = self._config.get("list_match")
            id_field = rest_write.get("id_field", "id")
            endpoint = rest_write.get("endpoint")
            item = self.coordinator.get_rest_list_item(section, list_index, list_match) or {}
            payload = {id_field: item.get(id_field), field: formatted}
            await self.coordinator.async_rest_write(endpoint, payload)
            return

        # Thing 属性写入模式
        if field:
            await self.coordinator.async_set_object_field(thing_key, field, formatted)
        else:
            await self.coordinator.async_set_property(thing_key, formatted)


def _noop_factory(coordinator, device, manufacturer, rationale, entity_key, config):
    """空操作工厂，透明协议只读设备不支持时间。"""
    return None


def _thing_factory(coordinator, entity_key, config):
    """Thing 时间工厂函数。"""
    return MideaThingTime(coordinator, entity_key, config)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """时间平台入口。"""
    await async_setup_platform_entities(
        hass, config_entry, async_add_entities,
        Platform.TIME, _noop_factory,
    )
    await async_setup_thing_entities(
        hass, config_entry, async_add_entities,
        Platform.TIME, _thing_factory,
    )

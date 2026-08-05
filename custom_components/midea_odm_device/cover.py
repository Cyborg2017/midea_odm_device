"""美的慧选设备 - 窗帘平台。

只服务 Thing 设备（V2 通用 API 控制）。
透明协议只读设备（T0xBC）不支持本平台。
"""
import logging
from typing import Any

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)
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


class MideaThingCover(MideaThingEntity, CoverEntity):
    """Thing 设备窗帘实体，支持开关、停止、位置设置和途中反向。"""

    def __init__(self, coordinator, entity_key, config):
        super().__init__(coordinator, entity_key, config, unique_id_prefix="tmcov")
        self._position_key = config.get("position_key")
        self._target_position_key = config.get(
            "target_position_key", self._position_key
        )
        self._module_code = config.get("module_code", entity_key)
        self._actions = config.get("actions") or {}
        # 临时运动方向，用于支持途中反向（不依赖 workStatus 等未证实字段）
        self._pending_motion: str | None = None
        self._pending_target_position: int | None = None

        device_class = config.get("device_class")
        if device_class:
            self._attr_device_class = device_class

        self._attr_assumed_state = config.get("assumed_state", False)

        features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )
        if self._target_position_key:
            features |= CoverEntityFeature.SET_POSITION
        self._attr_supported_features = features

    def _get_position(self) -> int | None:
        """从 Thing 属性读取当前开合百分比 (0-100)。"""
        if not self._position_key:
            return None
        val = self.thing_properties.get(self._position_key)
        if val is None:
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    def _clear_pending_motion_if_position_reached(self) -> None:
        """当前位置到达目标后清除临时运动方向。"""
        if self._pending_motion is None or self._pending_target_position is None:
            return
        current = self._get_position()
        if current is None:
            return
        try:
            if int(current) == self._pending_target_position:
                self._pending_motion = None
                self._pending_target_position = None
        except (TypeError, ValueError):
            return

    def _set_pending_motion(
        self, motion: str | None, target_position: int | None = None
    ) -> None:
        """设置临时运动方向。"""
        self._pending_motion = motion
        self._pending_target_position = target_position if motion else None

    @property
    def current_cover_position(self) -> int | None:
        """返回当前开合位置 (0=关 100=全开)。"""
        return self._get_position()

    @property
    def is_closed(self) -> bool | None:
        """返回是否完全关闭。"""
        pos = self._get_position()
        if pos is None:
            return None
        return pos == 0

    @property
    def is_opening(self) -> bool:
        """返回是否正在打开。"""
        self._clear_pending_motion_if_position_reached()
        return self._pending_motion == "opening"

    @property
    def is_closing(self) -> bool:
        """返回是否正在关闭。"""
        self._clear_pending_motion_if_position_reached()
        return self._pending_motion == "closing"

    @property
    def state(self) -> str | None:
        """返回窗帘状态。"""
        if self.is_opening:
            return CoverState.OPENING
        if self.is_closing:
            return CoverState.CLOSING
        if self.is_closed:
            return CoverState.CLOSED
        if self.is_closed is False:
            return CoverState.OPEN
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """打开窗帘。"""
        action_code = self._actions.get("open")
        if not action_code:
            return
        await self.coordinator.async_perform_action(self._module_code, action_code)
        self._set_pending_motion("opening", 100)
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """关闭窗帘。"""
        action_code = self._actions.get("close")
        if not action_code:
            return
        await self.coordinator.async_perform_action(self._module_code, action_code)
        self._set_pending_motion("closing", 0)
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """停止窗帘。"""
        action_code = self._actions.get("stop")
        if not action_code:
            return
        await self.coordinator.async_perform_action(self._module_code, action_code)
        self._set_pending_motion(None)
        self.async_write_ha_state()

    async def async_set_cover_position(self, position: int, **kwargs: Any) -> None:
        """设置目标开合位置。"""
        if not self._target_position_key:
            return
        target = max(0, min(100, int(position)))
        await self.coordinator.async_set_property(self._target_position_key, target)
        current = self._get_position()
        if current is None or target == current:
            motion = None
        elif target > current:
            motion = "opening"
        else:
            motion = "closing"
        self._set_pending_motion(motion, target)
        self.async_write_ha_state()


def _noop_factory(coordinator, device, manufacturer, rationale, entity_key, config):
    """空操作工厂，透明协议只读设备不支持窗帘。"""
    return None


def _thing_factory(coordinator, entity_key, config):
    """Thing 窗帘工厂函数。"""
    return MideaThingCover(coordinator, entity_key, config)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """窗帘平台入口。"""
    await async_setup_platform_entities(
        hass, config_entry, async_add_entities,
        Platform.COVER, _noop_factory,
    )
    await async_setup_thing_entities(
        hass, config_entry, async_add_entities,
        Platform.COVER, _thing_factory,
    )

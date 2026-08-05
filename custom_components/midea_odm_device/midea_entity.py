"""美的慧选设备集成实体基类模块。

提供两类实体基类:
  - MideaEntity:      透明协议只读设备实体基类（如 T0xBC）
                      只读取 device.attributes，无控制能力
  - MideaThingEntity: Thing Model V2 通用设备实体基类
                      支持查询/设置/Action

所有具体实体通过平台工厂生成，统一消费映射文件中的配置，
不引入设备特有字段名。
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .data_coordinator import MideaDataUpdateCoordinator, MideaThingDataCoordinator

_LOGGER = logging.getLogger(__name__)


def safe_key(key: str) -> str:
    """将含点的属性键转为 HA 实体唯一 ID 安全字符串。"""
    return key.replace(".", "_").replace(" ", "_").lower()


def _extract_rest_value(
    raw: Any,
    field: str | None,
    list_index: int | None,
    list_match: dict | None,
) -> Any:
    """从 REST section 原始数据中提取字段值。

    - list_match: 在列表中按字段匹配后取 field
    - list_index: 取列表第 N 项的 field
    - 普通 dict: 取 field
    """
    if not field:
        return raw
    if isinstance(raw, list):
        if list_match:
            for item in raw:
                if isinstance(item, dict) and all(
                    item.get(k) == v for k, v in list_match.items()
                ):
                    return item.get(field)
            return None
        if list_index is not None and 0 <= list_index < len(raw):
            item = raw[list_index]
            return item.get(field) if isinstance(item, dict) else None
        return None
    if isinstance(raw, dict):
        return raw.get(field)
    return None


class MideaEntity(CoordinatorEntity[MideaDataUpdateCoordinator], Entity):
    """透明协议只读设备实体基类。

    只读取 coordinator.data.attributes，不提供任何控制能力。
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MideaDataUpdateCoordinator,
        device,
        entity_key: str,
        config: dict | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._device = device
        self._entity_key = entity_key
        self._config = config or {}

        self._attr_unique_id = f"{device.device_id}_{safe_key(entity_key)}".lower()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.device_id))},
            model=device.model,
            serial_number=device.sn,
            manufacturer="Midea",
            name=device.device_name,
        )

        # 从配置中读取通用属性
        if self._config.get("translation_key"):
            self._attr_translation_key = self._config["translation_key"]
        elif self._config.get("label"):
            self._attr_name = self._config["label"]
        if self._config.get("icon"):
            self._attr_icon = self._config["icon"]
        if self._config.get("device_class"):
            self._attr_device_class = self._config["device_class"]
        if self._config.get("state_class"):
            self._attr_state_class = self._config["state_class"]
        if self._config.get("unit_of_measurement"):
            self._attr_native_unit_of_measurement = self._config["unit_of_measurement"]

    @property
    def device_attributes(self) -> dict:
        """返回设备属性字典。"""
        return self.coordinator.data.attributes if self.coordinator.data else {}

    @property
    def available(self) -> bool:
        """返回设备是否可用。"""
        return bool(self.coordinator.data and self.coordinator.data.available)

    def _get_nested_value(self, attribute_key: str | None) -> Any:
        """通用按属性键取值，支持点号嵌套。"""
        if not attribute_key:
            return None
        if "." in attribute_key:
            value: Any = self.device_attributes
            try:
                for key in attribute_key.split("."):
                    if isinstance(value, dict):
                        value = value.get(key)
                    else:
                        return None
                return value
            except (KeyError, TypeError):
                return None
        return self.device_attributes.get(attribute_key)


class MideaThingEntity(CoordinatorEntity[MideaThingDataCoordinator], Entity):
    """Thing Model V2 设备实体基类。

    所有 Thing 实体从映射文件配置 thing_key/field/section 等通用键取值，
    不引入任何设备特有字段名。
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MideaThingDataCoordinator,
        entity_key: str,
        config: dict,
        *,
        unique_id_prefix: str = "tm",
    ) -> None:
        super().__init__(coordinator)
        self._entity_key = entity_key
        self._config = config or {}

        info = coordinator._device_info or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.appliance_code))},
            name=info.get("name", "Midea Device"),
            manufacturer=info.get("manufacturer", "Midea"),
            model=info.get("model"),
            serial_number=info.get("sn"),
        )

        if config.get("translation_key"):
            self._attr_translation_key = config["translation_key"]
        elif config.get("label"):
            self._attr_name = config.get("label")
        self._attr_unique_id = (
            f"{coordinator.appliance_code}_{unique_id_prefix}_{safe_key(entity_key)}"
        )
        if config.get("icon"):
            self._attr_icon = config["icon"]

    @property
    def thing_properties(self) -> dict:
        """返回 Thing Model 属性字典。"""
        if not self.coordinator.data:
            return {}
        return self.coordinator.data.get("thing_properties", {}) or {}

    def _get_thing_value(self) -> Any:
        """按 thing_key + field 通用取值。

        - 标量: thing_properties[thing_key]
        - 对象字段: thing_properties[thing_key][field]
        - 设备专用端点: 配置 section 时从 REST 数据取值
        - 不指定 thing_key 时按 entity_key 兜底
        """
        # 设备专用端点取值模式
        section = self._config.get("section")
        if section:
            field = self._config.get("field")
            list_index = self._config.get("list_index")
            list_match = self._config.get("list_match")
            raw = self._get_rest_section(section)
            if raw is None:
                return None
            return _extract_rest_value(raw, field, list_index, list_match)

        # Thing 属性取值模式
        thing_key = self._config.get("thing_key", self._entity_key)
        field = self._config.get("field")
        raw = self.thing_properties.get(thing_key)
        if field and isinstance(raw, dict):
            return raw.get(field)
        return raw

    def _get_rest_section(self, section: str) -> Any:
        """获取指定 REST section 的原始数据。"""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(section)

    @property
    def available(self) -> bool:
        """返回设备是否可用。"""
        return self.coordinator.data is not None

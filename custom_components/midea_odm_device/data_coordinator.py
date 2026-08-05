"""美的慧选设备设备数据协调器模块。

提供两类协调器:
  - MideaDataUpdateCoordinator:    透明协议只读设备（T0xBC 等）
                                    仅轮询，无控制能力
  - MideaThingDataCoordinator:     Thing Model V2 通用设备
                                    通用 API，支持属性查询/设置/Action
"""
import logging
from datetime import timedelta
from typing import NamedTuple

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .core.device import MiedaDevice
from .core.api import MideaV2ThingApi

_LOGGER = logging.getLogger(__name__)


class MideaDeviceData(NamedTuple):
    """美的设备状态数据结构。"""
    attributes: dict
    available: bool
    connected: bool


class MideaDataUpdateCoordinator(DataUpdateCoordinator[MideaDeviceData]):
    """透明协议只读设备数据协调器（仅轮询，无控制能力）。"""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device: MiedaDevice,
        cloud=None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{device.device_name} ({device.device_id})",
            update_method=self.poll_device_state,
            update_interval=timedelta(
                seconds=config_entry.options.get(
                    CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL
                )
            ),
            always_update=False,
        )
        self.device = device
        self._device_id = device.device_id
        self._cloud = cloud
        self._online_check_counter = 0
        self._online_check_interval = 15

    async def _async_setup(self) -> None:
        """首次初始化，注册设备更新回调。"""
        self.data = await self.poll_device_state()
        self.device.register_update(self._device_update_callback)

    def _device_update_callback(self, status: dict) -> None:
        """设备状态更新回调，合并新状态并通知协调器。"""
        for key, value in status.items():
            self.device.attributes[key] = value
        self.async_set_updated_data(
            MideaDeviceData(
                attributes=self.device.attributes,
                available=self.device.connected,
                connected=self.device.connected,
            )
        )

    async def poll_device_state(self) -> MideaDeviceData:
        """轮询设备状态。"""
        # 定期检查在线状态
        self._online_check_counter += 1
        if self._online_check_counter >= self._online_check_interval:
            self._online_check_counter = 0
            await self._check_device_online_status()

        try:
            await self.device.refresh_status()
            updated = MideaDeviceData(
                attributes=self.device.attributes,
                available=self.device.connected,
                connected=self.device.connected,
            )
            self.async_set_updated_data(updated)
            return updated
        except Exception as e:
            _LOGGER.error(f"轮询设备状态失败: {e}")
            return MideaDeviceData(
                attributes=self.device.attributes,
                available=False,
                connected=False,
            )

    async def _check_device_online_status(self):
        """通过云端设备列表检查设备在线状态。"""
        if not self._cloud:
            return
        try:
            from .core.cloud import MeijuCloud
            if isinstance(self._cloud, MeijuCloud) and hasattr(self._cloud, "_homegroup_id"):
                home_id = self._cloud._homegroup_id
                if appliances := await self._cloud.list_appliances(home_id):
                    device_info = appliances.get(self._device_id)
                    if device_info:
                        is_online = device_info.get("online", False)
                        if is_online != self.device.connected:
                            _LOGGER.info(
                                f"设备 {self._device_id} 在线状态变更: "
                                f"{self.device.connected} -> {is_online}"
                            )
                            self.device._device_connected(is_online)
        except Exception as e:
            _LOGGER.warning(f"检查在线状态失败: {e}")


class MideaThingDataCoordinator(DataUpdateCoordinator[dict]):
    """Thing Model V2 通用设备数据协调器。

    数据结构:
      {
        "thing_properties": {prop_key: value, ...},  # Thing 属性
        "<endpoint_key>": <section_data>,             # 设备专用端点数据
        ...
      }
    """

    def __init__(
        self,
        hass: HomeAssistant,
        thing_api: MideaV2ThingApi,
        cloud,
        appliance_code: str,
        home_group_id: str,
        scan_interval: int,
        specific_endpoints: dict | None = None,
        quick_endpoint_keys: list[str] | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = thing_api
        self.cloud = cloud
        self.appliance_code = appliance_code
        self.home_group_id = home_group_id
        self.specific_endpoints = specific_endpoints or {}
        self.quick_endpoint_keys = quick_endpoint_keys
        self._pending_updates: dict = {}
        self._last_successful_data: dict | None = None

    async def _async_update_data(self) -> dict:
        """拉取设备数据：Thing 属性 + 设备专用端点，合并后返回。"""
        try:
            # 查询 Thing 属性
            thing_properties = await self.api.query_properties(self.appliance_code)

            # 并发请求设备专用端点
            rest_data: dict = {}
            if self.specific_endpoints:
                try:
                    rest_data = await self.api.fetch_rest_data(
                        self.appliance_code,
                        self.home_group_id,
                        self.specific_endpoints,
                        quick_keys=self.quick_endpoint_keys,
                    )
                except Exception as e:
                    _LOGGER.debug(f"设备专用端点数据获取失败: {e}")
                    rest_data = {}

            combined = {
                "thing_properties": thing_properties or {},
                **rest_data,
            }
            self._last_successful_data = combined

            # 合并乐观更新
            if self._pending_updates and combined.get("thing_properties"):
                combined["thing_properties"] = {
                    **combined["thing_properties"],
                    **self._pending_updates,
                }
                self._pending_updates.clear()

            return combined
        except Exception as err:
            # 失败时返回上次成功的数据（含乐观更新）
            if self._last_successful_data:
                cached = dict(self._last_successful_data)
                if self._pending_updates and cached.get("thing_properties"):
                    cached["thing_properties"] = {
                        **cached["thing_properties"],
                        **self._pending_updates,
                    }
                return cached
            raise UpdateFailed(f"获取设备数据失败: {err}") from err

    def apply_optimistic_update(self, properties: dict) -> None:
        """应用乐观更新，不触发刷新。"""
        self._pending_updates.update(properties)
        if self.data:
            updated_data = dict(self.data)
            if updated_data.get("thing_properties"):
                updated_data["thing_properties"] = {
                    **updated_data["thing_properties"],
                    **properties,
                }
            self.async_set_updated_data(updated_data)

    async def async_set_property(self, prop_key: str, prop_value) -> bool:
        """设置单个 Thing 属性。"""
        return await self.api.set_property(self.appliance_code, prop_key, prop_value)

    async def async_set_object_field(self, prop_key: str, field: str, value) -> bool:
        """更新对象型属性的单个字段（合并整个对象后整体写回）。"""
        current = (self.data or {}).get("thing_properties", {}).get(prop_key) if self.data else None
        if not isinstance(current, dict):
            current = {}
        merged = {**current, field: value}
        ok = await self.api.set_property(self.appliance_code, prop_key, merged)
        if ok:
            self.apply_optimistic_update({prop_key: merged})
        return ok

    async def async_perform_action(
        self, module_code: str, action_code: str, body: dict | None = None
    ) -> bool:
        """触发设备 Action。"""
        resp = await self.cloud.perform_thing_action(
            self.appliance_code, module_code, action_code, body or {}
        )
        if isinstance(resp, dict):
            await self.async_request_refresh()
            return True
        return False

    async def async_rest_write(
        self, endpoint_key: str, payload: dict
    ) -> dict | None:
        """调用设备专用端点写入数据。"""
        if endpoint_key not in self.specific_endpoints:
            _LOGGER.warning(f"设备专用端点 {endpoint_key} 未配置")
            return None
        base = {
            "applianceCode": str(self.appliance_code),
            "homegroupId": str(self.home_group_id),
        }
        body = {**base, **payload}
        try:
            endpoint = self.specific_endpoints[endpoint_key]
            resp = await self.cloud._api_request(endpoint, body)
            # 写入后立即触发刷新
            await self.async_request_refresh()
            return resp
        except Exception as e:
            _LOGGER.error(f"设备专用端点写入 {endpoint_key} 失败: {e}")
            return None

    def get_rest_list_item(
        self, section: str, list_index: int | None = None, list_match: dict | None = None
    ) -> dict | None:
        """从设备专用端点数据中取出整条 list item（用于写入时合并 id 等字段）。"""
        if not self.data:
            return None
        raw = self.data.get(section)
        if not isinstance(raw, list):
            return None
        if list_match:
            for item in raw:
                if isinstance(item, dict) and all(
                    item.get(k) == v for k, v in list_match.items()
                ):
                    return item
            return None
        if list_index is not None and 0 <= list_index < len(raw):
            item = raw[list_index]
            return item if isinstance(item, dict) else None
        return None

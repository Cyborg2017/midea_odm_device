"""美的慧选设备设备集成配置流程模块。

提供账号登录、家庭选择、设备选择、插件下载等配置流程。
"""
import asyncio
import logging
import os
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_TYPE
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ACCOUNT,
    CONF_MANUFACTURER_CODE,
    CONF_MODEL_NUMBER,
    CONF_PASSWORD,
    CONF_SELECTED_DEVICES,
    CONF_SELECTED_HOMES,
    CONF_SERVER,
    CONF_SMART_PRODUCT_ID,
    CONF_SN,
    CONF_SN8,
    STORAGE_PLUGIN_PATH,
)
from .core.cloud import get_midea_cloud
from .device_mapping import get_all_device_types

_LOGGER = logging.getLogger(__name__)

def _get_supported_device_types():
    """动态获取所有已注册的设备类型。"""
    return set(get_all_device_types().keys())

class ConfigFlow(config_entries.ConfigFlow, domain="midea_odm_device"):
    """美的慧选设备设备配置流程。"""

    _session = None
    _cloud = None
    _homes = None
    _home_names = None
    _appliances_info = None
    _supported_devices = None
    _selected_devices = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """返回选项流程处理器。"""
        return OptionsFlowHandler(config_entry)

    def _get_home_name(self, home_info, home_id) -> str:
        """获取家庭显示名称。"""
        if isinstance(home_info, dict):
            return home_info.get("name", f"家庭 {home_id}")
        return str(home_info) if home_info else f"家庭 {home_id}"

    @staticmethod
    def _build_device_label(appliance_code, info: dict) -> str:
        """构造设备在勾选列表中的展示标签（名称+型号+sn8+在线状态）。"""
        name = info.get("name", f"Midea {appliance_code}")
        model = info.get("model") or ""
        sn8 = info.get("sn8", "")
        online = info.get("online", False)
        parts = [name]
        if model:
            parts.append(f"型号: {model}")
        if sn8 and sn8 != "00000000":
            parts.append(f"SN8: {sn8}")
        parts.append("在线" if online else "离线")
        return " | ".join(parts)

    def _filter_supported_devices(self, appliances_info: dict) -> dict:
        """过滤出支持的设备。"""
        supported: dict = {}
        for appliance_code, info in appliances_info.items():
            device_type = info.get("type")
            if device_type in _get_supported_device_types():
                supported[appliance_code] = info
                _LOGGER.info(
                    f"[美的慧选设备] 发现支持的设备: {info.get('name')} (type=0x{device_type:02X})"
                )
            else:
                _LOGGER.debug(
                    f"[美的慧选设备] 跳过不支持的设备: {info.get('name')} (type={device_type})"
                )
        return supported

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """用户输入步骤：输入账号密码登录。"""
        errors: dict[str, str] = {}
        if self._session is None:
            self._session = async_create_clientsession(self.hass)
        if user_input is not None:
            server_key = 2

            self.hass.data.setdefault("midea_odm_device", {})
            self.hass.data["midea_odm_device"].setdefault("cloud_sessions", {})
            self.hass.data["midea_odm_device"].setdefault("cloud_login_locks", {})

            session_key = f"{user_input[CONF_ACCOUNT]}_{server_key}"
            if session_key not in self.hass.data["midea_odm_device"]["cloud_login_locks"]:
                self.hass.data["midea_odm_device"]["cloud_login_locks"][session_key] = asyncio.Lock()

            login_ok = False
            cloud = None
            try:
                async with self.hass.data["midea_odm_device"]["cloud_login_locks"][session_key]:
                    cloud = self.hass.data["midea_odm_device"]["cloud_sessions"].get(session_key)
                    if not cloud:
                        cloud = get_midea_cloud(
                            session=self._session,
                            account=user_input[CONF_ACCOUNT],
                            password=user_input[CONF_PASSWORD],
                        )

                    if cloud and getattr(cloud, "_access_token", None):
                        login_ok = True
                    elif cloud:
                        login_ok = await cloud.login()
                    else:
                        login_ok = False

                    if cloud and login_ok:
                        self.hass.data["midea_odm_device"]["cloud_sessions"][session_key] = cloud

                if login_ok:
                    self._cloud = cloud
                    self._user_input = user_input
                    self._nickname = cloud.nickname

                    homes = await cloud.list_home()
                    if homes:
                        _LOGGER.debug(f"[MideaSmart ConfigFlow] Found homes: {homes}")
                        self._homes = homes
                        self._home_names = {}
                        for home_id, home_info in homes.items():
                            self._home_names[home_id] = self._get_home_name(home_info, home_id)
                        return await self.async_step_select_homes()
                    else:
                        errors["base"] = "no_homes"
                else:
                    errors["base"] = "login_failed"
            except Exception as e:
                _LOGGER.exception("[MideaSmart ConfigFlow] Login error: %s", e)
                errors["base"] = "login_failed"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_ACCOUNT): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_select_homes(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """家庭选择步骤：选择要添加的家庭。"""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_homes = user_input.get(CONF_SELECTED_HOMES, [])
            if not selected_homes:
                errors["base"] = "no_homes_selected"
            else:
                selected_home_ids = []
                for home_id in selected_homes:
                    for key in [home_id, str(home_id), int(home_id) if str(home_id).isdigit() else None]:
                        if key is not None and key in self._homes and key not in selected_home_ids:
                            selected_home_ids.append(key)
                            break

                if not selected_home_ids:
                    errors["base"] = "no_homes_selected"
                else:
                    existing_entries = self.hass.config_entries.async_entries("midea_odm_device")
                    configured_homes = set()
                    for entry in existing_entries:
                        entry_homes = entry.data.get(CONF_SELECTED_HOMES, [])
                        for home_id in entry_homes:
                            configured_homes.add(str(home_id))

                    for home_id in selected_home_ids:
                        if str(home_id) in configured_homes:
                            errors["base"] = "home_already_configured"
                            break

                    if errors.get("base"):
                        home_options = {}
                        for home_id, home_info in self._homes.items():
                            home_options[str(home_id)] = self._get_home_name(home_info, home_id)
                        default_selected = list(home_options.keys())
                        return self.async_show_form(
                            step_id="select_homes",
                            data_schema=vol.Schema({
                                vol.Required(CONF_SELECTED_HOMES, default=default_selected): vol.All(
                                    cv.multi_select(home_options)
                                )
                            }),
                            errors=errors,
                        )

                    first_home_id = selected_home_ids[0]
                    first_home_name = self._home_names.get(first_home_id, f"家庭 {first_home_id}")

                    appliances_info = {}
                    for home_id in selected_home_ids:
                        appliances = await self._cloud.list_appliances(home_id)
                        if appliances:
                            for appliance_code, info in appliances.items():
                                appliances_info[appliance_code] = info

                    self._appliances_info = appliances_info
                    self._supported_devices = self._filter_supported_devices(appliances_info)

                    total_supported = len(self._supported_devices)

                    _LOGGER.info(
                        f"[MideaSmart ConfigFlow] Total devices: {len(appliances_info)}, "
                        f"Supported: {total_supported}"
                    )

                    if total_supported == 0:
                        errors["base"] = "no_supported_devices"
                        home_options = {}
                        for home_id, home_info in self._homes.items():
                            home_options[str(home_id)] = self._get_home_name(home_info, home_id)
                        default_selected = list(home_options.keys())
                        return self.async_show_form(
                            step_id="select_homes",
                            data_schema=vol.Schema({
                                vol.Required(CONF_SELECTED_HOMES, default=default_selected): vol.All(
                                    cv.multi_select(home_options)
                                )
                            }),
                            errors=errors,
                        )

                    self._config_data = {
                        CONF_TYPE: CONF_ACCOUNT,
                        CONF_ACCOUNT: self._user_input[CONF_ACCOUNT],
                        CONF_PASSWORD: self._user_input[CONF_PASSWORD],
                        CONF_SERVER: 2,
                        CONF_SELECTED_HOMES: [first_home_id],
                        "home_name": first_home_name,
                        "all_selected_homes": selected_home_ids,
                        "home_names": {str(hid): self._home_names.get(hid, f"家庭 {hid}") for hid in selected_home_ids}
                    }
                    self._total_devices = total_supported
                    self._total_homes = len(selected_home_ids)
                    return await self.async_step_select_devices()

        home_options = {}
        for home_id, home_info in self._homes.items():
            _LOGGER.debug(f"[MideaSmart ConfigFlow] Processing home_id: {home_id}, home_info: {home_info}, type: {type(home_info)}")
            home_options[str(home_id)] = self._get_home_name(home_info, home_info)

        default_selected = list(home_options.keys())
        _LOGGER.debug(f"[MideaSmart ConfigFlow] Home options: {home_options}")
        _LOGGER.debug(f"[MideaSmart ConfigFlow] Default selected: {default_selected}")

        return self.async_show_form(
            step_id="select_homes",
            data_schema=vol.Schema({
                vol.Required(CONF_SELECTED_HOMES, default=default_selected): vol.All(
                    cv.multi_select(home_options)
                )
            }),
            errors=errors,
        )

    async def async_step_select_devices(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """设备选择步骤：选择要添加的设备。"""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = user_input.get(CONF_SELECTED_DEVICES, [])
            if not selected:
                errors["base"] = "no_devices_selected"
            else:
                # 归一化 appliance_code (str -> int 优先)
                selected_codes = []
                for code in selected:
                    for key in [code, str(code), int(code) if str(code).isdigit() else None]:
                        if key is not None and key in self._supported_devices and key not in selected_codes:
                            selected_codes.append(key)
                            break

                if not selected_codes:
                    errors["base"] = "no_devices_selected"
                else:
                    self._selected_devices = {
                        code: self._supported_devices[code] for code in selected_codes
                    }
                    self._total_devices = len(self._selected_devices)
                    _LOGGER.info(
                        f"[MideaSmart ConfigFlow] User selected {self._total_devices} devices: "
                        f"{[self._supported_devices[c].get('name') for c in selected_codes]}"
                    )
                    return await self.async_step_download()

        device_options = {}
        for appliance_code, info in self._supported_devices.items():
            device_options[str(appliance_code)] = self._build_device_label(appliance_code, info)

        default_selected = list(device_options.keys())

        return self.async_show_form(
            step_id="select_devices",
            data_schema=vol.Schema({
                vol.Required(CONF_SELECTED_DEVICES, default=default_selected): vol.All(
                    cv.multi_select(device_options)
                )
            }),
            errors=errors,
            description_placeholders={
                "devices_count": str(len(self._supported_devices)),
            },
        )

    async def async_step_download(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """插件下载步骤：为选中设备下载插件。"""
        devices_to_download = self._selected_devices or self._supported_devices
        if devices_to_download is None or len(devices_to_download) == 0:
            return await self.async_step_confirm()

        if not hasattr(self, '_download_task') or self._download_task is None:
            self._download_progress = 0
            self._download_results = {"success": 0, "skipped": 0, "failed": 0}
            self._plugin_path = self.hass.config.path(STORAGE_PLUGIN_PATH)
            os.makedirs(self._plugin_path, exist_ok=True)
            self._appliances_list = list(devices_to_download.items())
            self._download_task = self.hass.async_create_task(
                self._do_download(),
                eager_start=True,
            )
            return self.async_show_progress(
                step_id="download",
                progress_action="download",
                progress_task=self._download_task,
            )

        if not self._download_task.done():
            return self.async_show_progress(
                step_id="download",
                progress_action="download",
                progress_task=self._download_task,
            )

        self._download_task = None
        return self.async_show_progress_done(next_step_id="confirm")

    async def _do_download(self):
        """执行插件下载任务。"""
        total = len(self._appliances_list)
        for appliance_code, info in self._appliances_list:
            device_name = info.get("name", f"Midea {appliance_code}")
            device_type = info.get("type")

            _LOGGER.info(f"[MideaSmart ConfigFlow] Downloading plugin for: {device_name}")

            try:
                plugin_file = await self._cloud.download_plugin(
                    path=self._plugin_path,
                    appliance_code=appliance_code,
                    smart_product_id=info.get(CONF_SMART_PRODUCT_ID),
                    device_type=device_type,
                    sn=info.get(CONF_SN),
                    sn8=info.get(CONF_SN8),
                    model_number=info.get(CONF_MODEL_NUMBER),
                    manufacturer_code=info.get(CONF_MANUFACTURER_CODE),
                )
                if plugin_file:
                    self._download_results["success"] += 1
                else:
                    self._download_results["skipped"] += 1
            except Exception as e:
                _LOGGER.warning(f"[MideaSmart ConfigFlow] Failed to download plugin for {device_name}: {e}")
                self._download_results["failed"] += 1

            self._download_progress += 1
            if total > 0:
                self.async_update_progress(self._download_progress / total)

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """确认步骤：显示配置摘要并创建配置入口。"""
        if user_input is not None:
            first_home_name = self._config_data.get("home_name", "")
            nickname = getattr(self, "_nickname", self._config_data.get(CONF_ACCOUNT, ""))
            title = f"{nickname} | {first_home_name}" if first_home_name else nickname

            selected_devices = self._selected_devices or self._supported_devices or {}
            self._config_data[CONF_SELECTED_DEVICES] = [str(code) for code in selected_devices.keys()]

            return self.async_create_entry(
                title=title,
                data=self._config_data,
            )

        download_results = getattr(self, "_download_results", None)
        download_summary = ""
        if download_results:
            success = download_results['success']
            skipped = download_results['skipped']
            failed = download_results['failed']
            if failed > 0:
                download_summary = f"✅ 成功 {success} 个\n⏭️ 跳过 {skipped} 个\n❌ 失败 {failed} 个"
            else:
                download_summary = f"✅ 成功 {success} 个\n⏭️ 跳过 {skipped} 个"

        devices_for_display = self._selected_devices or self._supported_devices
        device_list_lines = []
        if devices_for_display:
            for code, info in devices_for_display.items():
                device_list_lines.append(f"• {info.get('name', f'Midea {code}')}")

        device_list = "\n".join(device_list_lines)

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "homes_count": str(getattr(self, '_total_homes', 0)),
                "devices_count": str(getattr(self, '_total_devices', 0)),
                "download_summary": download_summary,
                "device_list": device_list,
            },
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """选项流程处理器：修改账号密码、刷新间隔等。"""
    def __init__(self, config_entry: config_entries.ConfigEntry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None, error=None):
        if user_input is not None:
            if user_input["option"] == "change_credentials":
                return await self.async_step_change_credentials()
            elif user_input["option"] == "change_scan_interval":
                return await self.async_step_change_scan_interval()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("option", default="change_credentials"): vol.In({
                    "change_credentials": "修改账号密码",
                    "change_scan_interval": "修改刷新间隔",
                })
            }),
            errors=error
        )

    async def async_step_change_credentials(self, user_input=None, error=None):
        """修改账号密码步骤。"""
        errors: dict[str, str] = {}

        if user_input is not None:
            cloud = get_midea_cloud(
                session=async_create_clientsession(self.hass),
                account=user_input[CONF_ACCOUNT],
                password=user_input[CONF_PASSWORD]
            )
            try:
                if await cloud.login():
                    current_data = dict(self._config_entry.data)
                    current_data[CONF_ACCOUNT] = user_input[CONF_ACCOUNT]
                    current_data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
                    current_data[CONF_SERVER] = 2

                    home_name = current_data.get("home_name", "")
                    account = user_input[CONF_ACCOUNT]
                    new_title = f"{account} | {home_name}" if home_name else account

                    self.hass.config_entries.async_update_entry(
                        self._config_entry,
                        title=new_title,
                        data=current_data
                    )
                    return self.async_create_entry(title="", data={})
                else:
                    errors["base"] = "login_failed"
            except Exception as e:
                _LOGGER.exception("[MideaSmart OptionsFlow] Login error: %s", e)
                errors["base"] = "login_failed"

        current_data = self._config_entry.data

        return self.async_show_form(
            step_id="change_credentials",
            data_schema=vol.Schema({
                vol.Required(CONF_ACCOUNT, default=current_data.get(CONF_ACCOUNT, "")): str,
                vol.Required(CONF_PASSWORD, default=""): str,
            }),
            errors=errors,
        )

    async def async_step_change_scan_interval(self, user_input=None):
        """修改刷新间隔步骤。"""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        from .const import CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL
        current = self._config_entry.options
        scan_options = [1, 2, 3, 4, 5, 10, 15, 20, 25, 30]
        current_val = current.get(CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL)
        schema = vol.Schema({
            vol.Required(
                CONF_REFRESH_INTERVAL,
                default=current_val if current_val in scan_options else DEFAULT_SCAN_INTERVAL,
            ): vol.In(scan_options),
        })
        return self.async_show_form(step_id="change_scan_interval", data_schema=schema)

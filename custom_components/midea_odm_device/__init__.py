"""美的慧选设备设备集成入口模块。

负责集成的初始化、配置入口的加载/卸载，以及设备发现与协调器创建。

支持两类设备:
  1. 透明协议只读设备（如 T0xBC 空气检测仪）- 走 MideaDataUpdateCoordinator
     仅轮询云端状态查询接口，无控制能力
  2. Thing Model V2 设备 - 走 MideaThingDataCoordinator
     通用 API，支持属性查询/设置/Action

新增设备只需在 device_mapping/ 下创建 T0xXX.py 映射文件。
"""
import asyncio
import logging
import os

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    Platform,
    CONF_TYPE,
    CONF_MODEL,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ACCOUNT,
    CONF_CATEGORY,
    CONF_MANUFACTURER_CODE,
    CONF_MODEL_NUMBER,
    CONF_PASSWORD,
    CONF_REFRESH_INTERVAL,
    CONF_SELECTED_DEVICES,
    CONF_SELECTED_HOMES,
    CONF_SERVER,
    CONF_SMART_PRODUCT_ID,
    CONF_SN,
    CONF_SN8,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    STORAGE_PLUGIN_PATH,
)
from .core.cloud import get_midea_cloud
from .core.device import MiedaDevice
from .core.api import MideaV2ThingApi
from .data_coordinator import MideaDataUpdateCoordinator, MideaThingDataCoordinator
from .device_mapping import get_device_protocol, get_specific_endpoints, load_mapping

_LOGGER = logging.getLogger(__name__)

# 支持的 HA 平台列表
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.TIME,
    Platform.BUTTON,
    Platform.COVER,
]

# 本集成仅通过 config entry 配置，不接受 YAML 配置
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """集成初始化入口（YAML 配置方式）。"""
    hass.data.setdefault(DOMAIN, {})

    def _ensure_storage_dir():
        """确保插件存储目录存在。"""
        storage_path = hass.config.path(STORAGE_PLUGIN_PATH)
        os.makedirs(storage_path, exist_ok=True)
        return storage_path

    await hass.async_add_executor_job(_ensure_storage_dir)
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """配置入口加载（UI 配置方式）。

    流程: 登录美的云 -> 获取家庭和设备列表 -> 按协议类型初始化协调器 -> 加载平台
    """
    device_type = config_entry.data.get(CONF_TYPE)
    _LOGGER.debug(f"[美的慧选设备] async_setup_entry type={device_type}")

    if device_type != CONF_ACCOUNT:
        return False

    account = config_entry.data.get(CONF_ACCOUNT)
    password = config_entry.data.get(CONF_PASSWORD)
    server = config_entry.data.get(CONF_SERVER)

    try:
        server = int(server)
    except Exception:
        pass

    # 初始化 hass.data 数据容器
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("cloud_sessions", {})
    hass.data[DOMAIN].setdefault("accounts", {})
    hass.data[DOMAIN].setdefault("cloud_login_locks", {})

    # 使用账号+服务器作为会话唯一标识，避免重复登录
    session_key = f"{account}_{server}"
    if session_key not in hass.data[DOMAIN]["cloud_login_locks"]:
        hass.data[DOMAIN]["cloud_login_locks"][session_key] = asyncio.Lock()

    async with hass.data[DOMAIN]["cloud_login_locks"][session_key]:
        cloud = hass.data[DOMAIN]["cloud_sessions"].get(session_key)
        if not cloud:
            cloud = get_midea_cloud(
                session=async_get_clientsession(hass),
                account=account,
                password=password,
            )
            if not cloud or not await cloud.login():
                _LOGGER.error("[美的慧选设备] 美的云登录失败")
                return False
            hass.data[DOMAIN]["cloud_sessions"][session_key] = cloud
        elif not cloud._access_token:
            if not await cloud.login():
                _LOGGER.error("[美的慧选设备] 美的云登录失败")
                return False

    selected_homes = config_entry.data.get(CONF_SELECTED_HOMES, [])

    try:
        homes = await cloud.list_home()
        if homes:
            bucket: dict = {
                "device_list": {},
                "coordinator_map": {},
                "thing_coordinators": {},
            }

            # 确定要遍历的家庭 ID 列表
            if not selected_homes:
                home_ids = list(homes.keys())
            else:
                home_ids = []
                for selected_home in selected_homes:
                    for key in [selected_home, str(selected_home),
                                int(selected_home) if str(selected_home).isdigit() else None]:
                        if key is not None and key in homes and key not in home_ids:
                            home_ids.append(key)
                            break

            # 创建 V2 Thing API 客户端（复用云登录态）
            thing_api = MideaV2ThingApi(cloud)
            thing_login_ok = bool(cloud._access_token)

            # 用户在配置流程中勾选的设备
            selected_device_codes = set(
                str(code) for code in config_entry.data.get(CONF_SELECTED_DEVICES, [])
            )

            for home_id in home_ids:
                appliances = await cloud.list_appliances(home_id)
                if appliances is None:
                    continue

                for appliance_code, info in appliances.items():
                    appliance_type = info.get(CONF_TYPE)
                    appliance_code_str = str(appliance_code)

                    # 跳过未勾选的设备
                    if selected_device_codes and appliance_code_str not in selected_device_codes:
                        _LOGGER.debug(
                            f"[美的慧选设备] 跳过未选中设备: "
                            f"{info.get(CONF_NAME)} ({appliance_code_str})"
                        )
                        continue

                    # 根据协议类型分发初始化
                    protocol = get_device_protocol(appliance_type)
                    if protocol == "v1_luaget":
                        try:
                            await _init_read_only_device(
                                hass, config_entry, cloud, appliance_code, info, bucket
                            )
                        except Exception as e:
                            _LOGGER.error(f"初始化只读设备失败: {appliance_code}, error: {e}")

                    elif protocol == "v2_thing":
                        if not thing_login_ok:
                            _LOGGER.warning(f"跳过 Thing 设备 {info.get(CONF_NAME)}: API 登录失败")
                            continue
                        try:
                            await _init_thing_device(
                                hass, config_entry, cloud, thing_api,
                                appliance_code_str, str(home_id), info, bucket
                            )
                        except Exception as e:
                            _LOGGER.error(f"初始化 Thing 设备失败: {appliance_code}, error: {e}")

                    else:
                        _LOGGER.debug(
                            f"跳过不支持的设备: {info.get(CONF_NAME)} (type={appliance_type})"
                        )

            hass.data[DOMAIN]["accounts"][config_entry.entry_id] = bucket

    except Exception as e:
        _LOGGER.error(f"[美的慧选设备] 获取设备列表失败: {e}")

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def _init_read_only_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    cloud,
    appliance_code,
    info: dict,
    bucket: dict,
) -> None:
    """初始化透明协议只读设备（如 T0xBC 空气检测仪）。"""
    _LOGGER.info(f"发现只读设备: {info.get(CONF_NAME)}")

    # 下载设备插件
    try:
        plugin_path = hass.config.path(STORAGE_PLUGIN_PATH)
        await cloud.download_plugin(
            path=plugin_path,
            appliance_code=appliance_code,
            smart_product_id=info.get(CONF_SMART_PRODUCT_ID),
            device_type=info.get(CONF_TYPE),
            sn=info.get(CONF_SN),
            sn8=info.get(CONF_SN8),
            model_number=info.get(CONF_MODEL_NUMBER),
            manufacturer_code=info.get(CONF_MANUFACTURER_CODE),
        )
    except Exception as e:
        _LOGGER.warning(f"[美的慧选设备] 下载插件失败 {info.get(CONF_NAME)}: {e}")

    # 创建设备实例
    device = MiedaDevice(
        name=info.get(CONF_NAME),
        device_id=appliance_code,
        device_type=info.get(CONF_TYPE),
        model=info.get(CONF_MODEL),
        subtype=info.get(CONF_MODEL_NUMBER),
        manufacturer_code=info.get(CONF_MANUFACTURER_CODE),
        category=info.get(CONF_CATEGORY),
        connected=info.get("online"),
        sn=info.get(CONF_SN),
        sn8=info.get(CONF_SN8),
        cloud=cloud,
    )

    # 从映射文件加载查询参数和计算规则
    try:
        mapping = await asyncio.to_thread(
            load_mapping,
            info.get(CONF_TYPE),
            info.get(CONF_SN8) or "",
            info.get(CONF_MODEL_NUMBER),
            info.get(CONF_CATEGORY),
        )
        device.set_queries(mapping.get("queries", [{}]))
        device.set_calculate(mapping.get("calculate"))
    except Exception:
        pass

    # 创建协调器并首次刷新
    coordinator = MideaDataUpdateCoordinator(hass, config_entry, device, cloud=cloud)
    hass.async_create_task(coordinator.async_config_entry_first_refresh())
    bucket["device_list"][appliance_code] = info
    bucket["coordinator_map"][appliance_code] = coordinator


async def _init_thing_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    cloud,
    thing_api: MideaV2ThingApi,
    appliance_code_str: str,
    home_group_id: str,
    info: dict,
    bucket: dict,
) -> None:
    """初始化 Thing Model V2 通用设备。"""
    device_name = info.get(CONF_NAME, f"Midea {appliance_code_str}")
    _LOGGER.info(f"[美的慧选设备] 发现 Thing 设备: {device_name} ({appliance_code_str})")

    # 读取用户配置的轮询间隔
    scan_interval = config_entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL)

    # 获取设备类型以加载对应的设备专用端点
    device_type = info.get(CONF_TYPE) or info.get("type")
    try:
        device_type_int = int(device_type) if device_type is not None else None
    except Exception:
        device_type_int = None

    specific_endpoints: dict = {}
    if device_type_int is not None:
        specific_endpoints = await asyncio.to_thread(get_specific_endpoints, device_type_int)

    # 创建协调器
    coordinator = MideaThingDataCoordinator(
        hass, thing_api, cloud,
        appliance_code_str, home_group_id, scan_interval,
        specific_endpoints=specific_endpoints,
    )
    coordinator._device_info = info

    await coordinator.async_config_entry_first_refresh()

    bucket["thing_coordinators"][appliance_code_str] = coordinator
    bucket["device_list"][appliance_code_str] = info
    bucket["coordinator_map"][appliance_code_str] = coordinator


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """卸载配置入口。"""
    device_type = config_entry.data.get(CONF_TYPE)
    if device_type == CONF_ACCOUNT:
        unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
        if unload_ok:
            try:
                hass.data.get(DOMAIN, {}).get("accounts", {}).pop(config_entry.entry_id, None)
            except Exception:
                pass
        return unload_ok
    return True

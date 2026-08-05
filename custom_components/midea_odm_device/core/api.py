"""美的慧选设备 API 客户端模块。

V2 Thing Model 通用 API 客户端（属性查询/设置/设备专用端点）。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


class MideaV2ThingApi:
    """V2 Thing Model API 客户端，复用美居云登录态和签名能力。"""

    def __init__(self, cloud) -> None:
        self._cloud = cloud

    async def query_properties(self, appliance_code: str | int) -> dict | None:
        """查询设备全部 Thing 属性。"""
        return await self._cloud.query_thing_properties(int(appliance_code))

    async def set_property(
        self, appliance_code: str | int, prop_key: str, prop_value: Any
    ) -> bool:
        """设置单个 Thing 属性。"""
        return await self._cloud.set_thing_properties(
            int(appliance_code), {prop_key: prop_value}
        )

    async def fetch_rest_data(
        self,
        appliance_code: str | int,
        home_group_id: str,
        specific_endpoints: dict,
        quick_keys: list[str] | None = None,
    ) -> dict:
        """并发请求设备专用端点，返回 section -> data 映射。"""
        base_data = {
            "applianceCode": str(appliance_code),
            "homegroupId": str(home_group_id),
        }

        endpoints = specific_endpoints
        if quick_keys:
            endpoints = {k: specific_endpoints[k] for k in quick_keys if k in specific_endpoints}

        async def _fetch_one(key: str, endpoint: str) -> tuple[str, Any]:
            try:
                resp = await self._cloud._api_request(endpoint, base_data)
                return key, resp
            except Exception as e:
                _LOGGER.debug(f"设备专用端点 {key} 请求失败: {e}")
                return key, None

        tasks = [_fetch_one(key, endpoint) for key, endpoint in endpoints.items()]
        results_list = await asyncio.gather(*tasks, return_exceptions=False)
        return dict(results_list)

"""美的云模块。

提供美的美居云的登录、设备列表获取、设备状态查询、
Thing Model V2 属性/Action 调用等能力。
"""
import logging
import time
import datetime
import json
import traceback
import os
import uuid
import aiofiles
from aiohttp import ClientSession
from secrets import token_hex
from .security import CloudSecurity, MeijuCloudSecurity

_LOGGER = logging.getLogger(__name__)

# 美居云密钥配置
_MEIJU_APP_KEY = "46579c15"
_MEIJU_LOGIN_KEY = "ad0ee21d48a64bf49f4fb583ab76e799"
_MEIJU_IOT_KEY = bytes.fromhex(format(9795516279659324117647275084689641883661667, 'x')).decode()
_MEIJU_HMAC_KEY = bytes.fromhex(format(117390035944627627450677220413733956185864939010425, 'x')).decode()
_MEIJU_API_URL = "https://mp-prod.smartmidea.net/mas/v5/app/proxy?alias="

class MideaCloud:
    """美的云基类，提供通用请求能力。"""

    def __init__(
            self,
            session: ClientSession,
            security: CloudSecurity,
            app_key: str,
            account: str,
            password: str,
            api_url: str,
            proxy: str | None = None
    ):
        self._device_id = CloudSecurity.get_deviceid(account)
        self._session = session
        self._security = security
        self._app_key = app_key
        self._account = account
        self._password = password
        self._api_url = api_url
        self._proxy = proxy
        self._access_token = None
        self._login_id = None
        self._uid = None
        self._token_invalid_retry_count = 0

    def _make_general_data(self):
        return {}

    @property
    def nickname(self):
        if not hasattr(self, "_nickname"):
            self._nickname = self._account
        return self._nickname

    @staticmethod
    def _is_token_invalid_response(response: dict) -> bool:
        """检查响应是否表示 token 失效。"""
        try:
            code = int(response.get("code", -1))
        except Exception:
            code = -1
        if code == 40002:
            return True
        msg = str(response.get("msg") or response.get("message") or "")
        msg_lower = msg.lower()
        return (
            "user token not exist" in msg_lower
            or ("token" in msg_lower and "not exist" in msg_lower)
            or "token校验不通过" in msg
        )

    async def _api_request(
        self,
        endpoint: str,
        data: dict,
        header=None,
        method="POST",
        _retried_after_login: bool = False,
        print_log: bool = False,
    ) -> dict | None:
        """通用 API 请求方法（带签名和 token 自动重试）。"""
        header = header or {}
        if not data.get("reqId"):
            data.update({"reqId": token_hex(16)})
        if not data.get("stamp"):
            data.update({"stamp": datetime.datetime.now().strftime("%Y%m%d%H%M%S")})
        random = str(int(time.time()))
        url = self._api_url + endpoint
        dump_data = json.dumps(data)
        sign = self._security.sign(dump_data, random)
        header.update({
            "content-type": "application/json; charset=utf-8",
            "secretVersion": "1",
            "sign": sign,
            "random": random,
        })
        if self._access_token is not None:
            header.update({"accesstoken": self._access_token})
        response: dict = {"code": -1}
        try:
            r = await self._session.request(
                method, url, headers=header, data=dump_data, timeout=30, proxy=self._proxy
            )
            raw = await r.read()
            _LOGGER.debug(f"美的云 API: {url}, header: {header}, data: {data}, response: {raw}")
            response = json.loads(raw)
        except Exception:
            traceback.print_exc()

        if int(response["code"]) == 0:
            if _retried_after_login:
                self._token_invalid_retry_count = 0
            if "data" in response:
                return response["data"]
            else:
                return {"message": "ok"}

        # token 失效时自动重新登录重试
        if (
            not _retried_after_login
            and isinstance(response, dict)
            and self._is_token_invalid_response(response)
        ):
            if self._token_invalid_retry_count >= 3:
                _LOGGER.warning(
                    "美的云 token 失效重试次数过多，已跳过。"
                    f"endpoint={endpoint}, retry_count={self._token_invalid_retry_count}"
                )
                return None
            self._token_invalid_retry_count += 1
            _LOGGER.warning(f"美的云 token 失效，准备重新登录重试。endpoint={endpoint}")
            self._access_token = None
            try:
                if await self.login():
                    return await self._api_request(
                        endpoint=endpoint, data=data, header=header, method=method,
                        _retried_after_login=True, print_log=print_log,
                    )
            except Exception:
                traceback.print_exc()
        return None

    async def _get_login_id(self) -> str | None:
        """获取登录 ID。"""
        data = self._make_general_data()
        data.update({"loginAccount": f"{self._account}", "type": "1"})
        if response := await self._api_request(endpoint="/v1/user/login/id/get", data=data):
            return response.get("loginId")
        return None

    async def login(self) -> bool:
        """登录美的云（子类实现）。"""
        raise NotImplementedError()

    async def list_home(self) -> dict | None:
        """获取家庭列表。"""
        return {1: "My home"}

    async def list_appliances(self, home_id) -> dict | None:
        """获取设备列表。"""
        raise NotImplementedError()

    async def download_plugin(
            self, path: str,
            appliance_code: str,
            smart_product_id: str,
            device_type: int,
            sn: str,
            sn8: str,
            model_number: str | None,
            manufacturer_code: str = "0000",
    ):
        """下载设备插件。"""
        raise NotImplementedError()

class MeijuCloud(MideaCloud):
    """美的美居云实现。"""

    APP_ID = "900"
    APP_VERSION = "8.20.0.2"

    def __init__(
            self,
            session: ClientSession,
            account: str,
            password: str,
            proxy: str | None = None,
    ):
        super().__init__(
            session=session,
            security=MeijuCloudSecurity(
                login_key=_MEIJU_LOGIN_KEY,
                iot_key=_MEIJU_IOT_KEY,
                hmac_key=_MEIJU_HMAC_KEY,
            ),
            app_key=_MEIJU_APP_KEY,
            account=account,
            password=password,
            api_url=_MEIJU_API_URL,
            proxy=proxy
        )
        self._homegroup_id = None

    async def login(self) -> bool:
        """登录美的美居云。"""
        if login_id := await self._get_login_id():
            self._login_id = login_id
            stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            data = {
                "iotData": {
                    "clientType": 1,
                    "deviceId": self._device_id,
                    "iampwd": self._security.encrypt_iam_password(self._login_id, self._password),
                    "iotAppId": self.APP_ID,
                    "loginAccount": self._account,
                    "password": self._security.encrypt_password(self._login_id, self._password),
                    "reqId": token_hex(16),
                    "stamp": stamp
                },
                "data": {
                    "appKey": self._app_key,
                    "deviceId": self._device_id,
                    "platform": 2
                },
                "timestamp": stamp,
                "stamp": stamp
            }
            if response := await self._api_request(endpoint="/mj/user/login", data=data):
                self._access_token = response["mdata"]["accessToken"]
                self._uid = str(response.get("uid", "") or response["mdata"].get("uid", ""))
                self._security.set_aes_keys(
                    self._security.aes_decrypt_with_fixed_key(response["key"]), None
                )
                if "userInfo" in response and "nickName" in response["userInfo"]:
                    self._nickname = response["userInfo"]["nickName"]
                else:
                    self._nickname = self._account
                return True
        return False

    async def list_home(self):
        """获取家庭列表。"""
        if response := await self._api_request(endpoint="/v1/homegroup/list/get", data={}):
            homes = {}
            for home in response["homeList"]:
                homes.update({int(home["homegroupId"]): home["name"]})
            return homes
        return None

    async def list_appliances(self, home_id) -> dict | None:
        """获取设备列表。"""
        self._homegroup_id = str(home_id)
        data = {"homegroupId": home_id}
        if response := await self._api_request(endpoint="/v1/appliance/home/list/get", data=data):
            appliances = {}
            for home in response.get("homeList") or []:
                for room in home.get("roomList") or []:
                    for appliance in room.get("applianceList"):
                        device_info = {
                            "name": appliance.get("name"),
                            "type": int(appliance.get("type"), 16),
                            "sn": self._security.aes_decrypt(appliance.get("sn")) if appliance.get("sn") else "",
                            "sn8": appliance.get("sn8", "00000000"),
                            "category": appliance.get("category"),
                            "smart_product_id": appliance.get("smartProductId", "0"),
                            "model_number": appliance.get("modelNumber", "0"),
                            "manufacturer_code": appliance.get("enterpriseCode", "0000"),
                            "model": appliance.get("productModel"),
                            "online": appliance.get("onlineStatus") == "1",
                        }
                        if device_info.get("sn8") is None or len(device_info.get("sn8")) == 0:
                            device_info["sn8"] = "00000000"
                        if device_info.get("model") is None or len(device_info.get("model")) == 0:
                            device_info["model"] = device_info["sn8"]
                        appliances[int(appliance["applianceCode"])] = device_info
            return appliances
        return None

    async def get_device_status(self, appliance_code: int, query: dict) -> dict | None:
        """通过云端 Lua 接口查询设备状态（T0xBC 等）。"""
        data = {
            "applianceCode": str(appliance_code),
            "command": {"query": query}
        }
        if response := await self._api_request(endpoint="/mjl/v1/device/status/lua/get", data=data):
            return response
        return None

    @staticmethod
    def _thing_headers() -> dict:
        """Thing Model API 专用请求头。"""
        return {
            "caller": "900",
            "call-source": "mideaApp",
            "call-module": "appPlugin",
        }

    @staticmethod
    def _thing_endpoint(alias: str) -> str:
        """构造 Thing Model API 端点（带 requestId 和 sync 参数）。"""
        return f"{alias}?requestId={uuid.uuid4().hex}&sync=true"

    async def _thing_api_request(
        self,
        endpoint: str,
        data: dict | list | None,
        header: dict | None = None,
        method: str = "GET",
        _retried_after_login: bool = False,
    ) -> dict | None:
        """Thing Model API 专用请求方法（不添加 reqId/stamp 到 body）。"""
        header = header or {}
        random_str = str(int(time.time()))
        url = self._api_url + endpoint

        if data is not None:
            dump_data = json.dumps(data)
        else:
            dump_data = ""

        sign = self._security.sign(dump_data, random_str)
        header.update({
            "content-type": "application/json; charset=utf-8",
            "secretVersion": "1",
            "sign": sign,
            "random": random_str,
        })
        if self._access_token is not None:
            header.update({"accesstoken": self._access_token})

        response: dict = {"code": -1}
        try:
            r = await self._session.request(
                method, url, headers=header,
                data=dump_data if data is not None else None,
                timeout=30, proxy=self._proxy,
            )
            raw = await r.read()
            _LOGGER.debug(f"Thing Model API: {url}, method={method}, data={data}, response={raw}")
            response = json.loads(raw)
        except Exception:
            traceback.print_exc()

        try:
            code = int(response.get("code", -1))
        except Exception:
            code = -1

        if code == 0:
            if _retried_after_login:
                self._token_invalid_retry_count = 0
            return response

        # token 失效时自动重新登录重试
        if (
            not _retried_after_login
            and isinstance(response, dict)
            and self._is_token_invalid_response(response)
        ):
            if self._token_invalid_retry_count >= 3:
                return None
            self._token_invalid_retry_count += 1
            _LOGGER.warning(f"Thing Model token 失效，准备重新登录。endpoint={endpoint}")
            self._access_token = None
            try:
                if await self.login():
                    return await self._thing_api_request(
                        endpoint=endpoint, data=data, header=header, method=method,
                        _retried_after_login=True,
                    )
            except Exception:
                traceback.print_exc()
        return None

    async def query_thing_properties(
        self, appliance_code: int, properties: list | None = None,
    ) -> dict | None:
        """查询设备 Thing 属性（GET 查全部，POST 查指定）。"""
        endpoint = self._thing_endpoint(f"/v1/thing/properties/{appliance_code}")
        method = "GET" if properties is None else "POST"
        response = await self._thing_api_request(
            endpoint=endpoint,
            data=None if properties is None else properties,
            header=self._thing_headers(),
            method=method,
        )
        if isinstance(response, dict):
            data = response.get("data")
            return data if isinstance(data, dict) else None
        return None

    async def set_thing_properties(self, appliance_code: int, properties: dict) -> bool:
        """设置设备 Thing 属性（PUT）。"""
        endpoint = self._thing_endpoint(f"/v1/thing/properties/{appliance_code}")
        response = await self._thing_api_request(
            endpoint=endpoint, data=properties,
            header=self._thing_headers(), method="PUT",
        )
        return isinstance(response, dict)

    async def perform_thing_action(
        self, appliance_code: int, module_code: str, action_code: str,
        body: dict | None = None,
    ) -> dict | None:
        """触发设备 Action（POST /v1/thing/action/{module}/{action}/{code}）。"""
        alias = f"/v1/thing/action/{module_code}/{action_code}/{appliance_code}"
        endpoint = self._thing_endpoint(alias)
        response = await self._thing_api_request(
            endpoint=endpoint, data=body or {},
            header=self._thing_headers(), method="POST",
        )
        return response

    async def download_plugin(
            self, path: str,
            appliance_code: str,
            smart_product_id: str,
            device_type: int,
            sn: str,
            sn8: str,
            model_number: str | None,
            manufacturer_code: str = "0000",
    ):
        """下载设备插件文件。"""
        appliance_info = {
            "appModel": sn8,
            "appEnterprise": manufacturer_code,
            "appType": f"0x{device_type:02X}",
            "applianceCode": str(appliance_code) if isinstance(appliance_code, int) else appliance_code,
            "smartProductId": str(smart_product_id) if isinstance(smart_product_id, int) else smart_product_id,
            "modelNumber": model_number or "0",
            "versionCode": 0
        }
        appliance_list = [appliance_info]
        data = {
            "applianceList": json.dumps(appliance_list),
            "iotAppId": self.APP_ID,
            "match": "1",
            "clientType": "1",
            "clientVersion": 201
        }
        fnm = None
        if response := await self._api_request(endpoint="/v1/plugin/update/getPluginV3", data=data):
            plugin_list = response.get("list", [])
            if not plugin_list:
                _LOGGER.warning(f"未找到设备类型 0x{device_type:02X} 的插件, sn: {sn}")
                return None

            # 优先匹配 sn 和设备类型
            matched_plugin = None
            for plugin in plugin_list:
                if plugin.get("applianceCode") == sn and plugin.get("appType") == f"0x{device_type:02X}":
                    matched_plugin = plugin
                    break

            # 其次只匹配设备类型
            if not matched_plugin:
                for plugin in plugin_list:
                    if plugin.get("appType") == f"0x{device_type:02X}":
                        matched_plugin = plugin
                        break

            if not matched_plugin:
                _LOGGER.warning(f"未找到匹配的插件，设备类型 0x{device_type:02X}, sn: {sn}")
                return None

            zip_url = matched_plugin.get("url")
            zip_title = matched_plugin.get("title", f"plugin_0x{device_type:02X}.zip")

            if not zip_url:
                _LOGGER.warning(f"插件无下载 URL: {zip_title}")
                return None

            fnm = f"{path}/{zip_title}"
            # 文件已存在则跳过下载
            if os.path.exists(fnm):
                _LOGGER.debug(f"插件文件已存在: {fnm}")
                return fnm

            try:
                os.makedirs(path, exist_ok=True)
                res = await self._session.get(zip_url)
                if res.status == 200:
                    zip_data = await res.read()
                    if zip_data:
                        async with aiofiles.open(fnm, "wb") as fp:
                            await fp.write(zip_data)
                        _LOGGER.info(f"插件下载完成: {fnm}")
                    else:
                        _LOGGER.warning(f"下载的插件文件为空: {zip_url}")
                else:
                    _LOGGER.warning(f"插件下载失败，状态码: {res.status}, url: {zip_url}")
            except Exception as e:
                _LOGGER.error(f"下载插件异常: {e}")
                traceback.print_exc()
        return fnm

def get_midea_cloud(session: ClientSession, account: str, password: str, proxy: str | None = None) -> MideaCloud | None:
    """创建美的美居云实例。"""
    return MeijuCloud(
        session=session,
        account=account,
        password=password,
        proxy=proxy
    )

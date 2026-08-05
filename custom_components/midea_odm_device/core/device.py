"""美的透明协议设备抽象（仅轮询版本）。

T0xBC 等设备只需定期轮询云端 API 获取传感器数据，
不需要任何控制能力。
"""
import logging

from .cloud import MideaCloud

_LOGGER = logging.getLogger(__name__)


class MiedaDevice:
    """美的设备（仅轮询，无控制能力）。"""

    def __init__(
        self,
        name: str,
        device_id: int,
        device_type: int,
        model: str | None,
        subtype: int | None,
        manufacturer_code: str | None,
        category: str | None,
        connected: bool,
        sn: str | None,
        sn8: str | None,
        cloud: MideaCloud | None,
    ):
        self._device_name = name
        self._device_id = device_id
        self._device_type = device_type
        self._model = model
        self._subtype = subtype
        self._sn = sn
        self._sn8 = sn8
        self._manufacturer_code = manufacturer_code
        self._category = category
        self._cloud = cloud
        self._connected = connected
        self._attributes: dict = {}
        self._updates: list = []
        self._queries: list = [{}]
        self._calculate: dict = {}

    @property
    def device_name(self): return self._device_name
    @property
    def device_id(self): return self._device_id
    @property
    def device_type(self): return self._device_type
    @property
    def model(self): return self._model
    @property
    def sn(self): return self._sn
    @property
    def sn8(self): return self._sn8
    @property
    def subtype(self): return self._subtype
    @property
    def category(self): return self._category
    @property
    def attributes(self): return self._attributes
    @property
    def connected(self): return self._connected

    def set_queries(self, queries: list):
        """设置查询参数列表（由映射文件加载）。"""
        self._queries = queries or [{}]

    def set_calculate(self, calculate: dict | None):
        """设置派生属性计算规则（由映射文件加载）。"""
        self._calculate = calculate or {}

    def _device_connected(self, connected: bool = True) -> None:
        """更新设备在线状态。"""
        self._connected = connected
        if connected:
            _LOGGER.debug(f"设备 {self._device_id} 已上线")
        else:
            _LOGGER.warning(f"设备 {self._device_id} 已离线")
        self._update_all({"connected": connected})

    async def refresh_status(self) -> bool:
        """通过云端 Lua 接口拉取设备属性，更新本地缓存。"""
        success = False
        for query in self._queries:
            actual_query = query.copy() if isinstance(query, dict) else query
            try:
                if status := await self._cloud.get_device_status(
                    appliance_code=self._device_id,
                    query=actual_query,
                ):
                    self._apply_status(status)
                    success = True
            except Exception as e:
                _LOGGER.warning(f"获取设备 {self._device_id} 状态失败: {e}")

        if success != self._connected:
            self._device_connected(success)
        return success

    def _apply_status(self, status: dict) -> None:
        """合并云端返回属性到本地缓存，执行派生计算，通知监听者。"""
        new_status: dict = {}
        for key, value in status.items():
            if self._attributes.get(key) != value:
                self._attributes[key] = value
                new_status[key] = value

        if new_status and self._calculate:
            self._run_calculate(new_status)

        if new_status:
            self._update_all(new_status)

    def _run_calculate(self, new_status: dict) -> None:
        """执行 calculate.get 派生属性计算。

        规则格式: {"lvalue": "[attr_name]", "rvalue": "float([temperature]) / 10"}
        将 rvalue 表达式中 [xxx] 替换为实际属性值后 eval 计算。
        """
        for rule in self._calculate.get("get", []):
            lvalue = rule.get("lvalue", "")
            rvalue_expr = rule.get("rvalue", "")
            if not lvalue or not rvalue_expr:
                continue
            attr_key = lvalue.strip("[]")
            try:
                import re
                refs = re.findall(r"\[([^\]]+)\]", rvalue_expr)
                expr = rvalue_expr
                for ref in refs:
                    val = self._attributes.get(ref)
                    expr = expr.replace(f"[{ref}]", repr(val))
                result = eval(expr)
                self._attributes[attr_key] = result
                new_status[attr_key] = result
            except Exception as e:
                _LOGGER.warning(f"派生计算规则 {attr_key} 执行失败: {e}")

    def register_update(self, update) -> None:
        """注册状态更新回调函数。"""
        self._updates.append(update)

    def _update_all(self, status: dict) -> None:
        """通知所有注册的回调函数。"""
        for update in self._updates:
            try:
                update(status)
            except Exception as e:
                _LOGGER.warning(f"更新回调异常: {e}")

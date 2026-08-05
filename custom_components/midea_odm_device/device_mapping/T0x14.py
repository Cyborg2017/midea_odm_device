"""T0x14 电动窗帘设备映射定义"""
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.const import Platform

DEVICE_MAPPING = {
    "default": {
        "manufacturer": "Midea",
        "model": "Smart Curtain",
        "rationale": ["off", "on"],
        "entities": {
            Platform.COVER: {
                "electricCurtain": {
                    "translation_key": "curtain",
                    "position_key": "electricCurtain.currentOpeningPercentage",
                    "target_position_key": "electricCurtain.targetOpeningPercentage",
                    "module_code": "electricCurtain",
                    "actions": {
                        "open": "open",
                        "close": "close",
                        "stop": "pause",
                    },
                    "device_class": CoverDeviceClass.CURTAIN,
                    "icon": "mdi:curtains",
                }
            },
            Platform.SWITCH: {
                "electricCurtain.motorReverse": {
                    "translation_key": "motor_reverse",
                    "thing_key": "electricCurtain.motorReverse",
                    "icon": "mdi:swap-horizontal",
                },
                "electricCurtain.manualPullMode": {
                    "translation_key": "manual_pull_mode",
                    "thing_key": "electricCurtain.manualPullMode",
                    "icon": "mdi:hand-back-right",
                },
            },
            Platform.SELECT: {
                "electricCurtain.motorSpeed": {
                    "translation_key": "motor_speed",
                    "thing_key": "electricCurtain.motorSpeed",
                    "options": [1, 2, 3],
                    "options_translation_keys": [
                        "motor_speed_silent",
                        "motor_speed_medium",
                        "motor_speed_fast"
                    ],
                    "icon": "mdi:speedometer",
                }
            },
        }
    }
}

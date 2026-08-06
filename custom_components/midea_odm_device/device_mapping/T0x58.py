"""T0x58 智能鱼缸设备映射定义"""
from homeassistant.const import Platform, UnitOfTime, UnitOfTemperature, PERCENTAGE
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

DEVICE_SPECIFIC_ENDPOINTS = {
    "dashboard": "/v1/fish-tank/feeding-records/dashboard",
    "filter_materials": "/v1/fish-tank/filter-materials/list"
}

DEVICE_MAPPING = {
    "default": {
        "manufacturer": "Midea",
        "model": "Smart Fish Tank",
        "rationale": ["off", "on"],
        "specific_endpoints": DEVICE_SPECIFIC_ENDPOINTS,
        "entities": {
            Platform.SENSOR: {
                "fishTank.currentWaterTemperature": {
                    "translation_key": "current_water_temperature",
                    "thing_key": "fishTank.currentWaterTemperature",
                    "device_class": SensorDeviceClass.TEMPERATURE,
                    "state_class": SensorStateClass.MEASUREMENT,
                    "unit": UnitOfTemperature.CELSIUS,
                    "icon": "mdi:thermometer"
                },
                "today_feed_count": {
                    "translation_key": "today_feed_count",
                    "section": "dashboard",
                    "field": "todayFeedPortionCount",
                    "state_class": SensorStateClass.MEASUREMENT,
                    "icon": "mdi:food-apple-outline"
                },
                "filter_remaining_days_slot1": {
                    "translation_key": "filter_remaining_days_slot1",
                    "section": "filter_materials",
                    "field": "remainingDays",
                    "list_match": {"slot": 1},
                    "state_class": SensorStateClass.MEASUREMENT,
                    "unit": UnitOfTime.DAYS,
                    "icon": "mdi:calendar-clock"
                },
                "filter_remaining_percent_slot1": {
                    "translation_key": "filter_remaining_percent_slot1",
                    "section": "filter_materials",
                    "field": "remainingPercent",
                    "list_match": {"slot": 1},
                    "state_class": SensorStateClass.MEASUREMENT,
                    "unit": PERCENTAGE,
                    "icon": "mdi:percent"
                },
                "filter_remaining_days_slot2": {
                    "translation_key": "filter_remaining_days_slot2",
                    "section": "filter_materials",
                    "field": "remainingDays",
                    "list_match": {"slot": 2},
                    "state_class": SensorStateClass.MEASUREMENT,
                    "unit": UnitOfTime.DAYS,
                    "icon": "mdi:calendar-clock"
                },
                "filter_remaining_percent_slot2": {
                    "translation_key": "filter_remaining_percent_slot2",
                    "section": "filter_materials",
                    "field": "remainingPercent",
                    "list_match": {"slot": 2},
                    "state_class": SensorStateClass.MEASUREMENT,
                    "unit": PERCENTAGE,
                    "icon": "mdi:percent"
                },
                "filter_install_time_slot1": {
                    "translation_key": "filter_install_time_slot1",
                    "section": "filter_materials",
                    "field": "lastReplacementTime",
                    "list_match": {"slot": 1},
                    "icon": "mdi:calendar-check"
                },
                "filter_install_time_slot2": {
                    "translation_key": "filter_install_time_slot2",
                    "section": "filter_materials",
                    "field": "lastReplacementTime",
                    "list_match": {"slot": 2},
                    "icon": "mdi:calendar-check"
                }
            },
            Platform.BINARY_SENSOR: {
                "fishTank.waterTemperatureState": {
                    "translation_key": "water_temperature_state",
                    "thing_key": "fishTank.waterTemperatureState",
                    "device_class": BinarySensorDeviceClass.PROBLEM,
                    "icon": "mdi:thermometer-alert"
                }
            },
            Platform.SWITCH: {
                "fishTank.power": {
                    "translation_key": "power",
                    "thing_key": "fishTank.power",
                    "icon": "mdi:power-plug"
                },
                "fishTank.waterPumpSwitch": {
                    "translation_key": "water_pump_switch",
                    "thing_key": "fishTank.waterPumpSwitch",
                    "icon": "mdi:water-pump"
                },
                "fishTank.feedProtectionSwitch": {
                    "translation_key": "feed_protection_switch",
                    "thing_key": "fishTank.feedProtectionSwitch",
                    "icon": "mdi:hand-back-right-outline"
                },
                "fishTank.indicatorLightSwitch": {
                    "translation_key": "indicator_light_switch",
                    "thing_key": "fishTank.indicatorLightSwitch",
                    "icon": "mdi:led-on"
                },
                "fishTank.silentSwitch": {
                    "translation_key": "silent_switch",
                    "thing_key": "fishTank.silentSwitch",
                    "icon": "mdi:volume-mute"
                },
                "fishTank.waterPumpDisconnectAlertSwitch": {
                    "translation_key": "water_pump_disconnect_alert_switch",
                    "thing_key": "fishTank.waterPumpDisconnectAlertSwitch",
                    "icon": "mdi:water-alert"
                },
                "childLock.childLockSwitch": {
                    "translation_key": "child_lock_switch",
                    "thing_key": "childLock.childLockSwitch",
                    "icon": "mdi:lock"
                }
            },
            Platform.NUMBER: {
                "petFeeder.feedCycle": {
                    "translation_key": "feed_cycle",
                    "thing_key": "petFeeder.feedCycle",
                    "unit": "h",
                    "min": 24,
                    "max": 72,
                    "step": 1,
                    "icon": "mdi:timer-sand"
                },
                "fishTank.waterTemperatureRangeSet.minimumTemperature": {
                    "translation_key": "water_temperature_min",
                    "thing_key": "fishTank.waterTemperatureRangeSet",
                    "field": "minimumTemperature",
                    "unit": "°C",
                    "min": 0,
                    "max": 40,
                    "step": 1,
                    "icon": "mdi:thermometer-minus"
                },
                "fishTank.waterTemperatureRangeSet.maximumTemperature": {
                    "translation_key": "water_temperature_max",
                    "thing_key": "fishTank.waterTemperatureRangeSet",
                    "field": "maximumTemperature",
                    "unit": "°C",
                    "min": 0,
                    "max": 40,
                    "step": 1,
                    "icon": "mdi:thermometer-plus"
                }
            },
            Platform.TIME: {
                "fishTank.silentTimeConfig.startTime": {
                    "translation_key": "silent_start_time",
                    "thing_key": "fishTank.silentTimeConfig",
                    "field": "startTime",
                    "value_format": "minutes",
                    "icon": "mdi:clock-start"
                },
                "fishTank.silentTimeConfig.endTime": {
                    "translation_key": "silent_end_time",
                    "thing_key": "fishTank.silentTimeConfig",
                    "field": "endTime",
                    "value_format": "minutes",
                    "icon": "mdi:clock-end"
                }
            },
            Platform.SELECT: {
                "fishTank.waterPumpDisconnectDelayTime": {
                    "translation_key": "water_pump_disconnect_delay_time",
                    "thing_key": "fishTank.waterPumpDisconnectDelayTime",
                    "options": [10, 30, 60, 300],
                    "options_translation_keys": [
                        "delay_10s",
                        "delay_30s",
                        "delay_1min",
                        "delay_5min"
                    ],
                    "icon": "mdi:timer-alert-outline"
                },
                "fishTank.waterPumpPauseTime": {
                    "translation_key": "water_pump_pause_time",
                    "thing_key": "fishTank.waterPumpPauseTime",
                    "options": [180, 300, 600, 900],
                    "options_translation_keys": [
                        "pause_3min",
                        "pause_5min",
                        "pause_10min",
                        "pause_15min"
                    ],
                    "icon": "mdi:timer-pause-outline"
                }
            },
            Platform.LIGHT: {
                "light": {
                    "translation_key": "light",
                    "power_key": "light.power",
                    "brightness_key": "light.brightness",
                    "effect_key": "light.currentExecutionSence",
                    "scenes": [0, 1, 2, 3, 4, 5],
                    "scenes_translation_keys": [
                        "light_scene_0",
                        "light_scene_1",
                        "light_scene_2",
                        "light_scene_3",
                        "light_scene_4",
                        "light_scene_5"
                    ],
                    "icon": "mdi:lightbulb"
                }
            },
            Platform.BUTTON: {
                "petFeeder.manualFeed": {
                    "translation_key": "manual_feed",
                    "module_code": "petFeeder",
                    "action_code": "manualFeed",
                    "body": {"feedPortion": 1},
                    "icon": "mdi:food-apple-outline"
                }
            }
        }
    }
}

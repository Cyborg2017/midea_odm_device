"""T0xBC 空气检测仪设备映射定义"""
from homeassistant.const import Platform, CONCENTRATION_PARTS_PER_MILLION, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, UnitOfTemperature
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass

# Only devices with these SN8 codes are supported
SUPPORTED_SN8 = {"ECGDN1MD"}

DEVICE_MAPPING = {
    "default": {
        "manufacturer": "Midea",
        "rationale": ["off", "on"],
        "queries": [{}],
        "calculate": {
            "get": [
                {
                    "lvalue": "[indoor_temperature]",
                    "rvalue": "float([temperature]) / 10"
                }
            ]
        },
        "centralized": [],
        "entities": {
            Platform.SENSOR: {
                "indoor_temperature": {
                    "translation_key": "indoor_temperature",
                    "device_class": SensorDeviceClass.TEMPERATURE,
                    "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    "state_class": SensorStateClass.MEASUREMENT
                },
                "humidity": {
                    "translation_key": "humidity",
                    "device_class": SensorDeviceClass.HUMIDITY,
                    "unit_of_measurement": "%",
                    "state_class": SensorStateClass.MEASUREMENT
                },
                "co2_value": {
                    "translation_key": "co2_value",
                    "device_class": SensorDeviceClass.CO2,
                    "unit_of_measurement": CONCENTRATION_PARTS_PER_MILLION,
                    "state_class": SensorStateClass.MEASUREMENT,
                    "attribute": "co2"
                },
                "pm10_value": {
                    "translation_key": "pm10_value",
                    "device_class": SensorDeviceClass.PM10,
                    "unit_of_measurement": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                    "state_class": SensorStateClass.MEASUREMENT,
                    "attribute": "pm10"
                },
                "pm25_value": {
                    "translation_key": "pm25_value",
                    "device_class": SensorDeviceClass.PM25,
                    "unit_of_measurement": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                    "state_class": SensorStateClass.MEASUREMENT,
                    "attribute": "pm25"
                },
                "voltage": {
                    "translation_key": "battery_level",
                    "device_class": SensorDeviceClass.BATTERY,
                    "unit_of_measurement": "%",
                    "state_class": SensorStateClass.MEASUREMENT
                }
            }
        }
    }
}

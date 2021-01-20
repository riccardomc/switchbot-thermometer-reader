import asyncio
import json

from bleak import BleakScanner

addresses = ["XX:XX:XX:XX:XX:XX"]
service_data_id = "00000d00-0000-1000-8000-00805f9b34fb"

devices_data = {}


def decode(data):
    """
    https://github.com/OpenWonderLabs/python-host/wiki/Meter-BLE-open-API
    """
    temperature_value = (data[4] & 0b00111111) + (data[3] & 0b00001111) / 10
    temperature_sign = -1 if data[4] & 0b10000000 == 0 else 1
    temperature_scale = "C" if data[5] & 0b10000000 == 0 else "F"
    temperature_value = (
        temperature_value * 1.8 + 32 if temperature_scale == "F" else temperature_value
    )
    humidity_value = data[5] & 0b01111111
    battery_value = data[2] & 0b01111111

    temperature_alert = (data[3] & 0b11000000) >> 6
    humidity_alert = (data[3] & 0b00110000) >> 4

    return {
        "alerts": {
            "temperature_alert": temperature_alert,
            "humidity_alert": humidity_alert,
        },
        "raw_values": {
            "battery_value": battery_value,
            "humidity_value": humidity_value,
            "temperature_scale": temperature_scale,
            "temperature_sign": temperature_sign,
            "temperature_value": temperature_value,
        },
        "human_readable": {
            "temperature": "%3.1f°%s"
            % (temperature_sign * temperature_value, temperature_scale),
            "humidity": "%d%%" % humidity_value,
            "battery": "%d%%" % battery_value,
        },
    }


def detection_callback(device, data):
    if device.address in addresses:
        service_data = data.service_data.get(service_data_id)
        if service_data:
            devices_data[device.address] = decode(service_data)


async def scan():
    scanner = BleakScanner()
    scanner.register_detection_callback(detection_callback)
    await scanner.start()
    while len(devices_data) != len(addresses):
        await asyncio.sleep(0.10)
    await scanner.stop()


async def main():
    try:
        await asyncio.wait_for(scan(), timeout=120.0)
        print(json.dumps(devices_data, indent=2))
    except asyncio.TimeoutError:
        print("got no devices")


asyncio.run(main())

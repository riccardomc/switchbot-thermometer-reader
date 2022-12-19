import asyncio
import json

from bleak import BleakScanner

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("switchbot")

addresses = set([])
service_data_id = "00000d00-0000-1000-8000-00805f9b34fb"

devices_data = {}


def decode(data):
    """
    https://github.com/OpenWonderLabs/python-host/wiki/Meter-BLE-open-API
    """
    temperature_value = (data[4] & 0b01111111) + (data[3] & 0b00001111) / 10
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
    service_data = data.service_data.get(service_data_id)
    if service_data:
        if device.address not in addresses:
            logger.info(f"found : {device.address} (new)")
            addresses.add(device.address)
        else:
            logger.info(f"found : {device.address}")
        decoded_service_data = decode(service_data)
        devices_data[device.address] = decoded_service_data


async def scan(scanner, sleep_interval=5):
    scanner.register_detection_callback(detection_callback)
    await scanner.start()
    await asyncio.sleep(sleep_interval)
    await scanner.stop()


async def main():
    while True:
        try:
            await asyncio.wait_for(scan(), timeout=10)
            print(json.dumps(devices_data, indent=2))
            await asyncio.sleep(5)
        except asyncio.TimeoutError:
            print("got no devices")

asyncio.run(main())

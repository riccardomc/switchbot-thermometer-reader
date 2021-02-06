import asyncio
import json

from bleak import BleakScanner
import paho.mqtt.client as mqtt

import traceback
from datetime import datetime

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("switchbot")

addresses = set([])
service_data_id = "00000d00-0000-1000-8000-00805f9b34fb"

devices_data = {}

# MQTT
mqtt_client = None
mqtt_username = ""
mqtt_password = ""
mqtt_hostname = ""
mqtt_hostport = 1883
mqtt_timeout = 30

# FIXME: MQTT implementation taken from:
# https://github.com/bbostock/Switchbot_Py_Meter/blob/master/meters.py
MQTT_TOPIC_STACK = {""}
MQTT_PAYLOAD_STACK = {""}


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
            logger.info("found device: %s" % device.address)
            addresses.add(device.address)
            discover(device.address)
        decoded_service_data = decode(service_data)
        publish(device.address, decoded_service_data)
        devices_data[device.address] = decoded_service_data


def mqtt_connect():
    global mqtt_client
    global mqtt_connected
    mqtt_client = mqtt.Client()
    mqtt_client.username_pw_set(mqtt_username, mqtt_password)

    def _on_connect(client, _, flags, return_code):
        global mqtt_connected
        mqtt_connected = True
        logger.info("MQTT connected: %s" % mqtt.connack_string(return_code))

    def _on_disconnect(client, userdata, return_code):
        if return_code != 0:
            logger.critical("MQTT Client disconnected with code: %d", return_code)

    def _on_publish(client, userdata, mid):
        pass

    def _on_log(mqttc, obj, level, string):
        logger.info("%s %s" % (level, string))

    mqtt_client.on_connect = _on_connect
    mqtt_client.on_publish = _on_publish
    mqtt_client.on_log = _on_log

    mqtt_client.connect(mqtt_hostname, mqtt_hostport, mqtt_timeout)
    mqtt_client.loop_start()


def discover(address):
    """
    https://www.home-assistant.io/docs/mqtt/discovery/
    """

    address_formatted = address.replace(":", "")
    # discovery_prefix>/<component>/[<node_id>/]<object_id>/config
    topic_temperature = "homeassistant/sensor/%s_T/config" % address_formatted

    message = {
        "device_class": "temperature",
        "name": "%s_T" % address_formatted,
        "state_topic": "homeassistant/sensor/%s_T/state" % address_formatted,
        "unit_of_measurement": "°C",
        "unique_id": "%s_T" % address_formatted,
        "value_template": "{{ value_json.raw_values.temperature_value }}",
    }

    mqtt_client.publish(topic_temperature, json.dumps(message), qos=0, retain=True)


def publish(address, data):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data["timestamp"] = timestamp
        message = json.dumps(data)
        address_formatted = address.replace(":", "")
        topic = "homeassistant/sensor/%s_T/state" % address_formatted
        MQTT_TOPIC_STACK.add(topic)
        MQTT_PAYLOAD_STACK.add(message)
        if mqtt_client:
            while len(MQTT_TOPIC_STACK) > 0:
                t = MQTT_TOPIC_STACK.pop()
                p = MQTT_PAYLOAD_STACK.pop()
                if len(t) > 0:
                    mqtt_client.publish(t, p, qos=0, retain=True)
        else:
            logger.warn("MQTT publish: can't send, no client")
    except Exception:
        logger.warn("MQTT publish: exception while sending")
        traceback.print_exc()


async def scan():
    mqtt_connect()
    scanner = BleakScanner()
    scanner.register_detection_callback(detection_callback)
    await scanner.start()
    while True:
        await asyncio.sleep(0.10)
    await scanner.stop()


async def main():
    try:
        await asyncio.wait_for(scan(), timeout=1200.0)
        print(json.dumps(devices_data, indent=2))
        await asyncio.sleep(5)
    except asyncio.TimeoutError:
        print("got no devices")

asyncio.run(main())

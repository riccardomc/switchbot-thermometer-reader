import asyncio
import json

from bleak import BleakScanner
import paho.mqtt.client as mqtt

import traceback
from datetime import datetime

addresses = ["XX:XX:XX:XX:XX:XX"]
service_data_id = "00000d00-0000-1000-8000-00805f9b34fb"

devices_data = {}

# MQTT
mqtt_client = None
mqtt_username = ""
mqtt_password = ""
mqtt_hostname = ""
mqtt_hostport = 1883
mqtt_timeout = 30

debug_level = 1

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
    if device.address in addresses:
        service_data = data.service_data.get(service_data_id)
        if service_data:
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
        if debug_level == 1:
            print(
                "on_connect: MQTT connection returned result: %s"
                % mqtt.connack_string(return_code)
            )

    def _on_disconnect(client, userdata, return_code):
        if return_code != 0:
            print("Unexpected disconnection: " + return_code)
        else:
            print("Disconnected.")

    def _on_publish(client, userdata, mid):
        if debug_level == 1:
            info = "on_publish: {}, {}, {}".format(client, userdata, str(mid))
            print(info)

    def _on_log(mqttc, obj, level, string):
        if debug_level == 1:
            print("on_log: " + string)

    mqtt_client.on_connect = _on_connect
    mqtt_client.on_publish = _on_publish
    mqtt_client.on_log = _on_log

    mqtt_client.connect(mqtt_hostname, mqtt_hostport, mqtt_timeout)
    mqtt_client.loop_start()


def publish(address, data):
    try:
        room = "baby"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data["timestamp"] = timestamp
        message = json.dumps(data)
        topic = "{}/{}".format(room.lower(), "meter")
        MQTT_TOPIC_STACK.add(topic)
        MQTT_PAYLOAD_STACK.add(message)
        if mqtt_client:
            while len(MQTT_TOPIC_STACK) > 0:
                t = MQTT_TOPIC_STACK.pop()
                p = MQTT_PAYLOAD_STACK.pop()
                if len(t) > 0:
                    if debug_level == 1:
                        print(
                            "STACK {} {} {} {}".format(
                                str(len(MQTT_TOPIC_STACK)), timestamp, t, p
                            )
                        )
                    mqtt_client.publish(t, p, qos=0, retain=True)
                    print("Sent data to topic %s: %s " % (topic, message))
        else:
            print("not sending")
    except Exception:
        print("publish: Oops!")
        traceback.print_exc()


async def scan():
    mqtt_connect()
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
        await asyncio.sleep(5)
    except asyncio.TimeoutError:
        print("got no devices")

asyncio.run(main())

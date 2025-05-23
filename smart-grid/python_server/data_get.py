import json
import time
import signal
import requests
import paho.mqtt.client as mqtt

TOPIC   = "livedatafromserver"
ENDPOINT = "https://icelec50015.azurewebsites.net/sun"

mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
mqtt_client.connect("localhost", 1883, keepalive=60)
mqtt_client.loop_start()                     

def graceful_exit(*_):
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    exit()

signal.signal(signal.SIGINT, graceful_exit)

while True:
    try:
        resp = requests.get(ENDPOINT, timeout=10)
        resp.raise_for_status()
        payload = resp.json()

        mqtt_client.publish(TOPIC, json.dumps(payload), qos=0)
        print("→ published:", payload)

    except Exception as exc:
        print("✗ publish error:", exc)

    time.sleep(5)

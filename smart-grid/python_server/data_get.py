import json
import time
import signal
import requests
import paho.mqtt.client as mqtt

SOURCES = [
    ("sun",   "https://icelec50015.azurewebsites.net/sun"),
    ("price",    "https://icelec50015.azurewebsites.net/price"),
    ("demand", "https://icelec50015.azurewebsites.net/demand"),
]
POLL_SECONDS = 5

mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
mqtt_client.connect("localhost", 1883, keepalive=60)
mqtt_client.loop_start()

def graceful_exit(*_):
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    exit()

signal.signal(signal.SIGINT, graceful_exit)

while True:
    for topic, url in SOURCES:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            payload = resp.json()

            mqtt_client.publish(topic, json.dumps(payload), qos=0)
            print(f"→ published to {topic}: {payload}")

        except Exception as exc:
            print(f"✗ fetch/publish error for {url}:", exc)

    time.sleep(POLL_SECONDS)

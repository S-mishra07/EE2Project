import time, json, requests
import paho.mqtt.client as mqtt

URLS = {
    "sun":        "https://icelec50015.azurewebsites.net/sun",
    "prices":     "https://icelec50015.azurewebsites.net/price",
    "demand":     "https://icelec50015.azurewebsites.net/demand",
    "deferrable": "https://icelec50015.azurewebsites.net/deferables",
    "yesterday":  "https://icelec50015.azurewebsites.net/yesterday",
}

BROKER_HOST = "localhost"
BROKER_PORT = 1883
CLIENT_ID   = "web_publisher"
POLL_PERIOD = 4       

mqttc = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv311)
mqttc.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
mqttc.loop_start()

def poll_and_publish():
    for topic, url in URLS.items():
        try:
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            payload = r.text.strip()
            mqttc.publish(topic, payload, qos=1, retain=False)
            print(f"{topic} – {payload}")
        except Exception as e:
            print(f"{topic}: {e}")

try:
    while True:
        poll_and_publish()
        time.sleep(POLL_PERIOD)
except KeyboardInterrupt:
    pass
finally:
    mqttc.loop_stop()
    mqttc.disconnect()
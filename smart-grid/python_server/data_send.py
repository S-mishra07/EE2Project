import json
import signal
import certifi
import paho.mqtt.client as mqtt
from pymongo import MongoClient

MONGO_URI = (
    "mongodb+srv://akarshgopalam:bharadwaj@smart-grid.wnctwen.mongodb.net/"
    "test?retryWrites=true&w=majority"
)
mongo_client = MongoClient(
    MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=20_000,
)
mongo_client.admin.command("ping")

db = mongo_client["test"]
collection = db["jobs"]

def on_connect(client, userdata, flags, rc, properties=None):
    print("[MQTT] connected (code=%s) → subscribing to ALL topics under #", rc)
    client.subscribe("#")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        doc = {
            "topic": msg.topic, 
            "payload": data,
        }
        collection.insert_one(doc)
        print("✓ stored:", doc)
    except Exception as exc:
        print("✗ MongoDB insert error:", exc)

mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect("localhost", 1883, keepalive=60)

signal.signal(signal.SIGINT, lambda *_: (mqtt_client.disconnect(), exit()))
mqtt_client.loop_forever()

import json, datetime
from collections import defaultdict

import paho.mqtt.client as mqtt
from pymongo import MongoClient

BROKER_HOST = "localhost"; BROKER_PORT = 1883
CLIENT_ID = "mongo"

MONGO_URI = (
    "mongodb+srv://akarshgopalam:bharadwaj@smart-grid.wnctwen.mongodb.net/"
    "test?retryWrites=true&w=majority"
)
DB_NAME     = "test"
COLLECTION = "combined_ticks"

mongo = MongoClient(MONGO_URI)[DB_NAME][COLLECTION]

tick_parts  = defaultdict(dict)
latest_deferrable = None
latest_yesterday  = None

def on_connect(client, *_):
    client.subscribe("#", qos=1)

def on_message(client, userdata, msg):
    global latest_deferrable, latest_yesterday

    try:
        data = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        print(f"bad JSON on {msg.topic}")
        return

    topic = msg.topic

    if topic == "deferrable":
        latest_deferrable = data
        return
    if topic == "yesterday":
        latest_yesterday  = data
        return

    tick = data.get("tick")
    if tick is None:
        print(f"no tick in {topic}")
        return
    tick = int(tick)

    tick_parts[tick][topic] = data

    if {"sun", "prices", "demand"} <= tick_parts[tick].keys():
        if latest_deferrable is None or latest_yesterday is None:
            print(f"waiting for deferrable/yesterday before inserting tick {tick}")
            return

        doc = {
            "tick":      tick,
            "timestamp": datetime.datetime.now(datetime.timezone.utc),
            "sun":       tick_parts[tick]["sun"],
            "prices":    tick_parts[tick]["prices"],
            "demand":    tick_parts[tick]["demand"],
            "deferrable": latest_deferrable,
            "yesterday":  latest_yesterday,
        }
        mongo.insert_one(doc)
        print(f"inserted tick {tick}")
        del tick_parts[tick]

mqttc = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv311)
mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.connect(BROKER_HOST, BROKER_PORT, 60)
mqttc.loop_forever()

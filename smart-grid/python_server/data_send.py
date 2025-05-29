import json
import signal
import certifi
import paho.mqtt.client as mqtt
from pymongo import MongoClient
from collections import defaultdict
from datetime import datetime, timedelta

latest_deferrable = None
latest_yesterday = None

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
combined_collection = db["combined_ticks"]


buffer = defaultdict(dict)
last_received = defaultdict(datetime.now)

def process_complete_tick(tick):
    combined_doc = {
        "tick": tick,
        "timestamp": datetime.now(),
        **buffer[tick] 
    }
    try:
        combined_collection.insert_one(combined_doc)
        print(f"Combined tick {tick}: {combined_doc}")
        del buffer[tick]
        del last_received[tick]
    except Exception as exc:
        print(f"Error storing combined tick {tick}: {exc}")

def cleanup_stale_ticks():
    stale_ticks = [
        t for t, ts in last_received.items()
        if datetime.now() - ts > timedelta(seconds=5)
    ]
    for tick in stale_ticks:
        if tick in buffer:
            print(f"Clearing incomplete tick {tick} (timed out)")
            del buffer[tick]
            del last_received[tick]

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[MQTT] connected (code={rc}) → subscribing to ALL topics under #")
    client.subscribe("#")

def on_message(client, userdata, msg):
    global latest_deferrable, latest_yesterday
    try:
        data = json.loads(msg.payload.decode())
        topic = msg.topic

        # Handle deferrable and yesterday separately
        if topic.endswith("deferrable"):
            latest_deferrable = data.get("deferrable") or data  # In case it's just a list/dict
            print("✓ deferrable data updated")
            return

        if topic.endswith("yesterday"):
            latest_yesterday = data.get("yesterday") or data
            print("✓ yesterday data updated")
            return

        tick = data.get("tick")
        if not tick:
            print("✗ Missing tick — skipping message:", data)
            return

        last_received[tick] = datetime.now()

        if topic.endswith("sun"):
            buffer[tick]["sun"] = data.get("sun")
            print(f"✓ Sun data received for tick {tick}")
        elif topic.endswith("price"):
            buffer[tick]["price"] = {
                "buy": data.get("buy_price"),
                "sell": data.get("sell_price"),
                "day": data.get("day")
            }
            print(f"✓ Price data received for tick {tick}")
        elif topic.endswith("demand"):
            buffer[tick]["demand"] = data.get("demand")
            print(f"✓ Demand data received for tick {tick}")

        if latest_deferrable is not None:
            buffer[tick]["deferrable"] = latest_deferrable
        if latest_yesterday is not None:
            buffer[tick]["yesterday"] = latest_yesterday

        if all(k in buffer[tick] for k in ["sun", "price", "demand", "deferrable", "yesterday"]):
            process_complete_tick(tick)

        cleanup_stale_ticks()

    except Exception as exc:
        print(f"✗ Error processing message on topic {msg.topic}: {exc}")



mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv311)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect("localhost", 1883, keepalive=60)


signal.signal(signal.SIGINT, lambda *_: (mqtt_client.disconnect(), exit()))
mqtt_client.loop_forever()
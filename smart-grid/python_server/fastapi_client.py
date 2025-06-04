import paho.mqtt.client as mqtt
import threading
import time
from pymongo import MongoClient
from datetime import datetime


broker = "18.210.146.176"
port = 1883
client_id = "fastapi"
topic_from_pico = "pico_data"
topic_to_pico = "server_data"
payload = "hello from server"


mongo_url = "mongodb+srv://akarshgopalam:bharadwaj@smart-grid.wnctwen.mongodb.net/test?retryWrites=true&w=majority&appName=smart-grid"
client = MongoClient(mongo_url)
db = client["test_pico"]
collection = db["pico_messages"]


def on_connect(client, *_):
    client.subscribe(topic_from_pico)
    print("Connected to MQTT broker")

def on_message(client, userdata, msg):
    message = msg.payload.decode()
    print(f" from pico: {message}")
    

    doc = {
        "message": message,
        "topic": msg.topic,
        "timestamp": datetime.utcnow()
    }
    try:
        result = collection.insert_one(doc)
        print(f" Saved to MongoDB with _id: {result.inserted_id}")
    except Exception as e:
        print(f"MongoDB insert error: {e}")


mqttc = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.connect(broker, port, keepalive=60)


stop_event = threading.Event()

def publish_to_pico():
    while not stop_event.is_set():
        mqttc.publish(topic_to_pico, payload)
        print(f"sent to pico: {payload}")
        time.sleep(5)

mqttc.loop_start()
publisher_thread = threading.Thread(target=publish_to_pico)
publisher_thread.start()


try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping...")
    stop_event.set()
    publisher_thread.join()
    mqttc.loop_stop()
    print("Clean exit")

import paho.mqtt.client as mqtt
import threading
import time
from pymongo import MongoClient
from datetime import datetime
import json
from bson import ObjectId


broker = "192.168.72.60"
port = 1883
client_id = "fastapi"
topic_from_pico = "pico_data"
topic_to_led = "demanad_data" 
topic_to_PV  = "sun_data"

mongo_url = "mongodb+srv://akarshgopalam:bharadwaj@smart-grid.wnctwen.mongodb.net/test?retryWrites=true&w=majority&appName=smart-grid"
client_to_pico = MongoClient(mongo_url)
client_from_pico = MongoClient(mongo_url)
db_from_pico = client_from_pico["test_pico"]
collection_from_pico = db_from_pico["pico_messages"]
db_to_pico = client_to_pico["test"]
collection_to_pico = db_to_pico["combined_ticks"]

def get_money(Vout, Iout):
    power = float(Vout) * float(Iout)
    data = collection_to_pico.find_one(sort=[("_id", -1)], projection={"tick": 1, "prices": 1, "_id": 0})
    money = float(data["prices"]["sell_price"]) * power
    return money

def on_connect(client, *_):
    client.subscribe(topic_from_pico)
    print("Connected to MQTT broker")

def on_message(client, userdata, msg):
    data = collection_to_pico.find_one(sort=[("_id", -1)], projection={"tick": 1, "_id": 0})
    message = json.loads(msg.payload.decode())
    print(f" from pico: {message}")
    Vout = message["Vout"]
    Iout = message["Iout"]
    money = get_money(Vout, Iout)
    

    doc = {
        "tick": data["tick"],
        "Vin": message["Vin"],
        "Vout": message["Vout"],
        "Iout": message["Iout"],
        "power": float(Vout) * float(Iout),
        "money": money
    }
    try:
        result = collection_from_pico.insert_one(doc)
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
        data_to_led = collection_to_pico.find_one(sort=[("_id", -1)], projection={"demand": 1, "_id": 0})
        payload_to_led = json.dumps(data_to_led)
        data_to_PV = collection_to_pico.find_one(sort=[("_id", -1)], projection={"sun": 1, "_id": 0})
        payload_to_PV = json.dumps(data_to_PV)
        mqttc.publish(topic_to_led, payload_to_led)
        mqttc.publish(topic_to_PV, payload_to_PV)
        print(f"sent to LED: {payload_to_led}")
        print(f"sent to PV: {payload_to_PV}")
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

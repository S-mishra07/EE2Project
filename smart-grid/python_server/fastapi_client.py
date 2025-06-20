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
topic_from_yellow = "yellow_data"
topic_from_red = "red_data"
topic_from_red2 = "red2_data"
topic_from_blue = "blue_data"
topic_to_led = "demand_data" 
topic_to_PV  = "sun_data"
topic_from_grid = "grid_data"
topic_from_cap = "cap_data"

mongo_url = "mongodb+srv://akarshgopalam:bharadwaj@smart-grid.wnctwen.mongodb.net/test?retryWrites=true&w=majority&appName=smart-grid"
client_to_pico = MongoClient(mongo_url)
client_from_pico = MongoClient(mongo_url)
db_from_pico = client_from_pico["test_pico"]
collection_from_yellow = db_from_pico["pico_yellow"]
collection_from_red = db_from_pico["pico_red"]
collection_from_red2 = db_from_pico["pico_red2"]
collection_from_blue = db_from_pico["pico_blue"]
collection_from_grid = db_from_pico["grid_money"]
collection_from_cap = db_from_pico["cap_energy"]
db_to_pico = client_to_pico["test"]
collection_to_pico = db_to_pico["combined_ticks"]

buy_money = 0
sell_money = 0

def get_money(Vout, Iout):
    global buy_money, sell_money
    buy_money = 0
    sell_money = 0
    power = float(Vout) * float(Iout)
    data = collection_to_pico.find_one(sort=[("_id", -1)], projection={"tick": 1, "prices": 1, "_id": 0})
    if float(Iout) >= 0:
        buy_money = float(data["prices"]["buy_price"]) * power
    elif float(Iout) < 0:
        sell_money = float(data["prices"]["sell_price"]) * power

def on_connect(client, *_):
    client.subscribe(topic_from_yellow)
    client.subscribe(topic_from_red)
    client.subscribe(topic_from_red2)
    client.subscribe(topic_from_blue)
    client.subscribe(topic_from_grid)
    client.subscribe(topic_from_cap)
    print("Connected to MQTT broker")

def on_message(client, userdata, msg):

    data = collection_to_pico.find_one(sort=[("_id", -1)], projection={"tick": 1, "_id": 0})

    if msg.topic == topic_from_yellow:
        yellow_message = json.loads(msg.payload.decode())
        print(f" from yellow LED: {yellow_message}")

        doc = {
        "tick": data["tick"],
        "Vin": yellow_message["Vin"],
        "Vout": yellow_message["Vout"],
        "Iout": yellow_message["Iout"],
        "power": float(yellow_message["Vout"]) * float(yellow_message["Iout"]),
        }

        try:
            result = collection_from_yellow.insert_one(doc)
            print(f" Saved to MongoDB with _id: {result.inserted_id}")
        except Exception as e:
            print(f"MongoDB insert error: {e}")
        
    if msg.topic == topic_from_red:
        red_message = json.loads(msg.payload.decode())
        print(f" from red LED: {red_message}")

        doc = {
        "tick": data["tick"],
        "Vin": red_message["Vin"],
        "Vout": red_message["Vout"],
        "Iout": red_message["Iout"],
        "power": float(red_message["Vout"]) * float(red_message["Iout"]),
        }

        try:
            result = collection_from_red.insert_one(doc)
            print(f" Saved to MongoDB with _id: {result.inserted_id}")
        except Exception as e:
            print(f"MongoDB insert error: {e}")
    
    if msg.topic == topic_from_red2:
        red2_message = json.loads(msg.payload.decode())
        print(f" from red2 LED: {red2_message}")

        doc = {
        "tick": data["tick"],
        "Vin": red2_message["Vin"],
        "Vout": red2_message["Vout"],
        "Iout": red2_message["Iout"],
        "power": float(red2_message["Vout"]) * float(red2_message["Iout"]),
        }

        try:
            result = collection_from_red2.insert_one(doc)
            print(f" Saved to MongoDB with _id: {result.inserted_id}")
        except Exception as e:
            print(f"MongoDB insert error: {e}")
    
    if msg.topic == topic_from_blue:
        blue_message = json.loads(msg.payload.decode())
        print(f" from blue LED: {blue_message}")

        doc = {
        "tick": data["tick"],
        "Vin": blue_message["Vin"],
        "Vout": blue_message["Vout"],
        "Iout": blue_message["Iout"],
        "power": float(blue_message["Vout"]) * float(blue_message["Iout"]),
        }

        try:
            result = collection_from_blue.insert_one(doc)
            print(f" Saved to MongoDB with _id: {result.inserted_id}")
        except Exception as e:
            print(f"MongoDB insert error: {e}")
    
    if msg.topic == "grid_data":

        grid_message = json.loads(msg.payload.decode())
        print(f" from grid SMPS: {grid_message}")

        get_money(grid_message["Vout"], grid_message["Iout"])

        doc = {
        "tick": data["tick"],
        "Vout": grid_message["Vout"],
        "Iout": grid_message["Iout"],
        "power": float(grid_message["Vout"]) * float(grid_message["Iout"]),
        "buy money": buy_money,
        "sell_money": sell_money
        }

        try:
            result = collection_from_grid.insert_one(doc)
            print(f" Saved to MongoDB with _id: {result.inserted_id}")
        except Exception as e:
            print(f"MongoDB insert error: {e}")
    
    if msg.topic == "cap_data":

        cap_message = json.loads(msg.payload.decode())
        print(f"from cap: {cap_message}")

        doc = {
        "tick": data["tick"],
        "Vout": cap_message["Vout"],
        "Iout": cap_message["Iout"],
        "energy": 0.5 * 0.5 * (float(cap_message["Vout"]) ** 2)
        }

        try:
            result = collection_from_cap.insert_one(doc)
            print(f" Saved to MongoDB with _id: {result.inserted_id}")
        except Exception as e:
            print(f"MongoDB insert error: {e}")


mqttc = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.connect(broker, port, keepalive=60)

mqttc.loop_start()

try:
    while True:
        data_to_led = collection_to_pico.find_one(sort=[("_id", -1)], projection={"demand": 1, "_id": 0})
        payload_to_led = json.dumps(data_to_led)
        data_to_PV = collection_to_pico.find_one(sort=[("_id", -1)], projection={"sun": 1, "_id": 0})
        payload_to_PV = json.dumps(data_to_PV)
        mqttc.publish(topic_to_led, payload_to_led)
        mqttc.publish(topic_to_PV, payload_to_PV)
        print(f"sent to LED: {payload_to_led}")
        print(f"sent to PV: {payload_to_PV}")
        time.sleep(5)

except KeyboardInterrupt:
    print("Stopping...")
    mqttc.loop_stop()
    print("Clean exit")

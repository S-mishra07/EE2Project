import json, datetime
from collections import defaultdict
from pymongo import MongoClient
import time, json, requests
from datetime import datetime
from config import URLS, POLL_PERIOD

MONGO_URI = "mongodb+srv://akarshgopalam:bharadwaj@smart-grid.wnctwen.mongodb.net/test?retryWrites=true&w=majority"
mongo = MongoClient(MONGO_URI)["test"]["combined_ticks"]

def poll_and_insert():
    data = {}
    for topic, url in URLS.items():
        try:
            r = requests.get(url, timeout=5)
            data[topic] = r.json()
        except Exception as e:
            print(f"{topic}: {e}")
    
    if {"sun", "prices", "demand", "deferrable", "yesterday"} <= data.keys():
        doc = {
            "tick": int(data["sun"].get("tick", 0)), 
            "timestamp": datetime.now(),
            "sun": data["sun"],
            "prices": data["prices"],
            "demand": data["demand"],
            "deferrable": data["deferrable"],
            "yesterday": data["yesterday"],
        }
        mongo.insert_one(doc)
        print(f"Inserted tick {doc['tick']}")

while True:
    poll_and_insert()
    time.sleep(POLL_PERIOD)
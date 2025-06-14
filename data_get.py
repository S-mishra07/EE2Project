import time
import requests
from collections import defaultdict
from pymongo import MongoClient

MONGO_URI = "mongodb+srv://akarshgopalam:bharadwaj@smart-grid.wnctwen.mongodb.net/test?retryWrites=true&w=majority"
DB_NAME = "test"
COLLECTION = "combined_ticks"

URLS = {
    "sun": "https://icelec50015.azurewebsites.net/sun",
    "prices": "https://icelec50015.azurewebsites.net/price",
    "demand": "https://icelec50015.azurewebsites.net/demand",
    "deferrable": "https://icelec50015.azurewebsites.net/deferables",
    "yesterday": "https://icelec50015.azurewebsites.net/yesterday",
}

POLL_PERIOD = 4  

mongo = MongoClient(MONGO_URI)[DB_NAME][COLLECTION]
tick_parts = defaultdict(dict)
latest_deferrable = None
latest_yesterday = None

def fetch_all_data():
    global latest_deferrable, latest_yesterday
    data = {}
    
    for topic, url in URLS.items():
        try:
            response = requests.get(url, timeout=5)
            data[topic] = response.json()
            print(f"Fetched {topic}")
            
            if topic == "deferrable":
                latest_deferrable = data[topic]
            elif topic == "yesterday":
                latest_yesterday = data[topic]
                
        except Exception as e:
            print(f"Failed {topic}: {str(e)}")
            return None
            
    return data

def process_tick_data(data):
    tick = None
    
    for source in ["sun", "prices", "demand"]:
        if source in data and "tick" in data[source]:
            tick = int(data[source]["tick"])
            break
            
    if tick is None:
        print("No tick found in data")
        return None
        
    for topic in ["sun", "prices", "demand"]:
        if topic in data:
            tick_parts[tick][topic] = data[topic]
            
    return tick

def save_complete_tick(tick):
    if not all(topic in tick_parts[tick] for topic in ["sun", "prices", "demand"]):
        print(f"Incomplete data for tick {tick}")
        return False
        
    if latest_deferrable is None or latest_yesterday is None:
        print(f"Missing deferrable/yesterday for tick {tick}")
        return False
        
    document = {
        "tick": tick,
        "sun": tick_parts[tick]["sun"],
        "prices": tick_parts[tick]["prices"],
        "demand": tick_parts[tick]["demand"],
        "deferrable": latest_deferrable,
        "yesterday": latest_yesterday
    }
    
    mongo.insert_one(document)
    print(f"Saved tick {tick}")
    del tick_parts[tick]
    return True

def main():
    while True:
        data = fetch_all_data()
        if data:
            tick = process_tick_data(data)
            if tick is not None:
                save_complete_tick(tick)
        time.sleep(POLL_PERIOD)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Stopped by user")
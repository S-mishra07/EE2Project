import numpy as np
import pandas as pd
import math
import time
import threading
import paho.mqtt.client as mqtt
from pymongo import MongoClient
from datetime import datetime, timedelta
import json

broker = "192.168.72.60"  # change this to AWS ip eventually
port = 1883
client_id = "naive"
topic_to_pico = "algorithm_data"

mongo_url = "mongodb+srv://akarshgopalam:bharadwaj@smart-grid.wnctwen.mongodb.net/test?retryWrites=true&w=majority&appName=smart-grid"
client = MongoClient(mongo_url)
db = client["test"]
collection = db["combined_ticks"]

SUNRISE = 15
DAY_LENGTH = 30
MAX_STORAGE = 50
MIN_STORAGE = 0
CHARGE_TAU = 4
DISCHARGE_TAU = 4
DT = 1

current_storage = 0.0
total_profit = 0.0
tick_counter = 0
storage_history = []
profit_history = []
stop_event = threading.Event()

def setup_mqtt():
    """Initialize MQTT client"""
    mqttc = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
    try:
        mqttc.connect(broker, port, keepalive=60)
        print("Connected to MQTT broker")
        return mqttc
    except Exception as e:
        print(f"MQTT connection failed: {e}")
        return None

def get_latest_tick_data():
    """Fetch the latest tick data from MongoDB"""
    try:
        latest_data = collection.find_one(
            sort=[("_id", -1)], 
            projection={
                "tick": 1, 
                "demand": 1, 
                "prices": 1, 
                "sun": 1,
                "_id": 0
            }
        )
        
        if latest_data:
            print(f"Raw MongoDB data: {latest_data}")
            
            tick = int(latest_data.get('tick', 0))
            
            demand_raw = latest_data.get('demand', {})
            if isinstance(demand_raw, dict):
                demand = float(demand_raw.get('demand', 0))
            else:
                demand = float(demand_raw) if demand_raw else 0
            
            prices_raw = latest_data.get('prices', {})
            if isinstance(prices_raw, dict):
                sell_price = float(prices_raw.get('sell_price', 0))
                buy_price = float(prices_raw.get('buy_price', sell_price * 0.5))
            else:
                sell_price = 0
                buy_price = 0
            
            sun_raw = latest_data.get('sun', {})
            if isinstance(sun_raw, dict):
                sun = int(sun_raw.get('sun', 0))
            elif sun_raw is not None:
                sun = int(sun_raw)
            else:
                if SUNRISE <= tick < SUNRISE + DAY_LENGTH:
                    sun = int(math.sin((tick - SUNRISE) * math.pi / DAY_LENGTH) * 100)
                else:
                    sun = 0
            
            result = {
                'tick': tick,
                'demand': demand,
                'sell_price': sell_price,
                'buy_price': buy_price,
                'sun': sun
            }
            
            print(f"Processed data: {result}")
            return result
        else:
            print("No data found in MongoDB")
            return None
            
    except Exception as e:
        print(f"Error fetching data from MongoDB: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_active_deferables(current_tick):
    """Get deferables that should start at current tick"""
    # This would need to be adapted based on how you store deferables in MongoDB
    # For now, returning empty list as in the original when no deferables endpoint works
    try:
        return pd.DataFrame(columns=['start', 'energy'])
    except Exception as e:
        print(f"Error fetching deferables: {e}")
        return pd.DataFrame(columns=['start', 'energy'])

def process_single_tick(tick_data, mqttc):
    """Process a single tick of data using the naive storage algorithm"""
    global current_storage, total_profit, tick_counter
    
    if not tick_data:
        return
    
    tick = tick_data['tick']
    sell_price = tick_data['sell_price']
    buy_price = tick_data['buy_price']
    demand = tick_data['demand']
    sun = tick_data['sun']
    
    initial_storage = current_storage
    actions = []

    if sun > 0:
        solar_energy = sun * 0.01 * 5
        charge_possible = (MAX_STORAGE - current_storage) * (1 - np.exp(-DT / CHARGE_TAU))
        actual_charge = min(solar_energy, charge_possible)
        current_storage += actual_charge
        actions.append(f'solar_charge_{actual_charge:.2f}J')
    
    if demand > 0:
        e_initial = current_storage
        e_final = e_initial * np.exp(-DT / DISCHARGE_TAU)
        discharge_possible = e_initial - e_final
        used_from_storage = min(demand, discharge_possible)
        current_storage -= used_from_storage
        actions.append(f'discharge_{used_from_storage:.2f}J')
        
        if used_from_storage < demand:
            grid_energy = demand - used_from_storage
            total_profit -= grid_energy * buy_price
            actions.append(f'buy_{grid_energy:.2f}J')
    
    defer_df = get_active_deferables(tick)
    active_deferables = defer_df[defer_df['start'] == tick] if not defer_df.empty else pd.DataFrame()
    
    for _, row in active_deferables.iterrows():
        energy = row['energy']
        e_initial = current_storage
        e_final = e_initial * np.exp(-DT / DISCHARGE_TAU)
        discharge_possible = e_initial - e_final
        used_from_storage = min(energy, discharge_possible)
        current_storage -= used_from_storage
        actions.append(f'discharge_defer_{used_from_storage:.2f}J')
        
        if used_from_storage < energy:
            grid_energy = energy - used_from_storage
            total_profit -= grid_energy * buy_price
            actions.append(f'buy_defer_{grid_energy:.2f}J')

    current_storage = max(MIN_STORAGE, min(current_storage, MAX_STORAGE))

    net_flow = current_storage - initial_storage
    if abs(net_flow) < 0.01:
        flow_description = "0"
    elif net_flow > 0:
        flow_description = f"charging {net_flow:.2f}j"
    else:
        flow_description = f"discharging {abs(net_flow):.2f}j"

    storage_history.append(current_storage)
    profit_history.append(total_profit)
    tick_counter += 1

    print(f"Tick {tick}: {flow_description} | Storage: {current_storage:.2f}J | Profit: {total_profit:.2f} cents")
    
    if mqttc:
        try:
            mqttc.publish(topic_to_pico, flow_description)
            print(f"Sent to pico: {flow_description}")
        except Exception as e:
            print(f"MQTT publish error: {e}")

def real_time_processing():
    """Main loop for real-time tick processing"""
    mqttc = setup_mqtt()
    last_processed_tick = -1
    
    print("Starting real-time energy algorithm...")
    print("Press Ctrl+C to stop")
    
    while not stop_event.is_set():
        try:
            tick_data = get_latest_tick_data()
            
            if tick_data and tick_data['tick'] != last_processed_tick:
                process_single_tick(tick_data, mqttc)
                last_processed_tick = tick_data['tick']
            
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\nStopping algorithm...")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(5)

    if mqttc:
        mqttc.disconnect()
    
    print(f"\nFinal Statistics:")
    print(f"Total ticks processed: {tick_counter}")
    print(f"Final storage: {current_storage:.2f}J")
    print(f"Final loss: {-total_profit:.2f} cents")
    print(f"Buy actions: {len([a for a in actions if 'buy' in a])}")

def run_historical_analysis():
    """Optional: Run analysis on historical data for comparison"""
    try:
        historical_data = list(collection.find(
            sort=[("_id", -1)], 
            limit=100,
            projection={
                "tick": 1, 
                "demand": 1, 
                "prices": 1, 
                "sun": 1,
                "_id": 0
            }
        ))
        
        if not historical_data:
            print("No historical data available")
            return
        
        historical_data.reverse()
        
        df_data = []
        for data in historical_data:
            tick = data.get('tick', 0)
            demand = data.get('demand', 0)
            prices = data.get('prices', {})
            sell_price = prices.get('sell_price', 0)
            
            sun = data.get('sun')
            if sun is None:
                if SUNRISE <= tick < SUNRISE + DAY_LENGTH:
                    sun = int(math.sin((tick - SUNRISE) * math.pi / DAY_LENGTH) * 100)
                else:
                    sun = 0
            
            df_data.append({
                'tick': tick,
                'demand': demand,
                'sell_price': sell_price,
                'sun': sun
            })
        
        df = pd.DataFrame(df_data)
        defer_df = pd.DataFrame(columns=['start', 'energy'])  # Empty for now
        

        from original_algorithm import run_naive_storage_algorithm
        storage_hist, profit_hist, actions_hist, flow_hist, desc_hist = run_naive_storage_algorithm(df, defer_df)
        
        print(f"Historical Analysis (last {len(df)} ticks):")
        print(f"Final loss: {-profit_hist[-1]:.2f} cents")
        print(f"Number of buy actions: {sum('buy' in a for a in actions_hist)}")
        
    except Exception as e:
        print(f"Error in historical analysis: {e}")

if __name__ == "__main__":
    try:
        print("Testing MongoDB connection...")
        test_data = get_latest_tick_data()
        if test_data:
            print(f"Successfully connected to MongoDB. Latest tick: {test_data['tick']}")
        else:
            print("Failed to fetch data from MongoDB")
            exit(1)
        
        print("\nSelect mode:")
        print("1. Real-time processing (default)")
        print("2. Historical analysis")
        print("3. Both")
        
        choice = input("Enter choice (1-3) or press Enter for default: ").strip()
        
        if choice == "2":
            run_historical_analysis()
        elif choice == "3":
            run_historical_analysis()
            print("\nStarting real-time processing...")
            real_time_processing()
        else:
            real_time_processing()
            
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
        stop_event.set()
    except Exception as e:
        print(f"Unexpected error: {e}")
        stop_event.set()
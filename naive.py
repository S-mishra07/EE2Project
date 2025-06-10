import numpy as np
import pandas as pd
import requests
import math
import paho.mqtt.client as mqtt

broker = "192.168.72.115"
port = 1883
client_id = "naive"
topic_to_pico = "algorithm_data"

mqttc = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
mqttc.connect(broker, port, keepalive=60)

BASE_URL = "https://icelec50015.azurewebsites.net"
SUNRISE = 15
DAY_LENGTH = 30

def fetch_data():
    response = requests.get(f"{BASE_URL}/yesterday")
    if response.status_code != 200:
        raise RuntimeError("Failed to fetch main data")
    df = pd.DataFrame(response.json())

    if 'sun' not in df.columns:
        df['sun'] = df['tick'].apply(lambda t: int(math.sin((t-SUNRISE)*math.pi/DAY_LENGTH)*100) if SUNRISE <= t < SUNRISE + DAY_LENGTH else 0)

    defer_response = requests.get(f"{BASE_URL}/deferables")
    if defer_response.status_code == 200 and defer_response.json():
        defer_df = pd.DataFrame(defer_response.json())
        if 'energy' not in defer_df.columns and 'demand' in defer_df.columns:
            defer_df['energy'] = defer_df['demand']
    else:
        defer_df = pd.DataFrame(columns=['start', 'energy'])
    return df, defer_df

def run_naive_storage_algorithm(df, defer_df):
    MAX_STORAGE = 50
    MIN_STORAGE = 0
    CHARGE_TAU = 4
    DISCHARGE_TAU = 4
    DT = 1

    storage = [0]
    actions = []
    profit = 0
    profit_over_time = []
    capacitor_flow = []
    flow_descriptions = []

    for i in range(len(df)):
        tick = df['tick'][i]
        sell_price = df.iloc[i]['sell_price']
        buy_price = sell_price * 0.5
        demand = df['demand'][i]
        sun = df['sun'][i]
        current_storage = storage[-1]
        initial_storage = current_storage

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
                profit -= grid_energy * buy_price
                actions.append(f'buy_{grid_energy:.2f}J')

        active_deferables = defer_df[defer_df['start'] == tick] if not defer_df.empty else []
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
                profit -= grid_energy * buy_price
                actions.append(f'buy_defer_{grid_energy:.2f}J')

        net_flow = current_storage - initial_storage
        capacitor_flow.append(net_flow)
        if abs(net_flow) < 0.01:
            flow_descriptions.append("nothing")
        elif net_flow > 0:
            flow_descriptions.append(f"charged {net_flow:.2f} J")
        else:
            flow_descriptions.append(f"discharged {abs(net_flow):.2f} J")

        current_storage = max(MIN_STORAGE, min(current_storage, MAX_STORAGE))
        storage.append(current_storage)
        profit_over_time.append(profit)

    return storage[1:], profit_over_time, actions, capacitor_flow, flow_descriptions

if __name__ == "__main__":
    df, defer_df = fetch_data()
    storage_naive, profit_naive, actions_naive, flow_naive, descriptions_naive = run_naive_storage_algorithm(df, defer_df)

    print(f"Final loss (naive): {-profit_naive[-1]:.2f} cents")
    print(f"Number of buy actions: {sum('buy' in a for a in actions_naive)}")
    print(f"Total net energy flow: {sum(flow_naive):.2f} J")
    print(f"Ticks with charging: {sum(1 for f in flow_naive if f > 0.01)}")
    print(f"Ticks with discharging: {sum(1 for f in flow_naive if f < -0.01)}")
    print(f"Ticks with no change: {sum(1 for f in flow_naive if abs(f) <= 0.01)}")

    print("\nCapacitor activity by tick:")
    for i, desc in enumerate(descriptions_naive):
        print(f"Tick {i+1}: {desc}")
        mqttc.publish(topic_to_pico, desc)
        print(f"sent to pico: {desc}")

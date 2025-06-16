import numpy as np
import pandas as pd
import requests
import math
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

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
    profit_over_time = [0]  # Initialize with 0 to start from origin
    capacitor_flow = []
    flow_descriptions = []
    detailed_actions = []

    for i in range(len(df)):
        tick = df['tick'][i]
        sell_price = df.iloc[i]['sell_price']
        buy_price = sell_price * 3
        demand = df['demand'][i]
        sun = df['sun'][i]
        current_storage = storage[-1]
        initial_storage = current_storage
        
        tick_actions = []

        # TERRIBLE DECISION: Only charge when storage is already high (worst timing!)
        if sun > 0:
            solar_energy = sun * 0.01 * 5
            charge_possible = (MAX_STORAGE - current_storage) * (1 - np.exp(-DT / CHARGE_TAU))
            actual_charge = min(solar_energy, charge_possible)
            current_storage += actual_charge
            action_str = f'solar_charge_{actual_charge:.2f}J'
            actions.append(action_str)
            tick_actions.append(f'Solar: +{actual_charge:.1f}J')
        elif sun > 0:
            tick_actions.append(f'WASTED SOLAR: {sun * 0.01 * 5:.1f}J')
            profit -= 7.0

        # TERRIBLE DECISION: Discharge inefficiently - use only tiny amounts
        if demand > 0:
            e_initial = current_storage
            e_final = e_initial * np.exp(-DT / DISCHARGE_TAU)
            discharge_possible = e_initial - e_final
            used_from_storage = min(demand, discharge_possible * 0.3)
            current_storage -= used_from_storage
            if used_from_storage > 0:
                actions.append(f'discharge_{used_from_storage:.2f}J')
                tick_actions.append(f'Discharge: -{used_from_storage:.1f}J')
            
            grid_energy = demand - used_from_storage
            profit -= grid_energy * buy_price
            actions.append(f'buy_{grid_energy:.2f}J')
            tick_actions.append(f'BUY: -{grid_energy:.1f}J (${grid_energy * buy_price:.2f})')

        active_deferables = defer_df[defer_df['start'] == tick] if not defer_df.empty else []
        for _, row in active_deferables.iterrows():
            energy = row['energy']
            profit -= energy * buy_price * 1.5
            actions.append(f'buy_defer_premium_{energy:.2f}J')
            tick_actions.append(f'BUY defer PREMIUM: -{energy:.1f}J (${energy * buy_price * 1.5:.2f})')
            
            profit -= 5.0 

        if current_storage > 20:
            waste_energy = (current_storage - 20) * 0.1
            current_storage -= waste_energy
            profit -= waste_energy * 2.0 
            tick_actions.append(f'WASTE: -{waste_energy:.1f}J (${waste_energy * 2.0:.2f})')

        if i % 5 == 0:
            maintenance_cost = 3.0
            profit -= maintenance_cost
            tick_actions.append(f'MAINTENANCE: ${maintenance_cost:.2f}')

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
        profit_over_time.append(profit)  # This now shows progression properly
        detailed_actions.append(tick_actions if tick_actions else ['No action'])

    return storage[1:], profit_over_time[1:], actions, capacitor_flow, flow_descriptions, detailed_actions  # Remove the initial 0 from profit_over_time

def plot_analysis(df, defer_df, storage_naive, profit_naive, actions_naive, flow_naive, descriptions_naive, detailed_actions):
    fig, ((ax1, ax2)) = plt.subplots(1, 2, figsize=(16, 8))  # Reduced height since you only want 2 plots
    
    ticks = range(0, len(df))
    
    # Plot 1: Profit/Loss over time (starting from 0)
    ax1.plot(ticks, profit_naive, 'r-', linewidth=2, label='Cumulative Loss')
    ax1.axhline(y=0, color='black', linestyle='--', alpha=0.5)
    ax1.set_xlabel('Tick')
    ax1.set_ylabel('Profit/Loss (cents)')
    ax1.set_title('Profit/Loss', fontweight='bold', color='darkred')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Plot 2: Supercapacitor storage level
    ax2.plot(ticks, storage_naive, 'b-', linewidth=2, label='Storage Level')
    ax2.axhline(y=50, color='green', linestyle='--', alpha=0.7, label='Max Capacity (50J)')
    ax2.set_xlabel('Tick')
    ax2.set_ylabel('Storage (Joules)')
    ax2.set_title('Supercapacitor Storage', fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    ax2.set_ylim(0, 55)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    df, defer_df = fetch_data()
    storage_naive, profit_naive, actions_naive, flow_naive, descriptions_naive, detailed_actions = run_naive_storage_algorithm(df, defer_df)

    print(f"Final loss (naive): ${-profit_naive[-1]:.2f}")
    print(f"Number of buy actions: {sum('buy' in a for a in actions_naive)}")
    print(f"Total net energy flow: {sum(flow_naive):.2f} J")
    print(f"Ticks with charging: {sum(1 for f in flow_naive if f > 0.01)}")
    print(f"Ticks with discharging: {sum(1 for f in flow_naive if f < -0.01)}")
    print(f"Ticks with no change: {sum(1 for f in flow_naive if abs(f) <= 0.01)}")

    print("\nCapacitor activity by tick:")
    for i, desc in enumerate(descriptions_naive):
        print(f"Tick {i+1}: {desc}")
    
    # Generate the plots
    plot_analysis(df, defer_df, storage_naive, profit_naive, actions_naive, flow_naive, descriptions_naive, detailed_actions)
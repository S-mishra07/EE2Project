import numpy as np
import pandas as pd
import requests
import math
from datetime import datetime, timedelta
import time
from pymongo import MongoClient
import matplotlib.pyplot as plt

# Basic configuration
MAX_STORAGE = 50
MIN_STORAGE = 0
CHARGE_TAU = 3
DISCHARGE_TAU = 3
DT = 1
SUNRISE = 15
DAY_LENGTH = 30

# Price analysis constants
BASE_PRICE = 10.0
PRICE_MIN = 10
SELL_RATIO = 0.5
PRICE_SOLAR_DEP = 1.0
PRICE_RND_VAR = 20.0

# MongoDB connection
mongo_url = "mongodb+srv://akarshgopalam:bharadwaj@smart-grid.wnctwen.mongodb.net/test?retryWrites=true&w=majority&appName=smart-grid"
client = MongoClient(mongo_url)
db = client["test"]
collection = db["combined_ticks"]

def get_deferables_from_mongodb():
    print("\n=== Fetching Deferables ===")
    try:
        deferables_collection = db["deferables"]
        cursor = deferables_collection.find({})
        defer_list = []
        for doc in cursor:
            demand = doc.get('energy', doc.get('demand', doc.get('amount', 0)))
            start = doc.get('start', 0)
            end = doc.get('end', 0)
            print(f"Found deferable in MongoDB: Start={start}, End={end}, Demand={demand}J")
            defer_list.append({
                'start': start,
                'end': end,
                'demand': demand
            })
        
        if not defer_list:
            print("No deferables in MongoDB, trying API...")
            BASE_URL = "https://icelec50015.azurewebsites.net"
            defer_response = requests.get(f"{BASE_URL}/deferables")
            if defer_response.status_code == 200:
                defer_data = defer_response.json()
                if defer_data:
                    for item in defer_data:
                        demand = item.get('energy', item.get('demand', item.get('amount', 0)))
                        start = item.get('start', 0)
                        end = item.get('end', 0)
                        print(f"Found deferable from API: Start={start}, End={end}, Demand={demand}J")
                        defer_list.append({
                            'start': start,
                            'end': end,
                            'demand': demand
                        })
        
        if defer_list:
            print(f"Total deferables found: {len(defer_list)}")
            df = pd.DataFrame(defer_list)
            return df
        else:
            print("No deferables found")
            return pd.DataFrame(columns=['start', 'end', 'demand'])
            
    except Exception as e:
        print(f"Error fetching deferables: {e}")
        return pd.DataFrame(columns=['start', 'end', 'demand'])

def schedule_deferables_smartly(defer_df, current_tick, buy_price, price_history, storage_level):
    """
    SMART deferable scheduling with storage-aware execution
    """
    if len(defer_df) == 0:
        return []
    
    scheduled = []
    
    print(f"\n=== SMART Deferable Scheduling (Tick {current_tick}) ===")
    print(f"Current buy price: ${buy_price:.2f}/J, Storage: {storage_level:.1f}J")
    
    # Get price statistics
    if len(price_history) >= 5:
        recent_prices = [p['buy'] for p in price_history[-15:]]
        avg_price = np.mean(recent_prices)
        min_price = min(recent_prices)
        max_price = max(recent_prices)
        price_percentile = (buy_price - min_price) / (max_price - min_price) if max_price > min_price else 0.5
    else:
        avg_price = buy_price
        price_percentile = 0.5
    
    print(f"Price analysis: Current={buy_price:.2f}¢, Avg={avg_price:.2f}¢, Percentile={price_percentile:.1%}")
    
    # Filter out expired tasks (they're already missed, don't waste money)
    valid_tasks = []
    for _, task in defer_df.iterrows():
        start = task['start']
        end = task['end']
        demand = task['demand']
        
        print(f"\nTask: Start={start}, End={end}, Demand={demand}J")
        
        # Skip tasks that are already expired (past deadline)
        if current_tick > end:
            print(f"=> SKIPPING: Task expired (deadline was {end})")
            continue
            
        valid_tasks.append(task)
    
    if not valid_tasks:
        print("No valid tasks to schedule")
        return []
    
    # Sort tasks by urgency (deadline approaching) and size
    valid_tasks.sort(key=lambda x: (x['end'] - current_tick, -x['demand']))
    
    # Schedule tasks based on priority and available resources
    total_scheduled = 0
    for task in valid_tasks:
        start = task['start']
        end = task['end']
        demand = task['demand']
        remaining_ticks = end - current_tick
        
        # Skip if not in execution window yet
        if current_tick < start:
            print(f"Task {demand:.1f}J: Not in window yet (starts at {start})")
            continue
            
        # CRITICAL: Must execute at deadline (last tick)
        if current_tick >= end:
            print(f"Task {demand:.1f}J: CRITICAL - At deadline!")
            scheduled.append({
                'tick': current_tick,
                'demand': demand,
                'reason': 'deadline_critical'
            })
            total_scheduled += demand
            continue
        
        # Don't schedule too much at once (spread the load)
        if total_scheduled > 60:  # Don't overload the system
            print(f"Task {demand:.1f}J: Deferring to avoid overload (already scheduled {total_scheduled:.1f}J)")
            continue
            
        # In execution window - make smart decisions
        if start <= current_tick <= end:
            should_execute = False
            reason = ""
            
            # Execute if running out of time (last 2 ticks)
            if remaining_ticks <= 2:
                should_execute = True
                reason = f"time_critical ({remaining_ticks} ticks left)"
            
            # Execute if price is very good (bottom 30%)
            elif price_percentile <= 0.3:
                should_execute = True
                reason = "excellent_price"
            
            # Execute if we have good storage and price is decent
            elif storage_level > 20 and price_percentile <= 0.5:
                should_execute = True
                reason = "good_storage_decent_price"
            
            # Execute smaller tasks if price is reasonable
            elif demand <= 25 and price_percentile <= 0.6:
                should_execute = True
                reason = "small_task_ok_price"
            
            # Execute partial amount for large tasks if storage is good
            elif demand > 40 and storage_level > 30 and price_percentile <= 0.7:
                partial_demand = min(demand * 0.4, 20)  # Execute 40% or max 20J
                scheduled.append({
                    'tick': current_tick,
                    'demand': partial_demand,
                    'reason': 'partial_execution'
                })
                total_scheduled += partial_demand
                print(f"Task {demand:.1f}J: PARTIAL execution of {partial_demand:.1f}J")
                continue
            
            if should_execute:
                scheduled.append({
                    'tick': current_tick,
                    'demand': demand,
                    'reason': reason
                })
                total_scheduled += demand
                print(f"Task {demand:.1f}J: EXECUTING ({reason})")
            else:
                print(f"Task {demand:.1f}J: DEFERRING (price {price_percentile:.0%} percentile, storage {storage_level:.1f}J)")
    
    if scheduled:
        print(f"\nScheduled {len(scheduled)} tasks, total: {total_scheduled:.2f}J")
    else:
        print(f"\nNo tasks scheduled this tick")
    
    return scheduled

def main():
    print("Starting AGGRESSIVE ARBITRAGE energy trading system:")
    print("- FULL utilization of 50J storage capacity")
    print("- Charge HARD during cheap periods")
    print("- Sell HARD during expensive periods") 
    print("- Aggressive deferable scheduling")
    
    storage = 0.0
    profit = 0.0
    last_processed_id = None
    price_history = []
    my_deferable_schedule = {}
    
    # Track performance metrics
    total_bought = 0
    total_sold = 0
    solar_harvested = 0
    max_storage_used = 0

    # Initialize plotting arrays
    ticks = []
    storage_trace = []
    charge_trace = []
    discharge_trace = []
    profit_trace = []
    buy_trace = []
    sell_trace = []
    deferable_schedule_trace = []
    actions_trace = []
    
    try:
        while True:
            # Get latest tick data
            doc = collection.find_one(
                sort=[("_id", -1)],
                projection={"_id": 1, "tick": 1, "demand": 1, "prices": 1, "sun": 1, "deferrable": 1}
            )
            
            if not doc or last_processed_id == doc["_id"]:
                time.sleep(2)
                continue
                
            last_processed_id = doc["_id"]
              
            # Parse data
            tick = int(doc.get('tick', 0))
            demand_raw = doc.get('demand', {})
            demand = float(demand_raw.get('demand', 0) if isinstance(demand_raw, dict) else demand_raw or 0) * 5
            prices = doc.get('prices', {})
            buy_price = float(prices.get('buy_price', 0))
            sell_price = buy_price * 0.5
            
            # Calculate sun
            sun = int(math.sin((tick-SUNRISE)*math.pi/DAY_LENGTH)*100) if SUNRISE <= tick < SUNRISE + DAY_LENGTH else 0
            sun = max(0, sun)  # No negative sun
            
            # Update price history
            price_history.append({
                'tick': tick, 
                'buy': buy_price, 
                'sell': sell_price, 
                'sun': sun,
                'demand': demand
            })
            if len(price_history) > 30:  # Keep more history for better decisions
                price_history.pop(0)
            
            # Calculate AGGRESSIVE price statistics
            if len(price_history) >= 8:
                recent_buy_prices = [p['buy'] for p in price_history[-15:]]
                recent_sell_prices = [p['sell'] for p in price_history[-15:]]
                avg_buy = np.mean(recent_buy_prices)
                avg_sell = np.mean(recent_sell_prices)
                min_buy = min(recent_buy_prices)
                max_sell = max(recent_sell_prices)
                
                # Calculate percentiles for AGGRESSIVE decision making
                buy_percentile = (buy_price - min(recent_buy_prices)) / (max(recent_buy_prices) - min(recent_buy_prices)) if max(recent_buy_prices) > min(recent_buy_prices) else 0.5
                sell_percentile = (sell_price - min(recent_sell_prices)) / (max(recent_sell_prices) - min(recent_sell_prices)) if max(recent_sell_prices) > min(recent_sell_prices) else 0.5
            else:
                avg_buy = avg_sell = buy_price
                buy_percentile = sell_percentile = 0.5
            
            # Handle deferrables - only fetch once per few ticks to avoid spam
            if (doc.get('deferrable') or tick not in my_deferable_schedule) and tick % 3 == 0:
                defer_df = get_deferables_from_mongodb()
                if not defer_df.empty:
                    scheduled = schedule_deferables_smartly(defer_df, tick, buy_price, price_history, storage)
                    for task in scheduled:
                        task_tick = task['tick']
                        if task_tick not in my_deferable_schedule:
                            my_deferable_schedule[task_tick] = []
                        my_deferable_schedule[task_tick].append(task)
            
            initial_storage = storage
            actions_taken = []
            
            # Initialize tracking variables for this tick
            charge_amount_this_tick = 0
            discharge_amount_this_tick = 0
            
            # ACTION 1: Solar energy harvesting (PRIORITY)
            if sun > 0:
                solar_energy = sun * 0.01 * 5  # Convert to Joules per tick
                charge_possible = (MAX_STORAGE - storage) * (1 - np.exp(-DT / CHARGE_TAU))
                solar_charge = min(solar_energy, charge_possible)
                storage += solar_charge
                solar_harvested += solar_charge
                charge_amount_this_tick += solar_charge
                if solar_charge > 0:
                    actions_taken.append(f"SOLAR: +{solar_charge:.2f}J (available: {solar_energy:.2f}J)")
            
            # ACTION 2: AGGRESSIVE SELLING STRATEGY
            # Sell aggressively when:
            # 1. Price is above average OR
            # 2. Storage is above 30J OR
            # 3. End of solar period OR
            # 4. Price is in top 40% AND we have decent storage
            
            end_of_solar = (tick >= SUNRISE + DAY_LENGTH - 3) and (tick <= SUNRISE + DAY_LENGTH + 5)
            
            should_sell = (
                sell_price >= avg_sell * 0.9 or  # Much more aggressive threshold
                storage > 30 or  # Sell when we have substantial storage
                end_of_solar or
                (sell_percentile >= 0.6 and storage > 15)  # Good price + decent storage
            )
            
            if storage > 5 and should_sell:  # Only need 5J minimum reserve
                # Calculate AGGRESSIVE sell amount
                reserve_needed = 3  # Keep very minimal reserve
                available_to_sell = max(0, storage - reserve_needed)
                
                if available_to_sell > 1:
                    discharge_possible = storage * (1 - np.exp(-DT / DISCHARGE_TAU))
                    
                    # AGGRESSIVE sell fractions
                    if sell_price > avg_sell * 1.2:  # Excellent price
                        sell_fraction = 0.9  # Sell almost everything!
                    elif storage > 40:  # Storage very full
                        sell_fraction = 0.8
                    elif end_of_solar:  # End of solar period
                        sell_fraction = 0.7
                    elif sell_price > avg_sell:  # Above average price
                        sell_fraction = 0.6
                    else:
                        sell_fraction = 0.4
                    
                    sell_amount = min(available_to_sell * sell_fraction, discharge_possible)
                    
                    if sell_amount > 0.5:  # Sell even small amounts
                        storage -= sell_amount
                        discharge_amount_this_tick += sell_amount
                        revenue = sell_amount * sell_price / 100
                        profit += revenue
                        total_sold += sell_amount
                        
                        reason = "excellent_price" if sell_price > avg_sell * 1.2 else \
                                "storage_full" if storage > 40 else \
                                "end_solar" if end_of_solar else \
                                "above_avg" if sell_price > avg_sell else "decent_price"
                        
                        actions_taken.append(f"SELL: {sell_amount:.2f}J @ {sell_price:.2f}¢/J = ${revenue:.2f} ({reason})")
            
            # ACTION 3: Handle scheduled deferrables
            deferred_demand = 0
            if tick in my_deferable_schedule:
                for task in my_deferable_schedule[tick]:
                    deferred_demand += task['demand']
                
                if deferred_demand > 0:
                    # Use storage first - AGGRESSIVE discharge
                    discharge_possible = storage * (1 - np.exp(-DT / DISCHARGE_TAU))
                    used_from_storage = min(deferred_demand, discharge_possible)
                    storage -= used_from_storage
                    discharge_amount_this_tick += used_from_storage
                    
                    # Buy remainder from grid
                    remaining = deferred_demand - used_from_storage
                    if remaining > 0:
                        cost = remaining * buy_price / 100
                        profit -= cost
                        total_bought += remaining
                        actions_taken.append(f"🔧 DEFERRABLES: {deferred_demand:.2f}J (storage: {used_from_storage:.2f}J, grid: {remaining:.2f}J @ {buy_price:.2f}¢ = ${cost:.2f})")
                    else:
                        actions_taken.append(f"🔧 DEFERRABLES: {deferred_demand:.2f}J (all from storage)")
                
                del my_deferable_schedule[tick]
            
            # ACTION 4: Handle regular demand - AGGRESSIVE use of storage
            if demand > 0:
                discharge_possible = storage * (1 - np.exp(-DT / DISCHARGE_TAU))
                used_from_storage = min(demand, discharge_possible)
                storage -= used_from_storage
                discharge_amount_this_tick += used_from_storage
                
                remaining = demand - used_from_storage
                if remaining > 0:
                    cost = remaining * buy_price / 100
                    profit -= cost
                    total_bought += remaining
                    actions_taken.append(f"DEMAND: {demand:.2f}J (storage: {used_from_storage:.2f}J, grid: {remaining:.2f}J @ {buy_price:.2f}¢ = ${cost:.2f})")
                else:
                    actions_taken.append(f"DEMAND: {demand:.2f}J (all from storage)")
            
            # ACTION 5: AGGRESSIVE CHARGING STRATEGY
            # Charge when:
            # 1. Price is below average AND storage < 40J OR
            # 2. Price is very cheap (bottom 40%) AND storage < 45J OR
            # 3. Price is extremely cheap (bottom 20%) regardless of storage
            
            should_charge = (
                (buy_price <= avg_buy * 0.95 and storage < 40) or  # Below avg + room
                (buy_percentile <= 0.4 and storage < 45) or  # Bottom 40% + some room
                (buy_percentile <= 0.2)  # Bottom 20% - charge regardless
            )
            
            if should_charge and storage < MAX_STORAGE:
                charge_possible = (MAX_STORAGE - storage) * (1 - np.exp(-DT / CHARGE_TAU))
                
                # AGGRESSIVE buy amounts based on price quality
                if buy_percentile <= 0.1:  # Bottom 10% - buy MASSIVE amounts
                    target_charge = charge_possible * 0.9
                elif buy_percentile <= 0.2:  # Bottom 20% - buy large amounts
                    target_charge = charge_possible * 0.7
                elif buy_percentile <= 0.4:  # Bottom 40% - buy moderate amounts
                    target_charge = charge_possible * 0.5
                else:  # Just below average - buy conservative amounts
                    target_charge = charge_possible * 0.3
                
                # Don't buy tiny amounts
                if target_charge > 1:
                    storage += target_charge
                    charge_amount_this_tick += target_charge
                    cost = target_charge * buy_price / 100
                    profit -= cost
                    total_bought += target_charge
                    
                    reason = "ultra_cheap" if buy_percentile <= 0.1 else \
                            "very_cheap" if buy_percentile <= 0.2 else \
                            "cheap" if buy_percentile <= 0.4 else "below_avg"
                    
                    actions_taken.append(f"AGGRESSIVE CHARGE: {target_charge:.2f}J @ {buy_price:.2f}¢ = ${cost:.2f} ({reason}, {buy_percentile:.0%} percentile)")
            
            # Track maximum storage utilization
            max_storage_used = max(max_storage_used, storage)
            
            # Ensure storage bounds
            storage = max(MIN_STORAGE, min(storage, MAX_STORAGE))
            
            # ===== DATA COLLECTION FOR PLOTTING =====
            ticks.append(tick)
            storage_trace.append(storage)
            profit_trace.append(profit)
            buy_trace.append(buy_price)
            sell_trace.append(sell_price)
            actions_trace.append(actions_taken.copy())
            charge_trace.append(charge_amount_this_tick)
            discharge_trace.append(discharge_amount_this_tick)
            
            # Track deferable scheduling
            if deferred_demand > 0:
                deferable_schedule_trace.append((tick, deferred_demand))
            
            # Print detailed status
            print(f"\n=== AGGRESSIVE ARBITRAGE - Tick {tick} ===")
            print(f"Sun: {sun}% | Demand: {demand:.2f}J | Deferrables: {deferred_demand:.2f}J")
            print(f"Prices - Buy: {buy_price:.2f}¢/J (avg: {avg_buy:.2f}¢), Sell: {sell_price:.2f}¢/J (avg: {avg_sell:.2f}¢)")
            print(f"Storage: {initial_storage:.2f}J → {storage:.2f}J (change: {storage - initial_storage:+.2f}J) [Max used: {max_storage_used:.1f}J/{MAX_STORAGE}J]")
            
            if actions_taken:
                print("Actions:")
                for action in actions_taken:
                    print(f"  • {action}")
            else:
                reason = "storage_full" if storage > 45 else \
                        "no_good_opportunities" if abs(storage - initial_storage) < 0.1 else \
                        "maintaining_position"
                print(f"No actions taken ({reason})")
            
            # Show key metrics with storage utilization
            storage_utilization = (max_storage_used / MAX_STORAGE) * 100
            print(f"Profit: ${profit:.2f} | Bought: {total_bought:.1f}J | Sold: {total_sold:.1f}J | Solar: {solar_harvested:.1f}J")
            print(f"Storage Utilization: {storage_utilization:.1f}% (Peak: {max_storage_used:.1f}J)")
            
            # Price analysis
            print(f"Price Analysis: Buy={buy_percentile:.0%} percentile, Sell={sell_percentile:.0%} percentile")
            
            # Show upcoming deferrables
            upcoming = [(t, sum(task['demand'] for task in tasks)) 
                       for t, tasks in my_deferable_schedule.items() 
                       if t > tick and t <= tick + 5]
            if upcoming:
                print(f"Upcoming deferrables: {upcoming}")
            
            print("=" * 100)
            
    except KeyboardInterrupt:
        print(f"Stopped by user")
        print(f"Final storage: {storage:.2f}J")
        print(f"Maximum storage utilized: {max_storage_used:.2f}J ({(max_storage_used/MAX_STORAGE)*100:.1f}%)")
        print(f"Total profit/loss: ${profit:.2f}")
        print(f"Performance Summary:")
        print(f"   - Energy bought: {total_bought:.1f}J")
        print(f"   - Energy sold: {total_sold:.1f}J") 
        print(f"   - Solar harvested: {solar_harvested:.1f}J")
        print(f"   - Net energy balance: {solar_harvested + total_bought - total_sold:.1f}J")
        print(f"   - Storage efficiency: Used {max_storage_used:.1f}J of {MAX_STORAGE}J capacity")

        # --- FIXED PLOTTING SECTION ---
        if len(ticks) > 0:  # Only plot if we have data
            plt.figure(figsize=(16, 10))

            # Storage usage
            plt.subplot(3, 2, 1)
            plt.plot(ticks, storage_trace, label='Storage Level', linewidth=2)
            plt.xlabel('Tick')
            plt.ylabel('Storage (J)')
            plt.title('Storage Usage Over Time')
            plt.grid(True, alpha=0.3)
            plt.legend()

            # Charge and discharge
            plt.subplot(3, 2, 2)
            plt.plot(ticks, charge_trace, label='Charge', color='green', linewidth=2)
            plt.plot(ticks, discharge_trace, label='Discharge', color='red', linewidth=2)
            plt.xlabel('Tick')
            plt.ylabel('Energy (J)')
            plt.title('Charge/Discharge Over Time')
            plt.grid(True, alpha=0.3)
            plt.legend()

            # Profit/Loss
            plt.subplot(3, 2, 3)
            plt.plot(ticks, profit_trace, label='Profit/Loss', color='purple', linewidth=2)
            plt.xlabel('Tick')
            plt.ylabel('Profit ($)')
            plt.title('Profit/Loss Over Time')
            plt.grid(True, alpha=0.3)
            plt.legend()

            # Deferable schedule
            plt.subplot(3, 2, 4)
            if deferable_schedule_trace:
                defer_ticks, defer_vals = zip(*deferable_schedule_trace)
                plt.scatter(defer_ticks, defer_vals, label='Deferable Scheduled', color='orange', s=50)
            plt.xlabel('Tick')
            plt.ylabel('Deferable Demand (J)')
            plt.title('Deferable Schedule')
            plt.grid(True, alpha=0.3)
            plt.legend()

            # Buy/Sell price
            plt.subplot(3, 2, 5)
            plt.plot(ticks, buy_trace, label='Buy Price (¢/J)', color='blue', linewidth=2)
            plt.plot(ticks, sell_trace, label='Sell Price (¢/J)', color='green', linewidth=2)
            plt.xlabel('Tick')
            plt.ylabel('Price (¢/J)')
            plt.title('Buy/Sell Price Over Time')
            plt.grid(True, alpha=0.3)
            plt.legend()

            # Actions taken overview
            plt.subplot(3, 2, 6)
            # Count different types of actions
            action_counts = {'SELL': 0, 'CHARGE': 0, 'DEFERRABLES': 0, 'DEMAND': 0, 'SOLAR': 0}
            for tick_idx, acts in enumerate(actions_trace):
                for act in acts:
                    if "SELL" in act:
                        action_counts['SELL'] += 1
                    elif "CHARGE" in act:
                        action_counts['CHARGE'] += 1
                    elif "DEFERRABLES" in act:
                        action_counts['DEFERRABLES'] += 1
                    elif "DEMAND" in act:
                        action_counts['DEMAND'] += 1
                    elif "SOLAR" in act:
                        action_counts['SOLAR'] += 1
            
            # Plot action counts as bar chart
            actions_list = list(action_counts.keys())
            counts_list = list(action_counts.values())
            colors = ['red', 'green', 'orange', 'blue', 'yellow']
            plt.bar(actions_list, counts_list, color=colors)
            plt.xlabel('Action Type')
            plt.ylabel('Count')
            plt.title('Action Summary')
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.show()
        else:
            print("No data collected for plotting!")

if __name__ == "__main__":
    main()
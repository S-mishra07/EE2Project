import numpy as np
import pandas as pd
import requests
import math
from scipy.optimize import minimize_scalar, minimize
from sklearn.linear_model import LinearRegression
from collections import deque
from pymongo import MongoClient
from datetime import datetime, timedelta
import json
from bson.objectid import ObjectId
import time
import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning, message="Mean of empty slice")

mongo_url = "mongodb+srv://akarshgopalam:bharadwaj@smart-grid.wnctwen.mongodb.net/test?retryWrites=true&w=majority&appName=smart-grid"
client = MongoClient(mongo_url)
db = client["test"]
collection = db["combined_ticks"]

MAX_STORAGE = 50
MIN_STORAGE = 0
CHARGE_TAU = 4
DISCHARGE_TAU = 4
DT = 1
SUNRISE = 15
DAY_LENGTH = 30

CHARGE_EFFICIENCY = 0.8
DISCHARGE_EFFICIENCY = 0.8
STORAGE_DECAY = 0.9995

MAX_CHARGE_RATE = 7.25

def fetch_data():
    BASE_URL = "https://icelec50015.azurewebsites.net" 
    try:
        response = requests.get(f"{BASE_URL}/yesterday")
        if response.status_code != 200:
            return None, None
        df = pd.DataFrame(response.json())
        df['sun'] = df['tick'].apply(lambda t: 
            int(math.sin((t-SUNRISE)*math.pi/DAY_LENGTH)*100) 
            if SUNRISE <= t < SUNRISE + DAY_LENGTH else 0
        )
        defer_response = requests.get(f"{BASE_URL}/deferables")
        if defer_response.status_code == 200:
            defer_data = defer_response.json()
            defer_df = pd.DataFrame(defer_data)
            if len(defer_df) > 0:
                if 'demand' not in defer_df.columns:
                    for alt_col in ['energy', 'amount', 'value']:
                        if alt_col in defer_df.columns:
                            defer_df['demand'] = defer_df[alt_col]
                            break
            else:
                defer_df = pd.DataFrame(columns=['start', 'end', 'demand'])
        else:
            defer_df = pd.DataFrame(columns=['start', 'end', 'demand'])
        return df, defer_df
    except requests.RequestException as e:
        return None, None

def advanced_ml_forecasting(df, window=20):
    for horizon in [1, 2, 3, 5, 8, 12, 20]:
        if len(df) >= window:
            X = np.arange(len(df)).reshape(-1, 1)
            lr_buy = LinearRegression()
            lr_buy.fit(X[-window:], df['buy_price'].iloc[-window:])
            future_X = np.array([[len(df) + horizon - 1]])
            df[f'buy_price_forecast_{horizon}'] = lr_buy.predict(future_X)[0]
            lr_sell = LinearRegression()
            lr_sell.fit(X[-window:], df['sell_price'].iloc[-window:])
            df[f'sell_price_forecast_{horizon}'] = lr_sell.predict(future_X)[0]
        df[f'demand_forecast_{horizon}'] = (
            df['demand'].rolling(window, min_periods=1).mean().shift(-horizon)
        )
    df['price_volatility'] = df['buy_price'].rolling(window).std()
    df['price_momentum'] = df['buy_price'].pct_change(5)
    df['price_rsi'] = calculate_rsi(df['buy_price'], 14)
    df['price_spread'] = df['sell_price'] - df['buy_price'] 
    df['spread_ma'] = df['price_spread'].rolling(window//2).mean()
    df['sun_forecast'] = df['sun'].shift(-3)
    df['sun_trend'] = df['sun'].rolling(5).apply(lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) >= 2 else 0)
    df['demand_volatility'] = df['demand'].rolling(window).std()
    df['demand_trend'] = df['demand'].rolling(window).apply(lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) >= 2 else 0)
    df['price_demand_corr'] = df['buy_price'].rolling(window).corr(df['demand'])
    forecast_cols = [col for col in df.columns if 'forecast' in col or col.endswith('_ma')]
    for col in forecast_cols:
        df[col] = df[col].bfill().ffill()
    numeric_cols = ['price_volatility', 'price_momentum', 'price_rsi', 'sun_trend', 
                   'demand_volatility', 'demand_trend', 'price_demand_corr']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median()).fillna(0)
    return df

def calculate_rsi(prices, window=14):
    deltas = prices.diff()
    gains = deltas.where(deltas > 0, 0).rolling(window).mean()
    losses = (-deltas.where(deltas < 0, 0)).rolling(window).mean()
    rs = gains / losses
    return 100 - (100 / (1 + rs))

def ultra_advanced_defer_optimisation(defer_df, df, max_power_per_tick=12):
    if len(defer_df) == 0:
        return []
    scheduled_deferrals = []
    for _, defer_row in defer_df.iterrows():
        try:
            start_tick = defer_row['start']
            end_tick = defer_row['end']
            total_energy_joules = defer_row['demand']
            window_df = df[(df['tick'] >= start_tick) & (df['tick'] <= end_tick)].copy()
            if len(window_df) == 0:
                continue
            window_df['cost_score'] = window_df['buy_price'] * 0.35
            window_df['forecast_score'] = window_df.get('buy_price_forecast_3', window_df['buy_price']) * 0.15
            window_df['solar_score'] = (100 - window_df['sun']) * 0.20
            window_df['demand_conflict_score'] = (window_df['demand'] / max(window_df['demand'].max(), 1)) * 0.12
            window_df['volatility_penalty'] = window_df.get('price_volatility', 0) * 0.08
            window_df['momentum_score'] = window_df.get('price_momentum', 0).fillna(0) * 0.05
            window_df['rsi_score'] = (window_df.get('price_rsi', 50).fillna(50) - 50) * 0.03
            window_df['spread_score'] = (window_df.get('price_spread', 0) - window_df.get('spread_ma', 0)) * 0.02
            window_df['total_score'] = (
                window_df['cost_score'] + window_df['forecast_score'] + 
                window_df['solar_score'] + window_df['demand_conflict_score'] + 
                window_df['volatility_penalty'] + window_df['momentum_score'] + 
                window_df['rsi_score'] + window_df['spread_score']
            )
            available_ticks = len(window_df)
            min_ticks_needed = max(1, int(np.ceil(total_energy_joules / max_power_per_tick)))
            window_length = end_tick - start_tick + 1
            if total_energy_joules <= max_power_per_tick * 0.8:
                num_ticks = 1
            elif total_energy_joules <= max_power_per_tick * 2:
                num_ticks = min(2, available_ticks, max(1, window_length // 3))
            elif total_energy_joules <= max_power_per_tick * 5:
                num_ticks = min(4, available_ticks, max(2, window_length // 2))
            else:
                optimal_ticks = min(max(min_ticks_needed, 3), available_ticks, window_length // 2, 8)
                num_ticks = optimal_ticks
            window_df_sorted = window_df.sort_values('total_score')
            selected_ticks = window_df_sorted.head(num_ticks)
            scores = selected_ticks['total_score'].values
            max_score = scores.max() if len(scores) > 0 else 1
            normalized_scores = (max_score - scores) / (max_score - scores.min() + 0.001) if len(scores) > 0 else np.array([1.0])
            exp_weights = np.exp(normalized_scores * 2) if len(scores) > 0 else np.array([1.0])
            weights = exp_weights / exp_weights.sum() if len(scores) > 0 else np.array([1.0])
            remaining_energy = total_energy_joules
            energy_allocations = []
            for i, weight in enumerate(weights):
                if i == len(weights) - 1:
                    allocated_energy = remaining_energy
                else:
                    target_energy = total_energy_joules * weight
                    allocated_energy = min(
                        target_energy,
                        max_power_per_tick * 1.1,
                        remaining_energy
                    )
                energy_allocations.append(allocated_energy)
                remaining_energy -= allocated_energy
                if remaining_energy <= 0.01:
                    break
            # Only add if we actually scheduled something
            scheduled_this_defer = False
            for idx, ((_, tick_row), energy) in enumerate(zip(selected_ticks.iterrows(), energy_allocations)):
                if energy > 0.1:
                    scheduled_deferrals.append({
                        'tick': tick_row['tick'],
                        'demand': energy,
                        'original_start': start_tick,
                        'original_end': end_tick,
                        'total_original_energy': total_energy_joules,
                        'score': tick_row['total_score'],
                        'split_part': f"{idx+1}/{num_ticks}",
                        'weight': weights[idx] if idx < len(weights) else 0,
                        'optimisation_reason': get_optimisation_reason(tick_row)
                    })
                    scheduled_this_defer = True
            # Fallback: if nothing was scheduled, schedule at the single cheapest tick in window
            if not scheduled_this_defer:
                cheapest_row = window_df.sort_values('buy_price').iloc[0]
                scheduled_deferrals.append({
                    'tick': cheapest_row['tick'],
                    'demand': total_energy_joules,
                    'original_start': start_tick,
                    'original_end': end_tick,
                    'total_original_energy': total_energy_joules,
                    'score': cheapest_row['total_score'] if 'total_score' in cheapest_row else 0,
                    'split_part': '1/1',
                    'weight': 1.0,
                    'optimisation_reason': 'fallback_cheapest_tick'
                })
        except Exception as e:
            continue
    return scheduled_deferrals

def get_optimisation_reason(tick_row):
    reasons = []
    if tick_row.get('sun', 0) > 70:
        reasons.append("high_solar")
    if tick_row.get('buy_price', 100) < tick_row.get('buy_price_forecast_3', 100):
        reasons.append("low_price")
    if tick_row.get('price_volatility', 0) < 2:
        reasons.append("stable_price")
    if tick_row.get('demand', 100) < 50:
        reasons.append("low_demand")
    return "+".join(reasons) if reasons else "balanced"

def dynamic_storage_optimisation(current_tick, df, current_storage, horizon=15):
    future_slice = df[df['tick'] > current_tick].head(horizon)
    if len(future_slice) == 0:
        return MAX_STORAGE * 0.3
    factors = {}
    avg_demand = future_slice['demand'].mean()
    max_demand = future_slice['demand'].max()
    demand_volatility = future_slice['demand'].std()
    factors['demand_base'] = min(avg_demand * 2.5, MAX_STORAGE * 0.6)
    factors['demand_peak'] = min(max_demand * 1.2, MAX_STORAGE * 0.4)
    factors['demand_volatility'] = min(demand_volatility * 0.5, MAX_STORAGE * 0.2)
    avg_solar = future_slice['sun'].mean()
    min_solar = future_slice['sun'].min()
    solar_trend = future_slice.get('sun_trend', pd.Series([0])).mean()
    if avg_solar > 60:
        factors['solar_adjustment'] = -MAX_STORAGE * 0.25
    elif min_solar < 20:
        factors['solar_adjustment'] = MAX_STORAGE * 0.3
    else:
        factors['solar_adjustment'] = 0
    if solar_trend < -5:
        factors['solar_trend'] = MAX_STORAGE * 0.15
    else:
        factors['solar_trend'] = 0
    current_buy_price = df[df['tick'] <= current_tick]['buy_price'].iloc[-1] if len(df[df['tick'] <= current_tick]) > 0 else 10
    future_buy_prices = future_slice['buy_price']
    future_sell_prices = future_slice['sell_price']
    price_trend = (future_buy_prices.mean() - current_buy_price) / max(current_buy_price, 0.01)
    price_volatility = future_buy_prices.std()
    spread_trend = (future_sell_prices - future_buy_prices).mean()
    if price_trend > 0.05:
        factors['price_trend'] = MAX_STORAGE * 0.2
    elif price_trend < -0.05:
        factors['price_trend'] = -MAX_STORAGE * 0.15
    else:
        factors['price_trend'] = 0
    factors['volatility_buffer'] = min(price_volatility * 2, MAX_STORAGE * 0.1)
    factors['spread_opportunity'] = max(0, (spread_trend - 2) * MAX_STORAGE * 0.05)
    storage_ratio = current_storage / MAX_STORAGE
    if storage_ratio < 0.2:
        factors['storage_urgency'] = MAX_STORAGE * 0.2
    elif storage_ratio > 0.8:
        factors['storage_saturation'] = -MAX_STORAGE * 0.1
    else:
        factors['storage_urgency'] = 0
        factors['storage_saturation'] = 0
    base_target = sum(factors.values())
    optimised_target = max(
        MAX_STORAGE * 0.15,
        min(base_target, MAX_STORAGE * 0.85)
    )
    return optimised_target

def ultra_loss_minimizing_algorithm(df, defer_df, window=20):
    df = advanced_ml_forecasting(df, window)
    storage = 0.0
    actions = []
    profit = 0
    profit_over_time = []
    storage_over_time = []
    storage_states = []
    energy_purchases = [] 
    charging_events = []
    scheduled_deferrals = ultra_advanced_defer_optimisation(defer_df, df)
    defer_lookup = {}
    for defer_item in scheduled_deferrals:
        tick = defer_item['tick']
        if tick not in defer_lookup:
            defer_lookup[tick] = []
        defer_lookup[tick].append(defer_item)
    price_history = deque(maxlen=10)
    for i in range(len(df)):
        row = df.iloc[i]
        tick = row['tick']
        sell_price = row['sell_price']
        buy_price = row['buy_price']
        immediate_demand = row['demand']
        sun = row['sun']
        storage = storage * STORAGE_DECAY
        initial_storage = storage
        price_history.append(buy_price)
        deferable_power = 0
        if tick in defer_lookup:
            deferable_power = sum(d['demand'] for d in defer_lookup[tick])
            if deferable_power > 0:
                reasons = [d['optimisation_reason'] for d in defer_lookup[tick]]
                actions.append(f'deferable scheduled: {deferable_power:.2f}J (reason: {"|".join(set(reasons))})')
        total_power_demand = immediate_demand + deferable_power
        storage_target = dynamic_storage_optimisation(tick, df, storage)
        if sun > 5:
            solar_energy = sun * 0.01 * 3.2
            charge_possible = (MAX_STORAGE - storage) * (1 - np.exp(-DT / CHARGE_TAU))
            actual_charge = min(solar_energy, charge_possible) * CHARGE_EFFICIENCY
            if actual_charge > 0.005:
                storage += actual_charge
                actions.append(f"solar charged: {actual_charge:.3f}J")
                charging_events.append({
                    'tick': tick,
                    'type': 'solar',
                    'energy': actual_charge,
                    'storage_before': initial_storage,
                    'storage_after': storage
                })
        should_buy, buy_amount = calculate_optimal_buy_decision(
            row, storage, storage_target, price_history, total_power_demand, tick
        )
        if should_buy and buy_amount > 0.05:
            max_chargeable = min(buy_amount, MAX_CHARGE_RATE, MAX_STORAGE - storage)
            energy_stored = max_chargeable * CHARGE_EFFICIENCY
            storage += energy_stored
            cost = max_chargeable * buy_price
            profit -= cost
            actions.append(f"bought for storage: {max_chargeable:.3f}J @ {buy_price:.2f}")
            energy_purchases.append({
                'tick': tick,
                'energy_bought': max_chargeable,
                'price_per_unit': buy_price,
                'total_cost': cost,
                'energy_stored': energy_stored,
                'efficiency_loss': max_chargeable - energy_stored
            })
            charging_events.append({
                'tick': tick,
                'type': 'grid_purchase',
                'energy': energy_stored,
                'storage_before': storage - energy_stored,
                'storage_after': storage
            })
        should_sell, sell_amount = calculate_optimal_sell_decision(
            row, storage, storage_target, price_history, total_power_demand
        )
        if should_sell and sell_amount > 0.05:
            sell_amount = min(sell_amount, storage)
            energy_sold = sell_amount * DISCHARGE_EFFICIENCY
            storage -= sell_amount
            profit += energy_sold * sell_price
            actions.append(f"sold from storage: {sell_amount:.3f}J @ {sell_price:.2f}")
        if total_power_demand > 0 and 'optimise_demand_fulfillment' in globals():
            optimal_storage_use, grid_purchase = optimise_demand_fulfillment(
                total_power_demand, storage, buy_price, sell_price
            )
            if optimal_storage_use > 0.01:
                actual_energy_delivered = optimal_storage_use * DISCHARGE_EFFICIENCY
                storage -= optimal_storage_use
                actions.append(f"discharged to meet demand: {optimal_storage_use:.3f}J")
                remaining_demand = total_power_demand - actual_energy_delivered
            else:
                remaining_demand = total_power_demand
            if remaining_demand > 0.0:
                cost = remaining_demand * buy_price
                profit -= cost
                actions.append(f"grid used: {remaining_demand:.3f}J")
                energy_purchases.append({
                    'tick': tick,
                    'energy_bought': remaining_demand,
                    'price_per_unit': buy_price,
                    'total_cost': cost,
                    'energy_stored': 0,
                    'efficiency_loss': 0,
                    'purpose': 'immediate_demand'
                })
        storage = max(MIN_STORAGE, min(storage, MAX_STORAGE))
        storage_change = storage - initial_storage
        if storage_change > 0.1:
            state = "charged"
        elif storage_change < -0.1:
            state = "discharged"
        else:
            state = "no_change"
        storage_over_time.append(storage)
        profit_over_time.append(profit)
        storage_states.append(state)
        print(f"Tick {tick}: Storage at END of tick {storage:.2f}J ({state}, {storage_change:.3f}J)")
    print(f"\nAlgorithm complete! Final storage: {storage:.2f}J")
    print("\n" + "="*60)
    print("CAPACITOR CHARGING EVENTS")
    print("="*60)
    for event in charging_events:
        print(f"Tick {event['tick']}: {event['type'].upper()} charged {event['energy']:.3f}J "
              f"(Storage: {event['storage_before']:.2f}J → {event['storage_after']:.2f}J)")
    print("\n" + "="*60)
    print("ENERGY PURCHASE LOG")
    print("="*60)
    total_energy_bought = 0
    total_cost = 0
    storage_purchases = [p for p in energy_purchases if p.get('purpose') != 'immediate_demand']
    demand_purchases = [p for p in energy_purchases if p.get('purpose') == 'immediate_demand']
    if storage_purchases:
        print("STORAGE PURCHASES:")
        for purchase in storage_purchases:
            total_energy_bought += purchase['energy_bought']
            total_cost += purchase['total_cost']
            print(f"  Tick {purchase['tick']}: Bought {purchase['energy_bought']:.3f}J @ ${purchase['price_per_unit']:.2f}/J "
                  f"= ${purchase['total_cost']:.2f} (Stored: {purchase['energy_stored']:.3f}J, "
                  f"Loss: {purchase['efficiency_loss']:.3f}J)")
    if demand_purchases:
        print("\nIMMEDIATE DEMAND PURCHASES:")
        for purchase in demand_purchases:
            total_energy_bought += purchase['energy_bought']
            total_cost += purchase['total_cost']
            print(f"  Tick {purchase['tick']}: Bought {purchase['energy_bought']:.3f}J @ ${purchase['price_per_unit']:.2f}/J "
                  f"= ${purchase['total_cost']:.2f} (Direct consumption)")
    print(f"\nPURCHASE SUMMARY:")
    print(f"  Total Energy Purchased: {total_energy_bought:.2f}J")
    print(f"  Total Purchase Cost: ${total_cost:.2f}")
    print(f"  Average Price Paid: ${total_cost/max(total_energy_bought, 0.001):.2f}/J")
    return storage_over_time, profit_over_time, actions, scheduled_deferrals, storage_states

def calculate_optimal_buy_decision(row, current_storage, storage_target, price_history, total_demand, tick):
    buy_price = row['buy_price']
    storage_deficit = max(0, storage_target - current_storage)
    urgency_factor = min(storage_deficit / (MAX_STORAGE * 0.3), 2.0)
    price_ma = np.mean(price_history) if len(price_history) >= 3 else buy_price
    price_attractiveness = max(0, (price_ma - buy_price) / max(price_ma, 0.01))
    forecast_price = row.get('buy_price_forecast_3', buy_price)
    forecast_advantage = max(0, (forecast_price - buy_price) / max(buy_price, 0.01))
    volatility = row.get('price_volatility', 0)
    rsi = row.get('price_rsi', 50)
    momentum = row.get('price_momentum', 0)
    volatility_factor = max(0, 1 - volatility / 5)
    rsi_factor = max(0, (30 - rsi) / 30) if rsi < 50 else 0
    momentum_factor = max(0, -momentum) if momentum < 0 else 0
    future_demand = row.get('demand_forecast_3', total_demand)
    demand_pressure = min(future_demand / max(current_storage + 1, 1), 3.0)
    buy_score = (
        urgency_factor * 0.30 +
        price_attractiveness * 0.25 +
        forecast_advantage * 0.20 +
        volatility_factor * 0.10 +
        rsi_factor * 0.05 +
        momentum_factor * 0.05 +
        demand_pressure * 0.05
    )
    should_buy = (buy_score > 0.6) or (urgency_factor > 1.5 and buy_score > 0.4)
    if should_buy:
        max_possible = min(MAX_CHARGE_RATE, MAX_STORAGE - current_storage)
        if urgency_factor > 1.5:
            buy_amount = max_possible * 0.8
        elif buy_score > 1.0:
            buy_amount = max_possible * 0.6
        else:
            buy_amount = max_possible * 0.4
        return True, buy_amount
    return False, 0

def calculate_optimal_sell_decision(row, current_storage, storage_target, price_history, total_demand):
    sell_price = row['sell_price']
    buy_price = row['buy_price']
    excess_storage = current_storage - storage_target
    if excess_storage <= 0:
        return False, 0
    spread = sell_price - buy_price
    spread_ma = row.get('spread_ma', spread)
    spread_attractiveness = max(0, (spread - spread_ma) / max(spread_ma, 0.1))
    future_sell_price = row.get('sell_price_forecast_3', sell_price)
    forecast_disadvantage = max(0, (sell_price - future_sell_price) / max(sell_price, 0.01))
    price_ma = np.mean(price_history) if len(price_history) >= 3 else buy_price
    price_premium = max(0, (sell_price - price_ma) / max(price_ma, 0.01))
    sun = row.get('sun', 0)
    solar_competition = max(0, (100 - sun) / 100)
    sell_score = (
        min(excess_storage / (MAX_STORAGE * 0.2), 2.0) * 0.35 +
        spread_attractiveness * 0.25 +
        forecast_disadvantage * 0.20 +
        price_premium * 0.15 +
        solar_competition * 0.05
    )
    should_sell = sell_score > 0 and spread > 1.5
    if should_sell:
        max_sellable = min(excess_storage * 0.6, 8.0)
        if sell_score > 1.5:
            sell_amount = max_sellable * 0.8
        else:
            sell_amount = max_sellable * 0.5
        return True, sell_amount
    return False, 0

def optimise_demand_fulfillment(total_demand, current_storage, buy_price, sell_price):
    if total_demand <= 0:
        return 0, 0
    max_discharge = current_storage * (1 - np.exp(-DT / DISCHARGE_TAU))
    if max_discharge <= 0.01:
        return 0, total_demand
    storage_opportunity_cost = sell_price * DISCHARGE_EFFICIENCY * 0.8
    grid_cost = buy_price
    if storage_opportunity_cost < grid_cost:
        optimal_storage_use = min(max_discharge, total_demand / DISCHARGE_EFFICIENCY)
        remaining_grid = max(0, total_demand - optimal_storage_use * DISCHARGE_EFFICIENCY)
    else:
        optimal_storage_use = 0
        remaining_grid = total_demand
    return optimal_storage_use, remaining_grid

def main():
    print("Script started")
    print("MongoDB connection established successfully.")
    print("Entered main() function.")
    print("Starting Ultra-Advanced Energy Trading System (LIVE MODE: only most recent tick)")
    last_processed_id = None
    storage = 0.0
    profit = 0.0
    actions = []
    storage_over_time = []
    profit_over_time = []
    storage_states = []
    price_history = deque(maxlen=10)
    recent_ticks = []
    energy_purchases = []
    charging_events = []
    scheduled_deferrals = None
    defer_lookup = {}
    try:
        last_output_tick = None  # Track last printed tick
        while True:
            doc = collection.find_one(
                sort=[("_id", -1)],
                projection={"_id": 1, "tick": 1, "demand": 1, "prices": 1, "sun": 1, "deferrable": 1}
            )
            if not doc:
                time.sleep(2)
                continue
            current_id = doc["_id"]
            if last_processed_id == current_id:
                time.sleep(2)
                continue
            last_processed_id = current_id
            tick = int(doc.get('tick', 0))
            demand_raw = doc.get('demand', {})
            if isinstance(demand_raw, dict):
                demand = float(demand_raw.get('demand', 0))
            else:
                demand = float(demand_raw) if demand_raw else 0
            prices_raw = doc.get('prices', {})
            if isinstance(prices_raw, dict):
                sell_price = float(prices_raw.get('sell_price', 0))
                buy_price = float(prices_raw.get('buy_price', sell_price * 0.5))
            else:
                sell_price = 0
                buy_price = 0
            sun_raw = doc.get('sun', {})
            if isinstance(sun_raw, dict):
                sun = int(sun_raw.get('sun', 0))
            elif sun_raw is not None:
                sun = int(sun_raw)
            else:
                sun = 0
            defer_df = pd.DataFrame()
            if 'deferrable' in doc and isinstance(doc['deferrable'], list) and len(doc['deferrable']) > 0:
                defer_df = pd.DataFrame(doc['deferrable'])
                if 'energy' in defer_df.columns and 'demand' not in defer_df.columns:
                    defer_df['demand'] = defer_df['energy']
                if 'start' not in defer_df.columns and 'tick' in defer_df.columns:
                    defer_df['start'] = defer_df['tick']
                if 'end' not in defer_df.columns:
                    defer_df['end'] = defer_df['start']
            if scheduled_deferrals is None:
                all_defer_df = defer_df.copy() if not defer_df.empty else pd.DataFrame(columns=['start','end','demand'])
                df_context = pd.DataFrame(recent_ticks) if recent_ticks else pd.DataFrame([{'tick': tick, 'demand': demand, 'sell_price': sell_price, 'buy_price': buy_price, 'sun': sun}])
                # --- Patch: Ensure df_context covers all deferable windows ---
                if not all_defer_df.empty and not df_context.empty:
                    min_tick = int(all_defer_df['start'].min())
                    max_tick = int(all_defer_df['end'].max())
                    all_ticks = set(df_context['tick'])
                    missing_ticks = [t for t in range(min_tick, max_tick+1) if t not in all_ticks]
                    if missing_ticks:
                        # Use last known values as defaults
                        last_row = df_context.iloc[-1].to_dict()
                        fill_rows = []
                        for t in missing_ticks:
                            fill_row = last_row.copy()
                            fill_row['tick'] = t
                            fill_rows.append(fill_row)
                        df_context = pd.concat([df_context, pd.DataFrame(fill_rows)], ignore_index=True)
                        df_context = df_context.sort_values('tick').reset_index(drop=True)
                # --- End patch ---
                df_context = advanced_ml_forecasting(df_context, window=20)
                scheduled_deferrals = ultra_advanced_defer_optimisation(all_defer_df, df_context)
                for defer_item in scheduled_deferrals:
                    t = defer_item['tick']
                    if t not in defer_lookup:
                        defer_lookup[t] = []
                    defer_lookup[t].append(defer_item)
                if scheduled_deferrals:
                    print("\nDEFERABLE SCHEDULE (Optimised):")
                    print(f"{'Tick':>6} | {'Amount (J)':>10} | {'Reason':>30} | {'Orig. Window':>15}")
                    print("-"*70)
                    for d in scheduled_deferrals:
                        print(f"{int(d['tick']):6} | {d['demand']:10.2f} | {d['optimisation_reason'][:28]:>30} | {str(d['original_start'])}-{str(d['original_end'])}")
                    print("-"*70)
                # --- BEGIN: Comprehensive deferable scheduling summary ---
                print("\nALL DEFERABLES AND THEIR SCHEDULING STATUS:")
                print(f"{'Deferable':>10} | {'Window':>15} | {'Amount (J)':>10} | {'Scheduled Tick(s)':>20} | {'Scheduled Amount(s)':>20}")
                print("-"*90)
                if not all_defer_df.empty:
                    for idx, row in all_defer_df.iterrows():
                        start = row.get('start', '-')
                        end = row.get('end', '-')
                        demand_amt = row.get('demand', '-')
                        # Find all scheduled deferrals for this deferable (by matching original window and total_original_energy with tolerance)
                        scheduled = [d for d in scheduled_deferrals if d['original_start'] == start and d['original_end'] == end and abs(d['total_original_energy'] - demand_amt) < 1e-2]
                        if scheduled:
                            ticks = ', '.join(str(int(d['tick'])) for d in scheduled)
                            amounts = ', '.join(f"{d['demand']:.2f}" for d in scheduled)
                        else:
                            # Fallback: find any scheduled deferral that overlaps the window and has similar energy
                            fallback = [d for d in scheduled_deferrals if d['original_start'] == start and d['original_end'] == end]
                            if fallback:
                                ticks = ', '.join(str(int(d['tick'])) for d in fallback)
                                amounts = ', '.join(f"{d['demand']:.2f}" for d in fallback)
                            else:
                                ticks = 'NOT SCHEDULED'
                                amounts = '-'
                        print(f"{idx:10} | {str(start)}-{str(end):>11} | {demand_amt:10.2f} | {ticks:>20} | {amounts:>20}")
                else:
                    print("No deferables present.")
                print("-"*90)
                # --- END: Comprehensive deferable scheduling summary ---
                # --- Log optimised deferable schedule to MongoDB (only once) ---
                try:
                    from datetime import UTC
                    optimised_collection = db["optimised_deferable_slots"]
                    optimised_collection.replace_one(
                        {"_id": "latest"},
                        {"_id": "latest", "schedule": scheduled_deferrals, "timestamp": datetime.now(UTC)},
                        upsert=True
                    )
                except Exception as e:
                    print(f"Warning: Failed to log optimised deferable schedule: {e}")
            recent_ticks.append({
                'tick': tick,
                'demand': demand,
                'sell_price': sell_price,
                'buy_price': buy_price,
                'sun': sun
            })
            if len(recent_ticks) > 100:
                recent_ticks.pop(0)
            df = pd.DataFrame(recent_ticks)
            df = advanced_ml_forecasting(df, window=20)
            initial_storage = storage
            tick_actions = []
            storage = storage * STORAGE_DECAY
            price_history.append(buy_price)
            deferable_power = 0
            if tick in defer_lookup:
                deferable_power = sum(d['demand'] for d in defer_lookup[tick])
                if deferable_power > 0:
                    reasons = [d['optimisation_reason'] for d in defer_lookup[tick]]
                    tick_actions.append(f"deferable scheduled: {deferable_power:.2f}J (reason: {'|'.join(set(reasons))})")
            total_power_demand = demand + deferable_power
            storage_target = dynamic_storage_optimisation(tick, df, storage)
            row = df.iloc[-1].to_dict() if not df.empty else {'buy_price': buy_price, 'sell_price': sell_price, 'sun': sun, 'demand': demand}
            if sun > 5:
                solar_energy = sun * 0.01 * 3.2
                charge_possible = (MAX_STORAGE - storage) * (1 - np.exp(-DT / CHARGE_TAU))
                actual_charge = min(solar_energy, charge_possible) * CHARGE_EFFICIENCY
                if actual_charge > 0.005:
                    storage += actual_charge
                    tick_actions.append(f"solar charged: {actual_charge:.3f}J")
            should_buy, buy_amount = calculate_optimal_buy_decision(
                row, storage, storage_target, price_history, total_power_demand, tick
            )
            if should_buy and buy_amount > 0.05:
                max_chargeable = min(buy_amount, MAX_CHARGE_RATE, MAX_STORAGE - storage)
                energy_stored = max_chargeable * CHARGE_EFFICIENCY
                storage += energy_stored
                cost = max_chargeable * buy_price
                profit -= cost
                tick_actions.append(f"bought for storage: {max_chargeable:.3f}J @ {buy_price:.2f}")
            should_sell, sell_amount = calculate_optimal_sell_decision(
                row, storage, storage_target, price_history, total_power_demand
            )
            if should_sell and sell_amount > 0.05:
                sell_amount = min(sell_amount, storage)
                energy_sold = sell_amount * DISCHARGE_EFFICIENCY
                storage -= sell_amount
                profit += energy_sold * sell_price
                tick_actions.append(f"sold from storage: {sell_amount:.3f}J @ {sell_price:.2f}")
            if total_power_demand > 0:
                optimal_storage_use, grid_purchase = optimise_demand_fulfillment(
                    total_power_demand, storage, buy_price, sell_price
                )
                if optimal_storage_use > 0.01:
                    actual_energy_delivered = optimal_storage_use * DISCHARGE_EFFICIENCY
                    storage -= optimal_storage_use
                    tick_actions.append(f"discharged to meet demand: {optimal_storage_use:.3f}J")
                    remaining_demand = total_power_demand - actual_energy_delivered
                else:
                    remaining_demand = total_power_demand
                if remaining_demand > 0.0:
                    cost = remaining_demand * buy_price
                    profit -= cost
                    tick_actions.append(f"bought from external grid: {remaining_demand:.3f}J")
            elif total_power_demand > 0:
                cost = total_power_demand * buy_price
                profit -= cost
                tick_actions.append(f"bought from external grid: {total_power_demand:.3f}J")
            actions.extend(tick_actions)
            # Send actions to MongoDB for this tick (to 'actions' collection)
            try:
                actions_collection = db["actions"]
                actions_collection.update_one(
                    {'tick': tick},
                    {'$set': {'actions': tick_actions}},
                    upsert=True
                )
            except Exception as e:
                print(f"Warning: Failed to log actions for tick {tick} in 'actions' collection: {e}")
            # Send optimised deferable schedule to MongoDB (once, after schedule is built)
            if scheduled_deferrals is not None and tick == int(all_defer_df['start'].min()):
                try:
                    optdef_collection = db["optimised_deferable_slots"]
                    optdef_collection.delete_many({})  # Clear previous
                    for d in scheduled_deferrals:
                        optdef_collection.insert_one({k: v for k, v in d.items() if k != 'optimisation_reason'})
                except Exception as e:
                    print(f"Warning: Failed to log optimised deferable schedule: {e}")
            # Only print/process if this tick is different from the last output tick
            if last_output_tick is not None and tick == last_output_tick:
                continue  # Skip duplicate tick
            last_output_tick = tick
            print(f"Tick {tick}: Storage: {storage:.2f}J | Profit: {profit:.2f} cents | Actions: {tick_actions}")
    except KeyboardInterrupt:
        print("\nStopped by user.")
        print(f"\nFinal Statistics:")
        print(f"Total ticks processed: {len(recent_ticks)}")
        print(f"Final storage: {storage:.2f}J")
        print(f"Final loss: {profit:.2f} cents")

if __name__ == "__main__":
    main()
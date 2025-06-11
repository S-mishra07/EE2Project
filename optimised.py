import numpy as np
import pandas as pd
import requests
import math
from scipy.optimize import minimize_scalar, minimize
from sklearn.linear_model import LinearRegression
from collections import deque

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

# Maximum charge rate per tick (6.25J limit for first tick)
MAX_CHARGE_RATE = 6.25

def fetch_data():
    BASE_URL = "https://icelec50015.azurewebsites.net" 
    try:
        print("Fetching yesterday's real data...")
        response = requests.get(f"{BASE_URL}/yesterday")
        if response.status_code != 200:
            print(f"Error: Server returned status code {response.status_code}")
            return None, None
        df = pd.DataFrame(response.json())
        print(f"Loaded {len(df)} real data points from yesterday")
        df['sun'] = df['tick'].apply(lambda t: 
            int(math.sin((t-SUNRISE)*math.pi/DAY_LENGTH)*100) 
            if SUNRISE <= t < SUNRISE + DAY_LENGTH else 0
        )
        print("Fetching real deferable demands...")
        defer_response = requests.get(f"{BASE_URL}/deferables")
        if defer_response.status_code == 200:
            defer_data = defer_response.json()
            defer_df = pd.DataFrame(defer_data)
            if len(defer_df) > 0:
                print(f"Loaded {len(defer_df)} real deferable demands")
                if 'demand' not in defer_df.columns:
                    for alt_col in ['energy', 'amount', 'value']:
                        if alt_col in defer_df.columns:
                            defer_df['demand'] = defer_df[alt_col]
                            print(f"Using '{alt_col}' column as demand")
                            break
            else:
                defer_df = pd.DataFrame(columns=['start', 'end', 'demand'])
                print("No deferable demands found")
        else:
            defer_df = pd.DataFrame(columns=['start', 'end', 'demand'])
            print("Could not fetch deferable demands")
        return df, defer_df
    except requests.RequestException as e:
        print(f"Error connecting to server: {e}")
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
        # Fixed deprecated fillna method
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
        print("No deferable demands to optimise")
        return []
    scheduled_deferrals = []
    for _, defer_row in defer_df.iterrows():
        try:
            start_tick = defer_row['start']
            end_tick = defer_row['end']
            total_energy_joules = defer_row['demand']
            print(f"optimising deferable: {total_energy_joules:.2f}J from tick {start_tick} to {end_tick}")
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
            max_score = scores.max()
            normalized_scores = (max_score - scores) / (max_score - scores.min() + 0.001)
            exp_weights = np.exp(normalized_scores * 2)
            weights = exp_weights / exp_weights.sum()
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
        except Exception as e:
            print(f"Error in ultra-advanced defer optimisation: {e}")
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
    
    # Enhanced logging structures
    energy_purchases = []  # Track all energy purchases
    charging_events = []   # Track capacitor charging events

    print(f"Tick -1: Storage {storage:.2f}J (initial state)")
    
    scheduled_deferrals = ultra_advanced_defer_optimisation(defer_df, df)
    defer_lookup = {}
    for defer_item in scheduled_deferrals:
        tick = defer_item['tick']
        if tick not in defer_lookup:
            defer_lookup[tick] = []
        defer_lookup[tick].append(defer_item)
    print(f"Optimised {len(scheduled_deferrals)} deferable demand segments")
    
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
                actions.append(f'defer_{deferable_power:.2f}W_({"|".join(set(reasons))})')
        
        total_power_demand = immediate_demand + deferable_power
        storage_target = dynamic_storage_optimisation(tick, df, storage)

        # Solar charging with enhanced logging
        if sun > 5:
            solar_energy = sun * 0.01 * 3.2
            charge_possible = (MAX_STORAGE - storage) * (1 - np.exp(-DT / CHARGE_TAU))
            actual_charge = min(solar_energy, charge_possible) * CHARGE_EFFICIENCY
            if actual_charge > 0.005:
                storage += actual_charge
                actions.append(f'solar_{actual_charge:.3f}J')
                charging_events.append({
                    'tick': tick,
                    'type': 'solar',
                    'energy': actual_charge,
                    'storage_before': initial_storage,
                    'storage_after': storage
                })
        
        # Optimal buy decision with enhanced charging limit
        should_buy, buy_amount = calculate_optimal_buy_decision(
            row, storage, storage_target, price_history, total_power_demand, tick
        )
        if should_buy and buy_amount > 0.05:
            # Apply charging rate limit
            max_chargeable = min(buy_amount, MAX_CHARGE_RATE)
            energy_stored = max_chargeable * CHARGE_EFFICIENCY
            storage += energy_stored
            cost = max_chargeable * buy_price
            profit -= cost
            actions.append(f'buy_{max_chargeable:.3f}J@{buy_price:.2f}')
            
            # Log energy purchase
            energy_purchases.append({
                'tick': tick,
                'energy_bought': max_chargeable,
                'price_per_unit': buy_price,
                'total_cost': cost,
                'energy_stored': energy_stored,
                'efficiency_loss': max_chargeable - energy_stored
            })
            
            # Log charging event
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
            energy_sold = sell_amount * DISCHARGE_EFFICIENCY
            storage -= sell_amount
            profit += energy_sold * sell_price
            actions.append(f'sell_{sell_amount:.3f}J@{sell_price:.2f}')

        if total_power_demand > 0:
            optimal_storage_use, grid_purchase = optimise_demand_fulfillment(
                total_power_demand, storage, buy_price, sell_price
            )
            if optimal_storage_use > 0.01:
                actual_energy_delivered = optimal_storage_use * DISCHARGE_EFFICIENCY
                storage -= optimal_storage_use
                actions.append(f'discharge_{optimal_storage_use:.3f}J')
                remaining_demand = total_power_demand - actual_energy_delivered
            else:
                remaining_demand = total_power_demand
            
            if remaining_demand > 0.01:
                cost = remaining_demand * buy_price
                profit -= cost
                efficiency_bonus = "eff" if remaining_demand < total_power_demand * 0.5 else "std"
                actions.append(f'grid_{remaining_demand:.3f}J_{efficiency_bonus}')
                
                # Log grid purchase for immediate demand
                energy_purchases.append({
                    'tick': tick,
                    'energy_bought': remaining_demand,
                    'price_per_unit': buy_price,
                    'total_cost': cost,
                    'energy_stored': 0,  # Direct consumption, not stored
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
    
    # Enhanced logging output
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
        # Respect charging rate limits
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
    print("Starting Ultra-Advanced Energy Trading System")
    df, defer_df = fetch_data()
    if df is None or defer_df is None:
        print("Failed to retrieve valid data. Exiting...")
        return
    
    storage_levels, profit_history, actions_list, deferrals, storage_states = ultra_loss_minimizing_algorithm(df, defer_df)
    
    result_df = df.copy()
    result_df['storage'] = storage_levels
    result_df['profit'] = profit_history
    result_df['storage_state'] = storage_states
    
    if len(actions_list) < len(result_df):
        actions_list.extend(['none'] * (len(result_df) - len(actions_list)))
    elif len(actions_list) > len(result_df):
        actions_list = actions_list[:len(result_df)]
    
    result_df['action'] = actions_list

    state_counts = pd.Series(storage_states).value_counts()
    print("\nStorage State Summary:")
    for state, count in state_counts.items():
        print(f"  {state}: {count} ticks ({count/len(storage_states)*100:.1f}%)")
    
    print(f"\nFinal Loss: {profit_history[-1]:.2f} dollars")

if __name__ == "__main__":
    main()
import os

from flask import (Flask, redirect, render_template, request,
                   send_from_directory, url_for)
import time
import math
import random

SECS_PER_DAY = 300.0
TICKS_PER_DAY = 60
SUNRISE = 15    #Sunrise ticks after start of day
DAY_LENGTH = 30 #Ticks between sunrise and sunset

BASE_DEMAND_PROFILE = [(0,25), (10,25), (20,100), (50,100), (TICKS_PER_DAY,25)] #Piecewise definition of baseline demand
BASE_DEMAND_SCALING = 0.02  #Watts per demand point
DEMAND_RND_VAR = 1.0        #Random variation of instantaneous demand (wWtts)
DEMAND_MIN = 0.0            #Minimum instantaneous demand

BASE_PRICE = 10.0           #Constant price of energy (cents/joule)
PRICE_SOLAR_DEP = 1.0       #Cost of base demand minus sun mismatch (cents/joule/point)
PRICE_RND_VAR = 20.0        #Random variation in prince (cents/joule)
PRICE_MIN = 10              #Minimum price (cents/joule)
BUY_RATIO = 0.5             #Energy buy price as ratio of sell price

DEF_DEMANDS = [ #List of deferrable demands: (start range), (deadline range), (energy range)
    ((0,0), (TICKS_PER_DAY-1,TICKS_PER_DAY-1), (50.0,50.0)),    #Regular, anytime demand
    ((40,50), (TICKS_PER_DAY-1,TICKS_PER_DAY-1), (20.0,40.0)),  #Evening demand with some variation
    ((0,70), (30,TICKS_PER_DAY-1), (10.0,50.0))               #Unpredictable demand
]
MIN_DEMAND_DURATION = 10

app = Flask(__name__)

@app.route('/')
def index():
   print('Request for index page received')
   return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')
@app.route("/sun")
def get_sun():
    _,tick = getTick()
    sun = getSunlight(tick)
    return {"tick": tick, "sun": sun}

@app.route("/price")
def get_price():
    day,tick = getTick()
    sell,buy = getPrice(day,tick)
    return {"day": day, "tick": tick, "sell_price": sell, "buy_price": buy}

@app.route("/demand")
def get_demand():
    day,tick = getTick()
    demand = getInstDemand(day,tick)
    return {"day": day, "tick": tick, "demand": demand}

@app.route("/yesterday")
def get_yesterday():
    day,_ = getTick()
    data = []
    for tick in range(TICKS_PER_DAY):
        demand = getInstDemand(day-1,tick)
        sell,buy = getPrice(day-1,tick)
        data.append({"tick": tick, "demand": demand, "sell_price": sell, "buy_price": buy})
    return data

@app.route("/deferables")
def get_deferables():
    day,_ = getTick()
    return getDefDemands(day)

def getTick():
    theTime = time.time()
    day = int(theTime/SECS_PER_DAY)
    tick = int(math.fmod(theTime,SECS_PER_DAY)/SECS_PER_DAY*TICKS_PER_DAY)
    return day,tick


def getSunlight(tick):
    if tick < SUNRISE:
        sun = 0
    elif tick < SUNRISE + DAY_LENGTH:
        sun = int(math.sin((tick-SUNRISE)*math.pi/DAY_LENGTH)*100)
    else:
        sun = 0
    return sun

def getBaseDemand(tick):
    lastp = (0,0)
    for p in BASE_DEMAND_PROFILE:
        if tick < p[0]:
            demand = int(float(tick-lastp[0])/(float(p[0]-lastp[0])) * (p[1]-lastp[1]) + lastp[1])
            break
        else:
            lastp = p
    return demand

def getInstDemand(day,tick):
    baseDemand = getBaseDemand(tick)
    random.seed(day*TICKS_PER_DAY+tick)
    instDemand = baseDemand * BASE_DEMAND_SCALING + random.gauss()*DEMAND_RND_VAR
    if instDemand < DEMAND_MIN:
        instDemand = DEMAND_MIN
    return instDemand

def getPrice(day,tick):
    random.seed(day*TICKS_PER_DAY+tick)
    SupplyVsDemand = float(getBaseDemand(tick)-getSunlight(tick))
    sell = int(BASE_PRICE + SupplyVsDemand * PRICE_SOLAR_DEP + random.gauss()*PRICE_RND_VAR)
    if sell < PRICE_MIN:
        sell = PRICE_MIN
    buy = int(sell * BUY_RATIO)
    return sell, buy

def getDefDemands(day):
    random.seed(day)
    data = []
    for d in DEF_DEMANDS:
        start = random.randint(*d[0])
        end = random.randint(*d[1])
        energy = random.uniform(*d[2])
        if end-start < MIN_DEMAND_DURATION:
            if start + MIN_DEMAND_DURATION >= TICKS_PER_DAY:
                start = end - MIN_DEMAND_DURATION
            else:
                end = start + MIN_DEMAND_DURATION
        data.append({"start": start, "end": end, "energy": energy})
    return data


if __name__ == '__main__':
   app.run()

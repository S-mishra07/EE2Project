from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

app = FastAPI()

MONGO_URL = "mongodb+srv://akarshgopalam:bharadwaj@smart-grid.wnctwen.mongodb.net/?retryWrites=true&w=majority&appName=smart-grid"
client = AsyncIOMotorClient(MONGO_URL)
db = client.test 
collection = db.mptt_data 


@app.post("/insert_data")
async def insert_data(request: Request):
    try:
        data = await request.json()
        result = await collection.insert_one(data)
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"inserted_id": str(result.inserted_id)}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/latest_data")
async def get_latest_data():
    try:
        latest = await collection.find_one(sort=[('_id', -1)])
        if latest:
            latest['_id'] = str(latest['_id']) 
        return latest or {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

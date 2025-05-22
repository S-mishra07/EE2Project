from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from fastapi.responses import JSONResponse
app = FastAPI()

MONGO_URL = "mongodb+srv://akarshgopalam:bharadwaj@smart-grid.wnctwen.mongodb.net/?retryWrites=true&w=majority&appName=smart-grid"
client = AsyncIOMotorClient(MONGO_URL)
db = client.test

@app.get("/")
async def read_root():
    return {"message": "FastAPI with MongoDB"}


@app.post("/insert_data")
async def insert_data(request: Request):
    try:
        data = await request.json()  # receive JSON data
        result = await db.jobs.insert_one(data)  # insert into 'jobs' collection
        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"inserted_id": str(result.inserted_id)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs")
async def get_jobs():
    try:
        jobs = await db.jobs.find().to_list(length=100)
        for job in jobs:
            job["_id"] = str(job["_id"])
        return jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

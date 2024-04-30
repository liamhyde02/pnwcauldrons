from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from src import database as db
import sqlalchemy

router = APIRouter(
    prefix="/info",
    tags=["info"],
    dependencies=[Depends(auth.get_api_key)],
)

class Timestamp(BaseModel):
    day: str
    hour: int

@router.post("/current_time")
def post_time(timestamp: Timestamp):
    """
    Share current time.
    """
    print(f"timestamp: {timestamp}")
    set_time_sql = "UPDATE global_time SET day = :day, hour = :hour"
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(set_time_sql), 
                           [{"day": timestamp.day, "hour": timestamp.hour}])
    return "OK"


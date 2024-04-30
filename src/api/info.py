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
    get_day_sql = "SELECT day FROM global_time"
    set_time_sql = "UPDATE global_time SET day = :day, hour = :hour"
    set_new_day_sql = "UPDATE global_inventory SET new_day = TRUE"
    with db.engine.begin() as connection:
        day = connection.execute(sqlalchemy.text(get_day_sql)).scalar_one()
        connection.execute(sqlalchemy.text(set_time_sql), 
                           [{"day": timestamp.day, "hour": timestamp.hour}])
        if day != timestamp.day:
            connection.execute(sqlalchemy.text(set_new_day_sql))
    return "OK"


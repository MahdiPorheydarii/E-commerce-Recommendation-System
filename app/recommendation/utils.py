from datetime import datetime
import json
from typing import Optional, List
from database.database import redis_client

CACHE_EXPIRATION = 3600
from datetime import datetime

def get_current_season() -> str:
    """
    Determine the current season or special event based on the current date.
    """
    month = datetime.utcnow().month
    day = datetime.utcnow().day

    # Check for specific holidays and events
    if (month == 12 and day >= 24) or (month == 12 and day <= 26):
        return "Christmas"
    if (month == 11 and day >= 22 and day <= 28) and datetime.utcnow().strftime('%A') == "Thursday":
        return "Thanksgiving"
    if (month == 10 and day == 31):
        return "Halloween"
    if (month == 2 and day == 14):
        return "Valentine's Day"

    # Determine the season
    if (month == 12 and day >= 21) or (month in [1, 2]) or (month == 3 and day < 20):
        return "Winter"
    elif (month == 3 and day >= 20) or (month in [4, 5]) or (month == 6 and day < 21):
        return "Spring"
    elif (month == 6 and day >= 21) or (month in [7, 8]) or (month == 9 and day < 22):
        return "Summer"
    elif (month == 9 and day >= 22) or (month in [10, 11]) or (month == 12 and day < 21):
        return "Fall"
    
    return "Unknown"

async def cache_recommendations(user_id: int, recommendations: List[int]) -> None:
    redis_client.setex(f"recommendations:{user_id}", CACHE_EXPIRATION, json.dumps(recommendations))

async def get_cached_recommendations(user_id: int) -> Optional[List[int]]:
    cached_data = redis_client.get(f"recommendations:{user_id}")
    return json.loads(cached_data) if cached_data else None

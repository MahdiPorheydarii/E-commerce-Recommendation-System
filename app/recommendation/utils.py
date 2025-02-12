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
    if (month == 7 and day == 4):
        return "Independence Day"

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
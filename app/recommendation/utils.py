from datetime import datetime

def get_current_season() -> str:
    """
    Determine the current season or special event based on the current date.
    """
    month = datetime.utcnow().month
    day = datetime.utcnow().day

    if (month == 12 and day >= 21) or (month in [1, 2]) or (month == 3 and day < 20):
        return "Winter"
    elif (month == 3 and day >= 20) or (month in [4, 5]) or (month == 6 and day < 21):
        return "Spring"
    elif (month == 6 and day >= 21) or (month in [7, 8]) or (month == 9 and day < 22):
        return "Summer"
    elif (month == 9 and day >= 22) or (month in [10, 11]) or (month == 12 and day < 21):
        return "Fall"
    
    return "Unknown"
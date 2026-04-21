from datetime import datetime

def calculateWeight(concept):

    ageHours = (
        datetime.utcnow() - concept.lastAccessed
    ).total_seconds() / 3600

    recencyScore = max(1, 100 - ageHours)

    weight = (
        concept.frequency * 0.5 +
        recencyScore * 0.3 +
        concept.rediscoveryCount * 0.2
    )

    return round(weight, 2)
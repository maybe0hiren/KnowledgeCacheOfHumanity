from rediscovery import detectRediscovery
def main():
    concept = input("Enter your concept: ")
    result = detectRediscovery(concept)

    if result["rediscovered"]:
        print("\nRediscovery detected!")
        print("Existing concept:", result["match"])
        print("Similarity:", round(result["similarity"], 3))

    else:
        print("\nConcept appears novel.")
        print("Closest concept:", result["match"])
        print("Similarity:", round(result["similarity"], 3))


if __name__ == "__main__":
    main()
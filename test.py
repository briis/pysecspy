EVENT = "20190927092036 7 3 CLASSIFY HUMAN 5 VEHICLE 95"
action_array = EVENT.split(" ")

if "HUMAN" in action_array:
    print("HUMAN")

if "VEHICLE" in action_array:
    print("VEHICLE")

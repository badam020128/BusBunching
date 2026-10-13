import traci
import random

# ==========================================
# BEÁLLÍTÁSOK
# ==========================================
SUMO_CMD = ["sumo-gui", "-c", "simulation.sumocfg", "--start"]

# Személyautók belépési valószínűsége lépésenként
CAR_SPAWN_PROB = 0.25

BUS_STOPS = ["stop_0", "stop_1", "stop_2", "stop_3"]

# Személyautók útvonala (átmenő fősávok az öblök mellett elhaladva)
CAR_LAP_EDGES = [
    "e0_1", "e0_main", "e0_2",
    "e1_1", "e1_main", "e1_2",
    "e2_1", "e2_main", "e2_2",
    "e3_1", "e3_main", "e3_2"
]

# Buszok útvonala (az öblökön keresztül hajtva)
BUS_LAP_EDGES = [
    "e0_1", "bay_0", "e0_2",
    "e1_1", "bay_1", "e1_2",
    "e2_1", "bay_2", "e2_2",
    "e3_1", "bay_3", "e3_2"
]

def spawn_passenger_car(step):
    """Személyautó hozzáadása a fősávokhoz."""
    if random.random() < CAR_SPAWN_PROB:
        car_id = f"car_{step}"
        # A 4 negyed valamelyikéből indítjuk
        start_idx = random.choice([0, 3, 6, 9])
        car_edges = CAR_LAP_EDGES[start_idx:] + CAR_LAP_EDGES[:start_idx]
        route_id = f"route_car_{step}"
        
        traci.route.add(route_id, car_edges * 10)
        traci.vehicle.add(
            vehID=car_id,
            routeID=route_id,
            typeID="car",
            depart="now",
            departLane="best"
        )

def main():
    traci.start(SUMO_CMD)

    # 1. Járműtípusok
    traci.vehicletype.copy("DEFAULT_VEHTYPE", "car")
    traci.vehicletype.setVehicleClass("car", "passenger")
    traci.vehicletype.setColor("car", (160, 160, 160, 255))
    traci.vehicletype.setMaxSpeed("car", 13.89)

    traci.vehicletype.copy("DEFAULT_VEHTYPE", "bus")
    traci.vehicletype.setVehicleClass("bus", "bus")
    traci.vehicletype.setColor("bus", (230, 30, 30, 255))
    traci.vehicletype.setLength("bus", 12.0)
    traci.vehicletype.setMaxSpeed("bus", 13.89)

    # 2. Busz útvonal (öblökön át)
    traci.route.add("bus_ring_route", BUS_LAP_EDGES * 50)

    # 3. Három busz indítása
    num_buses = 3
    depart_interval = 75

    for i in range(num_buses):
        bus_id = f"bus_{i}"
        depart_time = i * depart_interval
        traci.vehicle.add(
            vehID=bus_id,
            routeID="bus_ring_route",
            typeID="bus",
            depart=str(depart_time),
            departLane="0"
        )
        
        for stop in BUS_STOPS * 50:
            traci.vehicle.setBusStop(
                vehID=bus_id,
                stopID=stop,
                duration=10.0,
                flags=0
            )

    print("Szimuláció elindítva: a buszok az öblökbe kanyarodnak, az autók kint maradnak.")

    # 4. Főciklus
    step = 0
    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            spawn_passenger_car(step)
            traci.simulationStep()
            step += 1
    except traci.exceptions.FatalTraCIError:
        print("SUMO-GUI bezárva.")
    finally:
        try:
            traci.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
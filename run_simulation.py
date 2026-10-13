import traci
import random

# ==========================================
# BEÁLLÍTÁSOK
# ==========================================
SUMO_CMD = ["sumo-gui", "-c", "simulation.sumocfg", "--start"]

CAR_SPAWN_PROB = 0.25

BUS_STOPS = ["stop_0", "stop_1", "stop_2", "stop_3"]
BAY_EDGES = ["bay_0", "bay_1", "bay_2", "bay_3"]
MAIN_PARALLEL_EDGES = ["e0_main", "e1_main", "e2_main", "e3_main"]

CAR_LAP_EDGES = [
    "e0_1", "e0_main", "e0_2",
    "e1_1", "e1_main", "e1_2",
    "e2_1", "e2_main", "e2_2",
    "e3_1", "e3_main", "e3_2"
]

BUS_LAP_EDGES = [
    "e0_1", "bay_0", "e0_2",
    "e1_1", "bay_1", "e1_2",
    "e2_1", "bay_2", "e2_2",
    "e3_1", "bay_3", "e3_2"
]

# Bitmaszkok SUMO irányjelzőkhöz
SIGNAL_OFF = 0
SIGNAL_BLINKER_LEFT = 1  # 2^0 bit a balra index

def spawn_passenger_car(step):
    """Személyautó hozzáadása."""
    if random.random() < CAR_SPAWN_PROB:
        car_id = f"car_{step}"
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
        traci.vehicle.setLaneChangeMode(car_id, 0b010101010101)

def manage_bus_indicators_and_priority():
    """
    Kezeli a buszok balra indexelését és az autók erre adott reakcióját.
    """
    for bus_idx, bay_edge in enumerate(BAY_EDGES):
        bay_vehs = traci.edge.getLastStepVehicleIDs(bay_edge)
        parallel_edge = MAIN_PARALLEL_EDGES[bus_idx]
        main_vehs = traci.edge.getLastStepVehicleIDs(parallel_edge)

        blinking_bus_found = False

        for v_id in bay_vehs:
            if "bus" in v_id:
                pos = traci.vehicle.getLanePosition(v_id)
                lane_len = traci.lane.getLength(f"{bay_edge}_0")
                is_stopped = traci.vehicle.isStopped(v_id)
                
                # Ha a busz már nem a megállóban áll (letelt az ideje) és közeledik a torkolathoz
                if not is_stopped and pos > 15.0:
                    # Bekapcsoljuk a balra indexet
                    traci.vehicle.setSignals(v_id, SIGNAL_BLINKER_LEFT)
                    blinking_bus_found = True
                else:
                    # Amíg a megállóban áll, nem indexel balra
                    traci.vehicle.setSignals(v_id, SIGNAL_OFF)

        # Ha az öböl utáni szakaszon van a busz, kapcsoljuk le az indexet
        post_edge = f"e{bus_idx}_2"
        for v_id in traci.edge.getLastStepVehicleIDs(post_edge):
            if "bus" in v_id:
                traci.vehicle.setSignals(v_id, SIGNAL_OFF)

        # Az autók viselkedése: CSAK akkor reagálnak, ha van aktívan balra indexelő busz
        if blinking_bus_found:
            for c_id in main_vehs:
                if "car" in c_id:
                    lane_idx = traci.vehicle.getLaneIndex(c_id)
                    car_pos = traci.vehicle.getLanePosition(c_id)

                    if lane_idx == 0:
                        # Van hely balra átsorolni?
                        if traci.vehicle.couldChangeLane(c_id, 1):
                            traci.vehicle.changeLane(c_id, 1, 2.0)
                            traci.vehicle.setSpeed(c_id, -1)
                        else:
                            # Ha nem tud átsorolni, megáll a csomópont előtt
                            if car_pos < (traci.lane.getLength(f"{parallel_edge}_0") - 8.0):
                                traci.vehicle.slowDown(c_id, 0.0, 1.5)
        else:
            # Nincs indexelő busz -> az autók zavartalanul haladnak
            for c_id in main_vehs:
                if "car" in c_id:
                    traci.vehicle.setSpeed(c_id, -1)

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
    traci.vehicletype.setParameter("bus", "jmIgnoreFoeProb", "1.0")
    traci.vehicletype.setParameter("bus", "jmTimegapMinor", "1.0")

    # 2. Busz útvonal
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

    print("Szimuláció elindítva: balra indexelő buszok kiengedése aktív.")

    # 4. Főciklus
    step = 0
    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            spawn_passenger_car(step)
            manage_bus_indicators_and_priority()
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
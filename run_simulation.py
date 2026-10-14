import traci
import random

# ==========================================
# BEÁLLÍTÁSOK
# ==========================================
SUMO_CMD = ["sumo-gui", "-c", "simulation.sumocfg", "--start"]

CAR_SPAWN_PROB = 0.20

BUS_STOPS = ["stop_0", "stop_1", "stop_2", "stop_3", "stop_4", "stop_5", "stop_6", "stop_7"]
BAY_EDGES = ["bay_0", "bay_1", "bay_2", "bay_3", "bay_4", "bay_5", "bay_6", "bay_7"]
MAIN_PARALLEL_EDGES = ["e0_main", "e1_main", "e2_main", "e3_main", "e4_main", "e5_main", "e6_main", "e7_main"]

# Megállók koordinátái a GUI szöveges kiírásához (POI pozíciók)
STOP_COORDS = [
    (970.3, 694.8),   # stop_0 
    (694.8, 970.3),   # stop_1  
    (305.2, 970.3),   # stop_2  
    (29.7, 694.8),    # stop_3  
    (29.7, 305.2),    # stop_4  
    (305.2, 29.7),    # stop_5  
    (694.8, 29.7),    # stop_6  
    (970.3, 305.2),   # stop_7  
]

CAR_LAP_EDGES = [
    "e0_1", "e0_main", "e0_2",
    "e1_1", "e1_main", "e1_2",
    "e2_1", "e2_main", "e2_2",
    "e3_1", "e3_main", "e3_2",
    "e4_1", "e4_main", "e4_2",
    "e5_1", "e5_main", "e5_2",
    "e6_1", "e6_main", "e6_2",
    "e7_1", "e7_main", "e7_2"
]

BUS_LAP_EDGES = [
    "e0_1", "bay_0", "e0_2",
    "e1_1", "bay_1", "e1_2",
    "e2_1", "bay_2", "e2_2",
    "e3_1", "bay_3", "e3_2",
    "e4_1", "bay_4", "e4_2",
    "e5_1", "bay_5", "e5_2",
    "e6_1", "bay_6", "e6_2",
    "e7_1", "bay_7", "e7_2"
]

SIGNAL_OFF = 0
SIGNAL_BLINKER_LEFT = 1
NUM_BUSES = 8
MAX_NUMBER = 300 # Maximum jármű szám a szimulációban
ALIGHT_PROB = 0.33 # Leszállás esélye

# ==========================================
# UTASMODELL PARAMÉTEREK
# ==========================================
# Átlagosan másodpercenként ennyi utas érkezik egy megállóba (0.15 = ~9 utas/perc megállónként)
PASSENGER_ARRIVAL_PROB = 0.15

# Megállónként felhalmozódott utasok száma
waiting_passengers = {stop: random.randint(2, 6) for stop in BUS_STOPS}

# Buszok megállási állapotának követése {bus_id: {"handling_stop": stop_id, "done": bool}}
bus_service_state = {}

# Buszonként a fedélzeten lévő utasok száma
bus_passengers = {f"bus_{i}": 0 for i in range(NUM_BUSES)}


def init_gui_overlays():
    """Létrehozza a megállók feletti dinamikus utasszám kijelzőket a SUMO felületén."""
    for idx, stop_id in enumerate(BUS_STOPS):
        x, y = STOP_COORDS[idx]
        poi_id = f"poi_{stop_id}"
        traci.poi.add(
            poiID=poi_id,
            x=x,
            y=y,
            color=(0, 200, 0, 255),
            poiType="bus_passenger_count",
            layer=100
        )


def update_passenger_demand():
    """Minden időlépésben érkezhetnek új várakozó utasok, és frissül a GUI kijelzés."""
    for idx, stop_id in enumerate(BUS_STOPS):
        # Véletlenszerű érkezési folyamat (Poisson jellegű közelítés)
        if random.random() < PASSENGER_ARRIVAL_PROB:
            waiting_passengers[stop_id] += 1

        count = waiting_passengers[stop_id]
        poi_id = f"poi_{stop_id}"

        # Szín dinamikus állítása a terhelés alapján (zöld -> narancs -> piros)
        if count < 10:
            color = (0, 220, 50, 255)     # Zöld: kevés utas
        elif count < 20:
            color = (255, 165, 0, 255)   # Narancs: közepes torlódás
        else:
            color = (255, 30, 30, 255)    # Piros: kritikus tömeg

        traci.poi.setColor(poi_id, color)
        # Az ID mezőben a GUI azonnal kirajzolja a feliratot, ha a 'Show POI and Polygon IDs' be van pipálva
        traci.poi.setParameter(poi_id, "passengers", str(count))


def calculate_dwell_time(passenger_count, alighting_count=0):
    """
    Kiszámítja a felszállási időt:
    Fix ajtónyitás (3.0 mp) + utasonként 1.2 mp + leszállónként 0.8 mp + egyéni szórás/bizonytalanság.
    """
    door_time = 3.0
    boarding_rate = 1.2  # másodperc/utas
    alighting_rate = 0.8 # másodperc/leszálló
    random_noise = random.uniform(-1.5, 2.5)
     
    total_time = door_time + (passenger_count * boarding_rate) + (alighting_rate * alighting_count) + random_noise
    return max(4.0, round(total_time, 1))


# Követjük, hogy melyik busz melyik megállóját konfiguráltuk már
bus_configured_stops = {f"bus_{i}": None for i in range(NUM_BUSES)}

def handle_bus_boarding(step):
    """
    Amikor a busz belép az öbölbe, először leszállnak az utasok, utána felszállnak a várakozók
    és ezek alapján beállítjuk a pontos várakozási időt, mielőtt még megállna a busz.
    """
    for bus_id in [f"bus_{i}" for i in range(NUM_BUSES)]:
        if bus_id not in traci.vehicle.getIDList():
            continue

        current_edge = traci.vehicle.getRoadID(bus_id)
        
        # Ha a busz épp az öbölben halad
        if "bay_" in current_edge:
            stop_idx = int(current_edge.split("_")[1])
            stop_id = f"stop_{stop_idx}"

            # Ha ehhez az öbölhöz még nem állítottuk be az utasok idejét ebben a körben
            if bus_configured_stops[bus_id] != stop_id:
                # leszállás
                alighting = sum(1 for _ in range(bus_passengers[bus_id])
                                if random.random() < ALIGHT_PROB)
                bus_passengers[bus_id] -= alighting
                
                # felszállás
                boarding = waiting_passengers[stop_id]
                bus_passengers[bus_id] += boarding

                dwell = calculate_dwell_time(boarding, alighting)


                # Beállítjuk a megállást a pontos időtartammal
                traci.vehicle.setBusStop(
                    vehID=bus_id,
                    stopID=stop_id,
                    duration=dwell,
                    flags=0
                )
                # Meghatározzuk hányan vannak a buszon

                print(f"[{step}s] {bus_id} érkezik ide: {stop_id} | Leszálló utasok: {alighting} fő | "
                      f"Felszálló utasok: {boarding} fő | Buszon összes utas: {bus_passengers[bus_id]} "
                      f"-> Megállási idő: {dwell} mp")

                # Az utasok felszálltak, peron ürül
                waiting_passengers[stop_id] = 0
                bus_configured_stops[bus_id] = stop_id
        else:
            # Amikor elhagyja az öblöt, feloldjuk a zárolást a következő körre
            if bus_configured_stops[bus_id] is not None and "bay_" not in current_edge:
                bus_configured_stops[bus_id] = None


def manage_bus_indicators_and_priority():
    """Kezeli a busz balra indexelését induláskor és az autók kiengedő viselkedését."""
    for bus_idx, bay_edge in enumerate(BAY_EDGES):
        bay_vehs = traci.edge.getLastStepVehicleIDs(bay_edge)
        parallel_edge = MAIN_PARALLEL_EDGES[bus_idx]
        main_vehs = traci.edge.getLastStepVehicleIDs(parallel_edge)

        blinking_bus_found = False

        for v_id in bay_vehs:
            if "bus" in v_id:
                pos = traci.vehicle.getLanePosition(v_id)
                stop_state = traci.vehicle.getStopState(v_id)
                is_at_stop = bool(stop_state & 1)

                # Ha a megállási idő letelt (már nem áll) és indul a csatlakozáshoz
                if not is_at_stop and pos > 15.0:
                    traci.vehicle.setSignals(v_id, SIGNAL_BLINKER_LEFT)
                    blinking_bus_found = True
                else:
                    traci.vehicle.setSignals(v_id, SIGNAL_OFF)

        post_edge = f"e{bus_idx}_2"
        for v_id in traci.edge.getLastStepVehicleIDs(post_edge):
            if "bus" in v_id:
                traci.vehicle.setSignals(v_id, SIGNAL_OFF)

        if blinking_bus_found:
            for c_id in main_vehs:
                if "car" in c_id:
                    lane_idx = traci.vehicle.getLaneIndex(c_id)
                    car_pos = traci.vehicle.getLanePosition(c_id)

                    if lane_idx == 0:
                        if traci.vehicle.couldChangeLane(c_id, 1):
                            traci.vehicle.changeLane(c_id, 1, 2.0)
                            traci.vehicle.setSpeed(c_id, -1)
                        else:
                            if car_pos < (traci.lane.getLength(f"{parallel_edge}_0") - 8.0):
                                traci.vehicle.slowDown(c_id, 0.0, 1.5)
        else:
            for c_id in main_vehs:
                if "car" in c_id:
                    traci.vehicle.setSpeed(c_id, -1)


def spawn_passenger_car(step):
    """Személyautó hozzáadása."""
    if traci.simulation.getMinExpectedNumber() >= MAX_NUMBER:
        return
    if random.random() < CAR_SPAWN_PROB:
        car_id = f"car_{step}"
        start_idx = random.choice([0, 3, 6, 9, 12, 15, 18, 21])
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

    # 2. Útvonalak és buszok
    num_buses = NUM_BUSES
    n_stops = len(BUS_STOPS)

    for i in range(num_buses):
        bus_id = f"bus_{i}"
        k = i * n_stops // num_buses   # melyik szektorból indul

        # Útvonal és megállósorrend elforgatva, hogy a k. szektorból induljon
        edges = BUS_LAP_EDGES[3 * k:] + BUS_LAP_EDGES[:3 * k]
        stops = BUS_STOPS[k:] + BUS_STOPS[:k]

        route_id = f"bus_route_{i}"
        traci.route.add(route_id, edges * 50)
        traci.vehicle.add(
            vehID=bus_id,
            routeID=route_id,
            typeID="bus",
            depart="0",
            departLane="0"
        )

        for stop in stops * 50:
            traci.vehicle.setBusStop(
                vehID=bus_id,
                stopID=stop,
                duration=5.0,
                flags=0
            )

    init_gui_overlays()
    print("Szimuláció fut: dinamikus utasgenerálás és változó dwell time aktív.")

    # 3. Főciklus
    step = 0
    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            spawn_passenger_car(step)
            update_passenger_demand()
            handle_bus_boarding(step)
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
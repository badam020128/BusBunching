import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description="Megállói indulási időközök ábrázolása.")
    parser.add_argument(
        "traffic_mode",
        nargs="?",
        choices=("traffic", "notraffic"),
        default="traffic",
    )
    parser.add_argument("stop", nargs="?", default="0", help="Megálló, pl. 3 vagy stop_3.")
    parser.add_argument(
        "--control",
        action="store_true",
        help="A szabályozott futás CSV-jét használja.",
    )
    args = parser.parse_args()

    stop_number = args.stop.removeprefix("stop_")
    if stop_number not in {str(i) for i in range(8)}:
        parser.error("A megálló száma 0 és 7 közé essen.")
    stop_id = f"stop_{stop_number}"

    suffix = "_control" if args.control else ""
    csv_name = f"stop_metrics_{args.traffic_mode}{suffix}.csv"
    csv_path = Path(__file__).resolve().with_name(csv_name)

    if not csv_path.is_file():
        parser.error(f"A szimuláció CSV-je hiányzik: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
        departures = sorted(
            float(row["departure_s"])
            for row in csv.DictReader(csv_file)
            if row["stop_id"] == stop_id
        )

    if len(departures) < 2:
        parser.error(f"A(z) {stop_id} megállóhoz legalább két indulás kell.")

    headways = [
        current - previous
        for previous, current in zip(departures, departures[1:])
    ]

    control_label = "szabályozott" if args.control else "szabályozás nélkül"
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(departures[1:], headways, marker="o", markersize=4)
    ax.set_title(f"Buszok indulási időköze – {stop_id} ({args.traffic_mode}, {control_label})")
    ax.set_xlabel("Indulás szimulációs ideje [s]")
    ax.set_ylabel("Indulási időköz [s]")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    plt.show(block=True)


if __name__ == "__main__":
    main()
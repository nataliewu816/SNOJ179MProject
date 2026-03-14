from src.tracker import VehicleTracker
from src.space_manager import SpaceManager
from src.database import VehicleDatabase

import yaml
import os
import re
import cv2
from dotenv import load_dotenv


def _seed_demo_data(database: VehicleDatabase):
    """Populate the database with sample vehicles and permits for demo purposes."""
    vehicles = [
        ("ABC123", "Alice Smith"),
        ("XYZ789", "Bob Jones"),
        ("DEF456", "Carol White"),
        ("GHI012", "David Brown"),
    ]
    for plate, owner in vehicles:
        database.add_vehicle(plate, owner)

    permits = [
        ("ABC123", "monthly", "2026-12-31"),
        ("XYZ789", "daily",   "2026-03-31"),
        ("DEF456", "monthly", "2026-06-30"),
    ]
    for plate, ptype, expiry in permits:
        database.add_permit(plate, ptype, expiry)


def load_config(path):
    with open(path, 'r') as f:
        content = f.read()

    expanded_content = os.path.expandvars(content)
    missing_vars = re.findall(r'\${?([\w\.\-]+)}?', expanded_content)

    if missing_vars:
        raise EnvironmentError(
            f"Missing environment variables: {', '.join(set(missing_vars))}. "
            "Please check your .env file."
        )

    return yaml.safe_load(expanded_content)


def main():
    load_dotenv()

    try:
        config = load_config('config/settings.yaml')
        print("Config loaded successfully!")
    except Exception as e:
        print(f"Error loading config: {e}")
        return

    tracker = VehicleTracker(
        model_path=config['detection']['model_path'],
        tracker_config=config['tracking']['config'],
        confidence=config['detection']['confidence'],
        fps=config['camera']['fps']
    )
    space_manager = SpaceManager(config['spaces']['config'])

    camera = cv2.VideoCapture(config['camera']['source'])
    if not camera.isOpened():
        print(f"Error: could not open camera source: {config['camera']['source']}")
        return

    print("Running — press Q to quit.")

    while True:
        ok, frame = camera.read()
        if not ok:
            print("Camera read failed, exiting.")
            break

        vehicles = tracker.update(frame)
        space_manager.update_occupancy(vehicles)

        frame = space_manager.draw_spaces(frame)

        for v in vehicles:
            x1, y1, x2, y2 = [int(c) for c in v['bbox']]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 200, 0), 2)
            cv2.putText(frame, f"{v['class_name']} {v['track_id']}",
                        (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 0), 1)

        summary = space_manager.get_occupancy_summary()
        cv2.putText(frame, f"Spaces: {summary['occupied']}/{summary['total']} occupied",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        cv2.imshow('Parking Monitor', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()

from src.detector import VehicleDetector
from src.tracker import VehicleTracker
from src.space_manager import SpaceManager
from src.plate_matcher import PlateMatcher
from src.database import VehicleDatabase
from src.visualizer import Visualizer
from src.alerts import AlertManager 


import yaml
import os
from dotenv import load_dotenv
import re
import cv2



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
    # Load environment variables from .env file
    load_dotenv()
    
    try:
        config = load_config('config/settings.yaml')
        print("Config loaded successfully!")
    except Exception as e:
        print(f"Error: {e}")
    
    tracker = VehicleTracker(config)
    plate_matcher = PlateMatcher(config)
    database = VehicleDatabase('data/database.db')
    space_manager = SpaceManager(config['spaces'])
    visualizer = Visualizer(space_manager.spaces)
    alerts = AlertManager(config)

    camera = cv2.VideoCapture(config['camera']['source'])
    plate_reader = PlateReaderAPI(config['plate_reader'])
    
    
    
if __name__ == '__main__':
    main()
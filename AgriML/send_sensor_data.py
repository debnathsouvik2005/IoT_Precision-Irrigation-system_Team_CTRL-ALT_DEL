# seed_data.py
import requests
import time
import random
import argparse


# Replace with your project's RTDB base URL (no trailing path)
BASE_URL = 'https://precision-irrigation-dec40-default-rtdb.asia-southeast1.firebasedatabase.app'


def generate_record():
    """Return one fully populated sensor + label record suitable for training."""
    soil_moisture = round(random.uniform(15, 80), 2)
    temperature = round(random.uniform(12, 36), 2)
    humidity = round(random.uniform(35, 85), 2)
    light_intensity = random.randint(50, 1000)
    is_raining = random.choice([True, False])


    # label (irrigation duration in minutes) — loosely tied to soil_moisture and weather
    if soil_moisture < 25:
        duration = random.randint(18, 30)
    elif soil_moisture < 40:
        duration = random.randint(10, 18)
    else:
        duration = random.randint(0, 10)


    # Extra features required by training script
    days_since_last_irrigation = random.randint(0, 14)
    crop_stage = random.randint(0, 3)     # encode crop stages as int
    soil_type = random.randint(0, 4)      # encode soil types as int
    rainfall_forecast = round(random.uniform(0, 12), 2)  # mm expected


    record = {
        "soil_moisture": soil_moisture,
        "temperature": temperature,
        "humidity": humidity,
        "lightIntensity": light_intensity,
        "isRaining": is_raining,
        "irrigation_duration": duration,
        "days_since_last_irrigation": days_since_last_irrigation,
        # include alternative key just in case other code expects different name
        "days_since_irrigation": days_since_last_irrigation,
        "crop_stage": crop_stage,
        "soil_type": soil_type,
        "rainfall_forecast": rainfall_forecast
    }
    return record


def push_records(delay=0.15):
    url = f"{BASE_URL}/sensorData.json"
    print(f"Pushing records indefinitely to {url} (delay {delay}s)")
    i = 0
    while True:
        rec = generate_record()
        try:
            r = requests.post(url, json=rec, timeout=10)
            r.raise_for_status()
            key = r.json().get('name')
            i += 1
            print(f"[{i}] pushed key={key} soil={rec['soil_moisture']} irrigation={rec['irrigation_duration']}")
        except Exception as e:
            print(f"[{i}] error pushing record: {e}")
        time.sleep(delay)
    print("Done pushing records.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Firebase RTDB with training records.")
    parser.add_argument("--delay", type=float, default=0.15, help="Seconds between records")
    args = parser.parse_args()
    push_records(delay=args.delay)


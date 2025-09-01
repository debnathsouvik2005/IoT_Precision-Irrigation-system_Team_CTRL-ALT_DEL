import subprocess
import firebase_admin
from firebase_admin import credentials, db

# Initialize Firebase
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://your-project-id-default-rtdb.firebaseio.com/'
})

predictions_ref = db.reference('/predictions')

# --- Sample input data (replace with your sensor readings) ---
ml_input = {
    'sensor_data': {
        'soil_moisture': [25, 30, 28, 32, 27],
        'temperature': 29.5,
        'humidity': 65.0,
        'light_intensity': 850
    },
    'weather_data': {'rainfall_24h': 0},
    'crop_info': {'growth_stage': 3, 'days_since_irrigation': 2, 'soil_type': 2}
}

# Call ML script
result = subprocess.check_output(
    ["python", "irrigation_ML.py", str(ml_input)]
).decode().strip()

# Push prediction to Firebase
predictions_ref.push({
    'prediction': result
})

print("Prediction sent to Firebase:", result)

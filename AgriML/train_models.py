'''import firebase_admin
from firebase_admin import credentials, db

# Initialize Firebase Admin SDK
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://precision-irrigation-dec40-default-rtdb.asia-southeast1.firebasedatabase.app/sensorData.json/'
}'''

# train_models.py
import os
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib

import firebase_admin
from firebase_admin import credentials, db

# Try to import TensorFlow (optional); if not available, LSTM training is skipped.
try:
    import tensorflow as tf
    from tensorflow import keras
    TF_AVAILABLE = True
except Exception:
    TF_AVAILABLE = False
    print("TensorFlow not available — LSTM training will be skipped.")


# ============================
# Firebase admin init - update path to your JSON key if needed
# ============================
SERVICE_KEY_PATH = "serviceAccountKey.json"   # make sure this file is present
DB_URL = "https://precision-irrigation-dec40-default-rtdb.asia-southeast1.firebasedatabase.app"

if not os.path.exists(SERVICE_KEY_PATH):
    raise RuntimeError(f"Missing service account key file: {SERVICE_KEY_PATH}")

cred = credentials.Certificate(SERVICE_KEY_PATH)
firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})


# ============================
# Predictor class
# ============================
class IrrigationPredictor:
    def __init__(self):
        self.rf_model = None
        self.lstm_model = None
        self.scaler = StandardScaler()
        self.feature_columns = [
            'soil_moisture_avg', 'temperature', 'humidity',
            'light_intensity', 'rainfall_forecast', 'days_since_last_irrigation',
            'crop_stage', 'soil_type'
        ]

    def train_random_forest(self, training_data):
        X = training_data[self.feature_columns]
        y = training_data['irrigation_duration']
        n_samples = len(X)
        if n_samples < 5:
            raise RuntimeError(f"Not enough samples for training Random Forest (n={n_samples}). Need >= 5.")
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        self.rf_model = RandomForestRegressor(n_estimators=100, max_depth=10,
                                              random_state=42, min_samples_split=5)
        self.rf_model.fit(X_train_scaled, y_train)

        y_pred = self.rf_model.predict(X_test_scaled)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        print("Random Forest Model Performance:")
        print(f"MSE: {mse:.3f}")
        print(f"R2 Score: {r2:.3f}")

        importance = pd.DataFrame({
            'feature': self.feature_columns,
            'importance': self.rf_model.feature_importances_
        }).sort_values('importance', ascending=False)
        print("\nFeature Importance:")
        print(importance)
        return self.rf_model

    def create_lstm_model(self, sequence_length, n_features):
        model = keras.Sequential([
            keras.Input(shape=(sequence_length, n_features)),
            keras.layers.LSTM(50, return_sequences=True),
            keras.layers.Dropout(0.2),
            keras.layers.LSTM(50, return_sequences=False),
            keras.layers.Dropout(0.2),
            keras.layers.Dense(25),
            keras.layers.Dense(1)
        ])
        model.compile(optimizer='adam', loss='mse', metrics=[tf.keras.metrics.MeanSquaredError()])
        return model

    def prepare_sequences(self, data, sequence_length):
        features = data[self.feature_columns].values
        target = data['irrigation_duration'].values
        X, y = [], []
        for i in range(sequence_length, len(features)):
            X.append(features[i-sequence_length:i])
            y.append(target[i])
        return np.array(X), np.array(y)

    def train_lstm_model(self, time_series_data, sequence_length=24):
        X, y = self.prepare_sequences(time_series_data, sequence_length)
        if len(X) == 0:
            raise RuntimeError("Not enough data to prepare sequences for LSTM.")
        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]
        self.lstm_model = self.create_lstm_model(sequence_length, X.shape[2])

        early_stopping = keras.callbacks.EarlyStopping(monitor='val_loss',
                                                       patience=10,
                                                       restore_best_weights=True)

        self.lstm_model.fit(X_train, y_train, validation_data=(X_test, y_test),
                            epochs=50, batch_size=32,
                            callbacks=[early_stopping], verbose=1)
        return self.lstm_model

    def predict_irrigation_need(self, sensor_data, weather_data=None, crop_info=None):
        """
        sensor_data: dict with keys 'soil_moisture', 'temperature', 'humidity', 'light_intensity' (or lightIntensity)
        weather_data: dict with key 'rainfall_forecast' (optional)
        crop_info: dict with keys 'days_since_last_irrigation', 'crop_stage', 'soil_type' (optional)
        """
        if self.rf_model is None:
            raise RuntimeError("RF model not trained yet.")

        # build a single-row DataFrame with feature_columns
        row = {}
        row['soil_moisture_avg'] = float(sensor_data.get('soil_moisture', np.nan))
        row['temperature'] = float(sensor_data.get('temperature', np.nan))
        row['humidity'] = float(sensor_data.get('humidity', np.nan))
        row['light_intensity'] = float(sensor_data.get('light_intensity', sensor_data.get('lightIntensity', 0)))
        row['rainfall_forecast'] = float((weather_data or {}).get('rainfall_forecast', 0.0))
        row['days_since_last_irrigation'] = float((crop_info or {}).get('days_since_last_irrigation',
                                                                         (crop_info or {}).get('days_since_irrigation', 0.0)))
        row['crop_stage'] = float((crop_info or {}).get('crop_stage', 0.0))
        row['soil_type'] = float((crop_info or {}).get('soil_type', 0.0))

        df_row = pd.DataFrame([row], columns=self.feature_columns)
        X_scaled = self.scaler.transform(df_row)
        pred = self.rf_model.predict(X_scaled)
        return float(pred[0])


# ============================
# Fetching and cleaning data
# ============================
def fetch_firebase_training_data():
    ref = db.reference("sensorData")
    raw = ref.get()

    print("DEBUG: raw from /sensorData =", raw)

    if not raw or not isinstance(raw, dict):
        raise RuntimeError("No data found at '/sensorData'. Verify your database contents and rules.")

    rows = []
    for ts, rec in raw.items():
        # handle lists or single values for moisture
        moisture = rec.get('soil_moisture')
        if isinstance(moisture, list):
            moisture = sum(moisture) / len(moisture) if len(moisture) > 0 else np.nan

        def to_float(val, default=np.nan):
            try:
                if val is None:
                    return default
                return float(val)
            except Exception:
                return default

        rows.append({
            'soil_moisture_avg': to_float(moisture),
            'temperature': to_float(rec.get('temperature')),
            'humidity': to_float(rec.get('humidity')),
            'light_intensity': to_float(rec.get('lightIntensity') or rec.get('light_intensity')),
            'rainfall_forecast': to_float(rec.get('rainfall_forecast', 0.0)),
            'days_since_last_irrigation': to_float(rec.get('days_since_last_irrigation', rec.get('days_since_irrigation', 0))),
            'crop_stage': to_float(rec.get('crop_stage', 0.0)),
            'soil_type': to_float(rec.get('soil_type', 0.0)),
            'irrigation_duration': to_float(rec.get('irrigation_duration')),
        })

    df = pd.DataFrame(rows)
    print("Raw DataFrame shape:", df.shape)
    # ensure numeric coercion
    numeric_cols = ['soil_moisture_avg', 'temperature', 'humidity', 'light_intensity',
                    'rainfall_forecast', 'days_since_last_irrigation', 'crop_stage',
                    'soil_type', 'irrigation_duration']
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')

    # Fill sensible defaults for optional features
    df['rainfall_forecast'] = df['rainfall_forecast'].fillna(0.0)
    df['days_since_last_irrigation'] = df['days_since_last_irrigation'].fillna(0.0)
    df['crop_stage'] = df['crop_stage'].fillna(0.0)
    df['soil_type'] = df['soil_type'].fillna(0.0)
    df['light_intensity'] = df['light_intensity'].fillna(0.0)

    # Drop rows missing essential sensor values or target (irrigation_duration)
    df = df.dropna(subset=['soil_moisture_avg', 'temperature', 'humidity', 'irrigation_duration'])
    print("Cleaned DataFrame shape (after dropping unusable rows):", df.shape)
    return df


# ============================
# Main
# ============================
def main():
    os.makedirs('models', exist_ok=True)
    predictor = IrrigationPredictor()

    print("Fetching real data from Firebase...")
    training_df = fetch_firebase_training_data()
    print(f"Fetched {len(training_df)} usable records.")

    if len(training_df) == 0:
        print("No usable training records found. Run the seeder (seed_data.py) to create labeled records or ensure 'irrigation_duration' exists.")
        return

    try:
        print("Training Random Forest model...")
        predictor.train_random_forest(training_df)

        print("Saving RF model and scaler...")
        joblib.dump(predictor.rf_model, 'models/rf_irrigation_model.pkl')
        joblib.dump(predictor.scaler, 'models/feature_scaler.pkl')

        if TF_AVAILABLE:
            seq_len = 12
            if len(training_df) > seq_len + 1:
                print("\nTraining LSTM model...")
                predictor.train_lstm_model(training_df, sequence_length=seq_len)
                predictor.lstm_model.save('models/lstm_irrigation_model.h5')
                print("LSTM model saved.")
            else:
                print("Not enough data to train LSTM (need > sequence_length + 1). Skipping LSTM.")
        else:
            print("Skipping LSTM training because TensorFlow is not available.")

        # Example RF prediction using last_record:
        last_record = training_df.iloc[-1]
        sensor_data = {
            'soil_moisture': last_record['soil_moisture_avg'],
            'temperature': last_record['temperature'],
            'humidity': last_record['humidity'],
            'light_intensity': last_record['light_intensity']
        }
        weather_data = {'rainfall_forecast': last_record.get('rainfall_forecast', 0.0)}
        crop_info = {
            'growth_stage': last_record.get('crop_stage', 0.0),
            'days_since_last_irrigation': last_record.get('days_since_last_irrigation', 0.0),
            'soil_type': last_record.get('soil_type', 0.0)
        }

        if predictor.rf_model is not None:
            pred = predictor.predict_irrigation_need(sensor_data, weather_data, crop_info)
            print(f"\nExample RF prediction (minutes irrigation): {pred:.2f}")
        else:
            print("RF model not available for example prediction.")

    except Exception as e:
        print("Training failed:", e)


if __name__ == "__main__":
    main()

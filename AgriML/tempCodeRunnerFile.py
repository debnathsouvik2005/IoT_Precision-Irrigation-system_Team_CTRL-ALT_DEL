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

try:
    import tensorflow as tf
    from tensorflow import keras
    TF_AVAILABLE = True
except Exception:
    TF_AVAILABLE = False
    print("TensorFlow not available — LSTM training will be skipped.")


# Initialize Firebase Admin SDK
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://precision-irrigation-dec40-default-rtdb.asia-southeast1.firebasedatabase.app/sensorData.json'
})


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
        print(f"MSE: {mse:.2f}")
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

    def train_lstm_model(self, time_series_data, sequence_length=24):
        X, y = self.prepare_sequences(time_series_data, sequence_length)
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

    def prepare_sequences(self, data, sequence_length):
        features = data[self.feature_columns].values
        target = data['irrigation_duration'].values
        X, y = [], []
        for i in range(sequence_length, len(features)):
            X.append(features[i-sequence_length:i])
            y.append(target[i])
        return np.array(X), np.array(y)


# Function to fetch real data from Firebase Realtime Database
def fetch_firebase_training_data():
    ref = db.reference("sensorData")
    raw = ref.get()
    
    # Debug log: show what raw is
    print("DEBUG: raw from /sensorData =", raw)

    if not raw or not isinstance(raw, dict):
        raise RuntimeError("No data found at '/sensorData'. Verify your database contents and rules.")

    rows = []
    for ts, rec in raw.items():
        moisture = rec.get('soil_moisture')
        if isinstance(moisture, list):
            moisture = sum(moisture) / len(moisture)
        rows.append({
            'soil_moisture_avg': moisture,
            'temperature': rec.get('temperature'),
            'humidity': rec.get('humidity'),
            'light_intensity': rec.get('lightIntensity') or rec.get('light_intensity'),
            'rainfall_forecast': rec.get('rainfall_forecast', 0),
            'days_since_last_irrigation': rec.get('days_since_irrigation'),
            'crop_stage': rec.get('crop_stage'),
            'soil_type': rec.get('soil_type'),
            'irrigation_duration': rec.get('irrigation_duration')
        })

    df = pd.DataFrame(rows)
    df = df.dropna(subset=[
        'soil_moisture_avg', 'temperature', 'humidity',
        'light_intensity', 'rainfall_forecast',
        'days_since_last_irrigation', 'crop_stage',
        'soil_type', 'irrigation_duration'
    ])
    return df



def main():
    os.makedirs('models', exist_ok=True)
    predictor = IrrigationPredictor()

    print("Fetching real data from Firebase...")
    training_df = fetch_firebase_training_data()
    print(f"Fetched {len(training_df)} records.")

    print("Training Random Forest model...")
    predictor.train_random_forest(training_df)

    print("Saving RF model and scaler...")
    joblib.dump(predictor.rf_model, 'models/rf_irrigation_model.pkl')
    joblib.dump(predictor.scaler, 'models/feature_scaler.pkl')

    if TF_AVAILABLE:
        print("\nTraining LSTM model...")
        predictor.train_lstm_model(training_df, sequence_length=12)
        predictor.lstm_model.save('models/lstm_irrigation_model.h5')
        print("LSTM model saved.")
    else:
        print("Skipping LSTM training because TensorFlow is not available.")

    # Example prediction with last record
    last_record = training_df.iloc[-1]
    sensor_data = {
        'soil_moisture': [last_record['soil_moisture_avg']],
        'temperature': last_record['temperature'],
        'humidity': last_record['humidity'],
        'light_intensity': last_record['light_intensity']
    }
    weather_data = {'rainfall_24h': last_record['rainfall_forecast']}
    crop_info = {
        'growth_stage': last_record['crop_stage'],
        'days_since_irrigation': last_record['days_since_last_irrigation'],
        'soil_type': last_record['soil_type']
    }

    prediction = predictor.predict_irrigation_need(sensor_data, weather_data, crop_info)
    print(f"\nExample prediction: {prediction}")


if __name__ == "__main__":
    main()

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
import tensorflow as tf
from tensorflow import keras
import joblib
import requests
import json
from datetime import datetime, timedelta

class IrrigationPredictor:
    def __init__(self):
        self.rf_model = None
        self.lstm_model = None
        self.scaler = StandardScaler()
        self.feature_columns = [
            'soil_moisture_avg', 'temperature', 'humidity',
            'light_intensity', 'rainfall_forecast',
            'days_since_last_irrigation', 'crop_stage', 'soil_type'
        ]

    def prepare_features(self, sensor_data, weather_data, crop_info):
        features = {
            'soil_moisture_avg': np.mean(sensor_data['soil_moisture']),
            'temperature': sensor_data['temperature'],
            'humidity': sensor_data['humidity'],
            'light_intensity': sensor_data['light_intensity'],
            'rainfall_forecast': weather_data.get('rainfall_24h', 0),
            'days_since_last_irrigation': crop_info.get('days_since_irrigation', 1),
            'crop_stage': crop_info.get('growth_stage', 2),
            'soil_type': crop_info.get('soil_type', 2)
        }
        return pd.DataFrame([features])

    def train_random_forest(self, training_data):
        X = training_data[self.feature_columns]
        y = training_data['irrigation_duration']
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        self.rf_model = RandomForestRegressor(
            n_estimators=100, max_depth=10, random_state=42, min_samples_split=5
        )
        self.rf_model.fit(X_train_scaled, y_train)
        y_pred = self.rf_model.predict(X_test_scaled)
        print(f"MSE: {mean_squared_error(y_test, y_pred):.2f}")
        print(f"R2: {r2_score(y_test, y_pred):.3f}")
        return self.rf_model

    def create_lstm_model(self, sequence_length, n_features):
        model = keras.Sequential([
            keras.layers.LSTM(50, return_sequences=True,
                              input_shape=(sequence_length, n_features)),
            keras.layers.Dropout(0.2),
            keras.layers.LSTM(50, return_sequences=False),
            keras.layers.Dropout(0.2),
            keras.layers.Dense(25),
            keras.layers.Dense(1)
        ])
        model.compile(optimizer='adam', loss='mse', metrics=['mae'])
        return model

    def train_lstm_model(self, time_series_data, sequence_length=24):
        X, y = self.prepare_sequences(time_series_data, sequence_length)
        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]
        self.lstm_model = self.create_lstm_model(sequence_length, X.shape[2])
        early = keras.callbacks.EarlyStopping(
            monitor='val_loss', patience=10, restore_best_weights=True
        )
        self.lstm_model.fit(
            X_train, y_train, epochs=100, batch_size=32,
            validation_data=(X_test, y_test), callbacks=[early], verbose=1
        )
        return self.lstm_model

    def prepare_sequences(self, data, sequence_length):
        features = data[self.feature_columns].values
        target = data['irrigation_duration'].values
        X, y = [], []
        for i in range(sequence_length, len(features)):
            X.append(features[i-sequence_length:i])
            y.append(target[i])
        return np.array(X), np.array(y)

    def predict_irrigation_need(self, *, sensor_data, weather_forecast, crop_info):
        df = self.prepare_features(sensor_data, weather_forecast, crop_info)
        scaled = self.scaler.transform(df)
        preds = {}
        if self.rf_model:
            preds['rf'] = max(0, self.rf_model.predict(scaled)[0])
        if preds:
            duration = int(np.mean(list(preds.values())))
            return {
                'irrigation_needed': duration > 5,
                'duration_minutes': duration,
                'confidence': 0.9,
                'recommendations': []
            }
        return None

    def save_models(self, base_path='models/'):
        if self.rf_model:
            joblib.dump(self.rf_model, f'{base_path}rf_irrigation_model.pkl')
            joblib.dump(self.scaler, f'{base_path}feature_scaler.pkl')
        if self.lstm_model:
            self.lstm_model.save(f'{base_path}lstm_irrigation_model.h5')
        print("Models saved")

    def load_models(self, base_path='models/'):
        try:
            self.rf_model = joblib.load(f'{base_path}rf_irrigation_model.pkl')
            self.scaler = joblib.load(f'{base_path}feature_scaler.pkl')
            self.lstm_model = keras.models.load_model(f'{base_path}lstm_irrigation_model.h5')
            print("Models loaded")
        except Exception as e:
            print("Error loading models:", e)


# WeatherService omitted for brevity...


if __name__ == "__main__":
    import sys, ast

    # 1) Instantiate and load models
    predictor = IrrigationPredictor()
    predictor.load_models(base_path="models/")

    # 2) Read input argument
    if len(sys.argv) < 2:
        print("Error: Provide input dict")
        sys.exit(1)
    inp = ast.literal_eval(sys.argv[1])
    sensor = inp.get('sensor_data', {})
    weather = inp.get('weather_data', {})
    crop = inp.get('crop_info', {})

    # 3) Predict and print result
    result = predictor.predict_irrigation_need(
        sensor_data=sensor,
        weather_forecast=weather,
        crop_info=crop
    )
    print(result)

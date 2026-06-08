import pandas as pd
from pymongo import MongoClient
import streamlit as st
import pydeck as pdk
import requests

# =========================
# Secrets
# =========================

MONGO_URI = st.secrets["MONGO_URI"]
WEATHER_KEY = st.secrets["OPENWEATHER_KEY"]

# =========================
# MongoDB
# =========================

@st.cache_resource
def init_connection():
    return MongoClient(MONGO_URI)

client = init_connection()
db = client["flight_tracker"]
collection = db["taiwan_flights"]

# =========================
# Load Data
# =========================

@st.cache_data(ttl=60)
def get_data():
    items = list(collection.find({}, {"_id": 0}))
    df = pd.DataFrame(items)

    if not df.empty and "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values(by="timestamp", ascending=False)

    return df

# =========================
# Weather API
# =========================

@st.cache_data(ttl=1800)
def get_weather(city):

    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={WEATHER_KEY}&units=metric"
    )

    res = requests.get(url)

    if res.status_code != 200:
        return None

    data = res.json()

    return {
        "temp": data["main"]["temp"],
        "humidity": data["main"]["humidity"],
        "wind": data["wind"]["speed"],
        "desc": data["weather"][0]["description"]
    }

# =========================
# Travel Score
# =========================

def travel_score(w):

    score = 100

    if w["temp"] < 10:
        score -= 20
    if w["temp"] > 35:
        score -= 20
    if w["humidity"] > 85:
        score -= 10
    if w["wind"] > 8:
        score -= 15

    return max(score, 0)

# =========================
# UI
# =========================

st.title("✈️ FlightWeather Guide")
st.caption("航班 + 天氣智慧旅遊決策系統")

# 城市選擇
city = st.selectbox(
    "🌏 選擇旅遊目的地",
    ["Taipei", "Tokyo", "Seoul", "Bangkok", "Hong Kong", "Singapore"]
)

weather = get_weather(city)

if st.button("🔄 強制更新資料"):
    st.cache_data.clear()
    st.rerun()

df = get_data()

# =========================
# Weather Panel
# =========================

st.subheader("🌤️ 目的地天氣")

if weather:

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("溫度", f"{weather['temp']} °C")
    c2.metric("濕度", f"{weather['humidity']} %")
    c3.metric("風速", f"{weather['wind']} m/s")
    c4.metric("天氣", weather["desc"])

    score = travel_score(weather)

    st.subheader("🧳 Travel Comfort Score")
    st.progress(score / 100)
    st.metric("舒適度", f"{score}/100")

    st.subheader("📌 旅遊建議")

    advice = []

    if weather["temp"] < 15:
        advice.append("🧥 建議帶外套")

    if weather["humidity"] > 85:
        advice.append("☔ 濕度偏高")

    if weather["wind"] > 8:
        advice.append("💨 風較大")

    if score > 80:
        advice.append("✅ 適合旅遊")

    for a in advice:
        st.write(a)

# =========================
# Flight Dashboard
# =========================

if not df.empty:

    df["altitude"] = pd.to_numeric(df["altitude"], errors="coerce").fillna(0)
    df["velocity"] = pd.to_numeric(df["velocity"], errors="coerce").fillna(0)

    latest_time = df["timestamp"].max()
    latest_df = df[df["timestamp"] == latest_time].copy()

    st.subheader("📊 即時空域指標")

    col1, col2, col3 = st.columns(3)

    col1.metric("航班數", len(latest_df))
    col2.metric("平均速度", round(latest_df["velocity"].mean(), 1))
    col3.metric("最高高度", round(latest_df["altitude"].max(), 1))

    # =========================
    # 3D Map
    # =========================

    st.subheader("📍 3D 空域視覺化")

    def get_color(row):
        if row["altitude"] < 1500 or row["velocity"] < 50:
            return [255, 75, 75, 220]
        return [75, 255, 75, 220]

    latest_df["color"] = latest_df.apply(get_color, axis=1)

    heatmap_layer = pdk.Layer(
        "HeatmapLayer",
        data=df,
        get_position=["longitude", "latitude"],
        opacity=0.3
    )

    column_layer = pdk.Layer(
        "ColumnLayer",
        data=latest_df,
        get_position=["longitude", "latitude"],
        get_elevation="altitude",
        radius=1500,
        elevation_scale=1.5,
        get_fill_color="color",
        pickable=True
    )

    view_state = pdk.ViewState(
        latitude=25.0,
        longitude=121.2,
        zoom=7,
        pitch=45
    )

    deck = pdk.Deck(
        layers=[heatmap_layer, column_layer],
        initial_view_state=view_state,
        map_style="dark",
        tooltip={"text": "航班: {callsign}\n高度: {altitude}\n速度: {velocity}"}
    )

    st.pydeck_chart(deck)

    # =========================
    # Analysis
    # =========================

    st.subheader("📈 歷史分析")

    traffic = df.groupby("timestamp").size().reset_index(name="航班數")

    st.line_chart(traffic, x="timestamp", y="航班數")

    st.subheader("🚀 速度 vs 高度")

    st.scatter_chart(df, x="velocity", y="altitude")

    st.subheader("📋 資料預覽")

    st.dataframe(df.head(20))

else:
    st.warning("資料庫目前沒有資料")

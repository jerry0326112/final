import pandas as pd
from pymongo import MongoClient
import streamlit as st
import pydeck as pdk  
import numpy as np

MONGO_URI = st.secrets["MONGO_URI"]

@st.cache_resource
def init_connection():
    return MongoClient(MONGO_URI)

client = init_connection()
db = client["flight_tracker"]
collection = db["taiwan_flights"]

@st.cache_data(ttl=60)
def get_flight_data():
    items = list(collection.find({}, {"_id": 0}))
    df = pd.DataFrame(items)
    if not df.empty and "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        passenger_airlines = ["EVA", "CAL", "SJX", "MDA", "UIA", "TTW", "CPA", "JAL", "ANA", "THY", "CSC", "CES"]
        df["airline_code"] = df["callsign"].str[:3]
        df = df[df["airline_code"].isin(passenger_airlines)]
    return df

@st.cache_data(ttl=3600)
def get_weather_data():
    # 🌟 修正：將 floor('H') 改為 floor('h')，這是新版 Pandas 的正確寫法
    start_time = pd.Timestamp.now().floor('h') - pd.Timedelta(days=7)
    hours = pd.date_range(start=start_time, periods=168, freq='h')
    
    np.random.seed(42)
    precip = np.random.choice([0, 0, 0, 5, 10], size=168, p=[0.7, 0.1, 0.1, 0.05, 0.05])
    wind = np.random.normal(20, 5, size=168)
    return pd.DataFrame({"time": hours, "precipitation_mm": precip, "wind_speed_kmh": wind})

st.title("✈️ 台灣出入境客機運量與氣候影響分析")

if st.button("🔄 強制獲取最新資料"):
    st.cache_data.clear()
    st.rerun()

df = get_flight_data()
weather_df = get_weather_data()

if not df.empty:
    df["altitude"] = pd.to_numeric(df["altitude"], errors="coerce").fillna(0)
    df["velocity"] = pd.to_numeric(df["velocity"], errors="coerce").fillna(0)

    # 顯示指標
    latest_time = df["timestamp"].max()
    latest_df = df[df["timestamp"] == latest_time].copy()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("當前監測客機數", f"{len(latest_df)} 架")
    col2.metric("平均飛行速度", f"{round(latest_df['velocity'].mean(), 1)} m/s")
    col3.metric("最高飛行海拔", f"{round(latest_df['altitude'].max(), 1)} m")

    st.markdown("---")
    
    # 關聯分析
    st.subheader("⛈️ 天氣對航班運量的衝擊分析")
    
    # 使用 .dt.floor('h') 確保對齊
    df["hour_rounded"] = df["timestamp"].dt.floor("h")
    hourly_flights = df.groupby("hour_rounded").size().reset_index(name="客機架次")
    
    merged_data = pd.merge(hourly_flights, weather_df, left_on="hour_rounded", right_on="time", how="inner")
    
    c1, c2 = st.columns(2)
    c1.scatter_chart(merged_data, x="precipitation_mm", y="客機架次")
    c2.scatter_chart(merged_data, x="wind_speed_kmh", y="客機架次")

    # 3D 地圖
    st.subheader("📍 3D 即時客機監測")
    latest_df['color'] = latest_df.apply(lambda row: [255, 75, 75, 220] if row['altitude'] < 1500 else [75, 255, 75, 220], axis=1)
    
    r = pdk.Deck(
        layers=[pdk.Layer("ColumnLayer", data=latest_df, get_position=["longitude", "latitude"], 
                          get_elevation="altitude", elevation_scale=1.5, radius=1500, get_fill_color="color")],
        initial_view_state=pdk.ViewState(latitude=25.0, longitude=121.2, zoom=7.5, pitch=45),
        map_style="dark"
    )
    st.pydeck_chart(r)

    # 歷史統計
    st.subheader("📈 運量趨勢")
    daily_traffic = df.groupby(df["timestamp"].dt.date).size().reset_index(name="客機數量")
    st.bar_chart(daily_traffic, x="timestamp", y="客機數量")
    
    with st.expander("🔍 查看完整原始資料"):
        st.dataframe(df)
else:
    st.warning("資料庫暫無資料。")

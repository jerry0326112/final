import pandas as pd
from pymongo import MongoClient
import streamlit as st
import pydeck as pdk  
import requests # 🌟 新增：用來呼叫天氣 API

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
        df = df.sort_values(by="timestamp", ascending=False)
        
        # 🌟 核心過濾：只保留「知名客運航空公司」，剔除私人飛機或小飛機
        passenger_airlines = ["EVA", "CAL", "SJX", "MDA", "UIA", "TTW", "CPA", "JAL", "ANA", "THY", "CSC", "CES"]
        df["airline_code"] = df["callsign"].str[:3]
        df = df[df["airline_code"].isin(passenger_airlines)] # 只篩選客機
    return df

@st.cache_data(ttl=3600)
def get_weather_data():
    # 🌟 串接 Open-Meteo 免費氣象 API (桃園機場座標)，抓取過去 7 天到今天的逐小時降雨量與風速
    url = "https://api.open-meteo.com/v1/forecast?latitude=25.0777&longitude=121.2328&past_days=7&hourly=precipitation,windspeed_10m&timezone=Asia%2FTaipei"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        weather_df = pd.DataFrame({
            "time": pd.to_datetime(data["hourly"]["time"]),
            "precipitation_mm": data["hourly"]["precipitation"], # 降雨量
            "wind_speed_kmh": data["hourly"]["windspeed_10m"]    # 風速
        })
        return weather_df
    return pd.DataFrame()

st.title("✈️ 台灣出入境客機運量與氣候影響分析")

# 手動強制更新按鈕
if st.button("🔄 強制獲取最新衛星與氣象資料"):
    st.cache_data.clear() 
    st.rerun()            

df = get_flight_data()
weather_df = get_weather_data()

if not df.empty:
    df["altitude"] = pd.to_numeric(df["altitude"], errors="coerce").fillna(0)
    df["velocity"] = pd.to_numeric(df["velocity"], errors="coerce").fillna(0)

    # 1. 計算平均每天客機量
    df["date"] = df["timestamp"].dt.date
    daily_traffic = df.groupby("date").size().reset_index(name="客機數量")
    avg_daily_flights = int(daily_traffic["客機數量"].mean())

    latest_time = df["timestamp"].max()
    latest_df = df[df["timestamp"] == latest_time].copy()

    st.write(f"目前資料庫共累積 **{len(df)}** 筆商業客機紀錄。透過關聯桃園機場氣象數據，分析天候對航班營運之衝擊。")

    # ==========================================
    # 商業營運指標面板
    # ==========================================
    st.subheader("📊 航班營運與氣象指標")
    
    current_flights = len(latest_df)
    
    # 抓取最新的天氣狀況
    current_weather = "晴朗/多雲"
    if not weather_df.empty:
        latest_weather = weather_df.iloc[-1]
        if latest_weather["precipitation_mm"] > 0:
            current_weather = f"降雨 ({latest_weather['precipitation_mm']}mm)"
        
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="📅 平均每日客機運量", value=f"{avg_daily_flights} 架次")
    with col2:
        st.metric(label="🛰️ 當前監測客機數", value=f"{current_flights} 架次")
    with col3:
        st.metric(label="⛅ 桃園機場當前天候", value=current_weather)

    st.markdown("---")

    # ==========================================
    # 大數據分析區：客機量與天氣的關聯
    # ==========================================
    st.subheader("⛈️ 天氣對航班運量的衝擊分析")
    
    if not weather_df.empty:
        # 將飛機資料轉換為「逐小時」統計
        df["hour_rounded"] = df["timestamp"].dt.floor("H") # 把時間無條件捨去到整點
        hourly_flights = df.groupby("hour_rounded").size().reset_index(name="客機架次")
        
        # 🌟 Data Wrangling 炫技：將航班資料與氣象資料透過「時間」進行合併 (Merge)
        merged_data = pd.merge(hourly_flights, weather_df, left_on="hour_rounded", right_on="time", how="inner")
        
        col_w1, col_w2 = st.columns(2)
        with col_w1:
            st.markdown("**🌧️ 降雨量 vs 客機架次**")
            st.markdown("*(分析降雨是否造成航班延誤或數量減少)*")
            st.scatter_chart(merged_data, x="precipitation_mm", y="客機架次")
            
        with col_w2:
            st.markdown("**💨 風速 vs 客機架次**")
            st.markdown("*(分析強陣風對空域流量的影響)*")
            st.scatter_chart(merged_data, x="wind_speed_kmh", y="客機架次")
    else:
        st.warning("目前無法取得氣象 API 資料。")

    st.markdown("---")

    # ==========================================
    # 歷史趨勢與 3D 地圖
    # ==========================================
    st.subheader("📈 每日出入境客機運量趨勢")
    st.bar_chart(daily_traffic, x="date", y="客機數量")

    st.subheader("📍 3D 即時客機監測與歷史航道熱力圖")
    def get_color(row):
        if row['altitude'] < 1500 or row['velocity'] < 50:
            return [255, 75, 75, 220]  # 起降階段
        else:
            return [75, 255, 75, 220]  # 巡航階段

    latest_df['color'] = latest_df.apply(get_color, axis=1)

    heatmap_layer = pdk.Layer(
        "HeatmapLayer",
        data=df,
        get_position=["longitude", "latitude"],
        opacity=0.4,
        get_weight=1,
        radius_pixels=25,
    )

    column_layer = pdk.Layer(
        "ColumnLayer",
        data=latest_df,
        get_position=["longitude", "latitude"],
        get_elevation="altitude",
        elevation_scale=1.5,
        radius=1500,
        get_fill_color="color",
        pickable=True,
        auto_highlight=True,
    )

    view_state = pdk.ViewState(
        latitude=25.0,
        longitude=121.2,
        zoom=7.5,
        pitch=45,
        bearing=0,
    )

    r = pdk.Deck(
        layers=[heatmap_layer, column_layer],
        initial_view_state=view_state,
        tooltip={"text": "呼號: {callsign}\n高度: {altitude} m\n速度: {velocity} m/s"},
        map_style="dark", 
    )
    st.pydeck_chart(r)

    # 建立可以點開的摺疊區塊
    with st.expander("🔍 點擊展開查看完整原始資料 (包含資料庫所有歷史紀錄)"):
        st.dataframe(df)

else:
    st.warning("目前資料庫還沒有資料喔！等 GitHub 機器人跑完再重整網頁看看。")

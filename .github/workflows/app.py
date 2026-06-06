import pandas as pd
from pymongo import MongoClient
import streamlit as st
import pydeck as pdk  

MONGO_URI = st.secrets["MONGO_URI"]

@st.cache_resource
def init_connection():
    return MongoClient(MONGO_URI)

client = init_connection()
db = client["flight_tracker"]
collection = db["taiwan_flights"]

@st.cache_data(ttl=60)
def get_data():
    items = list(collection.find({}, {"_id": 0}))
    df = pd.DataFrame(items)
    if not df.empty and "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values(by="timestamp", ascending=False)
    return df

st.title("✈️ 北台灣空域監測站")

# 手動強制更新按鈕
if st.button("🔄 強制獲取最新衛星資料"):
    st.cache_data.clear() 
    st.rerun()            

df = get_data()

if not df.empty:
    df["altitude"] = pd.to_numeric(df["altitude"], errors="coerce").fillna(0)
    df["velocity"] = pd.to_numeric(df["velocity"], errors="coerce").fillna(0)

    latest_time = df["timestamp"].max()
    latest_df = df[df["timestamp"] == latest_time].copy()

    st.write(f"目前資料庫總共累積了 **{len(df)}** 筆歷史軌跡，當下為 **{latest_time.strftime('%Y-%m-%d %H:%M:%S')}** 的空域快照！🎉")

    # ==========================================
    # 即時空域指標面板
    # ==========================================
    st.subheader("📊 即時空域指標")
    
    current_flights = len(latest_df)
    avg_velocity = round(latest_df["velocity"].mean(), 1) if not latest_df.empty else 0
    max_altitude = round(latest_df["altitude"].max(), 1) if not latest_df.empty else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="🛰️ 當前監測航班數", value=f"{current_flights} 架次")
    with col2:
        st.metric(label="💨 平均飛行速度", value=f"{avg_velocity} m/s")
    with col3:
        st.metric(label="🏔️ 當前最高海拔", value=f"{max_altitude} m")

    st.markdown("---")

    # ==========================================
    # 3D 實時航班 + 歷史軌跡熱力圖
    # ==========================================
    st.subheader("📍 3D 即時航班與歷史航道熱力圖")
    st.markdown("*(柱體：當下航班位置與高度 |底層霓虹光暈：歷史累積的「空中高速公路」熱區)*")

    def get_color(row):
        if row['altitude'] < 1500 or row['velocity'] < 50:
            return [255, 75, 75, 220]  
        else:
            return [75, 255, 75, 220]  

    latest_df['color'] = latest_df.apply(get_color, axis=1)

    heatmap_layer = pdk.Layer(
        "HeatmapLayer",
        data=df,
        get_position=["longitude", "latitude"],
        opacity=0.35,
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

    st.markdown("---")

    # ==========================================
    # 大數據分析區
    # ==========================================
    st.subheader("📈 歷史大數據趨勢分析")

    col_a, col_b = st.columns(2)
    
    with col_a:
        # 🌟 這裡修改為 Top 10，避免 X 軸太擠導致破圖
        st.markdown("**🏆 熱門航空公司排行 (Top 10)**")
        df["airline"] = df["callsign"].str[:3]
        
        airline_mapping = {
            "EVA": "長榮航空 (EVA)", "CAL": "中華航空 (CAL)", 
            "SJX": "星宇航空 (SJX)", "MDA": "華信航空 (MDA)", 
            "UIA": "立榮航空 (UIA)", "TTW": "台灣虎航 (TTW)",
            "CPA": "國泰航空 (CPA)", "JAL": "日本航空 (JAL)", 
            "ANA": "全日空 (ANA)", "THY": "土耳其航空 (THY)",
            "CSC": "四川航空 (CSC)", "CES": "東方航空 (CES)"
        }
        df["airline_name"] = df["airline"].map(airline_mapping).fillna(df["airline"] + " (其他)")
        
        # 🌟 關鍵修正：只取前 10 名，並且直接將 Series 丟給 bar_chart，它就會乖乖照大小排好
        airline_counts = df["airline_name"].value_counts().head(10)
        st.bar_chart(airline_counts)

    with col_b:
        st.markdown("**⏳ 歷史空域流量趨勢**")
        traffic_trend = df.groupby("timestamp").size().reset_index(name="當下航班數")
        st.line_chart(traffic_trend, x="timestamp", y="當下航班數")

    # 🌟 新增：每日空域尖峰/離峰時段分析
    st.markdown("**⏰ 每日空域尖峰/離峰時段分析**")
    df["hour"] = df["timestamp"].dt.hour
    hourly_traffic = df.groupby("hour").size().reset_index(name="累計架次")
    
    # ==========================================
    # 🌟 關鍵修正：確保 X 軸顯示完整的 24 小時（沒資料的補 0）
    # ==========================================
    # 1. 建立一個包含 0 到 23 小時的完整資料表
    all_hours = pd.DataFrame({"hour": range(24)})
    
    # 2. 把完整的 24 小時跟我們抓到的資料「合併 (merge)」，找不到資料的格子就填上 0 (fillna)
    hourly_traffic = pd.merge(all_hours, hourly_traffic, on="hour", how="left").fillna(0)
    
    # 將數字小時轉換為 00:00 的字串格式，讓 X 軸更美觀
    hourly_traffic["時段"] = hourly_traffic["hour"].astype(int).astype(str).str.zfill(2) + ":00"
    
    # 畫圖
    st.bar_chart(hourly_traffic, x="時段", y="累計架次")

    st.markdown("**🚀 飛行速度與高度關係分析**")
    scatter_data = df.dropna(subset=["altitude", "velocity"])
    st.scatter_chart(scatter_data, x="velocity", y="altitude")

    st.subheader("📋 原始資料預覽")
    st.markdown("*(預設展示最新 10 筆快照)*")
    st.dataframe(df.head(10)) # 畫面上只佔一點點空間

    # 建立可以點開的摺疊區塊
    with st.expander("🔍 點擊展開查看完整原始資料 (包含資料庫所有歷史紀錄)"):
        st.dataframe(df) # 點開後會在這裡顯示整張資料表

else:
    st.warning("目前資料庫還沒有資料喔！等 GitHub 機器人跑完再重整網頁看看。")

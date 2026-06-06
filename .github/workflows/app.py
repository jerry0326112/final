import pandas as pd
from pymongo import MongoClient
import streamlit as st
import pydeck as pdk  # 🌟 導入 3D 與熱力圖套件

MONGO_URI = st.secrets["MONGO_URI"]

@st.cache_resource
def init_connection():
    return MongoClient(MONGO_URI)

client = init_connection()
db = client["flight_tracker"]
collection = db["taiwan_flights"]

# 將快取時間縮短為 60 秒，讓即時性更高
@st.cache_data(ttl=60)
def get_data():
    items = list(collection.find({}, {"_id": 0}))
    df = pd.DataFrame(items)
    if not df.empty and "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values(by="timestamp", ascending=False)
    return df

# 🌟 頂部標題
st.title("✈️ 北台灣空域監測站")

# ==========================================
# 🌟 創意一：手動強制更新按鈕
# ==========================================
if st.button("🔄 強制獲取最新衛星資料"):
    st.cache_data.clear() # 清除 Streamlit 快取
    st.rerun()            # 強制網頁重新整理

df = get_data()

if not df.empty:
    # 資料預處理：確保高度和速度是數值，並把空值補 0
    df["altitude"] = pd.to_numeric(df["altitude"], errors="coerce").fillna(0)
    df["velocity"] = pd.to_numeric(df["velocity"], errors="coerce").fillna(0)

    # 抓出「最新時間點」的一批飛機，用來計算即時 KPI 與畫當下 3D 柱狀體
    latest_time = df["timestamp"].max()
    latest_df = df[df["timestamp"] == latest_time].copy()

    st.write(f"目前資料庫總共累積了 **{len(df)}** 筆歷史軌跡，當下為 **{latest_time.strftime('%Y-%m-%d %H:%M:%S')}** 的空域快照！🎉")

    # ==========================================
    # 即時空域指標面板 (st.metric)
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
    # 🌟 創意二：3D 實時航班 + 歷史軌跡熱力圖（雙圖層）
    # ==========================================
    st.subheader("📍 3D 即時航班與歷史航道熱力圖")
    st.markdown("*(🟢/🔴 柱體：當下航班位置與高度 | 🌟 底層霓虹光暈：歷史累積的「空中高速公路」熱區)*")

    # 判斷當下航班的異常顏色邏輯
    def get_color(row):
        if row['altitude'] < 1500 or row['velocity'] < 50:
            return [255, 75, 75, 220]  # 紅色 (起降中或低速異常)
        else:
            return [75, 255, 75, 220]  # 科技綠 (正常巡航)

    latest_df['color'] = latest_df.apply(get_color, axis=1)

    # 圖層 1：歷史大數據熱力圖層 (使用全部的 df)
    heatmap_layer = pdk.Layer(
        "HeatmapLayer",
        data=df,
        get_position=["longitude", "latitude"],
        opacity=0.35,
        get_weight=1,
        radius_pixels=25,
    )

    # 圖層 2：當下航班的 3D 柱狀圖層 (使用最新時間的 latest_df)
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

    # 設定地圖視角 (傾斜 45 度展現立體感)
    view_state = pdk.ViewState(
        latitude=25.0,
        longitude=121.2,
        zoom=7.5,
        pitch=45,
        bearing=0,
    )

    # 整合雙圖層渲染，並套用內建 dark 樣式
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
    
    # 🌟 創意三：航空公司「中文實名制」解碼排行
    with col_a:
        st.markdown("**🏆 熱門航空公司排行**")
        df["airline"] = df["callsign"].str[:3]
        
        # 航空公司 ICAO 代碼映射字典
        airline_mapping = {
            "EVA": "長榮航空 (EVA)", "CAL": "中華航空 (CAL)", 
            "SJX": "星宇航空 (SJX)", "MDA": "華信航空 (MDA)", 
            "UIA": "立榮航空 (UIA)", "TTW": "台灣虎航 (TTW)",
            "CPA": "國泰航空 (CPA)", "JAL": "日本航空 (JAL)", 
            "ANA": "全日空 (ANA)", "THY": "土耳其航空 (THY)",
            "CSC": "四川航空 (CSC)", "CES": "東方航空 (CES)"
        }
        # 轉換名稱，若不在字典內則顯示原本代號並註記其他
        df["airline_name"] = df["airline"].map(airline_mapping).fillna(df["airline"] + " (其他)")
        
        airline_counts = df["airline_name"].value_counts().reset_index()
        airline_counts.columns = ["航空公司名稱", "航班數量"]
        st.bar_chart(airline_counts, x="航空公司名稱", "航班數量")

    with col_b:
        st.markdown("**⏳ 歷史空域流量趨勢**")
        traffic_trend = df.groupby("timestamp").size().reset_index(name="當下航班數")
        st.line_chart(traffic_trend, x="timestamp", y="當下航班數")

    st.markdown("**🚀 飛行速度與高度關係分析**")
    scatter_data = df.dropna(subset=["altitude", "velocity"])
    st.scatter_chart(scatter_data, x="velocity", y="altitude")

    st.subheader("📋 原始資料預覽 (最新 10 筆)")
    st.dataframe(df.head(10))

else:
    st.warning("目前資料庫還沒有資料喔！等 GitHub 機器人跑完再重整網頁看看。")

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

if st.button("🔄 強制獲取最新衛星資料"):
    st.cache_data.clear() 
    st.rerun()            

df = get_data()

# =====================================================
# 📊 新增：總覽 Dashboard（你原本沒有，我幫你加）
# =====================================================

if not df.empty:

    df["altitude"] = pd.to_numeric(df["altitude"], errors="coerce").fillna(0)
    df["velocity"] = pd.to_numeric(df["velocity"], errors="coerce").fillna(0)

    latest_time = df["timestamp"].max()
    latest_df = df[df["timestamp"] == latest_time].copy()

    st.subheader("📊 即時總覽 Dashboard")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("✈️ 航班數", len(latest_df))
    c2.metric("💨 平均速度", round(latest_df["velocity"].mean(), 1))
    c3.metric("🏔️ 最高高度", round(latest_df["altitude"].max(), 1))
    c4.metric("📦 總資料筆數", len(df))

    st.markdown("---")

    # =====================================================
    # 📍 3D 地圖（保留你的）
    # =====================================================

    st.subheader("📍 3D 即時航班")

    def get_color(row):
        if row['altitude'] < 1500 or row['velocity'] < 50:
            return [255, 75, 75, 220]
        else:
            return [75, 255, 75, 220]

    latest_df['color'] = latest_df.apply(get_color, axis=1)

    layer = pdk.Layer(
        "ColumnLayer",
        data=latest_df,
        get_position=["longitude", "latitude"],
        get_elevation="altitude",
        elevation_scale=1.5,
        radius=1500,
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
        layers=[layer],
        initial_view_state=view_state,
        map_style="dark",
        tooltip={"text": "{callsign}\n{altitude} m\n{velocity} m/s"}
    )

    st.pydeck_chart(deck)

    # =====================================================
    # 📈 強化版數據視覺化（重點）
    # =====================================================

    st.subheader("📈 數據視覺化分析（升級版）")

    tab1, tab2, tab3 = st.tabs(["航班流量", "航空公司", "高度分布"])

    # -------------------------
    # 📊 1. 流量趨勢（升級）
    # -------------------------
    with tab1:

        traffic = df.groupby("timestamp").size().reset_index(name="flights")

        st.line_chart(traffic, x="timestamp", y="flights")

        st.bar_chart(traffic.tail(20).set_index("timestamp"))

    # -------------------------
    # ✈️ 2. 航空公司分布
    # -------------------------
    with tab2:

        df["airline"] = df["callsign"].str[:3]
        airline_counts = df["airline"].value_counts().head(10)

        st.bar_chart(airline_counts)

        st.write("Top 航空公司分布")
        st.dataframe(airline_counts)

    # -------------------------
    # 🏔️ 3. 高度分布（新增）
    # -------------------------
    with tab3:

        st.histogram_chart(df["altitude"])

        st.scatter_chart(df, x="velocity", y="altitude")

    # =====================================================
    # 📋 原始資料
    # =====================================================

    st.subheader("📋 原始資料")

    st.dataframe(df.head(15))

else:
    st.warning("目前資料庫還沒有資料")

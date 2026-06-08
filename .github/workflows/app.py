import pandas as pd
from pymongo import MongoClient
import streamlit as st
import pydeck as pdk
import numpy as np

# =========================
# MongoDB
# =========================

MONGO_URI = st.secrets["MONGO_URI"]

@st.cache_resource
def init_connection():
    return MongoClient(MONGO_URI)

client = init_connection()
db = client["flight_tracker"]
collection = db["taiwan_flights"]

# =========================
# Data Loader
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
# UI
# =========================

st.title("✈️ Flight BI Dashboard")
st.caption("航空空域 BI 分析系統（Streamlit + MongoDB）")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

df = get_data()

# =========================
# Main
# =========================

if not df.empty:

    df["altitude"] = pd.to_numeric(df["altitude"], errors="coerce").fillna(0)
    df["velocity"] = pd.to_numeric(df["velocity"], errors="coerce").fillna(0)

    latest_time = df["timestamp"].max()
    latest_df = df[df["timestamp"] == latest_time].copy()

    # =========================
    # KPI DASHBOARD (BI CORE)
    # =========================

    st.subheader("📊 KPI Dashboard")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("✈️ 即時航班", len(latest_df))
    c2.metric("📦 總資料", len(df))
    c3.metric("💨 平均速度", round(df["velocity"].mean(), 1))
    c4.metric("🏔️ 最高高度", round(df["altitude"].max(), 1))

    st.markdown("---")

    # =========================
    # 3D MAP (你原本保留)
    # =========================

    st.subheader("📍 3D 空域視覺化")

    def get_color(row):
        if row["altitude"] < 1500 or row["velocity"] < 50:
            return [255, 80, 80, 220]
        return [80, 255, 120, 220]

    latest_df["color"] = latest_df.apply(get_color, axis=1)

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
        tooltip={"text": "航班: {callsign}\n高度: {altitude}\n速度: {velocity}"}
    )

    st.pydeck_chart(deck)

    st.markdown("---")

    # =========================
    # BI TABS SYSTEM
    # =========================

    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 流量趨勢",
        "✈️ 航空公司",
        "🏔️ 高度分布",
        "⚡ 關聯分析"
    ])

    # -------------------------
    # TAB 1: TRAFFIC TREND
    # -------------------------

    with tab1:

        st.subheader("航班流量趨勢")

        traffic = df.groupby("timestamp").size().reset_index(name="flights")

        st.line_chart(traffic, x="timestamp", y="flights")

        st.bar_chart(traffic.tail(20).set_index("timestamp"))

    # -------------------------
    # TAB 2: AIRLINES
    # -------------------------

    with tab2:

        st.subheader("航空公司 Top 10")

        df["airline"] = df["callsign"].str[:3]
        airline_counts = df["airline"].value_counts().head(10)

        st.bar_chart(airline_counts)

        st.dataframe(airline_counts)

    # -------------------------
    # TAB 3: ALTITUDE DISTRIBUTION
    # -------------------------

    with tab3:

        st.subheader("高度分布 Histogram")

        hist, bins = np.histogram(df["altitude"], bins=20)

        hist_df = pd.DataFrame({
            "range": [
                f"{int(bins[i])}-{int(bins[i+1])}" for i in range(len(hist))
            ],
            "count": hist
        })

        st.bar_chart(hist_df.set_index("range"))

    # -------------------------
    # TAB 4: CORRELATION
    # -------------------------

    with tab4:

        st.subheader("速度 vs 高度")

        st.scatter_chart(df, x="velocity", y="altitude")

    # =========================
    # STATUS INSIGHT (BI FEATURE)
    # =========================

    st.markdown("---")
    st.subheader("🧠 空域狀態分析")

    avg_speed = df["velocity"].mean()

    if avg_speed < 60:
        st.success("🟢 空域穩定（低流量）")
    elif avg_speed < 120:
        st.warning("🟡 中等流量")
    else:
        st.error("🔴 高流量（繁忙空域）")

    # =========================
    # RAW DATA
    # =========================

    st.subheader("📋 原始資料")

    st.dataframe(df.head(20))

else:
    st.warning("目前資料庫沒有資料")

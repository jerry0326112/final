import pandas as pd
from pymongo import MongoClient
import streamlit as st

MONGO_URI = st.secrets["MONGO_URI"]


@st.cache_resource
def init_connection():
    return MongoClient(MONGO_URI)


client = init_connection()
db = client["flight_tracker"]
collection = db["taiwan_flights"]


@st.cache_data(ttl=600)
def get_data():
    items = list(collection.find({}, {"_id": 0}))
    df = pd.DataFrame(items)
    if not df.empty and "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values(by="timestamp", ascending=False)
    return df


st.title("✈️ 北台灣航班追蹤儀表板")

df = get_data()

if not df.empty:
    st.write(f"目前資料庫中已經累積了 **{len(df)}** 筆航班軌跡紀錄！🎉")

    st.subheader("📍 航班軌跡地圖")
    st.map(df)

    st.subheader("📊 原始資料預覽 (最新 10 筆)")
    st.dataframe(df.head(10))

    st.subheader("📈 航班高度分佈統計")
    df["altitude"] = pd.to_numeric(df["altitude"], errors="coerce")
    chart_data = df.dropna(subset=["altitude"])
    st.bar_chart(chart_data, y="altitude")

    st.subheader("🏆 熱門航空公司排行")
    df["airline"] = df["callsign"].str[:3]
    airline_counts = df["airline"].value_counts().reset_index()
    airline_counts.columns = ["航空公司代碼", "航班數量"]
    st.bar_chart(airline_counts, x="航空公司代碼", y="航班數量")

    st.subheader("🚀 飛行速度與高度關係分析")
    df["velocity"] = pd.to_numeric(df["velocity"], errors="coerce")
    scatter_data = df.dropna(subset=["altitude", "velocity"])
    st.scatter_chart(scatter_data, x="velocity", y="altitude")

    st.subheader("⏳ 歷史空域流量趨勢")
    traffic_trend = (
        df.groupby("timestamp").size().reset_index(name="當下航班數")
    )
    st.line_chart(traffic_trend, x="timestamp", y="當下航班數")

else:
    st.warning("目前資料庫還沒有資料喔！等 GitHub 機器人跑完再重整網頁看看。")

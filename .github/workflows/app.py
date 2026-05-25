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
    return pd.DataFrame(items)


st.title("✈️ 北台灣航班追蹤儀表板")

df = get_data()

if not df.empty:
    st.write(f"目前資料庫中已經累積了 **{len(df)}** 筆航班軌跡紀錄！🎉")

    st.subheader("📍 航班軌跡地圖")
    st.map(df)

    st.subheader("📊 原始資料預覽")
    st.dataframe(df)

    st.subheader("🏢 航空公司航班數量統計")
    df["airline"] = df["callsign"].astype(str).str[:3]
    airline_counts = df["airline"].value_counts()
    st.bar_chart(airline_counts)

else:
    st.warning("目前資料庫還沒有資料喔！等 GitHub 機器人跑完再重整網頁看看。")

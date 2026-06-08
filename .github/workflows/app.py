import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk

# =========================
# MongoDB 設定
# =========================
MONGO_URI = st.secrets["MONGO_URI"]

@st.cache_resource
def init_connection():
    from pymongo import MongoClient
    return MongoClient(MONGO_URI)

client = init_connection()
db = client["flight_tracker"]
collection = db["price_trends"]  # 切換為票價趨勢集合

@st.cache_data(ttl=60)
def get_data():
    items = list(collection.find({}, {"_id": 0}))
    df = pd.DataFrame(items)
    if not df.empty and "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values(by="timestamp", ascending=False)
    return df

# =========================
# UI 介面
# =========================
st.title("✈️ 跨國航線機票價格動態監測看板")
st.markdown("監測台北（TPE）直飛首爾（ICN）與釜山（PUS）之即時票價走勢與訂票決策分析。")

if st.button("🔄 重新整理票價數據"):
    st.cache_data.clear()
    st.rerun()

df = get_data()

# =========================
# Main Dashboard
# =========================
if not df.empty:
    df["price_twd"] = pd.to_numeric(df["price_twd"], errors="coerce").fillna(10000)
    
    # =========================
    # KPI DASHBOARD
    # =========================
    st.subheader("📊 票價核心指標")
    c1, c2, c3, c4 = st.columns(4)
    
    min_price = df["price_twd"].min()
    avg_price = df["price_twd"].mean()
    
    c1.metric("✈️ 已監測航班數", len(df))
    c2.metric("🔥 當前最低票價", f"${min_price:,.0f} TWD")
    c3.metric("💵 市場平均票價", f"${avg_price:,.0f} TWD")
    c4.metric("📈 票價波動指數 (標準差)", f"{round(df['price_twd'].std(), 0)}")

    st.markdown("---")

    # =========================
    # 3D 航線弧線視覺化 (Pydeck ArcLayer)
    # =========================
    st.subheader("📍 跨海航線動態票價弧線")
    st.markdown("_弧線由台北（TPE）出發。綠色代表票價低於均價（推薦購買），紅色代表票價偏高（建議觀望）。_")

    def get_arc_color(row):
        if row["price_twd"] <= avg_price:
            return [40, 255, 120, 200]  # 綠色
        return [255, 80, 80, 200]       # 紅色

    df["color"] = df.apply(get_arc_color, axis=1)

    # 建立高階 3D 弧線圖
    layer = pdk.Layer(
        "ArcLayer",
        data=df,
        get_source_position=["from_lng", "from_lat"],
        get_target_position=["to_lng", "to_lat"],
        get_source_color="color",
        get_target_color="color",
        get_width=4,
        pickable=True
    )

    view_state = pdk.ViewState(
        latitude=29.5,
        longitude=125.0,
        zoom=4.5,
        pitch=50
    )

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style="dark",
        tooltip={"text": "航班: {flight_no}\n航線: {route}\n航空公司: {airline}\n當前票價: ${price_twd} TWD"}
    )
    st.pydeck_chart(deck)

    st.markdown("---")

    # =========================
    # BI TABS SYSTEM
    # =========================
    tab1, tab2, tab3 = st.tabs(["📈 價格歷史趨勢", "✈️ 航空公司比價", "📅 星期幾出發最划算"])

    with tab1:
        st.subheader("票價歷史波動走勢")
        trend_df = df.groupby("timestamp")["price_twd"].min().reset_index()
        st.line_chart(trend_df, x="timestamp", y="price_twd")

    with tab2:
        st.subheader("各大航空公司最低票價對比")
        airline_prices = df.groupby("airline")["price_twd"].min()
        st.bar_chart(airline_prices)

    with tab3:
        st.subheader("出發日（星期幾）與票價關聯分析")
        day_prices = df.groupby("departure_day_of_week")["price_twd"].mean()
        st.bar_chart(day_prices)

    # =========================
    # STATUS INSIGHT
    # = "========================
    st.markdown("---")
    st.subheader("🧠 訂票推薦決策系統")
    
    current_lowest = df.head(1)["price_twd"].values[0] if len(df) > 0 else avg_price
    
    if current_lowest < avg_price * 0.9:
        st.success("🟢 當前票價顯著低於歷史均價！觸發【強烈推薦購買】訊號。")
    elif current_lowest > avg_price * 1.1:
        st.error("🔴 當前票價正處於高點（可能逢旅遊旺季），建議【暫緩觀望】。")
    else:
        st.warning("🟡 票價處於正常合理區間，可依個人行程需求進行訂購。")

    st.subheader("📋 原始票價監測明細")
    st.dataframe(df[["flight_no", "airline", "route", "departure_day_of_week", "price_twd", "timestamp"]])
else:
    st.warning("目前資料庫內尚無票價資料，請先至 MongoDB 寫入數據。")

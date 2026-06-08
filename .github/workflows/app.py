import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import requests

# =========================
# MongoDB 設定
# =========================

MONGO_URI = st.secrets["MONGO_URI"]

@st.cache_resource
def init_connection():
    from pymongo import MongoClient
    return MongoClient(MONGO_URI)

client = init_connection()
# 轉型為旅遊資料庫與集合
db = client["kr_travel"]
collection = db["spots_and_budget"]

# =========================
# Data Loader & 匯率 API 管線
# =========================

@st.cache_data(ttl=3600)
def get_krw_rate():
    """動態串接外部 API 獲取最新台幣對韓元匯率 (1 TWD = X KRW)"""
    try:
        res = requests.get("https://open.er-api.com/v6/latest/TWD", timeout=5)
        data = res.json()
        return round(data["rates"]["KRW"], 2)
    except Exception:
        return 41.50  # 發生異常時的基準安全回報匯率

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

st.title("🇰🇷 韓國雙城動態旅遊與預算看板")
st.markdown("整合首爾、釜山即時旅遊據點、實時匯率計算與費用分析的決策系統。")

if st.button("🔄 重新整理最新情報"):
    st.cache_data.clear()
    st.rerun()

# 獲取基礎數據
df = get_data()
krw_rate = get_krw_rate()

# =========================
# Main Dashboard
# =========================

if not df.empty:

    # 確保關鍵欄位型態正確
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").fillna(4.0)
    df["estimated_cost_twd"] = pd.to_numeric(df["estimated_cost_twd"], errors="coerce").fillna(0)
    
    # 動態特徵工程：依據即時匯率，自動計算出對應的韓元花費
    df["estimated_cost_krw"] = df["estimated_cost_twd"] * krw_rate

    # =========================
    # KPI DASHBOARD (旅遊核心指標)
    # =========================

    st.subheader("📊 旅程核心指標")

    c1, c2, c3, c4 = st.columns(4)

    total_cost_twd = df["estimated_cost_twd"].sum()
    
    c1.metric("📍 已規劃景點", len(df))
    c2.metric("💰 預估總花費 (TWD)", f"${total_cost_twd:,.0f}")
    c3.metric("⭐️ 平均景點評價", f"{round(df['rating'].mean(), 1)} / 5.0")
    c4.metric("💱 即時韓元匯率", f"1 : {krw_rate}")

    st.markdown("---")

    # =========================
    # 3D MAP (雙城地理分佈)
    # =========================

    st.subheader("🗺️ 首爾 / 釜山景點 3D 分佈圖")
    st.markdown("_高度代表該地點的預估花費，顏色區分城市（藍色：首爾，橘紅色：釜山）_")

    def get_color(row):
        # 區分首爾與釜山（例如廣安里一帶）
        if row["city"] == "Seoul":
            return [80, 150, 255, 220]  # 藍色
        return [255, 120, 80, 220]     # 橘紅色

    df["color"] = df.apply(get_color, axis=1)

    # 運用你原本引以為傲的 Pydeck 進行視覺化
    layer = pdk.Layer(
        "ColumnLayer",
        data=df,
        get_position=["longitude", "latitude"],
        get_elevation="estimated_cost_twd",
        elevation_scale=0.5,  # 依預算高度等比例縮放
        radius=300,
        get_fill_color="color",
        pickable=True
    )

    # 設定初始視角中心點為韓國中心地帶
    view_state = pdk.ViewState(
        latitude=36.5,
        longitude=127.5,
        zoom=6.5,
        pitch=45
    )

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style="dark",
        tooltip={
            "text": "地點: {spot_name}\n城市: {city}\n分類: {category}\n預估花費: {estimated_cost_twd} TWD\n當地折合: {estimated_cost_krw:,.0f} KRW\n評價: {rating}⭐"
        }
    )

    st.pydeck_chart(deck)

    st.markdown("---")

    # =========================
    # BI TABS SYSTEM (多維度分析)
    # =========================

    tab1, tab2, tab3, tab4 = st.tabs([
        "💰 預算結構分析",
        "🏙️ 城市景點佔比",
        "⭐️ 評價星級分佈",
        "⚡ 價格 vs 評價關聯"
    ])

    # -------------------------
    # TAB 1: BUDGET ANALYSIS
    # -------------------------
    with tab1:
        st.subheader("各分類預算花費 (TWD)")
        # 依種類（美食、住宿、購物）分組統計花費
        cost_by_cat = df.groupby("category")["estimated_cost_twd"].sum()
        st.bar_chart(cost_by_cat)

    # -------------------------
    # TAB 2: CITIES PROPORTION
    # -------------------------
    with tab2:
        st.subheader("雙城規劃據點數量對比")
        city_counts = df["city"].value_counts()
        st.bar_chart(city_counts)
        st.dataframe(city_counts.rename("景點數量"))

    # -------------------------
    # TAB 3: RATING DISTRIBUTION
    # -------------------------
    with tab3:
        st.subheader("景點星級分佈直方圖")
        hist, bins = np.histogram(df["rating"], bins=5, range=(1, 5))
        
        hist_df = pd.DataFrame({
            "星級區間": [f"{bins[i]}-{bins[i+1]}⭐" for i in range(len(hist))],
            "數量": hist
        })
        st.bar_chart(hist_df.set_index("星級區間"))

    # -------------------------
    # TAB 4: CORRELATION
    # -------------------------
    with tab4:
        st.subheader("預估價格 vs 景點評分關聯性")
        st.markdown("_檢視是不是越貴的餐廳或行程評價就越高_")
        st.scatter_chart(df, x="estimated_cost_twd", y="rating")

    # =========================
    # STATUS INSIGHT (智慧旅遊預算分析)
    # =========================

    st.markdown("---")
    st.subheader("🧠 財務與行程健康度診斷")

    if total_cost_twd < 30000:
        st.success("🟢 預算控制極佳！屬於經濟實惠型充實行程，換匯壓力較低。")
    elif total_cost_twd < 60000:
        st.warning("🟡 預算處於中高水位。提醒你多留意在首爾或釜山商圈的購物刷卡開銷！")
    else:
        st.error("🔴 預算已超出預期警戒線！建議檢視下方的原始清單，適度調整高單價行程或大餐。")

    # =========================
    # RAW DATA
    # =========================

    st.subheader("📋 完整行程規劃明細")
    st.dataframe(df[["spot_name", "city", "category", "rating", "estimated_cost_twd", "estimated_cost_krw"]])

else:
    st.warning("目前資料庫內尚無旅遊行程資料，請先至 MongoDB 寫入數據。")

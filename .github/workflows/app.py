import numpy as np  # 注入地理圍欄數學向量計算
import pandas as pd
from pymongo import MongoClient
import pydeck as pdk
import streamlit as st

MONGO_URI = st.secrets["MONGO_URI"]

# ==========================================
# ⚙️ 地理圍欄參數定義
# ==========================================
AIRPORTS = {
    "桃園國際機場 (TPE)": {"lat": 25.0797, "lon": 121.2342},
    "台北松山機場 (TSA)": {"lat": 25.0697, "lon": 121.5525},
}
GEOFENCE_RADIUS_KM = 15.0  # 地理圍欄半徑 (公里)


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


# ==========================================
# 🧮 地理圍欄核心演算法 (Haversine 半正矢公式)
# ==========================================
def calculate_distance(df, airport_lat, airport_lon):
    """使用 Haversine 公式向量化計算經緯度與機場的距離 (公里)"""
    lon1, lat1 = np.radians(df["longitude"]), np.radians(df["latitude"])
    lon2, lat2 = np.radians(airport_lon), np.radians(airport_lat)

    dlon = lon2 - lon1
    dlat = lat2 - lat1  # ✨ 已修正：將原本的 dlat1 改回 lat1
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    )
    c = 2 * np.arcsin(np.sqrt(a))
    return c * 6371.0  # 地球平均半徑 (公里)


def apply_geofencing(target_df):
    """判定航班屬於哪個機場的圍欄範圍"""
    if target_df.empty:
        target_df["near_airport"] = None
        return target_df

    # 初始化預設欄位
    target_df["near_airport"] = "其它一般空域"

    # 計算到各機場的距離，若小於半徑則歸類給該機場
    for airport_name, coords in AIRPORTS.items():
        dist_col = f"dist_{airport_name}"
        target_df[dist_col] = calculate_distance(
            target_df, coords["lat"], coords["lon"]
        )

        # 滿足半徑內的航班，標記機場標籤
        target_df.loc[
            target_df[dist_col] <= GEOFENCE_RADIUS_KM, "near_airport"
        ] = airport_name

    return target_df


# ==========================================
# 🎨 Streamlit 網頁主體定義
# ==========================================
st.set_page_config(layout="wide")  # 寬螢幕模式讓儀表板大數據排版更美觀
st.title("✈️ 北台灣空域監測站")

# 手動強制更新按鈕
if st.button("🔄 強制獲取最新衛星資料"):
    st.cache_data.clear()
    st.rerun()

df = get_data()

if not df.empty:
    # ------------------------------------------
    # 資料基礎清洗與核心特徵工程
    # ------------------------------------------
    df["altitude"] = pd.to_numeric(df["altitude"], errors="coerce").fillna(0)
    df["velocity"] = pd.to_numeric(df["velocity"], errors="coerce").fillna(0)
    df["hour"] = df["timestamp"].dt.hour

    # 🌟 關鍵注入：進行地理圍欄標籤劃分
    df = apply_geofencing(df)

    latest_time = df["timestamp"].max()
    latest_df = df[df["timestamp"] == latest_time].copy()

    st.write(
        f"目前資料庫總共累積了 **{len(df)}** 筆歷史軌跡，當下為 **{latest_time.strftime('%Y-%m-%d %H:%M:%S')}** 的空域快照！🎉"
    )

    # ==========================================
    # 📊 面板一：即時空域指標面板
    # ==========================================
    st.subheader("📊 即時空域指標")

    current_flights = len(latest_df)
    avg_velocity = (
        round(latest_df["velocity"].mean(), 1) if not latest_df.empty else 0
    )
    max_altitude = (
        round(latest_df["altitude"].max(), 1) if not latest_df.empty else 0
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="🛰️ 當前監測航班數", value=f"{current_flights} 架次")
    with col2:
        st.metric(label="💨 平均飛行速度", value=f"{avg_velocity} m/s")
    with col3:
        st.metric(label="🏔️ 當前最高海拔", value=f"{max_altitude} m")

    st.markdown("---")

    # ==========================================
    # 🏢 面板二：機場地理圍欄起降流量分析 (即時)
    # ==========================================
    st.subheader("🏢 機場地理圍欄起降流量分析")
    st.markdown(
        f"*(分析半徑：核心機場周圍 **{GEOFENCE_RADIUS_KM} 公里** 內的管制空域)*"
    )

    col_tpe, col_tsa = st.columns(2)

    with col_tpe:
        tpe_now = len(
            latest_df[latest_df["near_airport"] == "桃園國際機場 (TPE)"]
        )
        st.metric(label="✈️ 桃園機場 (TPE) 當前起降中", value=f"{tpe_now} 架次")
        if tpe_now > 0:
            tpe_flights = latest_df[
                latest_df["near_airport"] == "桃園國際機場 (TPE)"
            ][["callsign", "altitude", "velocity"]]
            st.dataframe(tpe_flights, use_container_width=True)
        else:
            st.caption("目前無航班處於桃園機場圍欄內。")

    with col_tsa:
        tsa_now = len(
            latest_df[latest_df["near_airport"] == "台北松山機場 (TSA)"]
        )
        st.metric(label="🛩️ 台北松山 (TSA) 當前起降中", value=f"{tsa_now} 架次")
        if tsa_now > 0:
            tsa_flights = latest_df[
                latest_df["near_airport"] == "台北松山機場 (TSA)"
            ][["callsign", "altitude", "velocity"]]
            st.dataframe(tsa_flights, use_container_width=True)
        else:
            st.caption("目前無航班處於松山機場圍欄內。")

    st.markdown("---")

    # ==========================================
    # 📍 面板三：3D 實時航班 + 歷史軌跡熱力圖
    # ==========================================
    st.subheader("📍 3D 即時航班與歷史航道熱力圖")
    st.markdown(
        "*(柱體：當下航班位置與高度 | 底層霓虹光暈：歷史累積的「空中高速公路」熱區)*"
    )

    def get_color(row):
        if row["altitude"] < 1500 or row["velocity"] < 50:
            return [255, 75, 75, 220]  # 紅色：低空/慢速（起降階段）
        else:
            return [75, 255, 75, 220]  # 綠色：正常巡航階段

    latest_df["color"] = latest_df.apply(get_color, axis=1)

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
        tooltip={
            "text": "呼號: {callsign}\n高度: {altitude} m\n速度: {velocity} m/s\n隸屬空域: {near_airport}"
        },
        map_style="dark",
    )

    st.pydeck_chart(r)

    st.markdown("---")

    # ==========================================
    # 📈 面板四：大數據分析區
    # ==========================================
    st.subheader("📈 歷史大數據趨勢分析")

    # 第一組對比：航空公司 vs 總流量趨勢
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**🏆 熱門航空公司排行 (Top 10)**")
        df["airline"] = df["callsign"].str[:3]

        airline_mapping = {
            "EVA": "長榮航空 (EVA)",
            "CAL": "中華航空 (CAL)",
            "SJX": "星宇航空 (SJX)",
            "MDA": "華信航空 (MDA)",
            "UIA": "立榮航空 (UIA)",
            "TTW": "台灣虎航 (TTW)",
            "CPA": "國泰航空 (CPA)",
            "JAL": "日本航空 (JAL)",
            "ANA": "全日空 (ANA)",
            "THY": "土耳其航空 (THY)",
            "CSC": "四川航空 (CSC)",
            "CES": "東方航空 (CES)",
        }
        df["airline_name"] = (
            df["airline"].map(airline_mapping).fillna(df["airline"] + " (其他)")
        )

        airline_counts = df["airline_name"].value_counts().head(10)
        st.bar_chart(airline_counts)

    with col_b:
        st.markdown("**⏳ 歷史空域流量趨勢**")
        traffic_trend = (
            df.groupby("timestamp").size().reset_index(name="當下航班數")
        )
        st.line_chart(traffic_trend, x="timestamp", y="當下航班數")

    # 第二組對比：機場圍欄佔用比率 vs 雙機場 24 小時流量交叉對比
    col_c, col_d = st.columns(2)

    with col_c:
        st.markdown("**📊 歷史累積機場管制空域佔用率**")
        airport_counts = df["near_airport"].value_counts().reset_index()
        airport_counts.columns = ["空域分類", "歷史累積軌跡數"]
        st.bar_chart(airport_counts, x="空域分類", y="歷史累積軌跡數")

    with col_d:
        st.markdown("**⏰ 兩大機場歷史起降尖峰時段對比 (24h)**")
        pure_airports_df = df[df["near_airport"].isin(AIRPORTS.keys())]
        if not pure_airports_df.empty:
            # 建立多欄交叉對比
            airport_hourly = (
                pure_airports_df.groupby(["hour", "near_airport"])
                .size()
                .unstack(fill_value=0)
            )
            # 補齊 24 小時整點刻度
            airport_hourly = airport_hourly.reindex(range(24), fill_value=0)
            airport_hourly.index = [
                f"{str(h).zfill(2)}:00" for h in airport_hourly.index
            ]
            st.line_chart(airport_hourly)
        else:
            st.caption("目前尚無足夠的機場圍欄軌跡資料。")

    # 第三組對比：全空域時段 vs 散佈圖
    col_e, col_f = st.columns(2)

    with col_e:
        st.markdown("**⏰ 每日全空域尖峰/離峰時段分析 (歷史總和)**")
        hourly_traffic = df.groupby("hour").size().reset_index(name="累計架次")
        all_hours = pd.DataFrame({"hour": range(24)})
        hourly_traffic = pd.merge(
            all_hours, hourly_traffic, on="hour", how="left"
        ).fillna(0)
        hourly_traffic["時段"] = (
            hourly_traffic["hour"].astype(int).astype(str).str.zfill(2)
            + ":00"
        )
        st.bar_chart(hourly_traffic, x="時段", y="累計架次")

    with col_f:
        st.markdown("**🚀 全空域飛行速度與高度關係分析**")
        scatter_data = df.dropna(subset=["altitude", "velocity"])
        st.scatter_chart(scatter_data, x="velocity", y="altitude")

    # ==========================================
    # 📋 原始資料預覽
    # ==========================================
    st.markdown("---")
    st.subheader("📋 原始資料預覽")
    st.markdown("*(預設展示最新 10 筆快照，已包含機場距離與歸類欄位)*")
    st.dataframe(df.head(10))

    with st.expander("🔍 點擊展開查看完整原始資料 (包含資料庫所有歷史紀錄)"):
        st.dataframe(df)

else:
    st.warning("目前資料庫還沒有資料喔！等 GitHub 機器人跑完再重整網頁看看。")

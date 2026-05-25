import streamlit as st
import pandas as pd
from pymongo import MongoClient

# 為了在本機快速看到畫面，我們暫時把連線字串貼在這裡 
# (注意：這個檔案等一下"先不要"上傳到 GitHub，我們之後會教你怎麼隱藏密碼部署)
MONGO_URI = "mongodb+srv://jerry0326:x0326147589@cluster0.l27f1ok.mongodb.net/?appName=Cluster0"

# 連線到資料庫
@st.cache_resource # 這個裝飾器可以讓網頁不用每次重整都重新連線資料庫
def init_connection():
    return MongoClient(MONGO_URI)

client = init_connection()
db = client["flight_tracker"]
collection = db["taiwan_flights"]

# 從資料庫抓取資料
@st.cache_data(ttl=600) # 設定資料快取 10 分鐘，避免資料庫超載
def get_data():
    # 抓取所有資料，並排除 MongoDB 自動產生的 '_id' 欄位
    items = list(collection.find({}, {"_id": 0})) 
    return pd.DataFrame(items)

st.title("✈️ 北台灣航班追蹤儀表板")

# 載入資料
df = get_data()

# 確保資料庫裡有資料才畫圖
if not df.empty:
    st.write(f"目前資料庫中已經累積了 **{len(df)}** 筆航班軌跡紀錄！🎉")
    
    # 1. 繪製互動式地圖 (Streamlit 內建功能，會自動抓 latitude 和 longitude 欄位)
    st.subheader("📍 航班軌跡地圖")
    st.map(df)
    
    # 2. 顯示原始資料表
    st.subheader("📊 原始資料預覽")
    st.dataframe(df)
    
else:
    st.warning("目前資料庫還沒有資料喔！等 GitHub 機器人跑完再重整網頁看看。")
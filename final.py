import requests
from pymongo import MongoClient
import datetime
import os  

# 讓程式去系統的「環境變數」裡面找密碼，找不到就報錯
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError("找不到 MONGO_URI，請檢查環境變數設定！")

# 2. 連線到 MongoDB
client = MongoClient(MONGO_URI)
db = client["flight_tracker"]       # 建立/選擇名為 flight_tracker 的資料庫
collection = db["taiwan_flights"]   # 建立/選擇名為 taiwan_flights 的資料表

# 3. 設定北台灣的 Bounding Box (經緯度範圍)
lamin = 24.5  # 最小緯度
lamax = 25.5  # 最大緯度
lomin = 120.5 # 最小經度
lomax = 122.0 # 最大經度

# 組合 API 請求網址
url = f"https://opensky-network.org/api/states/all?lamin={lamin}&lomin={lomin}&lamax={lamax}&lomax={lomax}"

print("📡 正在抓取北台灣上空的航班資料...\n")

try:
    response = requests.get(url)
    
    # 檢查是否成功取得回應
    if response.status_code == 200:
        data = response.json()
        states = data.get('states') 

        if states:
            print(f"✅ 成功抓取！目前共有 {len(states)} 架飛機在該空域。\n")
            
            flight_data_list = [] # 準備一個空列表，用來裝所有飛機的資料
            
            for flight in states:
                # 整理成 MongoDB 需要的「字典 (Dictionary)」格式
                flight_info = {
                    "callsign": flight[1].strip() if flight[1] else "無呼號",
                    "longitude": flight[5],
                    "latitude": flight[6],
                    "altitude": flight[7],
                    "velocity": flight[9],
                    "timestamp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)
                }
                flight_data_list.append(flight_info) # 把這架飛機塞進列表裡
                
                
                print(f"✈️ 呼號: {flight_info['callsign']:8} | 高度: {flight_info['altitude']}m | 速度: {flight_info['velocity']}m/s")
            
            print("-" * 50)
            
            # 4. 最重要的一步：把整個列表的飛機資料，一次寫入 MongoDB！
            collection.insert_many(flight_data_list)
            print("🎉 太棒了！所有資料已成功存入 MongoDB 雲端資料庫！")
            
        else:
            print("⚠️ 目前該 Bounding Box 內沒有抓取到任何航班資料。")
    else:
        print(f"❌ 抓取失敗，HTTP 狀態碼：{response.status_code}")

except Exception as e:
    print(f"發生錯誤：{e}")

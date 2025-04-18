from flask import Flask, request
import json, random, requests, os, time, re
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, QuickReply, 
    QuickReplyButton, MessageAction, FlexSendMessage, LocationMessage, 
    PostbackAction, PostbackEvent, TemplateSendMessage, ButtonsTemplate)

#Azure Translation
from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

#Money
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, timezone, timedelta

#calender
from google.oauth2 import service_account
from googleapiclient.discovery import build
from apscheduler.schedulers.background import BackgroundScheduler

#read env
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
from googleapiclient.discovery import build

random_list=[]
last_msg = ""
memlist = ""

app = Flask(__name__)

# -------- LINE BOT 憑證 --------
access_token = os.getenv("access_token")
channel_secret =  os.getenv("channel_secret")
line_bot_api = LineBotApi(access_token)
line_handler = WebhookHandler(channel_secret)

# 翻譯
API_KEY = os.getenv("API_KEY")
ENDPOINT = os.getenv("ENDPOINT")
REGION = os.getenv("REGION")

# money
def setup_sheets_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    credentials_dict = {
        "type" :"service_account",
        "project_id": os.getenv("project_id_money"),
        "private_key_id": os.getenv("private_key_id_money"),
        "private_key": os.getenv("private_key_money").replace('\\n', '\n'),
        "client_email": os.getenv("client_email_money"),
        "client_id": os.getenv("client_id_money"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": os.getenv("client_x509_cert_url_money"),
        "universe_domain": "googleapis.com"
    }
    

    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(creds)
    return client
sheets_client = setup_sheets_client()
user_data = {}

# -------- 抽籤功能 --------
def foodpush():
    food = TextSendMessage(
        text='食物!',
        quick_reply=QuickReply(
            items=[
                QuickReplyButton(action=MessageAction(label='拉麵', text="拉麵")),
                QuickReplyButton(action=MessageAction(label='咖哩飯', text="咖哩飯")),
                QuickReplyButton(action=MessageAction(label='滷肉飯', text="滷肉飯")),
                QuickReplyButton(action=MessageAction(label='義大利麵', text="義大利麵")),
                QuickReplyButton(action=MessageAction(label='披薩', text="披薩")),
                QuickReplyButton(action=MessageAction(label='鍋燒意麵', text="鍋燒意麵")),
                QuickReplyButton(action=MessageAction(label='燒烤', text="燒烤")),
                QuickReplyButton(action=MessageAction(label='牛肉麵', text="牛肉麵")),
                QuickReplyButton(action=MessageAction(label='鱔魚意麵', text="鱔魚意麵")),
                QuickReplyButton(action=MessageAction(label='牛排', text="牛排")),
            ]
        )
    )
    return food

def drinkpush():
    drink = TextSendMessage(
        text='飲料店!',
        quick_reply=QuickReply(
            items=[
                QuickReplyButton(action=MessageAction(label='五十嵐', text="五十嵐")),
                QuickReplyButton(action=MessageAction(label='珍煮丹', text="珍煮丹")),
                QuickReplyButton(action=MessageAction(label='春水堂', text="春水堂")),
                QuickReplyButton(action=MessageAction(label='鶴茶樓', text="鶴茶樓")),
                QuickReplyButton(action=MessageAction(label='麻古茶坊', text="麻古茶坊")),
                QuickReplyButton(action=MessageAction(label='五桐號', text="五桐號")),
                QuickReplyButton(action=MessageAction(label='迷客夏', text="迷客夏")),
                QuickReplyButton(action=MessageAction(label='CoCo', text="CoCo")),
            ]
        )
    )
    return drink

def listpush():
    plist = TextSendMessage(
        text='推薦清單',
        quick_reply=QuickReply(
            items=[
                QuickReplyButton(action=MessageAction(label='吃的', text="吃什麼")),
                QuickReplyButton(action=MessageAction(label='喝的', text="喝什麼")),
            ]
        )
    )
    return plist

def randomone(tk, msg, last_msg_01, memlist):
    if msg == '開始抽籤吧':
        res = random.choice(random_list)
        line_bot_api.reply_message(tk, TextSendMessage(text='抽選結果為' + res))
        memlist = ""
        last_msg_01 = ""
    elif msg == '清空清單':
        random_list.clear()
        line_bot_api.reply_message(tk, TextSendMessage(text='已清空抽選清單'))
    elif msg == '給我一些想法!':
        line_bot_api.reply_message(tk, listpush())
    elif msg == '吃什麼':
        line_bot_api.reply_message(tk, foodpush())
        memlist = "foodlist"
    elif msg == '喝什麼':
        line_bot_api.reply_message(tk, drinkpush())
        memlist = "drinklist"
    else:
        if memlist == "foodlist":
            random_list.append(msg)
            back_01 = [
                TextSendMessage(text = msg+' 已加入抽選清單 (  OuO)b'),
                foodpush()
                ]
            line_bot_api.reply_message(tk, back_01)
        elif memlist == "drinklist":
            random_list.append(msg)
            back_02 = [
                TextSendMessage(text = msg+' 已加入抽選清單 (  oTo)b'),
                drinkpush()
                ]
            line_bot_api.reply_message(tk, back_02)
        else:
            random_list.append(msg)
    return last_msg_01, memlist

# -------- 天氣查詢功能 --------
def weather(address):
    result = {}
    code = os.getenv('code')
    try:
        urls = [
            f'https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization={code}',
            f'https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001?Authorization={code}'
        ]
        for url in urls:
            req = requests.get(url)
            data = req.json()
            station = data['records']['Station']
            for i in station:
                city = i['GeoInfo']['CountyName']
                area = i['GeoInfo']['TownName']
                key = f'{city}{area}'
                if key not in result:
                    weather = i['WeatherElement']['Weather']
                    temp = i['WeatherElement']['AirTemperature']
                    humid = i['WeatherElement']['RelativeHumidity']
                    result[key] = f'目前天氣：{weather}，溫度 {temp}°C，相對濕度 {humid}%'
    except:
        return "🌧️ 目前無法取得天氣資料"

    try:
        aqi_url = 'https://data.moenv.gov.tw/api/v2/aqx_p_432?api_key=你的 AQI 金鑰&limit=1000&format=JSON'
        req = requests.get(aqi_url)
        data = req.json()
        records = data['records']
        aqi_status = ["良好", "普通", "對敏感族群不健康", "對所有族群不健康", "非常不健康", "危害"]

        for item in records:
            county = item['county']
            sitename = item['sitename']
            aqi = int(item['aqi'])
            status = aqi_status[min(aqi // 50, 5)]
            key = f'{county}{sitename}'
            for k in result:
                if county in k:
                    result[k] += f'\n\nAQI：{aqi}，空氣品質{status}。'
    except:
        pass

    for key, value in result.items():
        if key in address:
            return f'「{address}」\n{value}\n\n🔗 [詳細內容請見中央氣象署官網](https://www.cwa.gov.tw/)'
    return "找不到天氣資訊"

# -------- 翻譯功能 --------
def azure_translate(user_input, to_language):
    if to_language == None:
        return "Please select a language"
    else:
        apikey = os.getenv("API_KEY")
        endpoint = os.getenv("ENDPOINT")
        region = os.getenv("REGION")
        credential = AzureKeyCredential(apikey)
        text_translator = TextTranslationClient(credential=credential, endpoint=endpoint, region=region)
        
        try:
            response = text_translator.translate(body=[user_input], to_language=[to_language])
            print(response)
            translation = response[0] if response else None
            if translation:
                detected_language = translation.detected_language
                result = ''
                if detected_language:
                    print(f"偵測到輸入的語言: {detected_language.language} 信心分數: {detected_language.score}")
                for translated_text in translation.translations:
                    result += f"翻譯成: '{translated_text.to}'\n結果: '{translated_text.text}'"
                return result

        except HttpResponseError as exception:
            if exception.error is not None:
                print(f"Error Code: {exception.error.code}")
                print(f"Message: {exception.error.message}")
                
def chooseLen(tk, msg):
    back_03 = [
        TextSendMessage(text = '請選擇要翻譯的語言:',
        quick_reply = QuickReply(
            items=[
                QuickReplyButton(action=PostbackAction(label="英文",data=f"lang=en&text={msg}",display_text="英文")),
                QuickReplyButton(action=PostbackAction(label="日文",data=f"lang=ja&text={msg}",display_text="日文")),
                QuickReplyButton(action=PostbackAction(label="韓文",data=f"lang=ko&text={msg}",display_text="韓文")),
                QuickReplyButton(action=PostbackAction(label="繁體中文",data=f"lang=zh-Hant&text={msg}",display_text="繁體中文")),
                QuickReplyButton(action=PostbackAction(label="簡體中文",data=f"lang=zh-Hans&text={msg}",display_text="簡體中文")),
                QuickReplyButton(action=PostbackAction(label="文言文",data=f"lang=lzh&text={msg}",display_text="文言文")),
                QuickReplyButton(action=PostbackAction(label="法文",data=f"lang=fr&text={msg}",display_text="法文")),
                QuickReplyButton(action=PostbackAction(label="西班牙文",data=f"lang=es&text={msg}",display_text="西班牙文")),
                QuickReplyButton(action=PostbackAction(label="阿拉伯文",data=f"lang=ar&text={msg}",display_text="阿拉伯文")),
                QuickReplyButton(action=PostbackAction(label="德文",data=f"lang=de&text={msg}",display_text="德文"))
            ]
        ))
    ]
    line_bot_api.reply_message(tk, back_03)
                
# -------- 記帳功能 --------
# 開啟指定的 Google 試算表
sheet = sheets_client.open("python money").sheet1

def choose(num, month_str):
    if num == 1:
        choose = TextSendMessage(
            text='請選擇分類',
            quick_reply=QuickReply(
                items=[
                    QuickReplyButton(action=MessageAction(label='餐飲', text="餐飲")),
                    QuickReplyButton(action=MessageAction(label='交通', text="交通")),
                    QuickReplyButton(action=MessageAction(label='購物', text="購物")),
                    QuickReplyButton(action=MessageAction(label='醫療', text="醫療")),
                    QuickReplyButton(action=MessageAction(label='娛樂', text="娛樂")),
                    QuickReplyButton(action=MessageAction(label='其他', text="其他")),
                ]
            )
            
        )
    elif num == 2:
        choose = TextSendMessage(
            text='請選擇要查詢的分類：',
            quick_reply=QuickReply(
                quick_replies = [
                    QuickReplyButton(action=MessageAction(label='餐飲', text="查 餐飲")),
                    QuickReplyButton(action=MessageAction(label='交通', text="查 交通")),
                    QuickReplyButton(action=MessageAction(label='購物', text="查 購物")),
                    QuickReplyButton(action=MessageAction(label='醫療', text="查 醫療")),
                    QuickReplyButton(action=MessageAction(label='娛樂', text="查 娛樂")),
                    QuickReplyButton(action=MessageAction(label='其他', text="查 其他")),
                ]
            )
        )
    elif num == 3:
        choose = TextSendMessage(
            text='請選擇要查詢的類別：',
            quick_reply=QuickReply(
                quick_replies = [
                    QuickReplyButton(action=MessageAction(label='餐飲', text=f"查詢月類別 {month_str} 餐飲")),
                    QuickReplyButton(action=MessageAction(label='交通', text=f"查詢月類別 {month_str} 交通")),
                    QuickReplyButton(action=MessageAction(label='購物', text=f"查詢月類別 {month_str} 購物")),
                    QuickReplyButton(action=MessageAction(label='醫療', text=f"查詢月類別 {month_str} 醫療")),
                    QuickReplyButton(action=MessageAction(label='娛樂', text=f"查詢月類別 {month_str} 娛樂")),
                    QuickReplyButton(action=MessageAction(label='其他', text=f"查詢月類別 {month_str} 其他")),
                ]
            )
        )
    return choose

def money(tk, msg, user_id):
    if msg in ["餐飲", "交通", "購物","醫療","娛樂", "其他"]:
        if user_id in user_data:  # 確認用戶有先執行「我要記帳」
            user_data[user_id]["category"] = msg
            line_bot_api.reply_message(tk, TextSendMessage(text=f'你選擇了 {msg} 類別，請輸入金額。'))
        else:
            line_bot_api.reply_message(tk, TextSendMessage(text='請先輸入『我要記帳』開始記帳流程。'))
    elif msg.isdigit():  
        if user_id in user_data and user_data[user_id]["category"]:
            user_data[user_id]["amount"] = int(msg)
            category = user_data[user_id]["category"]
            amount = user_data[user_id]["amount"]
            # 將資料寫入 Google Sheets
            tz_utc_8 = timezone(timedelta(hours=8))
            now = datetime.now(tz_utc_8).strftime("%Y-%m-%d %H:%M:%S")
            sheet.append_row([now, user_id, category, amount])

            line_bot_api.reply_message(tk, TextSendMessage(text=f'已記錄 {category}: {amount} 元！'))
            del user_data[user_id]
        else:
            line_bot_api.reply_message(tk, TextSendMessage(text='請先選擇分類'))
    elif msg == "查詢":
        # 從 Google Sheet 讀取所有資料
        records = sheet.get_all_values()
        header = records[0]
        data = records[1:]

        
        user_records = [row for row in data if row[1] == user_id]
        last_five = user_records[-5:]

        if not last_five:
            line_bot_api.reply_message(tk, TextSendMessage(text='目前沒有記帳紀錄。'))
        else:
            reply_lines = ['你最近的記帳紀錄：']
            for row in last_five:
                reply_lines.append(f"{row[0]} - {row[2]}: {row[3]} 元")
            line_bot_api.reply_message(tk, TextSendMessage(text='\n'.join(reply_lines)))
    elif msg == '查詢類別':
        line_bot_api.reply_message(tk, choose(2,''))
        
    elif msg.startswith("查 "):
        
        category_to_check = msg.replace("查 ", "").strip()

        if category_to_check not in ["餐飲", "交通", "購物","醫療","娛樂", "其他"]:
            line_bot_api.reply_message(tk, TextSendMessage(text='請輸入正確的分類（餐飲、交通、娛樂、其他）'))
        else:
            
            records = sheet.get_all_values()[1:]
            
            user_records = [row for row in records if row[1] == user_id and row[2] == category_to_check]
            
            last_five = user_records[-5:]

            if not last_five:
                line_bot_api.reply_message(tk, TextSendMessage(text=f'你在『{category_to_check}』分類中沒有紀錄。'))
            else:
                reply_lines = [f"你在『{category_to_check}』分類的最近紀錄："]
                for row in last_five:
                    reply_lines.append(f"{row[0]}: {row[3]} 元")
                line_bot_api.reply_message(tk, TextSendMessage(text='\n'.join(reply_lines)))
    elif msg.startswith("查詢日期 "):
        
        date_to_check = msg.replace("查詢日期 ", "").strip()

        try:
            
            datetime.strptime(date_to_check, "%Y-%m-%d")
        except ValueError:
            line_bot_api.reply_message(tk, TextSendMessage(text='請使用正確的日期格式（例如：2025-04-01）'))
            return

        
        records = sheet.get_all_values()[1:]  
        user_records = [row for row in records if row[1] == user_id and row[0].startswith(date_to_check)]

        if not user_records:
            line_bot_api.reply_message(tk, TextSendMessage(text=f'你在 {date_to_check} 沒有記帳紀錄。'))
        else:
            total_amount = sum(int(row[3]) for row in user_records if row[3].isdigit())
            reply_lines = [f"{date_to_check} 的記帳紀錄："]
            for row in user_records:
                reply_lines.append(f"{row[2]}：{row[3]} 元")
            reply_lines.append(f"\n💰 總支出：{total_amount} 元")
            line_bot_api.reply_message(tk, TextSendMessage(text='\n'.join(reply_lines)))
    elif msg.startswith("查詢月 "):

         month_to_check = msg.replace("查詢月 ", "").strip()

         try:

            start_date = datetime.strptime(month_to_check, "%Y-%m")
         except ValueError:
            line_bot_api.reply_message(tk, TextSendMessage(text='請使用正確的日期格式（例如：2025-04）'))
            return


         start_of_month = start_date.replace(day=1)  # 該月的起始日期（1日）

         end_of_month = (start_of_month.replace(month=start_of_month.month % 12 + 1) - timedelta(days=1))

         start_of_month_str = start_of_month.strftime("%Y-%m-%d")
         end_of_month_str = end_of_month.strftime("%Y-%m-%d")


         records = sheet.get_all_values()[1:]  # 不要標題列
         user_records = [row for row in records if row[1] == user_id and start_of_month_str <= row[0][:10] <= end_of_month_str]

         if not user_records:
             line_bot_api.reply_message(tk, TextSendMessage(text=f'你在 {start_of_month_str} 到 {end_of_month_str} 期間沒有記帳紀錄。'))
         else:
             total_amount = sum(int(row[3]) for row in user_records if row[3].isdigit())
             reply_lines = [f"你在 {start_of_month_str} 到 {end_of_month_str} 期間的記錄："]
             for row in user_records:
                 reply_lines.append(f"{row[0]} - {row[2]}: {row[3]} 元")
             reply_lines.append(f"\n💰 總支出：{total_amount} 元")
             line_bot_api.reply_message(tk, TextSendMessage(text='\n'.join(reply_lines)))
    elif msg.startswith("查詢月類別 "):
         parts = msg.replace("查詢月類別 ", "").strip().split()


         if len(parts) == 1:
             month_str = parts[0]
             try:
                 datetime.strptime(month_str, "%Y-%m")
             except ValueError:
                 line_bot_api.reply_message(tk, TextSendMessage(text='請使用正確的日期格式（例如：2025-04）'))
                 return
             line_bot_api.reply_message(tk, choose(3,month_str))
             return


         elif len(parts) == 2:
             month_str, category = parts
             try:
                start_date = datetime.strptime(month_str, "%Y-%m")
             except ValueError:
                line_bot_api.reply_message(tk, TextSendMessage(text='請使用正確的日期格式（例如：2025-04）'))
                return


             start_of_month = start_date.replace(day=1)
             if start_of_month.month == 12:
                 next_month = start_of_month.replace(year=start_of_month.year + 1, month=1, day=1)
             else:
                 next_month = start_of_month.replace(month=start_of_month.month + 1, day=1)
             end_of_month = next_month - timedelta(days=1)

             start_str = start_of_month.strftime("%Y-%m-%d")
             end_str = end_of_month.strftime("%Y-%m-%d")


             records = sheet.get_all_values()[1:]  
             filtered = [
                 row for row in records
                 if row[1] == user_id and row[2] == category and start_str <= row[0][:10] <= end_str
                 ]

             if not filtered:
                 line_bot_api.reply_message(tk, TextSendMessage(text=f'{month_str} 在『{category}』分類中沒有記帳紀錄。'))
             else:
                 total_amount = sum(int(row[3]) for row in filtered if row[3].isdigit())
                 reply_lines = [f"{month_str} 在『{category}』分類的記錄："]
                 for row in filtered:
                     reply_lines.append(f"{row[0]}: {row[3]} 元")
                 reply_lines.append(f"\n💰 總支出：{total_amount} 元")
                 line_bot_api.reply_message(tk, TextSendMessage(text='\n'.join(reply_lines)))
    # 其他無效輸入
    
    else:
        line_bot_api.reply_message(tk, TextSendMessage(text='請輸入關鍵字來進行記帳操作\n- 我要記帳\n- 查詢\n- 查詢類別\n- 查詢日期 YYYY-MM-DD\n- 查詢月 YYYY-MM\n- 查詢月類別 YYYY-MM'))

# -------- 查詢附近美食 --------
main_menu = {
    "附近美食": ["1公里內4★以上", "3公里內4.2★以上", "5公里內4.5★以上"],
    "附近景點": ["1公里內3.5★以上", "3公里內4★以上", "5公里內4.2★以上", "10公里內4.5★以上"],
    "各地美食": ["北台灣", "中台灣", "南臺灣", "東台灣"],
    "各地景點": ["北台灣", "中台灣", "南臺灣", "東台灣"]
}

# 台灣縣市與區域的資料
taiwan_counties = {
    "北台灣": ["台北市", "新北市", "基隆市", "桃園市", "新竹市", "新竹縣"],
    "中台灣": ["苗栗縣", "台中市", "彰化縣", "南投縣", "雲林縣"],
    "南台灣": ["嘉義縣", "嘉義市", "台南市", "高雄市", "屏東縣", "澎湖縣"],
    "東台灣": ["宜蘭縣", "花蓮縣", "台東縣"] 
}

def foodie(tk, user_id, result):
    if result[0] in main_menu:
        if result[0] == '附近美食' or result[0] == '附近景點':
            if len(result) == 1:  # 尚未選範圍
                location_ok = 'N'
                if os.path.exists('/tmp/'+user_id+'.txt'):
                    with open('/tmp/'+user_id+'.txt', 'r') as f:
                        line = f.readline()
                        data = line.strip().split(',')
                        old_timestamp = int(data[2])
                    current_timestamp = int(time.time())
                    if current_timestamp - old_timestamp < 600:
                        location_ok = 'Y'
                
                if location_ok == 'Y':                
                    ranges = main_menu[result[0]]
                    buttons_template = ButtonsTemplate(
                        title="選擇範圍", 
                        text="請選擇" + result[0] + "多大的範圍", 
                        actions=[MessageAction(label=range, text=result[0] + " " + range) for range in ranges]
                    )
                    template_message = TemplateSendMessage(alt_text="選擇範圍", template=buttons_template)
                    line_bot_api.reply_message(tk, template_message)
                else:
                    line_bot_api.reply_message(tk, TextSendMessage(text='需要分享你的位置資訊才能進行查詢'))
            else:
                with open('/tmp/'+user_id+'.txt', 'r') as f:
                    line = f.readline()
                    data = line.strip().split(',')
                    latitude = data[0]
                    longitude = data[1]
                if result[0] == '附近美食':
                    type = 'restaurant'    # 餐廳
                else:
                    type = 'tourist_attraction'   # 旅遊景點
                pat = r'(\d+)公里內([\d|.]+)★以上'
                match = re.search(pat,result[1])
                radius = int(match.group(1)) * 1000
                stars = match.group(2)
                API_KEY_foodie = os.getenv('API_KEY_foodie')
                # Google Places API URL
                url = f'https://maps.googleapis.com/maps/api/place/nearbysearch/json'
                pagetoken = None
                target = ''
                cc=0
                while True:
                    # 設定請求的參數
                    params = {
                        'location': f'{latitude},{longitude}',  # 經緯度
                        'radius': radius,  # 半徑，單位是米
                        'type': type,  # 類型設置為餐廳
                    #    'keyword': '美食',  # 關鍵字，這裡你可以設置為美食
                        'language': 'zh-TW',
                        'key': API_KEY_foodie,  # 你的 API 金鑰
                        'rankby': 'prominence',  # prominence:按受歡迎程度排序/distance：按距離排序  
                    #    'opennow': 'true',  # 查詢當前開放的餐廳
                    }
                    if pagetoken:
                        params['pagetoken'] = pagetoken
                    # 發送請求到 Google Places API
                    response = requests.get(url, params=params)
                    # 解析回應的 JSON 數據
                    data = response.json() 
                    cc = cc + 1                    
                    # 取出附近標的物的名稱、地址、評價
                    if data['status'] == 'OK':
                        for place in data['results']:    # name, vicinity, geometry.location(lat,lng), rating, user_ratings_total, price_level, formatted_address
                            name = place['name']
                            address = place.get('vicinity', '無地址')
                            rating = place.get('rating', 0)
                            if rating > float(stars):
                                target += f"【{name}】{rating}★\n{address}\n"
                        #if cc == 1:
                        #    line_bot_api.reply_message(tk,TextSendMessage(text=target))
                        #    return                       
                        pagetoken = data.get('next_page_token')   # 一次20筆，是否有下一頁
                        if not pagetoken:
                            break     # 沒有下一頁，跳出迴圈                  
                        time.sleep(2)   # 有下一頁，等待幾秒鐘（如：2秒鐘以上，避免超過 API 請求限制）
                if target != '':                            
                    line_bot_api.reply_message(tk,TextSendMessage(text=target)) 
                else:
                    print("無法找到" + result[0])

    else:
        buttons_template = ButtonsTemplate(
            title="選擇項目", 
            text="請選擇你要查詢的項目", 
            actions=[MessageAction(label=menu_item, text=menu_item) for menu_item in main_menu.keys()]
        )
        template_message = TemplateSendMessage(alt_text="選擇項目", template=buttons_template)
        line_bot_api.reply_message(tk, template_message)

def location(latitude, longitude, user_id, tk):
    current_timestamp = int(time.time())
    with open('/tmp/'+user_id+'.txt', 'w') as f:
        f.write(f"{latitude},{longitude},{current_timestamp}\n")
    buttons_template = ButtonsTemplate(
        title="選擇項目", 
        text="請選擇你要查詢的項目", 
        actions=[
            MessageAction(label=menu_item, text=menu_item) for menu_item in main_menu.keys()
        ]
    )
    template_message = TemplateSendMessage(alt_text="選擇項目", template=buttons_template)
    line_bot_api.reply_message(tk, template_message)

# -------- 行事曆 --------
USER_ID = os.getenv('USER_ID')

# 服務帳戶的日曆授權
def get_calendar_service():
    calendar_credentials_dict = {
        "type" :"service_account",
        "project_id": os.getenv("project_id"),
        "private_key_id": os.getenv("private_key_id"),
        "private_key": os.getenv("private_key").replace('\\n', '\n'),
        "client_email": os.getenv("client_email"),
        "client_id": os.getenv("client_id"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": os.getenv("client_x509_cert_url"),
        "universe_domain": "googleapis.com"
    }
    calendar_scopes = ['https://www.googleapis.com/auth/calendar']
    credentials = service_account.Credentials.from_service_account_info(
        calendar_credentials_dict, scopes=calendar_scopes)
    calendar_service = build('calendar', 'v3', credentials=credentials)
    return calendar_service
calendar_credentials = get_calendar_service()

# 新增事件
def add_event(summary, start_time, end_time, location=''):
    service = get_calendar_service()
    event = {
        'summary': summary,
        'location': location,
        'start': {'dateTime': start_time, 'timeZone': 'Asia/Taipei'},
        'end': {'dateTime': end_time, 'timeZone': 'Asia/Taipei'},
    }
    service.events().insert(calendarId='primary', body=event).execute()

# 刪除事件
def delete_event_by_keyword(keyword):
    service = get_calendar_service()
    now = datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(calendarId='primary', timeMin=now, maxResults=10).execute()
    for event in events_result.get('items', []):
        if keyword in event['summary']:
            service.events().delete(calendarId='primary', eventId=event['id']).execute()
            return True
    return False

# 查詢今天的事件
def get_today_events():
    service = get_calendar_service()
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0).isoformat() + '+08:00'
    end = now.replace(hour=23, minute=59, second=59).isoformat() + '+08:00'
    events_result = service.events().list(
        calendarId='primary',
        timeMin=start,
        timeMax=end,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])

# 自然語言處理（NLU）來解析意圖
def parse_intent(text):
    if any(kw in text for kw in ['新增', '安排', '有個']):
        return 'add'
    elif any(kw in text for kw in ['刪', '取消', '不要']):
        return 'delete'
    elif any(kw in text for kw in ['查', '有什麼', '行程']):
        return 'query'
    else:
        return 'unknown'

# 提取時間
def extract_datetime(text):
    match = re.search(r'(\d{4}-\d{2}-\d{2})[ ]?(\d{2}:\d{2})?', text)
    if match:
        date_str = match.group(1)
        time_str = match.group(2) or '09:00'
        dt = datetime.strptime(f'{date_str} {time_str}', "%Y-%m-%d %H:%M")
        return dt
    elif '明天' in text:
        dt = datetime.now() + timedelta(days=1)
        return dt.replace(hour=9, minute=0)
    elif '今天' in text:
        dt = datetime.now()
        return dt.replace(hour=9, minute=0)
    return None

# 提取事件信息
def extract_event_info(text):
    dt = extract_datetime(text)
    if dt:
        title = text.split(str(dt.date()))[0].strip()
        return title, dt
    return text, None

# 定時推播行程
def daily_push():
    events = get_today_events()
    if not events:
        msg = "今天沒有安排行程喔～"
    else:
        msg = "今天行程：\n"
        for e in events:
            time = e['start'].get('dateTime', '')[11:16]
            msg += f"- {time} {e['summary']}\n"
    line_bot_api.push_message(USER_ID, TextSendMessage(text=msg))
    
def calender(tk, intent, text):
    if intent == 'add':
        title, dt = extract_event_info(text)
        if dt:
            keyword = text.replace('新增', '').replace('安排', '').strip()
            end = dt + timedelta(hours=1)
            add_event(title, dt.isoformat(), end.isoformat())
            reply = f"已新增行程：{keyword}，新增時間：{dt.strftime('%Y-%m-%d %H:%M')}"
        else:
            reply = "請提供正確的時間格式，例如：'我明天早上9點開會'"
    elif intent == 'query':
        events = get_today_events()
        if events:
            reply = "今天行程：\n" + '\n'.join([f"- {e['start']['dateTime'][11:16]} {e['summary']}" for e in events])
        else:
            reply = "今天沒有行程喔"
    elif intent == 'delete':
        keyword = text.replace('刪除', '').replace('取消', '').strip()
        result = delete_event_by_keyword(keyword)
        reply = f"已刪除「{keyword}」行程" if result else f"找不到包含「{keyword}」的行程"
    else:
        reply = "請說明你想做什麼，例如：\n- 幫我新增明天下午3點開會\n- 查一下今天有什麼行程\n- 取消跟某人的約"

    line_bot_api.reply_message(tk, TextSendMessage(text=reply))    


# 啟動排程
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(daily_push, 'cron', hour=8, minute=0)
    scheduler.start()


# -------- 接收 LINE 訊息 --------
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']        
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        line_handler.handle(body, signature)  
    except:
        print("error, but still work.") 
    return 'OK'


@line_handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global last_msg, memlist, random_list
    msg = event.message.text
    tk = event.reply_token
    user_id = event.source.user_id
    result = msg.split()
    if msg == '抽籤':
        random_list.clear()
        #FlexMessage = json.load(open('random.json','r',encoding='utf-8'))
        #line_bot_api.reply_message(tk, FlexSendMessage('抽籤',FlexMessage))
        line_bot_api.reply_message(tk, TextSendMessage(text='給我一些想法! -> 推薦清單\n清空清單 -> 清單重置\n\n直接輸入文字將加入抽選項目中\n選項都加入完後 輸入開始抽籤吧'))
        last_msg = "random"
    elif msg == '查詢天氣':
        line_bot_api.reply_message(tk, TextSendMessage(text='請傳送位置資訊以查詢天氣與空氣品質'))
        last_msg = "weather"
    elif msg == '翻譯':
        line_bot_api.reply_message(tk, TextSendMessage(text='翻譯功能啟用\n請輸入欲翻譯的文字:'))
        last_msg = "translator"
    elif msg == '我要記帳':
        line_bot_api.reply_message(tk, choose(1,''))
        user_data[user_id] = {"category": None, "amount": None}
        last_msg = "money"
    elif msg == '關閉記帳功能':
        last_msg = ""
    elif msg == '查詢附近美食與景點':
        line_bot_api.reply_message(tk, TextSendMessage(text='請按左下角加號分享你的位置'))
        last_msg = "foodie01"
    elif msg == '行事曆':
        line_bot_api.reply_message(tk, TextSendMessage(text='新增行程/刪除行程/查詢行程'))
        last_msg = "calender"
    elif msg == '關閉行事曆':
        last_msg = ""
    elif last_msg == "random":
        last_msg, memlist = randomone(tk, msg, last_msg, memlist)
    elif last_msg == "translator":
        chooseLen(tk, msg)
        last_msg = ""
    elif last_msg == "money":
        money(tk, msg, user_id)
    elif last_msg == "foodie02":
        foodie(tk, user_id, result)
    elif last_msg == "calender":
        intent = parse_intent(msg)
        calender(tk, intent, msg)
    #print(msg)


@line_handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    global last_msg
    tk = event.reply_token
    address = event.message.address.replace('台', '臺')
    latitude = event.message.latitude
    longitude = event.message.longitude
    user_id = event.source.user_id
    if last_msg == "foodie01":
        location(latitude, longitude, user_id, tk)
        last_msg = "foodie02"
    elif last_msg == "weather":
        line_bot_api.reply_message(tk, TextSendMessage(text=weather(address)))

    
@line_handler.add(PostbackEvent)
def handle_postback(event):
    tk = event.reply_token
    postback_data = event.postback.data
    params = {}
    for param in postback_data.split("&"):
        key, value = param.split("=")
        params[key] = value
    user_input = params.get("text")
    language = params.get("lang")
    result = azure_translate(user_input, language)
    line_bot_api.reply_message(tk, [TextMessage(text=result if result else "No translation available")])

if __name__ == '__main__':
    app.run()
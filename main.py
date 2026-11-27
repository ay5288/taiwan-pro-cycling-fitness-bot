import os, re, json, datetime, urllib.parse, requests
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, FollowEvent, TextMessage, LocationMessage,
    TextSendMessage, FlexSendMessage, BubbleContainer, CarouselContainer,
    BoxComponent, TextComponent, ButtonComponent, URIAction, MessageAction
)

app = FastAPI()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

# ⚠️ 1. 請填入「台灣單車騎行運動健身戰情室資料庫」的 Google Apps Script /exec 網址
GOOGLE_SHEET_API = "https://script.google.com/macros/s/AKfycbzQ-2cmIYBCQ1zlouCudHp8TWfVdhKCg1F3YV95FhAgTFQJpHqKAeGKBpPtUMLgdgaK/exec"
# ⚠️ 2. 請填入這個單車健身機器人的 LINE 官方帳號 ID（包含 @ 符號，例如 @123abcde）
LINE_BOT_BASIC_ID = "@090yvcoe"
# ⚠️ 3. 請填入這個單車健身機器人的 Render 公開網址（結尾不要加斜線）
RENDER_BASE_URL = "https://taiwan-pro-cycling-fitness-bot.onrender.com"
# ⚠️ 4. 可填入您的 Notion 單車安全帽／功率碼表／能量膠／運動水壺嚴選網址（未填自動隱藏）
NOTION_BIKE_SHOP_URL = ""

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

BIKE_FIT_LOGS = [
    {"rec_id": "B101", "mode": "🚴‍♂️ 公路車有氧耐力", "route": "五股微風運河 ➡️ 八里左岸來回", "km": 22.0, "mins": 62, "kcal": 580, "time": "今日早晨"},
    {"rec_id": "B102", "mode": "⛰️ 觀音山爬坡間歇", "route": "五股成泰路 ➡️ 觀音山遊客中心", "km": 15.0, "mins": 58, "kcal": 640, "time": "昨日傍晚"},
    {"rec_id": "B103", "mode": "⚡ 90 RPM 踏頻巡航", "route": "二重環狀自行車道全圈", "km": 20.0, "mins": 52, "kcal": 520, "time": "前日訓練"}
]

PRO_BIKE_ROUTES = [
    {"id": "P1", "tag": "河濱有氧", "name": "五股微風運河 ➡️ 八里渡船頭左岸線", "km": 22.0, "mins": 65, "kcal": 580, "level": "平坦燃脂 ⭐", "toilets": "成蘆橋下公廁、獅子頭山水匯集廣場公廁、關渡橋下公廁、八里渡船頭公廁", "supplies": "微風運河租借站（飲水機/打氣筒）、八里左岸7-11、渡船頭老街補給", "map_q": "五股微風運河自行車道 八里左岸"},
    {"id": "P2", "tag": "踏頻練車", "name": "二重環狀自行車道（大台北都會公園全圈）", "km": 20.0, "mins": 55, "kcal": 520, "level": "零紅綠燈 ⭐⭐", "toilets": "辰光橋下公廁、幸福水漾園區公廁、疏洪追風公園公廁、成蘆橋下公廁", "supplies": "三重/蘆洲/五股租借站（免費飲水機）、重新橋觀光市集補給站", "map_q": "二重環狀自行車道 大台北都會公園"},
    {"id": "P3", "tag": "爬坡挑戰", "name": "五股成泰路 ➡️ 觀音山遊客中心爬坡線", "km": 15.0, "mins": 60, "kcal": 640, "level": "陡坡爬升 ⭐⭐⭐⭐", "toilets": "凌雲禪寺公廁、觀音山遊客中心無障礙乾淨公廁", "supplies": "成泰路起點7-11/全家（務必補滿水壺）、觀音山遊客中心免費飲水機", "map_q": "觀音山遊客中心 凌雲路"},
    {"id": "P4", "tag": "海景耐力", "name": "關渡大橋 ➡️ 淡水金色水岸 ➡️ 漁人碼頭線", "km": 24.0, "mins": 72, "kcal": 630, "level": "海風耐力 ⭐⭐", "toilets": "關渡水岸公園公廁、紅樹林步道公廁、淡水捷運站後方、漁人碼頭公廁", "supplies": "關渡碼頭補給站、淡水老街超商群、漁人碼頭7-11與咖啡廳", "map_q": "關渡水岸公園 淡水漁人碼頭自行車道"},
    {"id": "P5", "tag": "河濱有氧", "name": "大稻埕碼頭 ➡️ 社子島島頭公園環線", "km": 18.5, "mins": 54, "kcal": 485, "level": "夕陽微風 ⭐", "toilets": "大稻埕貨櫃市集公廁、延平河濱公園公廁、社子島島頭公園景觀公廁", "supplies": "大稻埕貨櫃市集、社子大橋下租借站飲水機、延平北路超商", "map_q": "大稻埕碼頭 社子島島頭公園自行車道"},
    {"id": "P6", "tag": "爬坡挑戰", "name": "故宮至善路 ➡️ 陽明山風櫃嘴經典爬坡", "km": 13.0, "mins": 55, "kcal": 610, "level": "北台灣聖地 ⭐⭐⭐⭐⭐", "toilets": "楓林橋旁流動公廁、風櫃嘴涼亭景觀台周邊", "supplies": "至善路底7-11補給站（最後補給點，山上無超商務必備足兩壺水）", "map_q": "風櫃嘴 景觀台"}
]
def get_cycling_wind():
    try:
        u = "https://open-meteo.com"
        cur = requests.get(u, timeout=6).json().get("current", {})
        temp = cur.get("temperature_2m", 22)
        wspd = cur.get("wind_speed_10m", 12)
        wdeg = cur.get("wind_direction_10m", 45)
        dirs = ["北風", "東北風", "東風", "東南風", "南風", "西南風", "西風", "西北風"]
        wdir = dirs[int((wdeg + 22.5) // 45) % 8]
        tip = "往八里淡水方向順風好騎，回程五股注意逆風保留體力！" if "北" in wdir or "東" in wdir else "往五股二重方向順風，去程八里注意逆風配速！"
        return f"🌡️ {temp}°C · 🌬️ {wdir} {wspd} km/h\n💡 騎士建議：{tip}"
    except Exception:
        return "🌡️ 22°C · 🌬️ 微風徐徐，極佳的單車有氧訓練天氣！"

def call_sheet(payload: dict):
    try:
        r = requests.post(GOOGLE_SHEET_API, json=payload, timeout=12)
        return r.json()
    except Exception:
        return {}

def get_user_name(uid: str):
    try:
        return line_bot_api.get_profile(uid).display_name
    except Exception:
        return "單車騎士"

@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"status": "Online", "service": "Taiwan Pro Cycling & Fitness Cockpit App 4.5"}

@app.post("/api/bike_add")
async def web_bike_add(
    mode: str = Form("🚴‍♂️ 公路車有氧耐力"),
    route: str = Form("五股微風運河 ➡️ 八里左岸"),
    km: float = Form(22.0),
    mins: int = Form(60),
    kcal: int = Form(580)
):
    bid = f"B{int(datetime.datetime.utcnow().timestamp() * 1000)}"
    now_t = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%m/%d %H:%M")
    BIKE_FIT_LOGS.insert(0, {
        "rec_id": bid,
        "mode": mode.strip() or "🚴‍♂️ 公路車有氧耐力",
        "route": route.strip() or "河濱單車訓練",
        "km": round(float(km or 0), 1),
        "mins": int(mins or 60),
        "kcal": int(kcal or 580),
        "time": now_t
    })
    call_sheet({
        "action": "add_bike",
        "rec_id": bid,
        "user_id": "web_rider",
        "user_name": "戰情室騎士",
        "mode": mode,
        "route": route,
        "dist_km": km,
        "mins": mins,
        "kcal": kcal
    })
    return RedirectResponse(url="/bike_pro?msg=added", status_code=303)
@app.get("/bike_pro", response_class=HTMLResponse)
def pro_cycling_fitness_cockpit(msg: str = ""):
    S = chr(47)
    logs_json = json.dumps(BIKE_FIT_LOGS, ensure_ascii=False)
    routes_json = json.dumps(PRO_BIKE_ROUTES, ensure_ascii=False)
    tot_km = round(sum(float(x.get("km", 0)) for x in BIKE_FIT_LOGS), 1)
    tot_kcal = sum(int(x.get("kcal", 0)) for x in BIKE_FIT_LOGS)
    tot_mins = sum(int(x.get("mins", 0)) for x in BIKE_FIT_LOGS)
    tot_co2 = round(tot_km * 0.21, 1)
    toast_html = '<div class="toast">🏆 單車訓練數據已同步寫入雲端里程存摺！</div>' if msg == "added" else ""

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no"/>
    <title>🚴‍♂️ 專業單車騎行碼表 ＆ 運動健身戰情室 Pro</title>
    <style>
      * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
      body {{ margin: 0; padding: 0 0 92px 0; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif; background: radial-gradient(circle at top right, #162136, #090C12 62%); color: #F8FAFC; min-height: 100vh; }}
      .topbar {{ background: rgba(9, 12, 18, 0.92); backdrop-filter: blur(18px); padding: 15px 18px; position: sticky; top: 0; z-index: 100; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(56, 189, 248, 0.25); }}
      .topbar h1 {{ margin: 0; font-size: 16px; font-weight: 900; color: #F8FAFC; letter-spacing: 0.4px; }}
      .badge-pro {{ font-size: 11px; background: linear-gradient(135deg, #38BDF8, #F59E0B); color: #090C12; padding: 4px 10px; border-radius: 20px; font-weight: 900; }}
      .wrap {{ max-width: 540px; margin: 0 auto; padding: 14px; }}
      .toast {{ background: rgba(16, 185, 129, 0.2); border: 1px solid #10B981; color: #A7F3D0; padding: 12px; border-radius: 14px; font-size: 13px; font-weight: 700; margin-bottom: 12px; text-align: center; }}
      .kpi-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 14px; }}
      .kpi {{ background: linear-gradient(145deg, rgba(22, 30, 46, 0.9), rgba(14, 19, 30, 0.95)); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 18px; padding: 12px; }}
      .kpi-num {{ font-size: 21px; font-weight: 900; color: #38BDF8; margin-top: 4px; }}
      .card {{ background: rgba(19, 26, 40, 0.88); backdrop-filter: blur(16px); border: 1px solid rgba(255,255,255,0.1); border-radius: 22px; padding: 16px; margin-bottom: 14px; box-shadow: 0 12px 30px rgba(0,0,0,0.45); }}
      .cockpit-box {{ background: linear-gradient(135deg, rgba(56, 189, 248, 0.14), rgba(245, 158, 11, 0.1)); border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 22px; padding: 16px; margin-bottom: 14px; }}
      .speed-big {{ font-size: 42px; font-weight: 900; color: #38BDF8; line-height: 1.1; font-variant-numeric: tabular-nums; }}
      .info-pill {{ background: rgba(9, 13, 22, 0.85); border-left: 3px solid #38BDF8; padding: 8px 10px; border-radius: 10px; font-size: 12px; color: #E2E8F0; margin-top: 8px; line-height: 1.5; }}
      .info-pill.supply {{ border-left-color: #10B981; }}
      .chips {{ display: flex; gap: 8px; overflow-x: auto; padding-bottom: 12px; scrollbar-width: none; }}
      .chip {{ white-space: nowrap; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); color: #CBD5E1; padding: 8px 14px; border-radius: 20px; font-size: 12px; font-weight: 700; cursor: pointer; }}
      .chip.active {{ background: linear-gradient(135deg, #0284C7, #38BDF8); border-color: #BAE6FD; color: #090C12; font-weight: 900; }}
      .btn-row {{ display: flex; gap: 8px; margin-top: 10px; }}
      .btn {{ flex: 1; text-align: center; text-decoration: none; padding: 11px 6px; border-radius: 14px; font-size: 12px; font-weight: 800; cursor: pointer; border: none; color: #fff; }}
      .btn-cyan {{ background: linear-gradient(135deg, #0284C7, #38BDF8); color: #090C12; font-weight: 900; }}
      .btn-gold {{ background: linear-gradient(135deg, #F59E0B, #D97706); color: #090C12; font-weight: 900; }}
      .btn-green {{ background: linear-gradient(135deg, #10B981, #059669); }}
      .btn-glass {{ background: rgba(255,255,255,0.09); color: #E2E8F0; border: 1px solid rgba(255,255,255,0.16); }}
      .field {{ width: 100%; background: rgba(9, 12, 18, 0.92); border: 1px solid rgba(56, 189, 248, 0.25); color: #fff; padding: 12px; border-radius: 12px; font-size: 14px; margin-top: 8px; }}
      .page {{ display: none; }}
      .page.active {{ display: block; }}
      .tabbar {{ position: fixed; bottom: 0; left: 0; right: 0; background: rgba(9, 12, 18, 0.96); backdrop-filter: blur(18px); border-top: 1px solid rgba(56, 189, 248, 0.22); display: flex; padding: 8px 8px 14px; z-index: 120; }}
      .tab {{ flex: 1; text-align: center; color: #94A3B8; font-size: 12px; font-weight: 800; cursor: pointer; padding-top: 4px; }}
      .tab.active {{ color: #38BDF8; }}
      .tab-cta {{ background: linear-gradient(135deg, #38BDF8, #0284C7); color: #090C12; padding: 8px 12px; border-radius: 20px; font-size: 12px; font-weight: 900; }}
    </style></head><body>
    <div class="topbar"><h1>🚴‍♂️ 單車騎行碼表 ＆ 運動健身戰情室</h1><span class="badge-pro">COCKPIT PRO</span></div>
    <div id="page-cockpit" class="page active"><div class="wrap">
      {toast_html}
      <div class="kpi-grid">
        <div class="kpi"><div style="font-size:11px;color:#94A3B8;">🚴‍♂️ 累計單車里程</div><div class="kpi-num">{tot_km} km</div></div>
        <div class="kpi"><div style="font-size:11px;color:#94A3B8;">🔥 累計燃脂大卡</div><div class="kpi-num" style="color:#F87171;">{tot_kcal} kcal</div></div>
        <div class="kpi"><div style="font-size:11px;color:#94A3B8;">⏱️ 累計騎行時間</div><div class="kpi-num" style="color:#FBBF24;">{tot_mins} 分</div></div>
        <div class="kpi"><div style="font-size:11px;color:#94A3B8;">🌱 減碳愛地球</div><div class="kpi-num" style="color:#34D399;">{tot_co2} kg</div></div>
      </div>

      <div class="cockpit-box">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span style="font-size:12px;font-weight:800;color:#7DD3FC;">📟 GPS 專業單車碼表（即時測速/計時）</span>
          <span id="gps-status" style="font-size:11px;color:#FBBF24;font-weight:800;">待命就緒</span>
        </div>
        <div style="display:flex;align-items:baseline;gap:10px;margin-top:8px;">
          <div class="speed-big" id="live-spd">0.0</div>
          <div style="font-size:14px;color:#94A3B8;font-weight:800;">km/h</div>
          <div style="margin-left:auto;text-align:right;">
            <div style="font-size:18px;font-weight:900;color:#FBBF24;" id="live-dist">0.00 km</div>
            <div style="font-size:12px;color:#CBD5E1;" id="live-time">00:00:00 · 0 kcal</div>
          </div>
        </div>
        <div class="btn-row" style="margin-top:12px;">
          <button type="button" class="btn btn-cyan" id="gps-btn" onclick="toggleGps()">▶️ 開始 GPS 碼表計時</button>
          <button type="button" class="btn btn-glass" onclick="resetGps()">🔄 歸零</button>
        </div>
      </div>

      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <div>
            <div style="font-size:15px;font-weight:900;color:#FBBF24;">🎵 單車黃金踏頻節拍器</div>
            <div style="font-size:11px;color:#94A3B8;margin-top:2px;">維持高迴轉速，高效燃脂且保護膝蓋</div>
          </div>
          <button type="button" class="btn btn-gold" id="bpm-btn" style="max-width:125px;" onclick="toggleBpm()">▶️ 90 RPM</button>
        </div>
        <div class="chips" style="margin-top:10px;padding-bottom:0;">
          <div class="chip" onclick="setRpm(70, this)">⛰️ 爬坡 70 RPM</div>
          <div class="chip" onclick="setRpm(80, this)">🚲 巡航 80 RPM</div>
          <div class="chip active" onclick="setRpm(90, this)">⚡ 燃脂 90 RPM</div>
        </div>
      </div>

      <div class="chips">
        <div class="chip active" onclick="filterRoute('all', this)">🗺️ 全部經典單車路線</div>
        <div class="chip" onclick="filterRoute('河濱有氧', this)">🌊 河濱有氧</div>
        <div class="chip" onclick="filterRoute('踏頻練車', this)">⚡ 踏頻練車</div>
        <div class="chip" onclick="filterRoute('爬坡挑戰', this)">⛰️ 爬坡挑戰</div>
      </div>
      <div id="route-box"></div>
    </div></div>
    <div id="page-fit" class="page"><div class="wrap">
      <div class="card">
        <div style="font-size:16px;font-weight:900;color:#38BDF8;margin-bottom:4px;">💓 年齡最大心率 ＆ 5 大燃脂訓練區間精算</div>
        <div style="font-size:12px;color:#94A3B8;">輸入您的年齡，精算 Zone 2 黃金減脂心率區間：</div>
        <div style="display:flex;gap:8px;margin-top:8px;">
          <input id="age-in" type="number" class="field" placeholder="輸入年齡 (如 35)" style="margin-top:0;"/>
          <button type="button" class="btn btn-cyan" style="max-width:110px;" onclick="calcHrZone()">✨ 算心率區間</button>
        </div>
        <div id="hr-res" style="display:none;background:rgba(9,13,22,0.85);padding:12px;border-radius:12px;margin-top:10px;font-size:12px;line-height:1.7;color:#E2E8F0;border-left:3px solid #38BDF8;"></div>
      </div>

      <div class="card">
        <div style="font-size:16px;font-weight:900;color:#FBBF24;margin-bottom:4px;">🛞 單車前後輪建議胎壓 PSI 精算器</div>
        <div style="display:flex;gap:8px;margin-top:8px;">
          <input id="rider-w" type="number" class="field" placeholder="騎士體重 kg (如 68)" style="margin-top:0;"/>
          <select id="tire-w" class="field" style="margin-top:0;">
            <option value="25">公路車 700x25c</option>
            <option value="28" selected>公路車 700x28c</option>
            <option value="35">小折 / 礫石車 35c</option>
          </select>
        </div>
        <button type="button" class="btn btn-gold" style="width:100%;margin-top:10px;" onclick="calcPsi()">⚡ 精算前後輪胎壓 PSI</button>
        <div id="psi-res" style="display:none;background:rgba(9,13,22,0.85);padding:12px;border-radius:12px;margin-top:10px;font-size:12px;color:#FEF3C7;border-left:3px solid #F59E0B;"></div>
      </div>

      <div class="card">
        <div style="font-size:16px;font-weight:900;color:#34D399;margin-bottom:4px;">🥤 騎行後蛋白質 ＆ 電解質營養精算器</div>
        <div style="font-size:12px;color:#94A3B8;">輸入本次騎行公里數與體重，精算超商增肌減脂黃金修復餐：</div>
        <div style="display:flex;gap:8px;margin-top:8px;">
          <input id="nut-km" type="number" class="field" placeholder="騎行 km (如 25)" style="margin-top:0;"/>
          <input id="nut-w" type="number" class="field" placeholder="體重 kg (如 68)" style="margin-top:0;"/>
        </div>
        <button type="button" class="btn btn-green" style="width:100%;margin-top:10px;" onclick="calcNutrition()">🥗 精算運動後蛋白質 ＆ 電解質</button>
        <div id="nut-res" style="display:none;background:rgba(9,13,22,0.88);padding:12px;border-radius:12px;margin-top:10px;font-size:12px;line-height:1.7;color:#D1FAE5;border-left:3px solid #10B981;"></div>
      </div>
    </div></div>

    <div id="page-logs" class="page"><div class="wrap">
      <div class="card">
        <div style="font-size:16px;font-weight:900;color:#38BDF8;margin-bottom:4px;">➕ 寫入今日單車運動健身訓練日誌</div>
        <form action="{S}api{S}bike_add" method="post">
          <select name="mode" class="field">
            <option value="🚴‍♂️ 公路車有氧耐力">🚴‍♂️ 公路車有氧耐力（約 26 kcal/km）</option>
            <option value="⚡ 90 RPM 踏頻燃脂">⚡ 90 RPM 踏頻燃脂（約 28 kcal/km）</option>
            <option value="⛰️ 山道爬坡間歇訓練">⛰️ 山道爬坡間歇訓練（約 40 kcal/km）</option>
          </select>
          <input name="route" class="field" placeholder="📍 騎行路線（如：五股微風運河 ➡️ 八里左岸）" required/>
          <input name="km" type="number" step="0.1" class="field" placeholder="📏 總騎行公里數（如：22.0）" required/>
          <input name="mins" type="number" class="field" placeholder="⏱️ 總騎行分鐘數（如：60）" value="60"/>
          <input name="kcal" type="number" class="field" placeholder="🔥 消耗大卡（如：580）" value="580"/>
          <button type="submit" class="btn btn-cyan" style="width:100%;margin-top:12px;padding:14px;">🏆 同步至雲端單車里程存摺</button>
        </form>
      </div>
      <div id="log-box"></div>
    </div></div>

    <div class="tabbar">
      <div class="tab active" onclick="switchTab('cockpit', this)">📟 碼表與路線</div>
      <div class="tab" onclick="switchTab('fit', this)">💓 心率與營養</div>
      <div class="tab" onclick="switchTab('logs', this)"><span class="tab-cta">🏆 訓練日誌</span></div>
    </div>
    <script>
      const ROUTES = {routes_json};
      const LOGS = {logs_json};
      let curTag = 'all';
      let curRpm = 90, bpmTimer = null, audioCtx = null;
      let gpsWatch = null, secTimer = null, elapsedSec = 0, totalDist = 0, lastPos = null;

      function calcHaversine(lat1, lon1, lat2, lon2) {{
        const R = 6371, dLat = (lat2 - lat1) * Math.PI / 180, dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLon/2)**2;
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
      }}

      function toggleGps() {{
        const btn = document.getElementById('gps-btn');
        const st = document.getElementById('gps-status');
        if (gpsWatch !== null) {{
          navigator.geolocation.clearWatch(gpsWatch);
          clearInterval(secTimer);
          gpsWatch = null;
          btn.innerText = '▶️ 繼續 GPS 碼表計時';
          st.innerText = '已暫停計時';
          return;
        }}
        if (!navigator.geolocation) {{ st.innerText = '瀏覽器不支援 GPS'; return; }}
        btn.innerText = '⏸️ 暫停碼表';
        st.innerText = '🛰️ GPS 衛星追蹤中...';
        secTimer = setInterval(() => {{
          elapsedSec++;
          const hh = String(Math.floor(elapsedSec/3600)).padStart(2,'0');
          const mm = String(Math.floor((elapsedSec%3600)/60)).padStart(2,'0');
          const ss = String(elapsedSec%60).padStart(2,'0');
          const kcal = Math.round(totalDist * 26);
          document.getElementById('live-time').innerText = `${{hh}}:${{mm}}:${{ss}} · ${{kcal}} kcal`;
        }}, 1000);
        gpsWatch = navigator.geolocation.watchPosition(pos => {{
          const lat = pos.coords.latitude, lon = pos.coords.longitude;
          const spd = pos.coords.speed ? (pos.coords.speed * 3.6) : 0;
          if (lastPos) {{
            const d = calcHaversine(lastPos.lat, lastPos.lon, lat, lon);
            if (d > 0.003 && d < 0.5) totalDist += d;
          }}
          lastPos = {{lat, lon}};
          document.getElementById('live-spd').innerText = spd.toFixed(1);
          document.getElementById('live-dist').innerText = totalDist.toFixed(2) + ' km';
        }}, err => {{ st.innerText = '請開啟手機定位權限'; }}, {{enableHighAccuracy: true}});
      }}

      function resetGps() {{
        if (gpsWatch !== null) toggleGps();
        elapsedSec = 0; totalDist = 0; lastPos = null;
        document.getElementById('live-spd').innerText = '0.0';
        document.getElementById('live-dist').innerText = '0.00 km';
        document.getElementById('live-time').innerText = '00:00:00 · 0 kcal';
        document.getElementById('gps-btn').innerText = '▶️ 開始 GPS 碼表計時';
        document.getElementById('gps-status').innerText = '已歸零待命';
      }}

      function setRpm(val, el) {{
        curRpm = val;
        document.querySelectorAll('#page-cockpit .card .chip').forEach(x => x.classList.remove('active'));
        el.classList.add('active');
        if (bpmTimer) {{ toggleBpm(); toggleBpm(); }}
      }}

      function toggleBpm() {{
        const btn = document.getElementById('bpm-btn');
        if (bpmTimer) {{ clearInterval(bpmTimer); bpmTimer = null; btn.innerText = '▶️ ' + curRpm + ' RPM'; return; }}
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        btn.innerText = '⏸️ 停止';
        const ms = Math.round(60000 / (curRpm * 2));
        bpmTimer = setInterval(() => {{
          const osc = audioCtx.createOscillator(), gain = audioCtx.createGain();
          osc.frequency.value = 920;
          gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.08);
          osc.connect(gain); gain.connect(audioCtx.destination);
          osc.start(); osc.stop(audioCtx.currentTime + 0.09);
        }}, ms);
      }}

      function calcHrZone() {{
        const age = Number(document.getElementById('age-in').value || 35);
        const maxHr = Math.round(208 - 0.7 * age);
        const z2Low = Math.round(maxHr * 0.6), z2High = Math.round(maxHr * 0.7);
        const z3High = Math.round(maxHr * 0.8), z4High = Math.round(maxHr * 0.9);
        const box = document.getElementById('hr-res');
        box.style.display = 'block';
        box.innerHTML = `💓 預估最大心率：<b>${{maxHr}} bpm</b><br>🔥 <b>Zone 2 黃金燃脂區：${{z2Low}} ~ ${{z2High}} bpm</b>（減脂最有效！）<br>⚡ Zone 3 有氧心肺區：${{z2High}} ~ ${{z3High}} bpm<br>🚀 Zone 4 無氧衝刺區：${{z3High}} ~ ${{z4High}} bpm`;
      }}

      function calcPsi() {{
        const w = Number(document.getElementById('rider-w').value || 68);
        const t = Number(document.getElementById('tire-w').value || 28);
        let front = 75, rear = 80;
        if (t === 25) {{ front = Math.round(80 + (w - 65) * 0.6); rear = front + 5; }}
        else if (t === 28) {{ front = Math.round(68 + (w - 65) * 0.5); rear = front + 5; }}
        else {{ front = Math.round(52 + (w - 65) * 0.4); rear = front + 4; }}
        const box = document.getElementById('psi-res');
        box.style.display = 'block';
        box.innerText = `🛞 建議前輪胎壓：${{front}} PSI · 後輪胎壓：${{rear}} PSI（兼顧抓地力與滾動速度！）`;
      }}

      function calcNutrition() {{
        const km = Number(document.getElementById('nut-km').value || 25);
        const w = Number(document.getElementById('nut-w').value || 68);
        const mins = Math.round(km * 2.8);
        const pro = Math.round(w * (km >= 30 ? 0.35 : 0.25));
        const carb = Math.round(w * (km >= 30 ? 0.8 : 0.5));
        const water = Math.round(mins * 11 + 300);
        const box = document.getElementById('nut-res');
        box.style.display = 'block';
        box.innerHTML = `🥗 <b>騎行 ${{km}} km 黃金 30 分鐘修復營養處方：</b><br>• 🥩 優質蛋白質：<b>${{pro}} g</b>（約無糖豆漿 1 瓶 ＋ 茶葉蛋 2 顆）<br>• 🍌 肝醣回補碳水：<b>${{carb}} g</b>（約中型香蕉 1 根或地瓜 1 條）<br>• 💧 防抽筋水分／電解質：<b>${{water}} ml</b>（含鈉鉀電解質飲）`;
      }}

      function filterRoute(tag, el) {{
        curTag = tag;
        document.querySelectorAll('#page-cockpit > .wrap > .chips .chip').forEach(x => x.classList.remove('active'));
        el.classList.add('active');
        renderRoutes();
      }}

      function renderRoutes() {{
        const list = ROUTES.filter(r => curTag === 'all' || r.tag === curTag);
        document.getElementById('route-box').innerHTML = list.map(r => {{
          const navU = `https:{S}{S}://google.com{S}?q=${{encodeURIComponent(r.map_q)}}`;
          const wcU = `https:{S}{S}://google.com{S}?q=${{encodeURIComponent(r.name.split(' ') + ' 公廁')}}`;
          const supU = `https:{S}{S}://google.com{S}?q=${{encodeURIComponent(r.name.split(' ') + ' 飲水機 便利商店')}}`;
          return `<div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span style="font-size:11px;font-weight:800;color:#38BDF8;background:rgba(56,189,248,0.15);padding:3px 9px;border-radius:8px;">${{r.tag}} · ${{r.level}}</span>
              <span style="font-size:13px;font-weight:900;color:#FBBF24;">📏 ${{r.km}} km · ${{r.mins}} 分</span>
            </div>
            <div style="font-size:17px;font-weight:900;color:#fff;margin-top:6px;">${{r.name}}</div>
            <div style="font-size:12px;color:#F87171;font-weight:700;margin-top:4px;">🔥 預估燃脂：約 ${{r.kcal}} kcal（減碳 ${{Math.round(r.km*0.21*10)/10}} kg）</div>
            <div class="info-pill"><b>🚻 沿途公廁：</b>${{r.toilets}}</div>
            <div class="info-pill supply"><b>💧 飲水補給：</b>${{r.supplies}}</div>
            <div class="btn-row">
              <a class="btn btn-cyan" href="${{navU}}" target="_blank">🗺️ 路線導航</a>
              <a class="btn btn-glass" href="${{wcU}}" target="_blank">🚻 沿途廁所</a>
              <a class="btn btn-green" href="${{supU}}" target="_blank">💧 飲水補給</a>
            </div>
          </div>`;
        }}).join('');
      }}

      function renderLogs() {{
        document.getElementById('log-box').innerHTML = LOGS.map(x => `<div class="card">
          <div style="display:flex;justify-content:space-between;"><span style="color:#38BDF8;font-weight:800;font-size:12px;">${{x.mode}}</span><span style="color:#94A3B8;font-size:11px;">${{x.time}}</span></div>
          <div style="font-size:16px;font-weight:900;color:#fff;margin-top:4px;">${{x.route}}</div>
          <div style="font-size:13px;color:#34D399;font-weight:700;margin-top:6px;">📏 ${{x.km}} km · ⏱️ ${{x.mins}} 分 · 🔥 ${{x.kcal}} kcal</div>
        </div>`).join('');
      }}

      function switchTab(t, el) {{ document.querySelectorAll('.page').forEach(x => x.classList.remove('active')); document.querySelectorAll('.tab').forEach(x => x.classList.remove('active')); document.getElementById('page-' + t).classList.add('active'); el.classList.add('active'); }}
      renderRoutes();
      renderLogs();
    </script></body></html>"""
    return HTMLResponse(content=html)
def make_bike_pro_card():
    S = chr(47)
    app_uri = f"{RENDER_BASE_URL}/bike_pro?openExternalBrowser=1"
    log_uri = f"https:{S}{S}line.me{S}R{S}oaMessage{S}{LINE_BOT_BASIC_ID}{S}?{urllib.parse.quote('騎車 22公里 五股八里線')}"
    nut_uri = f"https:{S}{S}line.me{S}R{S}oaMessage{S}{LINE_BOT_BASIC_ID}{S}?{urllib.parse.quote('補給 25公里 68公斤')}"
    ride_invite = urllib.parse.quote(f"🚴‍♂️【單車運動健身約騎召集令！】\n📍 集合點：五股微風運河成蘆橋下\n🗺️ 路線：五股 ➡️ 八里左岸來回 22 km（沿途公廁／飲水補給已查好）\n📲 開啟 GPS 單車碼表 ＆ 路線戰情室：\nhttps:{S}{S}line.me{S}R{S}ti{S}p{S}{LINE_BOT_BASIC_ID}")
    share_uri = f"https:{S}{S}line.me{S}R{S}share?text={ride_invite}"

    tot_km = round(sum(float(x.get("km", 0)) for x in BIKE_FIT_LOGS), 1)
    tot_kcal = sum(int(x.get("kcal", 0)) for x in BIKE_FIT_LOGS)
    wind_info = get_cycling_wind()

    bubble_1 = BubbleContainer(
        size="mega",
        header=BoxComponent(layout="vertical", background_color="#090C12", padding_all="16px", contents=[
            TextComponent(text="🚴‍♂️ 單車騎行碼表 ＆ 健身戰情室", weight="bold", size="md", color="#38BDF8", wrap=True),
            TextComponent(text="GPS 碼表測速 · 燃脂心率 · 騎後營養精算", size="xs", color="#FBBF24", weight="bold", wrap=True, margin="xs")
        ]),
        body=BoxComponent(layout="vertical", spacing="sm", background_color="#FFFFFF", contents=[
            BoxComponent(layout="horizontal", spacing="sm", contents=[
                BoxComponent(layout="vertical", background_color="#131A28", corner_radius="12px", padding_all="10px", align_items="center", contents=[
                    TextComponent(text="🚴‍♂️ 累計里程", size="xxs", color="#38BDF8", weight="bold"),
                    TextComponent(text=f"{tot_km} km", size="sm", color="#FFFFFF", weight="bold", margin="xs")
                ]),
                BoxComponent(layout="vertical", background_color="#131A28", corner_radius="12px", padding_all="10px", align_items="center", contents=[
                    TextComponent(text="🔥 累計燃脂", size="xxs", color="#F87171", weight="bold"),
                    TextComponent(text=f"{tot_kcal} kcal", size="sm", color="#FFFFFF", weight="bold", margin="xs")
                ])
            ]),
            BoxComponent(layout="vertical", background_color="#F0F9FF", corner_radius="14px", padding_all="12px", contents=[
                TextComponent(text="🌬️ 河濱即時風向雷達（出發必看）：", size="xs", color="#0369A1", weight="bold"),
                TextComponent(text=wind_info, size="xs", color="#0F172A", wrap=True, margin="xs")
            ])
        ]),
        footer=BoxComponent(layout="vertical", spacing="sm", background_color="#FFFFFF", contents=[
            ButtonComponent(style="primary", color="#0284C7", height="sm", action=URIAction(label="📟 開啟 GPS 碼表 ＆ 路線戰情室", uri=app_uri)),
            BoxComponent(layout="horizontal", spacing="sm", contents=[
                ButtonComponent(style="primary", color="#131A28", height="sm", action=URIAction(label="🚴‍♂️ 記里程", uri=log_uri)),
                ButtonComponent(style="secondary", height="sm", action=MessageAction(label="🗺️ 查路線", text="單車路線"))
            ]),
            BoxComponent(layout="horizontal", spacing="sm", contents=[
                ButtonComponent(style="primary", color="#10B981", height="sm", action=URIAction(label="🥗 算營養", uri=nut_uri)),
                ButtonComponent(style="primary", color="#D97706", height="sm", action=MessageAction(label="💓 算心率", text="燃脂心率 35歲"))
            ])
        ])
    )

    host = "maps." + "google.com"
    tools_btns = [
        BoxComponent(layout="horizontal", spacing="sm", contents=[
            ButtonComponent(style="primary", color="#0284C7", height="sm", action=URIAction(label="🚻 沿途公廁", uri=f"https:{S}{S}{host}{S}?q=河濱公園+公廁")),
            ButtonComponent(style="primary", color="#10B981", height="sm", action=URIAction(label="💧 飲水補給", uri=f"https:{S}{S}{host}{S}?q=自行車租借站+飲水機"))
        ]),
        BoxComponent(layout="horizontal", spacing="sm", contents=[
            ButtonComponent(style="secondary", height="sm", action=MessageAction(label="🛞 算胎壓", text="胎壓 68公斤")),
            ButtonComponent(style="secondary", height="sm", action=MessageAction(label="✅ 出發安檢", text="出發安檢"))
        ]),
        ButtonComponent(style="primary", color="#2563EB", height="sm", action=URIAction(label="📢 發送 LINE 車友約騎召集令", uri=share_uri))
    ]
    if NOTION_BIKE_SHOP_URL.startswith("http"):
        tools_btns.append(ButtonComponent(style="secondary", height="sm", action=URIAction(label="🚴‍♂️ 單車碼表／安全帽／能量膠嚴選", uri=NOTION_BIKE_SHOP_URL)))

    bubble_2 = BubbleContainer(
        size="mega",
        header=BoxComponent(layout="vertical", background_color="#090C12", padding_all="16px", contents=[
            TextComponent(text="🛠️ 沿途補給救援 ＆ 約騎召集令", weight="bold", size="md", color="#38BDF8", wrap=True),
            TextComponent(text="公廁、飲水機、胎壓精算與出發前5項安檢", size="xs", color="#FBBF24", weight="bold", wrap=True, margin="xs")
        ]),
        body=BoxComponent(layout="vertical", spacing="xs", background_color="#FFFFFF", contents=[
            TextComponent(text="👈 向左滑動返回「GPS 碼表與燃脂戰情室」", size="xxs", color="#64748B", weight="bold")
        ]),
        footer=BoxComponent(layout="vertical", spacing="sm", background_color="#FFFFFF", contents=tools_btns)
    )
    return CarouselContainer(contents=[bubble_1, bubble_2])
@app.post("/callback")
async def callback(request: Request):
    sig = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), sig)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return "OK"

@handler.add(FollowEvent)
def on_follow(event):
    card = make_bike_pro_card()
    line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="🚴‍♂️ 專業單車騎行碼表 ＆ 運動健身戰情室已啟動", contents=card))

@handler.add(MessageEvent, message=LocationMessage)
def on_location(event):
    S = chr(47)
    lat, lon = event.message.latitude, event.message.longitude
    host = "maps." + "google.com"
    wc_u = f"https:{S}{S}{host}{S}?q=河濱公園+公廁@{lat},{lon}"
    sup_u = f"https:{S}{S}{host}{S}?q=自行車租借站+飲水機@{lat},{lon}"
    fix_u = f"https:{S}{S}{host}{S}?q=自行車行+維修@{lat},{lon}"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"📍 已定位您的騎行座標！\n🚻 附近公廁導航：\n{wc_u}\n💧 飲水機與租借站：\n{sup_u}\n🛠️ 附近單車維修救援：\n{fix_u}"))

@handler.add(MessageEvent, message=TextMessage)
def on_text(event):
    uid = event.source.user_id
    uname = get_user_name(uid)
    txt = event.message.text.strip()

    try:
        if txt == "單車路線":
            lines = ["🗺️【雙北經典單車訓練路線 ＆ 廁所飲水補給】"]
            for r in PRO_BIKE_ROUTES:
                lines.append(f"\n• {r['name']}（{r['km']}km / {r['mins']}分 / 約{r['kcal']}kcal）\n  🚻 廁所：{r['toilets']}\n  💧 補給：{r['supplies']}")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="\n".join(lines)))
            return

        if txt == "出發安檢":
            chk = (
                "✅【單車出發前 5 項黃金安全檢查（ABCDE）】\n"
                "1. A (Air) 胎壓：用拇指按壓輪胎確認飽滿不軟扁，避免蛇咬爆胎。\n"
                "2. B (Brakes) 煞車：原地推動車身並分別捏緊前後煞車，確認煞停靈敏不磨框。\n"
                "3. C (Chain) 鏈條：空轉踏板測試變速順暢、鏈條無生鏽異音。\n"
                "4. D (Drop) 快拆/貫通軸：確認前後輪軸心與座管束已鎖緊無鬆動。\n"
                "5. E (Equipment) 裝備：戴好安全帽、開啟前後車燈並備妥水壺與手機！"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=chk))
            return

        if any(k in txt for k in ["營養", "蛋白質", "電解質", "飲食", "吃什麼", "補給"]):
            nums = re.findall(r"\d+(?:\.\d+)?", txt)
            km = float(next(iter(nums), 25.0))
            w = float(nums) if len(nums) >= 2 else 68.0
            mins = round(km * 2.8)
            pro = round(w * (0.35 if km >= 30 else 0.25))
            carb = round(w * (0.8 if km >= 30 else 0.5))
            water = round(mins * 11 + 300)
            nut_msg = (
                f"🥗【騎行 {int(km)} km（體重 {int(w)}kg）運動後營養精算】\n"
                f"• 🥩 優質蛋白質：{pro} g（修復腿部肌纖維）\n"
                f"• 🍌 黃金碳水：{carb} g（快速回補肝醣不累垮）\n"
                f"• 💧 防抽筋水分＋電解質：{water} ml\n"
                "🏪 7-11／全家實戰組合：無糖高纖豆漿 450ml ＋ 茶葉蛋 2 顆 ＋ 香蕉 1 根 ＋ 運動飲料兌水！"
            )
            card = make_bike_pro_card()
            line_bot_api.reply_message(event.reply_token, [
                TextSendMessage(text=nut_msg),
                FlexSendMessage(alt_text="🚴‍♂️ 單車騎行碼表 ＆ 健身戰情室 Pro", contents=card)
            ])
            return

        if "心率" in txt:
            m_age = re.search(r"(\d{1,3})", txt)
            age = int(m_age.group(1)) if m_age else 35
            max_hr = round(208 - 0.7 * age)
            z2_l, z2_h = round(max_hr * 0.6), round(max_hr * 0.7)
            z3_h = round(max_hr * 0.8)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💓【{age} 歲騎士運動健身心率區間】\n• 預估最大心率：{max_hr} bpm\n• 🔥 Zone 2 黃金減脂區：{z2_l} ~ {z2_h} bpm（燃燒脂肪效率最高！）\n• ⚡ Zone 3 有氧心肺區：{z2_h} ~ {z3_h} bpm（提升長途耐力）"))
            return

        if "胎壓" in txt:
            m_w = re.search(r"(\d{2,3})", txt)
            w = int(m_w.group(1)) if m_w else 68
            f28 = round(68 + (w - 65) * 0.5)
            r28 = f28 + 5
            f25 = round(80 + (w - 65) * 0.6)
            r25 = f25 + 5
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🛞【體重 {w} kg 單車建議胎壓 PSI】\n• 公路車 700x28c：前輪 {f28} PSI / 後輪 {r28} PSI\n• 公路車 700x25c：前輪 {f25} PSI / 後輪 {r25} PSI\n💡 小提醒：雨天或河濱地濕時，可適度降低 5 PSI 增加抓地力！"))
            return

        if txt != "單車" and any(k in txt for k in ["騎車", "公里", "km", "紀錄", "記錄"]):
            m_km = re.search(r"(\d+(?:\.\d+)?)", txt)
            km = float(m_km.group(1)) if m_km else 20.0
            is_climb = any(k in txt for k in ["爬坡", "山", "觀音山", "風櫃嘴"])
            kcal = round(km * (38 if is_climb else 26))
            mins = round(km * (3.8 if is_climb else 2.8))
            co2 = round(km * 0.21, 2)
            bid = f"B{int(datetime.datetime.utcnow().timestamp() * 1000)}"
            now_t = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%m/%d %H:%M")
            BIKE_FIT_LOGS.insert(0, {"rec_id": bid, "mode": "⛰️ 爬坡間歇訓練" if is_climb else "🚴‍♂️ 公路車有氧耐力", "route": txt[:20], "km": round(km, 1), "mins": mins, "kcal": kcal, "time": now_t})
            call_sheet({"action": "add_bike", "rec_id": bid, "user_id": uid, "user_name": uname, "mode": "單車訓練", "route": txt[:20], "dist_km": km, "mins": mins, "kcal": kcal})
            card = make_bike_pro_card()
            line_bot_api.reply_message(event.reply_token, [
                TextSendMessage(text=f"🏆 太強了！單車運動數據已寫入雲端日誌：\n• 騎行里程：{round(km, 1)} km（約 {mins} 分鐘）\n• 燃脂熱量：約 {kcal} kcal\n• 減碳貢獻：{co2} kg CO₂"),
                FlexSendMessage(alt_text="🚴‍♂️ 單車騎行碼表 ＆ 健身戰情室 Pro", contents=card)
            ])
            return

        card = make_bike_pro_card()
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="🚴‍♂️ 單車騎行碼表 ＆ 健身戰情室 Pro", contents=card))
    except Exception as e:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🚴‍♂️ 系統小提示：{str(e)[:60]}（請輸入「單車」刷新畫面）"))

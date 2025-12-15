import time
import datetime
import json
import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from openai import OpenAI

# ================= 1. 从环境变量读取配置 (云端安全模式) =================

# 在本地运行时，如果找不到环境变量，可以用 os.getenv 的第二个参数作为默认值(填你自己的Key方便本地测试)
API_KEY = os.getenv("MY_AI_KEY")
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"
SERVER_CHAN_KEY = os.getenv("MY_SERVER_KEY")

HISTORY_FILE = "history.json"

COMPETITIONS = [
    {
        "name": "先进成图大赛",
        "url": "http://www.chengtudasai.com/"
    },
    {
        "name": "中国高校智能机器人创意大赛",
        "url": "https://www.robotcontest.cn/home/homepage"
    },
    {
        "name": "智能精密装配大赛",
        "url": "http://www.nusac.cn/AUBO/Information?t=TZGG"
    },
    {
        "name": "智能制造赛",
        "url": "http://cmes-imic.org.cn/?page_id=3870"
    },
    {
        "name": "机器人及人工智能大赛",
        "url": "https://craic.yuntop.com/#/index"
    },
    {
        "name": "睿抗机器人—数字孪生赛道",
        "url": "https://www.raicom.com.cn/docs.html"
    },
    {
        "name": "西门子杯赛",
        "url": "http://www.siemenscup-cimc.org.cn/competition/index"
    },
    {
        "name": "机械产品数字化设计赛",
        "url": "https://meicc-pic.hust.edu.cn/tzgg.htm"
    },
]


# ================= 2. 功能模块 =================

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(history_data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=4)


def send_wechat_msg(title, content):
    if not SERVER_CHAN_KEY:
        print("⚠️ 未配置 Server酱 Key")
        return
    url = f"https://sctapi.ftqq.com/{SERVER_CHAN_KEY}.send"
    data = {"title": title, "desp": content}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"❌ 推送失败: {e}")


def init_driver():
    print("正在启动浏览器内核 (Cloud Mode)...")
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # --- 云端/Linux 必须加的参数 ---
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # -----------------------------
    options.page_load_strategy = 'eager'
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    return driver


def fetch_content(driver, url):
    try:
        driver.get(url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        for trash in soup(['script', 'style', 'noscript', 'iframe', 'footer']):
            trash.extract()
        return soup.get_text(separator='\n', strip=True)[:3000]
    except Exception as e:
        print(f"  ❌ 抓取失败: {e}")
        return None


def analyze_with_ai(content):
    if not API_KEY: return {"latest_title": "No Key", "is_important": False, "reason": "No API Key"}
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    prompt = f"""
    分析以下文本，找出【最新】的一条通知：
    {content}
    返回JSON：
    {{ "latest_title": "标题", "is_important": true/false, "reason": "摘要" }}
    important条件：新一届比赛的赛题、规则、报名。忽略培训、名单。
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except:
        return {"latest_title": "Error", "is_important": False, "reason": "AI Error"}


# ================= 3. 主逻辑 =================

def main():
    print(f"\n🚀 云端任务启动: {datetime.datetime.now()}")
    driver = init_driver()
    history = load_history()
    push_buffer = []

    try:
        for comp in COMPETITIONS:
            print(f"Checking {comp['name']}...")
            content = fetch_content(driver, comp['url'])
            if content:
                res = analyze_with_ai(content)
                title = res.get("latest_title", "")
                if title != history.get(comp['name'], ""):
                    history[comp['name']] = title
                    if res.get("is_important"):
                        push_buffer.append(f"### {comp['name']}\n{title}\n{res.get('reason')}\n[链接]({comp['url']})")
            print("-" * 20)
    finally:
        driver.quit()
        save_history(history)  # 保存到本地文件，等待 GitHub Actions 把它提交回仓库

    if push_buffer:
        send_wechat_msg("发现竞赛更新", "\n\n".join(push_buffer))


if __name__ == "__main__":
    main()
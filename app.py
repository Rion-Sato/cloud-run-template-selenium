from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

app = Flask(__name__)

# ブラウザの設定
def create_chrome_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=chrome_options)
    return driver

@app.route('/reserve', methods=['POST'])
def reserve():
    url = request.json.get('url')
    driver = create_chrome_driver()

    try:
        driver.get(url)
        time.sleep(3)
        reserve_button = driver.find_element("xpath", "//button[contains(text(), '予約')]")
        reserve_button.click()
        time.sleep(2)
        return jsonify({"status": "success", "message": "予約が完了しました"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    finally:
        driver.quit()
from flask import Flask, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import requests
from urllib.parse import urlparse
import pandas as pd
import io

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

@app.route('/', methods=['POST'])
def reserve():
    def login_by_selenium(create_chrome_driver_func, login_url, email, password):
        driver = create_chrome_driver_func()
        driver.get(login_url)
        
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "LOGINID"))
            )
            
            email_field = driver.find_element(By.NAME, "LOGINID")
            password_field = driver.find_element(By.NAME, "PASSWORD")
            login_button = driver.find_element(By.NAME, "submit")

            email_field.send_keys(email)
            password_field.send_keys(password)
            login_button.click()

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH,"/html/body/div[1]/div[2]/div/ul[1]/li[3]"))
            )

            return driver

        except Exception as e:
            print(f"Login failed: {e}")
            return None

    # リクエストの検証
    request_json = request.json
    if not request_json:
        return ('No JSON payload received', 400)
    
    required_fields = ['email', 'password', 'year', 'offer_status']
    if not all(field in request_json for field in required_fields):
        return ('Missing required fields', 400)
    
    email = request_json['email']
    password = request_json['password']
    year = request_json['year'] #int型
    offer_status = request_json['offer_status']

    # 設定値
    login_url = "https://app.offerbox.jp/v2/clogin"
    csv_url = f"https://app.offerbox.jp/v2/ccsvcompany/favoritelist.csv?year={year}"
    detail_url = "https://app.offerbox.jp/cstudent/prof/"

    driver = login_by_selenium(create_chrome_driver, login_url, email, password)
    if not driver:
        return ('Login failed', 500)

    # 年度の切り替え処理
    try:
        selected_year = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//span[@id='gtm_amplitude_active_year']"))
        )
        if selected_year.text != f"{year}年卒":
            dropdown = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//a[@class='dropdown-toggle js-dropdownToggle']"))
            )
            driver.execute_script("arguments[0].click();", dropdown)

            year_option = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((
                    By.XPATH,
                    f"//input[@type='radio' and @name='activeyear' and @value='{year}']/parent::*/parent::*"
                ))
            )
            year_option.click()

            WebDriverWait(driver, 10).until(
                EC.staleness_of(year_option)
            )

    except TimeoutException as e:
        print(f"Year selection failed: {e}")
        return ('Year selection failed', 500)

    # セッション作成とCSVダウンロード
    session = requests.Session()
    cookies = driver.get_cookies()
    domain = urlparse(driver.current_url).netloc

    for cookie in cookies:
        session.cookies.set(
            name=cookie['name'],
            value=cookie['value'],
            domain=cookie.get('domain', domain),
            path=cookie.get('path', '/')
        )

    headers = {
        'User-Agent': driver.execute_script("return navigator.userAgent;"),
        'Referer': driver.current_url
    }

    driver.quit()

    csv_res = session.get(csv_url, headers=headers, allow_redirects=False)
    
    session.close()

    if csv_res.status_code != 200:
        return (f'Failed to download CSV: {csv_res.status_code}', 500)

    # データ処理
    df = pd.read_csv(io.StringIO(csv_res.content.decode('shift_jis')))
    df = df[df['活動状況'] != "就職活動終了"]

    if offer_status == "初回オファー":
        df = df[df['オファー'] != "済"]
    elif offer_status == "再オファー":
        df = df[df['オファー'] == "済"]
    else:
        return ('Invalid offer_status', 400)

    # URL生成
    student_ids = df[df.columns[0]].astype(str)
    url_list = [f"{detail_url}{id}" for id in student_ids]

    return url_list
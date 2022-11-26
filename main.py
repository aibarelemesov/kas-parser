from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import time
import psycopg2

#iterate over seller addresses
def persist_address(links, costs, phone_id):
    driver = webdriver.Chrome()
    cur = conn.cursor()
    driver.get('https://kaspi.kz/shop/nur-sultan/')
    driver.find_element("xpath", "//button[@id='current-location-yes']").click()
    for link, cost in zip(links, costs):
        driver.get('https://kaspi.kz' + link.attrs.get('href'))
        name = driver.find_element("xpath", "//h1[@class='merchant-profile__name']").text
        name_list = name.split()
        name = ' '.join(name_list[:len(name_list) - 3])
        cost = cost[:-1]
        cost = ''.join(cost.split())
        print(phone_id)

        #persisting phone-store relationship with it cost 
        try:
            cur.execute("select exists (select 1 from phone_store_availabale where phone_id = %s and store_name = %s)", (phone_id, name))
            result = [r[0] for r in cur.fetchall()]
            result = result[0]
            if not result:
                cur.execute("insert into phone_store_availabale (phone_id, store_name, phone_cost) values (%s, %s, %s)", (phone_id, name, cost))
                conn.commit()
        except psycopg2.Error as e:
            print(e)
            conn.rollback()

        #persisting all addresses of a seller
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        addresses = soup.select("td[class*='_address']")
        if not addresses:
            try:
                cur.execute("select exists (select 1 from stores where store_name = %s and address = %s)", (name, "Online"))
                result = [r[0] for r in cur.fetchall()]
                result = result[0]
                if not result:
                    cur.execute("insert into stores (store_name, address) values (%s, %s)", (name, "Online"))
                    conn.commit()
            except psycopg2.Error as e:
                print(e)
                conn.rollback()
        else: 
            for adr in addresses:
                adres = adr.get_text().split('(',1)[0]
                try:
                    cur.execute("select exists (select 1 from stores where store_name = %s and address = %s)", (name, adres))
                    result = [r[0] for r in cur.fetchall()]
                    result = result[0]
                    if not result:
                        cur.execute("insert into stores (store_name, address) values (%s, %s)", (name, adres))
                        conn.commit()
                except psycopg2.Error as e:
                    print(e)
                    conn.rollback()

    
#iterate over good sellers
def parse_sellers(driver, url, phone_img_url):
    cur = conn.cursor()
    driver.get(url)
    # driver.find_element("xpath", "//a[text()='Астана']").click()
    phoneSoup = BeautifulSoup(driver.page_source, 'html.parser')
    specs = phoneSoup.find_all('li', class_ = 'short-specifications__text')
    full_name = phoneSoup.find('h1', class_ = 'item__heading').text
    phone_name = re.split(' \d ГБ', full_name)[0].split('Смартфон ')[1].split()
    brand = phone_name[0]
    phone_name.pop(0)
    phone_name = ' '.join(phone_name)
    vals = (phone_img_url, brand, phone_name,)

    #save phone specs into vals
    for spec in specs:
        to_dict = spec.text.split(': ')
        spec = dict((to_dict,))
        key = list(spec.keys())[0]
        val = spec[key].split()[0]
        necessary_specs = ['Технология NFC','Цвет','Диагональ','Размер оперативной памяти','Процессор','Объем встроенной памяти', 'Емкость аккумулятора']
        if key in necessary_specs:
            vals += (val,)
    
    phone_id = None
    
    #check if phone exists in table
    try:
        cur.execute("select exists (select 1 from phones where img_url = %s and brand = %s and phone_name = %s and has_nfc = %s and color = %s and diagonal_inch = %s and ram = %s and processor = %s and memory = %s and accum_vol = %s)", vals)
        result = [r[0] for r in cur.fetchall()]
        result = result[0]
        print('AAAAAAA', result, type(result))
        print(vals)
        #get phone_id if exists and insert and save phone_id if doesnt exists
        if result:
            cur.execute("select id from phones where img_url = %s and brand = %s and phone_name = %s and has_nfc = %s and color = %s and diagonal_inch = %s and ram = %s and processor = %s and memory = %s and accum_vol = %s", vals)
            phone_id = [r[0] for r in cur.fetchall()][0]
        else:
            cur.execute("insert into phones (img_url, brand, phone_name, has_nfc, color, diagonal_inch, ram, processor, memory, accum_vol) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id", vals)
            conn.commit()
            phone_id = cur.fetchone()[0]
        print(phone_id)
    except psycopg2.Error as e:
        conn.rollback()
    
        
    #iterate over all good sellers
    is_next_page_sellers_available = True
    while is_next_page_sellers_available:
        next_page_attrs = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "//li[text()='Следующая']"))).get_attribute("class").split()
        if '_disabled' in next_page_attrs:
            is_next_page_sellers_available = False
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        sellers = soup.find('table', class_ = 'sellers-table__self')
        links = sellers.find_all('a', attrs={'class': None})
        costs = sellers.find_all('div',  class_ = 'sellers-table__price-cell-text')
        filtred_costs = []
        for cost in costs:
            if '_installments-price' not in cost.attrs['class']:
                filtred_costs.append(cost.text)
        persist_address(links, filtred_costs, phone_id)
        if is_next_page_sellers_available:
            print(is_next_page_sellers_available)
            driver.find_element("xpath", "//li[text()='Следующая']").click()
            time.sleep(5)
        
        
        

#iterate over pages with goods
def get_phones(driver, url):
    driver.get(url)
    action = ActionChains(driver)
    is_next_page_available = True
    next_page_attrs = driver.find_element("xpath", "(//li[contains(@class, 'pagination__el')])[7]").get_attribute("class").split()
    if '_disabled' in next_page_attrs:
        is_next_page_available = False

    try:
        action.move_to_element(driver.find_element("xpath", "(//img[@class=\'item-card__image\'])[10]")).perform()
    except NoSuchElementException:
        print("i cant")

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    phones = soup.find_all('div', class_ = 'item-card ddl_product ddl_product_link undefined')

    for phone in phones:
        new_url = phone.find('a', class_ = 'item-card__name-link').attrs.get('href')
        phone_img_url = phone.find('img', class_ = 'item-card__image').attrs.get('src')
        parse_sellers(driver, new_url, phone_img_url)

    return is_next_page_available

conn = psycopg2.connect(
    host="localhost",
    database="postgres",
    user="postgres",
    password="12345")

cur = conn.cursor()

iterate_further = True
driver = webdriver.Chrome()
page_num = 1
url = 'https://kaspi.kz/shop/nur-sultan/c/smartphones/class-2-sim-cards/?page='
while iterate_further:
    iterate_further = get_phones(driver, url + str(page_num))
    page_num += 1

cur.close()
conn.close()

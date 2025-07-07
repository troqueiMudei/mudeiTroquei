import os
import re
import random
import urllib
import requests
import io
import base64
import logging
import json
from datetime import datetime
from functools import wraps
from PIL import Image, ImageEnhance, ImageFilter
from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
import phpserialize
import math
import urllib.parse
from webdriver_manager.chrome import ChromeDriverManager

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Mapeamento de bairros
BAIRROS = {
    1: "Barra da Tijuca",
    2: "Recreio dos Bandeirantes",
    3: "Vargem Grande",
    4: "Vargem Pequena",
    5: "Gardênia Azul",
    6: "Cidade de Deus",
    7: "Curicica",
    8: "Taquara",
    9: "Pechincha",
    10: "Freguesia (Jacarepaguá)",
    11: "Camorim",
    12: "Tanque",
    13: "Praça Seca",
    14: "Madureira",
    16: "Cascadura",
    17: "Campinho",
    18: "Méier",
    19: "Engenho de Dentro",
    20: "Vila Isabel",
    21: "Tijuca",
    22: "Maracanã",
    23: "São Cristóvão",
    24: "Centro",
    25: "Flamengo",
    26: "Botafogo",
    27: "Copacabana",
    28: "Ipanema",
    29: "Leblon",
    30: "Jardim Botânico",
    31: "Laranjeiras",
    32: "Cosme Velho",
    33: "Glória",
    34: "Santa Teresa",
    35: "Lapa",
    36: "Penha",
    37: "Olaria",
    38: "Ramos",
    39: "Bonsucesso",
    40: "Ilha do Governador",
    41: "Pavuna",
    42: "Anchieta",
    43: "Guadalupe",
    44: "Deodoro",
    45: "Realengo",
    46: "Bangu",
    47: "Campo Grande",
    48: "Santa Cruz",
    49: "Sepetiba",
    50: "Guaratiba",
    51: "Pedra de Guaratiba",
    52: "Grajaú",
    53: "Engenho Novo",
    54: "Rocha Miranda",
    55: "Higienópolis"
}

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'chave_secreta_aqui')

# Configuração da conexão com o banco de dados MySQL
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '162.241.62.120'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'mudeit26__teste'),
    'password': os.getenv('DB_PASSWORD', 'teste2025@'),
    'database': os.getenv('DB_NAME', 'mudeit26_site'),
    'connection_timeout': 30,
    'connect_timeout': 30,
    'consume_results': True,
    'autocommit': True,
    'pool_name': 'web_pool',
    'pool_size': 5,
    'pool_reset_session': True
}

# Classe para buscar produtos por imagem no Google Lens
class ProdutoFinder:
    def __init__(self):
        self.driver = None
        self.base_url = "https://lens.google.com/uploadbyurl?url="
        self.max_retries = 3
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/125.0'
        ]

    def _safe_extract(self, element, selector):
        """Extrai texto de forma segura"""
        try:
            el = element.find_element(By.CSS_SELECTOR, selector)
            return el.text.strip()
        except:
            return "Produto similar"

    def _safe_extract_img(self, element):
        """Extrai imagem do elemento de forma segura"""
        try:
            img = element.find_element(By.XPATH, ".//img")
            return img.get_attribute('src')
        except:
            return ""

    def _safe_extract_url(self, element):
        """Extrai URL do elemento de forma segura"""
        try:
            if element.tag_name == 'a':
                return element.get_attribute('href')
            link = element.find_element(By.XPATH, ".//a")
            return link.get_attribute('href')
        except:
            return "#"

    def _safe_extract_price(self, element):
        """Extrai preço do elemento de forma segura com seletores atualizados"""
        try:
            price_selectors = [
                ".//span[contains(@class, 'price')]",
                ".//span[contains(@class, 'e10twf')]",
                ".//span[contains(@class, 'a8Pemb')]",
                ".//span[contains(@class, 'T14wmb')]",
                ".//div[contains(@class, 'NRRPPb')]/span",
                ".//span[contains(text(), 'R$') or contains(text(), '$') or contains(text(), 'USD')]",
                ".//span[@aria-label='Price']",
                ".//div[contains(@class, 'sh-np__product-price')]/span"
            ]
            for selector in price_selectors:
                try:
                    el = element.find_element(By.XPATH, selector)
                    price_text = el.text.strip()
                    if price_text and ('$' in price_text or 'R$' in price_text or price_text[0].isdigit()):
                        cleaned_price = re.sub(r'[^\d,.R$]', '', price_text)
                        return cleaned_price if cleaned_price else "Preço não disponível"
                except:
                    continue
            return "Preço não disponível"
        except Exception as e:
            logger.warning(f"Erro ao extrair preço: {str(e)}")
            return "Preço não disponível"

    def _convert_image_to_url(self, image=None, image_url=None, image_data=None):
        """Converte imagem para URL usando serviço ImgBB"""
        try:
            if image is not None:
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                optimal_size = (1000, 1000)
                image.thumbnail(optimal_size, Image.LANCZOS)
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.2)
                image = image.filter(ImageFilter.SHARPEN)
                img_buffer = io.BytesIO()
                image.save(img_buffer, format='JPEG', quality=90)
                img_buffer.seek(0)
                files = {'image': ('image.jpg', img_buffer, 'image/jpeg')}

            elif image_data is not None:
                try:
                    img = Image.open(io.BytesIO(image_data))
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    optimal_size = (1000, 1000)
                    img.thumbnail(optimal_size, Image.LANCZOS)
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(1.2)
                    img = img.filter(ImageFilter.SHARPEN)
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format='JPEG', quality=90)
                    img_buffer.seek(0)
                    files = {'image': ('image.jpg', img_buffer, 'image/jpeg')}
                except Exception as img_error:
                    logger.warning(f"Failed to process image data: {str(img_error)}")
                    files = {'image': ('image.jpg', image_data, 'image/jpeg')}

            elif image_url is not None:
                headers = {
                    'User-Agent': random.choice(self.user_agents),
                    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                    'Referer': 'https://mude.ind.br/',
                    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                }
                for attempt in range(3):
                    try:
                        response = requests.get(image_url, headers=headers, timeout=10 * (attempt + 1))
                        if response.status_code == 200:
                            break
                    except Exception as req_error:
                        logger.warning(f"Attempt {attempt + 1} failed: {str(req_error)}")
                        if attempt < 2:
                            time.sleep(2)
                if response.status_code != 200:
                    logger.error(f"Error downloading image: {response.status_code}")
                    return image_url
                try:
                    img = Image.open(io.BytesIO(response.content))
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    optimal_size = (1000, 1000)
                    img.thumbnail(optimal_size, Image.LANCZOS)
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(1.2)
                    img = img.filter(ImageFilter.SHARPEN)
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format='JPEG', quality=90)
                    img_buffer.seek(0)
                    files = {'image': ('image.jpg', img_buffer, 'image/jpeg')}
                except Exception as proc_error:
                    logger.warning(f"Failed to process downloaded image: {str(proc_error)}")
                    files = {'image': ('image.jpg', response.content, 'image/jpeg')}

            else:
                logger.error("No valid image input provided.")
                return None

            retries = 3
            for attempt in range(retries):
                try:
                    response = requests.post(
                        'https://api.imgbb.com/1/upload',
                        params={'key': '8234882d2cc5bc9c7f2f239283951076'},
                        files=files,
                        timeout=30
                    )
                    if response.status_code == 200 and 'data' in response.json() and 'url' in response.json()['data']:
                        url = response.json()['data']['url']
                        logger.info(f"Image converted to URL: {url}")
                        return url
                    logger.error(f"Error uploading image: {response.status_code} - {response.text}")
                    if attempt < retries - 1:
                        time.sleep(2)
                except Exception as e:
                    logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt < retries - 1:
                        time.sleep(2)

            if image_url:
                return image_url
            return None

        except Exception as e:
            logger.error(f"Error converting image: {str(e)}")
            return image_url if image_url else None

    def _extract_with_javascript(self):
        """Fallback com extração via JavaScript"""
        try:
            return self.driver.execute_script("""
                const results = [];
                const containers = document.querySelectorAll(
                    'div.sh-dgr__grid-result, div.sh-dlr__list-result, div.pla-unit, div.Lv3Kxc, div.kb0PBd.cvP2Ce'
                );
                containers.forEach(container => {
                    try {
                        const titleEl = container.querySelector('h3, h4, [role="heading"], [class*="title"], [class*="header"]');
                        const priceEl = container.querySelector(
                            'span[class*="price"], span[class*="e10twf"], span[class*="a8Pemb"], span[class*="T14wmb"], ' +
                            'span[aria-label="Price"], div[class*="NRRPPb"] span, span[contains(text(), "R$")]'
                        );
                        const linkEl = container.querySelector('a');
                        const imgEl = container.querySelector('img');
                        if (titleEl || linkEl) {
                            results.push({
                                nome: titleEl?.innerText?.trim() || 'Produto similar',
                                preco: priceEl?.innerText?.trim() || 'Preço não disponível',
                                url: linkEl?.href || '#',
                                img: imgEl?.src || ''
                            });
                        }
                    } catch (e) {
                        console.error('Error extracting product:', e);
                    }
                });
                return results.slice(0, 5);
            """) or []
        except Exception as e:
            logger.error(f"Erro na extração com JavaScript: {str(e)}")
            return []

    def _extract_products_selenium(self):
        """Método robusto para extração de produtos em 2025"""
        try:
            print(f"\nURL atual: {self.driver.current_url}")
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-snc], div.srKDX.cvP2Ce"))
            )
            for y in [300, 600, 900]:
                self.driver.execute_script(f"window.scrollTo(0, {y});")
                time.sleep(1.5)
            produtos = self._extract_with_javascript()
            if produtos:
                return produtos
            selectors = [
                "//div[contains(@class, 'sh-dgr__grid-result')]",
                "//div[contains(@class, 'Lv3Kxc')]",
                "//div[contains(@class, 'kb0PBd cvP2Ce')]",
                "//div[@role='listitem']",
                "//div[@data-product]"
            ]
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        produtos = []
                        for element in elements[:5]:
                            try:
                                produto = {
                                    "nome": self._safe_extract_text(element),
                                    "preco": self._safe_extract_price(element),
                                    "url": self._safe_extract_url(element),
                                    "img": self._safe_extract_img(element)
                                }
                                if produto["nome"] and produto["url"]:
                                    produtos.append(produto)
                            except Exception as e:
                                logger.warning(f"Erro ao extrair produto: {str(e)}")
                                continue
                        if produtos:
                            return produtos
                except Exception as e:
                    logger.warning(f"Seletor {selector} não encontrado: {str(e)}")
                    continue
            return []
        except Exception as e:
            print(f"Erro na extração principal: {str(e)}")
            return self._extract_products_alternative()

    def _safe_extract_text(self, element):
        """Extrai texto do elemento de forma segura"""
        try:
            for selector in [".//h3", ".//h4", ".//div[contains(@class, 'title')]", ".//div[contains(@class, 'header')]"]:
                try:
                    el = element.find_element(By.XPATH, selector)
                    text = el.text.strip()
                    if text:
                        return text
                except:
                    continue
            return "Produto similar"
        except:
            return "Produto similar"

    def _safe_extract_attr(self, element, selector, attribute):
        """Extrai atributo de forma segura"""
        try:
            el = element.find_element(By.CSS_SELECTOR, selector)
            return el.get_attribute(attribute)
        except:
            return "#"

    def _extract_products_alternative(self):
        """Método alternativo quando o principal falha"""
        try:
            produtos = []
            elements = self.driver.find_elements(By.CSS_SELECTOR, "div[role='listitem'], div[role='article']")
            for element in elements[:5]:
                try:
                    produto = {
                        "nome": element.find_element(By.CSS_SELECTOR, "[role='heading']").text,
                        "preco": self._safe_extract_price(element),
                        "url": element.find_element(By.CSS_SELECTOR, "a").get_attribute("href"),
                        "img": element.find_element(By.CSS_SELECTOR, "img").get_attribute("src")
                    }
                    produtos.append(produto)
                except:
                    continue
            return produtos if produtos else []
        except:
            return []

    def _initialize_driver(self):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--window-size=1280,720")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        os.environ['SELENIUM_DISABLE_MANAGER'] = '1'
        try:
            self.driver = webdriver.Chrome(
                service=Service(executable_path='/usr/bin/chromedriver'),
                options=chrome_options
            )
            return True
        except Exception as e:
            logger.error(f"Falha ao inicializar o WebDriver: {str(e)}")
            return False

    def _extract_from_lens_page(self):
        """Extrai produtos diretamente da página do Google Lens"""
        produtos = []
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.srKDX.cvP2Ce"))
            )
            container = self.driver.find_element(By.CSS_SELECTOR, "div.srKDX.cvP2Ce")
            product_elements = container.find_elements(By.CSS_SELECTOR, "div.kb0PBd.cvP2Ce")[:10]
            for product in product_elements:
                try:
                    produto = {
                        "nome": self._safe_extract(product, "div[role='heading']"),
                        "preco": self._safe_extract_price(product),
                        "url": self._safe_extract_attr(product, "a", "href"),
                        "img": self._safe_extract_attr(product, "img", "src")
                    }
                    if (produto["nome"] and
                            produto["url"] and
                            not produto["url"].startswith((
                                "https://lens.google.com",
                                "http://lens.google.com",
                                "https://www.google.com",
                                "http://www.google.com"
                            )) and
                            not produto["url"].split('://')[1].split('/')[0].endswith(
                                ('google.com', 'googleapis.com'))):
                        produtos.append(produto)
                        if len(produtos) >= 5:
                            break
                except Exception as e:
                    print(f"Erro ao extrair produto: {str(e)}")
                    continue
            return produtos
        except Exception as e:
            print(f"Erro na extração da página do Lens: {str(e)}")
            return []

    def buscar_produtos_por_url(self, image_url):
        """Busca produtos no Google Lens com extração robusta"""
        print(f"\n=== Iniciando busca para imagem: {image_url} ===")
        if not self._initialize_driver():
            print("Falha ao inicializar o driver")
            return []
        try:
            encoded_url = urllib.parse.quote(image_url)
            search_url = f"https://lens.google.com/uploadbyurl?url={encoded_url}"
            print(f"\nURL de busca no Google Lens: {search_url}")
            self.driver.get(search_url)
            time.sleep(8)
            try:
                shopping_tab = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Shopping')]"))
                )
                shopping_tab.click()
                time.sleep(3)
            except Exception as e:
                print(f"Não encontrou aba Shopping: {str(e)}")
            current_url = self.driver.current_url
            print(f"\nURL atual após redirecionamento: {current_url}")
            produtos = self._extract_products_selenium()
            if not produtos:
                produtos = self._extract_from_lens_page()
            print(f"\n=== Resultados encontrados ===")
            for i, p in enumerate(produtos, 1):
                print(f"{i}. {p.get('nome', '')} | {p.get('preco', '')} | {p.get('url', '')}")
            return produtos
        except Exception as e:
            print(f"\nErro durante a busca: {str(e)}")
            return []
        finally:
            self.cleanup()
            print("\n=== Busca concluída ===")

    def cleanup(self):
        """Encerra o driver de forma segura"""
        try:
            if self.driver:
                self.driver.quit()
                print("Driver encerrado com sucesso")
        except Exception as e:
            print(f"Erro ao encerrar driver: {str(e)}")
        finally:
            self.driver = None

finder = ProdutoFinder()

def get_db_connection():
    max_retries = 3
    retry_delay = 5
    for attempt in range(max_retries):
        try:
            logger.info(f"Tentativa {attempt + 1} de conexão com o MySQL em {DB_CONFIG['host']}")
            connection = mysql.connector.connect(
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database'],
                connection_timeout=30,
                connect_timeout=30,
                consume_results=True,
                autocommit=True
            )
            cursor = connection.cursor(buffered=True)
            cursor.execute("SELECT 1")
            cursor.fetchall()
            cursor.close()
            logger.info("Conexão com MySQL estabelecida com sucesso")
            return connection
        except mysql.connector.Error as err:
            logger.error(f"Erro ao conectar ao MySQL (tentativa {attempt + 1}): {err}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"Erro inesperado ao conectar ao MySQL: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    logger.error("Falha ao conectar ao MySQL após várias tentativas")
    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'admin123':
            session['logged_in'] = True
            return redirect(url_for('lista_fichas'))
        else:
            return "Usuário ou senha inválidos", 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def lista_fichas():
    """Página principal que lista todas as fichas com paginação"""
    status_filtro = request.args.get('status')
    page = request.args.get('page', 1, type=int)
    per_page = 15
    try:
        conn = get_db_connection()
        if not conn:
            return "Erro ao conectar ao banco de dados", 500
        cursor = conn.cursor(dictionary=True)
        count_sql = """
        SELECT COUNT(DISTINCT entry_id) AS total FROM frmt_form_entry_meta
        """
        if status_filtro:
            count_sql += " WHERE entry_id IN (SELECT entry_id FROM frmt_form_entry_meta WHERE meta_key = 'radio-3' AND meta_value = %s)"
            cursor.execute(count_sql, (status_filtro,))
        else:
            cursor.execute(count_sql)
        total_records = cursor.fetchone()['total']
        total_pages = math.ceil(total_records / per_page)
        offset = (page - 1) * per_page
        sql = """
        SELECT
            entry_id AS id,
            MAX(CASE WHEN meta_key = 'name-1' THEN meta_value END) AS nome,
            MAX(CASE WHEN meta_key = 'phone-1' THEN meta_value END) AS telefone,
            MAX(CASE WHEN meta_key = 'email-1' THEN meta_value END) AS email,
            MAX(CASE WHEN meta_key = 'text-1' THEN meta_value END) AS descricao,
            MAX(CASE WHEN meta_key = 'text-3' THEN meta_value END) AS localCompra,
            MAX(CASE WHEN meta_key = 'text-4' THEN meta_value END) AS dataDeCompra,
            MAX(CASE WHEN meta_key = 'currency-1' THEN meta_value END) AS valor,
            MAX(CASE WHEN meta_key = 'radio-2' THEN meta_value END) AS possuiNota,
            MAX(CASE WHEN meta_key = 'radio-3' THEN meta_value END) AS status,
            MAX(CASE WHEN meta_key = 'text-2' THEN meta_value END) AS marcaUso,
            MAX(CASE WHEN meta_key = 'textarea-1' THEN meta_value END) AS descricaoItem,
            MAX(CASE WHEN meta_key = 'number-1' THEN meta_value END) AS altura,
            MAX(CASE WHEN meta_key = 'number-2' THEN meta_value END) AS largura,
            MAX(CASE WHEN meta_key = 'number-3' THEN meta_value END) AS profundidade,
            MAX(CASE WHEN meta_key = 'radio-1' THEN meta_value END) AS troca,
            MAX(CASE WHEN meta_key = 'text-5' THEN meta_value END) AS text5,
            MAX(CASE WHEN meta_key = 'upload-1' THEN meta_value END) AS arquivo
        FROM frmt_form_entry_meta
        """
        if status_filtro:
            sql += " HAVING status = %s"
            sql += " GROUP BY entry_id ORDER BY id DESC LIMIT %s OFFSET %s"
            cursor.execute(sql, (status_filtro, per_page, offset))
        else:
            sql += " GROUP BY entry_id ORDER BY id DESC LIMIT %s OFFSET %s"
            cursor.execute(sql, (per_page, offset))
        fichas = cursor.fetchall()
        for ficha in fichas:
            if ficha['arquivo']:
                try:
                    dados_serializados = ficha['arquivo'].encode('utf-8')
                    dados = phpserialize.loads(dados_serializados, decode_strings=True)
                    ficha['arquivo_url'] = dados['file']['file_url'][0]
                except Exception as e:
                    print(f"Erro ao desserializar arquivo da ficha ID {ficha['id']}: {e}")
                    ficha['arquivo_url'] = None
            else:
                ficha['arquivo_url'] = None
        cursor.close()
        conn.close()
        start_page = page - 2 if page > 2 else 1
        end_page = start_page + 4
        if end_page > total_pages:
            end_page = total_pages
            start_page = end_page - 4 if end_page > 4 else 1
        pagination = {
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'total_records': total_records,
            'start_page': start_page,
            'end_page': end_page
        }
        return render_template('lista_fichas.html', fichas=fichas, pagination=pagination, status_filtro=status_filtro)
    except Exception as e:
        logger.error(f"Erro ao listar fichas: {str(e)}")
        return f"Erro ao processar a solicitação: {str(e)}", 500

@app.route('/detalhes/<int:id>')
@login_required
def detalhes_ficha(id):
    """Página de detalhes de uma ficha específica com busca de produtos similares"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Erro ao conectar ao banco de dados", 500
        cursor = conn.cursor(dictionary=True)
        sql = """
        SELECT
            entry_id AS id,
            MAX(CASE WHEN meta_key = 'name-1' THEN meta_value END) AS nome,
            MAX(CASE WHEN meta_key = 'phone-1' THEN meta_value END) AS telefone,
            MAX(CASE WHEN meta_key = 'email-1' THEN meta_value END) AS email,
            MAX(CASE WHEN meta_key = 'text-1' THEN meta_value END) AS descricao,
            MAX(CASE WHEN meta_key = 'text-3' THEN meta_value END) AS localCompra,
            MAX(CASE WHEN meta_key = 'text-4' THEN meta_value END) AS dataDeCompra,
            MAX(CASE WHEN meta_key = 'currency-1' THEN meta_value END) AS valor,
            MAX(CASE WHEN meta_key = 'radio-2' THEN meta_value END) AS possuiNota,
            MAX(CASE WHEN meta_key = 'radio-3' THEN meta_value END) AS status,
            MAX(CASE WHEN meta_key = 'text-2' THEN meta_value END) AS marcaUso,
            MAX(CASE WHEN meta_key = 'textarea-1' THEN meta_value END) AS descricaoItem,
            MAX(CASE WHEN meta_key = 'number-1' THEN meta_value END) AS altura,
            MAX(CASE WHEN meta_key = 'number-2' THEN meta_value END) AS largura,
            MAX(CASE WHEN meta_key = 'number-3' THEN meta_value END) AS profundidade,
            MAX(CASE WHEN meta_key = 'radio-1' THEN meta_value END) AS troca,
            MAX(CASE WHEN meta_key = 'text-5' THEN meta_value END) AS text5,
            MAX(CASE WHEN meta_key = 'upload-1' THEN meta_value END) AS arquivo
        FROM frmt_form_entry_meta
        WHERE entry_id = %s
        GROUP BY entry_id
        """
        cursor.execute(sql, (id,))
        ficha = cursor.fetchone()
        if not ficha:
            cursor.close()
            conn.close()
            return "Ficha não encontrada", 404
        if ficha.get('arquivo'):
            try:
                dados_serializados = ficha['arquivo'].encode('utf-8')
                dados = phpserialize.loads(dados_serializados, decode_strings=True)
                ficha['arquivo_url'] = dados['file']['file_url'][0]
            except Exception as e:
                logger.error(f"Erro ao desserializar arquivo da ficha ID {ficha['id']}: {e}")
                ficha['arquivo_url'] = None
        else:
            ficha['arquivo_url'] = None
        if ficha.get('arquivo_url'):
            print(f"\nIniciando busca para imagem: {ficha['arquivo_url']}")
            finder = ProdutoFinder()
            try:
                produtos = finder.buscar_produtos_por_url(ficha['arquivo_url'])
                ficha['produtos_similares'] = [
                    {
                        'nome': p['nome'],
                        'preco': p['preco'] if p['preco'] != 'Preço não disponível' else 'Consultar',
                        'url': p['url'],
                        'img': p['img']
                    } for p in produtos if p['nome'] and p['url']
                ]
                if not ficha['produtos_similares']:
                    print("Nenhum produto similar encontrado")
                else:
                    print(f"Encontrados {len(ficha['produtos_similares'])} produtos similares")
            except Exception as e:
                print(f"Erro na busca: {str(e)}")
                ficha['produtos_similares'] = []
            finally:
                finder.cleanup()
        else:
            ficha['produtos_similares'] = []
            print("Nenhuma URL de imagem disponível para busca")
        try:
            valor_estimado = float(ficha.get('valor', '0'))
        except (ValueError, TypeError):
            valor_estimado = 0.0
        valor_estimado = valor_estimado * 1.05
        ficha['valorEstimado'] = float(valor_estimado)
        ficha['demandaMedia'] = float(valor_estimado * 1.05)
        ficha['demandaAlta'] = float(valor_estimado * 1.10)
        if ficha.get('dataDeCompra'):
            try:
                data_obj = datetime.strptime(ficha['dataDeCompra'], '%Y-%m-%d')
                ficha['dataDeCompra_br'] = data_obj.strftime('%d/%m/%Y')
            except ValueError:
                try:
                    datetime.strptime(ficha['dataDeCompra'], '%d/%m/%Y')
                    ficha['dataDeCompra_br'] = ficha['dataDeCompra']
                except ValueError:
                    ficha['dataDeCompra_br'] = ficha['dataDeCompra']
        else:
            ficha['dataDeCompra_br'] = None
        ficha['altura'] = ficha.get('altura', '0')
        ficha['largura'] = ficha.get('largura', '0')
        ficha['profundidade'] = ficha.get('profundidade', '0')
        cursor.close()
        conn.close()
        return render_template('detalhes_ficha.html', ficha=ficha)
    except Exception as e:
        print(f"\nERRO GRAVE: {str(e)}")
        return render_template('erro.html', mensagem="Ocorreu um erro ao processar a ficha"), 500

@app.route('/atualizar_status/<int:id>', methods=['POST'])
@login_required
def atualizar_status(id):
    """Rota para atualizar o status de uma ficha"""
    novo_status = request.form['status']
    try:
        conn = get_db_connection()
        if not conn:
            return "Erro ao conectar ao banco de dados", 500
        cursor = conn.cursor()
        sql = """
        UPDATE frmt_form_entry_meta
        SET meta_value = %s
        WHERE entry_id = %s AND meta_key = 'radio-3'
        """
        cursor.execute(sql, (novo_status, id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('detalhes_ficha', id=id))
    except Exception as e:
        logger.error(f"Erro ao atualizar status: {str(e)}")
        return f"Erro ao processar a solicitação: {str(e)}", 500

@app.route('/test-db')
def test_db():
    """Rota para testar a conexão com o banco de dados"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            return {
                'status': 'success',
                'message': 'Conexão com banco de dados estabelecida',
                'config': {
                    'host': DB_CONFIG['host'],
                    'port': DB_CONFIG['port'],
                    'database': DB_CONFIG['database']
                }
            }
        else:
            return {
                'status': 'error',
                'message': 'Não foi possível estabelecer conexão com o banco de dados',
                'config': {
                    'host': DB_CONFIG['host'],
                    'port': DB_CONFIG['port'],
                    'database': DB_CONFIG['database']
                }
            }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'config': {
                'host': DB_CONFIG['host'],
                'port': DB_CONFIG['port'],
                'database': DB_CONFIG['database']
            }
        }

@app.route('/preview_ficha', methods=['POST'])
def preview_ficha():
    """Rota para visualizar os dados do formulário antes de cadastrar"""
    try:
        form_data = {
            'nome': request.form.get('nome', ''),
            'cpf': request.form.get('cpf', ''),
            'telefone': request.form.get('telefone', ''),
            'email': request.form.get('email', ''),
            'produto': request.form.get('produto', ''),
            'marca': request.form.get('marca', ''),
            'quantidade': float(request.form.get('quantidade', 1)),
            'data_compra': request.form.get('data_compra', ''),
            'valor': float(request.form.get('valor_unitario', 0)),
            'marcaUso': request.form.get('marcas_uso', ''),
            'descricao': request.form.get('descricao', ''),
            'altura': float(request.form.get('altura', 0)),
            'largura': float(request.form.get('largura', 0)),
            'profundidade': float(request.form.get('profundidade', 0)),
            'bairro': int(request.form.get('bairro', 0)),
            'outroBairro': request.form.get('outro_bairro', ''),
            'voltagem': request.form.get('voltagem', ''),
            'precisa_limpeza': request.form.get('precisa_limpeza', 'não'),
            'precisa_desmontagem': request.form.get('precisa_desmontagem', 'não'),
            'possui_nota_fiscal': request.form.get('possui_nota_fiscal', 'não'),
            'aceita_credito': request.form.get('aceita_credito', 'não'),
            'tipo_reparo': request.form.get('tipo_reparo', 'nenhum'),
            'estado': request.form.getlist('estado[]'),
            'imagem_url': None,
            'produtos_similares': []
        }
        if 'imagem' in request.files:
            imagem = request.files['imagem']
            if imagem.filename != '':
                try:
                    img = Image.open(imagem)
                    img_url = finder._convert_image_to_url(image=img)
                    form_data['imagem_url'] = img_url
                    if img_url:
                        produtos = finder.buscar_produtos_por_url(img_url)
                        form_data['produtos_similares'] = [
                            {
                                'nome': p['nome'],
                                'preco': p['preco'] if p['preco'] != 'Preço não disponível' else 'Consultar',
                                'url': p['url'],
                                'img': p['img']
                            } for p in produtos if p['nome'] and p['url']
                        ]
                except Exception as e:
                    logger.error(f"Erro ao processar imagem: {str(e)}")
                    form_data['erro_imagem'] = str(e)
        form_data['bairro_nome'] = BAIRROS.get(form_data['bairro'], "Bairro não encontrado")
        if form_data['data_compra']:
            try:
                data_obj = datetime.strptime(form_data['data_compra'], '%Y-%m-%d')
                form_data['data_compra_br'] = data_obj.strftime('%d/%m/%Y')
            except ValueError:
                form_data['data_compra_br'] = form_data['data_compra']
        else:
            form_data['data_compra_br'] = "Não informada"
        valor_estimado = form_data['valor'] * 1.05
        form_data['valorEstimado'] = valor_estimado
        form_data['demandaMedia'] = valor_estimado * 1.05
        form_data['demandaAlta'] = valor_estimado * 1.10
        return render_template('preview_ficha.html', ficha=form_data)
    except Exception as e:
        logger.error(f"Erro ao processar pré-visualização: {str(e)}")
        return render_template('erro.html', mensagem="Ocorreu um erro ao processar a pré-visualização"), 500

@app.route('/nova_ficha')
def nova_ficha():
    """Exibe o formulário para cadastrar uma nova ficha"""
    return render_template('form_ficha.html', bairros=BAIRROS)

@app.route('/cadastrar_ficha', methods=['POST'])
def cadastrar_ficha():
    """Rota para cadastrar a ficha após a pré-visualização"""
    try:
        return redirect(url_for('lista_fichas'))
    except Exception as e:
        logger.error(f"Erro ao cadastrar ficha: {str(e)}")
        return render_template('erro.html', mensagem="Ocorreu um erro ao cadastrar a ficha"), 500

if __name__ == '__main__':
    app.run(debug=True)
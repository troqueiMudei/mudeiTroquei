import os
import re
import random
import urllib.parse
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
import io
import requests
import phpserialize
import math
from webdriver_manager.chrome import ChromeDriverManager

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

    def _initialize_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--window-size=1280,720")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(f"user-agent={random.choice(self.user_agents)}")
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            return True
        except Exception as e:
            logger.error(f"Falha ao inicializar o WebDriver: {str(e)}")
            return False

    def cleanup(self):
        try:
            if self.driver:
                self.driver.quit()
                logger.info("Driver encerrado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao encerrar driver: {str(e)}")
        finally:
            self.driver = None

    def _extract_products_robust(self):
        try:
            time.sleep(5)
            produtos = self._extract_with_javascript()
            if produtos:
                return produtos
            selectors = [
                "//div[contains(@class, 'sh-dgr__grid-result')]",
                "//div[contains(@class, 'Lv3Kxc')]",
                "//div[contains(@class, 'PJLMUc')]",
                "//a[contains(@class, 'UAQDqe')]",
                "//div[@data-product]",
                "//div[contains(@class, 'commercial-unit')]"
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
                    continue
            return []
        except Exception as e:
            logger.error(f"Erro na extração robusta: {str(e)}")
            return []

    def _safe_extract_text(self, element):
        try:
            selectors = [".//h3", ".//h4", ".//div[contains(@class, 'title')]", ".//div[contains(@class, 'header')]"]
            for selector in selectors:
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

    def _safe_extract_price(self, element):
        try:
            price_selectors = [
                ".//span[contains(@class, 'a8Pemb')]",
                ".//span[contains(@class, 'e10twf')]",
                ".//div[contains(text(), 'R$')]",
                ".//span[@aria-hidden='true']",
                ".//span[contains(@class, 'currency')]",
                ".//div[contains(@class, 'sh-price')]",
                ".//span[contains(@class, 'formatted-price')]",
                ".//div[contains(@class, 'price-container')]",
            ]
            for selector in price_selectors:
                try:
                    el = element.find_element(By.XPATH, selector)
                    price_text = el.text.strip()
                    if price_text and self._is_valid_price_text(price_text):
                        return price_text
                except:
                    continue
            return "Preço não disponível"
        except:
            return "Preço não disponível"

    def _is_valid_price_text(self, text):
        if not text:
            return False
        if 'R$' in text or '$' in text:
            return True
        return False

    def _safe_extract_url(self, element):
        try:
            if element.tag_name == 'a':
                return element.get_attribute('href')
            link = element.find_element(By.XPATH, ".//a")
            return link.get_attribute('href')
        except:
            return "#"

    def _safe_extract_img(self, element):
        try:
            img = element.find_element(By.XPATH, ".//img")
            return img.get_attribute('src')
        except:
            return ""

    def _convert_image_to_url(self, image=None, image_url=None, image_data=None):
        try:
            img_buffer = io.BytesIO()
            if image:
                image.save(img_buffer, format='JPEG')
            elif image_data:
                img_buffer.write(image_data)
            elif image_url:
                response = requests.get(image_url)
                img_buffer.write(response.content)
            else:
                return None
            img_buffer.seek(0)
            files = {'image': ('image.jpg', img_buffer, 'image/jpeg')}
            response = requests.post(
                'https://api.imgbb.com/1/upload',
                params={'key': '8234882d2cc5bc9c7f2f239283951076'},
                files=files
            )
            return response.json()['data']['url']
        except:
            return None

    def _extract_with_javascript(self):
        try:
            return self.driver.execute_script("""
                const results = [];
                document.querySelectorAll('div.sh-dgr__grid-result').forEach(item => {
                    results.push({
                        nome: item.querySelector('h3')?.textContent || 'Produto similar',
                        preco: item.querySelector('span.a8Pemb')?.textContent || 'Preço não disponível',
                        url: item.querySelector('a')?.href || '#',
                        img: item.querySelector('img')?.src || ''
                    });
                });
                return results.slice(0, 5);
            """)
        except:
            return []

    def buscar_produtos_por_url(self, image_url):
        if not self._initialize_driver():
            return []
        try:
            encoded_url = urllib.parse.quote(image_url)
            search_url = f"{self.base_url}{encoded_url}"
            self.driver.get(search_url)
            time.sleep(5)
            try:
                shopping_tab = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Shopping')]"))
                )
                shopping_tab.click()
                time.sleep(5)
            except:
                pass
            produtos = self._extract_products_robust()
            return produtos
        finally:
            self.cleanup()

    def _safe_extract_price_from_string(self, price_str):
        if not price_str or price_str == "Preço não disponível":
            return 0.0
        price_str = re.sub(r'[^0-9.,]', '', price_str).replace(',', '.')
        try:
            return float(price_str)
        except ValueError:
            return 0.0

    def calcular_valores_estimados(self, ficha):
        precos = [self._safe_extract_price_from_string(p['preco']) for p in ficha.get('produtos_similares', []) if self._safe_extract_price_from_string(p['preco']) > 0]
        media_precos = sum(precos) / len(precos) if precos else 0.0
        valor_de_mercado = media_precos * 0.5 if media_precos > 0 else float(ficha.get('valor', 0))
        valor_base = valor_de_mercado
        valores = {
            'valorDeMercado': self._calcular_despesas(valor_base),
            'valorEstimado': self._calcular_despesas(valor_base * 1.05),
            'demandaMedia': self._calcular_despesas(valor_base * 1.05 * 1.05),
            'demandaAlta': self._calcular_despesas(valor_base * 1.05 * 1.10),
        }
        ficha['valoresEstimados'] = valores
        ficha['valorOriginal'] = float(ficha.get('valor', 0))
        return ficha

    def _calcular_despesas(self, base):
        imposto = base * 0.06
        comissao = base * 0.15
        cartao = base * 0.05
        total_despesas = imposto + comissao + cartao
        total_final = base - total_despesas
        return {
            'base': base,
            'imposto': imposto,
            'comissao': comissao,
            'cartaoCredito': cartao,
            'totalDespesas': total_despesas,
            'totalFinal': total_final
        }

finder = ProdutoFinder()

def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except:
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
    if request.method =="POST":
        if request.form['username'] == 'admin' and request.form['password'] == 'admin123':
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
    status_filtro = request.args.get('status')
    page = request.args.get('page', 1, type=int)
    per_page = 15
    conn = get_db_connection()
    if not conn:
        return "Erro ao conectar ao banco de dados", 500
    cursor = conn.cursor(dictionary=True)
    count_sql = "SELECT COUNT(DISTINCT entry_id) AS total FROM frmt_form_entry_meta"
    params = () if not status_filtro else (status_filtro,)
    if status_filtro:
        count_sql += " WHERE entry_id IN (SELECT entry_id FROM frmt_form_entry_meta WHERE meta_key = 'radio-3' AND meta_value = %s)"
    cursor.execute(count_sql, params)
    total_records = cursor.fetchone()['total']
    total_pages = math.ceil(total_records / per_page)
    offset = (page - 1) * per_page
    sql = """
        SELECT
            entry_id AS id,
            MAX(CASE WHEN meta_key = 'name-1' THEN meta_value END) AS nome,
            MAX(CASE WHEN meta_key = 'cpf-1' THEN meta_value END) AS cpf,
            MAX(CASE WHEN meta_key = 'phone-1' THEN meta_value END) AS telefone,
            MAX(CASE WHEN meta_key = 'email-1' THEN meta_value END) AS email,
            MAX(CASE WHEN meta_key = 'produto-1' THEN meta_value END) AS produto,
            MAX(CASE WHEN meta_key = 'marca-1' THEN meta_value END) AS marca,
            MAX(CASE WHEN meta_key = 'quantidade-1' THEN meta_value END) AS quantidade,
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
            MAX(CASE WHEN meta_key = 'bairro-1' THEN meta_value END) AS bairro,
            MAX(CASE WHEN meta_key = 'outro_bairro-1' THEN meta_value END) AS outroBairro,
            MAX(CASE WHEN meta_key = 'voltagem-1' THEN meta_value END) AS voltagem,
            MAX(CASE WHEN meta_key = 'precisa_limpeza-1' THEN meta_value END) AS precisa_limpeza,
            MAX(CASE WHEN meta_key = 'precisa_desmontagem-1' THEN meta_value END) AS precisa_desmontagem,
            MAX(CASE WHEN meta_key = 'possui_nota_fiscal-1' THEN meta_value END) AS possui_nota_fiscal,
            MAX(CASE WHEN meta_key = 'aceita_credito-1' THEN meta_value END) AS aceita_credito,
            MAX(CASE WHEN meta_key = 'tipo_reparo-1' THEN meta_value END) AS tipo_reparo,
            MAX(CASE WHEN meta_key = 'estado-1' THEN meta_value END) AS estado_json,
            MAX(CASE WHEN meta_key = 'upload-1' THEN meta_value END) AS arquivo
        FROM frmt_form_entry_meta
    """
    group_params = (per_page, offset)
    if status_filtro:
        sql += " WHERE entry_id IN (SELECT entry_id FROM frmt_form_entry_meta WHERE meta_key = 'radio-3' AND meta_value = %s)"
        group_params = (status_filtro, per_page, offset)
    sql += " GROUP BY entry_id ORDER BY id DESC LIMIT %s OFFSET %s"
    cursor.execute(sql, group_params)
    fichas = cursor.fetchall()
    for ficha in fichas:
        if ficha.get('arquivo'):
            try:
                dados = phpserialize.loads(ficha['arquivo'].encode('utf-8'), decode_strings=True)
                ficha['arquivo_url'] = dados['file']['file_url'][0]
            except:
                ficha['arquivo_url'] = None
        ficha['estado'] = json.loads(ficha.get('estado_json', '[]'))
        ficha['bairro_nome'] = BAIRROS.get(int(ficha.get('bairro', 0)), "Bairro não encontrado")
    cursor.close()
    conn.close()
    pagination = {
        'page': page,
        'total_pages': total_pages,
        # add other
    }
    return render_template('lista_fichas.html', fichas=fichas, pagination=pagination, status_filtro=status_filtro)

@app.route('/detalhes/<int:id>')
@login_required
def detalhes_ficha(id):
    conn = get_db_connection()
    if not conn:
        return "Erro ao conectar ao banco de dados", 500
    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT
            entry_id AS id,
            MAX(CASE WHEN meta_key = 'name-1' THEN meta_value END) AS nome,
            MAX(CASE WHEN meta_key = 'cpf-1' THEN meta_value END) AS cpf,
            MAX(CASE WHEN meta_key = 'phone-1' THEN meta_value END) AS telefone,
            MAX(CASE WHEN meta_key = 'email-1' THEN meta_value END) AS email,
            MAX(CASE WHEN meta_key = 'produto-1' THEN meta_value END) AS produto,
            MAX(CASE WHEN meta_key = 'marca-1' THEN meta_value END) AS marca,
            MAX(CASE WHEN meta_key = 'quantidade-1' THEN meta_value END) AS quantidade,
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
            MAX(CASE WHEN meta_key = 'bairro-1' THEN meta_value END) AS bairro,
            MAX(CASE WHEN meta_key = 'outro_bairro-1' THEN meta_value END) AS outroBairro,
            MAX(CASE WHEN meta_key = 'voltagem-1' THEN meta_value END) AS voltagem,
            MAX(CASE WHEN meta_key = 'precisa_limpeza-1' THEN meta_value END) AS precisa_limpeza,
            MAX(CASE WHEN meta_key = 'precisa_desmontagem-1' THEN meta_value END) AS precisa_desmontagem,
            MAX(CASE WHEN meta_key = 'possui_nota_fiscal-1' THEN meta_value END) AS possui_nota_fiscal,
            MAX(CASE WHEN meta_key = 'aceita_credito-1' THEN meta_value END) AS aceita_credito,
            MAX(CASE WHEN meta_key = 'tipo_reparo-1' THEN meta_value END) AS tipo_reparo,
            MAX(CASE WHEN meta_key = 'estado-1' THEN meta_value END) AS estado_json,
            MAX(CASE WHEN meta_key = 'upload-1' THEN meta_value END) AS arquivo
        FROM frmt_form_entry_meta
        WHERE entry_id = %s
        GROUP BY entry_id
    """
    cursor.execute(sql, (id,))
    ficha = cursor.fetchone()
    if not ficha:
        return "Ficha não encontrada", 404
    if ficha.get('arquivo'):
        try:
            dados = phpserialize.loads(ficha['arquivo'].encode('utf-8'), decode_strings=True)
            ficha['arquivo_url'] = dados['file']['file_url'][0]
        except:
            ficha['arquivo_url'] = None
    if ficha['arquivo_url']:
        produtos = finder.buscar_produtos_por_url(ficha['arquivo_url'])
        ficha['produtos_similares'] = produtos
    else:
        ficha['produtos_similares'] = []
    ficha = finder.calcular_valores_estimados(ficha)
    if ficha.get('dataDeCompra'):
        try:
            data_obj = datetime.strptime(ficha['dataDeCompra'], '%Y-%m-%d')
            ficha['dataDeCompra_br'] = data_obj.strftime('%d/%m/%Y')
        except:
            ficha['dataDeCompra_br'] = ficha['dataDeCompra']
    ficha['bairro_nome'] = BAIRROS.get(int(ficha.get('bairro', 0)), "Bairro não encontrado")
    ficha['estado'] = json.loads(ficha.get('estado_json', '[]'))
    cursor.close()
    conn.close()
    return render_template('detalhes_ficha.html', ficha=ficha)

@app.route('/nova_ficha')
@login_required
def nova_ficha():
    return render_template('nova_ficha.html', bairros=BAIRROS)

@app.route('/preview_ficha', methods=['POST'])
@login_required
def preview_ficha():
    form_data = {
        'nome': request.form.get('nome', ''),
        'cpf': request.form.get('cpf', ''),
        'telefone': request.form.get('telefone', ''),
        'email': request.form.get('email', ''),
        'produto': request.form.get('produto', ''),
        'marca': request.form.get('marca', ''),
        'quantidade': request.form.get('quantidade', '1'),
        'data_compra': request.form.get('data_compra', ''),
        'valor': request.form.get('valor_unitario', '0'),
        'marcaUso': request.form.get('marcas_uso', ''),
        'descricao': request.form.get('descricao', ''),
        'altura': request.form.get('altura', '0'),
        'largura': request.form.get('largura', '0'),
        'profundidade': request.form.get('profundidade', '0'),
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
    if 'imagem' in request.files and request.files['imagem'].filename != '':
        imagem = request.files['imagem']
        img = Image.open(imagem)
        form_data['imagem_url'] = finder._convert_image_to_url(image=img)
        if form_data['imagem_url']:
            form_data['produtos_similares'] = finder.buscar_produtos_por_url(form_data['imagem_url'])
    form_data['bairro_nome'] = BAIRROS.get(form_data['bairro'], "Bairro não encontrado")
    if form_data['data_compra']:
        try:
            data_obj = datetime.strptime(form_data['data_compra'], '%Y-%m-%d')
            form_data['data_compra_br'] = data_obj.strftime('%d/%m/%Y')
        except:
            form_data['data_compra_br'] = form_data['data_compra']
    else:
        form_data['data_compra_br'] = ''
    form_data = finder.calcular_valores_estimados(form_data)
    return render_template('preview_ficha.html', ficha=form_data)

@app.route('/cadastrar_ficha', methods=['POST'])
@login_required
def cadastrar_ficha():
    conn = get_db_connection()
    if not conn:
        return "Erro ao conectar ao banco de dados", 500
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(entry_id) FROM frmt_form_entry_meta")
    entry_id = (cursor.fetchone()[0] or 0) + 1
    meta_data = [
        ('name-1', request.form.get('nome', '')),
        ('cpf-1', request.form.get('cpf', '')),
        ('phone-1', request.form.get('telefone', '')),
        ('email-1', request.form.get('email', '')),
        ('produto-1', request.form.get('produto', '')),
        ('marca-1', request.form.get('marca', '')),
        ('quantidade-1', request.form.get('quantidade', '')),
        ('text-4', request.form.get('data_compra', '')),
        ('currency-1', request.form.get('valor_unitario', '')),
        ('text-2', request.form.get('marcas_uso', '')),
        ('text-1', request.form.get('descricao', '')),
        ('number-1', request.form.get('altura', '')),
        ('number-2', request.form.get('largura', '')),
        ('number-3', request.form.get('profundidade', '')),
        ('bairro-1', request.form.get('bairro', '')),
        ('outro_bairro-1', request.form.get('outro_bairro', '')),
        ('voltagem-1', request.form.get('voltagem', '')),
        ('precisa_limpeza-1', request.form.get('precisa_limpeza', '')),
        ('precisa_desmontagem-1', request.form.get('precisa_desmontagem', '')),
        ('possui_nota_fiscal-1', request.form.get('possui_nota_fiscal', '')),
        ('aceita_credito-1', request.form.get('aceita_credito', '')),
        ('tipo_reparo-1', request.form.get('tipo_reparo', '')),
        ('estado-1', json.dumps(request.form.getlist('estado[]'))),
        ('radio-3', 'Pendente'),
    ]
    if request.form.get('imagem_url'):
        arquivo_data = phpserialize.dumps({'file': {'file_url': [request.form.get('imagem_url')]}})
        meta_data.append(('upload-1', arquivo_data.decode('utf-8')))
    for key, value in meta_data:
        cursor.execute("INSERT INTO frmt_form_entry_meta (entry_id, meta_key, meta_value) VALUES (%s, %s, %s)", (entry_id, key, value))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('lista_fichas'))

@app.route('/atualizar_status/<int:id>', methods=['POST'])
@login_required
def atualizar_status(id):
    novo_status = request.form['status']
    conn = get_db_connection()
    if not conn:
        return "Erro ao conectar ao banco de dados", 500
    cursor = conn.cursor()
    cursor.execute("UPDATE frmt_form_entry_meta SET meta_value = %s WHERE entry_id = %s AND meta_key = 'radio-3'", (novo_status, id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('detalhes_ficha', id=id))

if __name__ == '__main__':
    app.run(debug=True)
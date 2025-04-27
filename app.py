import os
import re
import time
import requests
import io
import base64
import logging
import json
from datetime import datetime
from functools import wraps
from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import phpserialize
import math

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'chave_secreta_aqui')

# Configuração da conexão com o banco de dados MySQL
DB_CONFIG = {
    'host': '162.241.62.121',
    'port': 3306,
    'user': 'mudeit26_teste',
    'password': 'teste2025@',
    'database': 'mudeit26_site'
}


# Classe para buscar produtos por imagem no Google Lens
class ProdutoFinder:
    def __init__(self):
        self.driver = None
        self.max_retries = 3
        self.page_load_timeout = 40

    def _convert_image_to_url(self, image):
        """
        Converte uma imagem para URL usando o serviço imgbb
        """
        try:
            if image.mode != 'RGB':
                image = image.convert('RGB')

            img_buffer = io.BytesIO()
            image.save(img_buffer, format='JPEG', quality=95)
            img_buffer.seek(0)

            retries = 3
            for attempt in range(retries):
                try:
                    files = {'image': ('image.jpg', img_buffer, 'image/jpeg')}
                    response = requests.post(
                        'https://api.imgbb.com/1/upload',
                        params={'key': '8234882d2cc5bc9c7f2f239283951076'},
                        files=files,
                        timeout=30
                    )

                    if response.status_code == 200:
                        url = response.json()['data']['url']
                        logger.info(f"Imagem convertida para URL: {url}")
                        return url
                    else:
                        logger.error(f"Erro no upload da imagem: {response.status_code}")
                        if attempt < retries - 1:
                            time.sleep(2)
                            continue
                except Exception as e:
                    logger.error(f"Tentativa {attempt + 1} falhou: {str(e)}")
                    if attempt < retries - 1:
                        time.sleep(2)
                        continue
            return None

        except Exception as e:
            logger.error(f"Erro ao converter imagem: {str(e)}")
            return None

    def _initialize_driver(self):
        chrome_options = Options()

        # Essential configurations
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')

        # Anti-bot detection
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # User agent mais realista
        chrome_options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36')

        # Outras configurações
        chrome_options.add_argument('--lang=pt-BR')
        chrome_options.add_argument('--window-size=1920,1080')

        # Memory optimization
        chrome_options.add_argument('--memory-pressure-off')
        chrome_options.add_argument('--disk-cache-size=1')
        chrome_options.add_argument('--media-cache-size=1')
        chrome_options.add_argument('--disable-application-cache')
        chrome_options.add_argument('--aggressive-cache-discard')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-logging')

        # Performance settings
        prefs = {
            'profile.managed_default_content_settings.images': 2,
            'profile.default_content_settings.images': 2,
            'disk-cache-size': 1,
            'profile.password_manager_enabled': False,
            'profile.default_content_settings.popups': 2,
            'download.prompt_for_download': False,
            'download.default_directory': '/tmp/downloads'
        }
        chrome_options.add_experimental_option('prefs', prefs)

        try:
            service = Service(
                executable_path='/usr/local/bin/chromedriver',
                log_path='/dev/null'  # Disable logging
            )

            self.driver = webdriver.Chrome(
                service=service,
                options=chrome_options
            )

            # Adicionar JavaScript para ocultar automação
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })

            self.driver.set_page_load_timeout(self.page_load_timeout)
            self.driver.implicitly_wait(10)

            return True
        except Exception as e:
            logger.error(f"Driver initialization failed: {str(e)}")
            if self.driver:
                self.driver.quit()
            return False

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        """Explicit cleanup method"""
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.delete_all_cookies()
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error in cleanup: {str(e)}")
            finally:
                self.driver = None

    def buscar_produtos(self, imagem):
        try:
            if not self.driver and not self._initialize_driver():
                logger.error("Falha ao inicializar o driver")
                return []

            img_url = self._convert_image_to_url(imagem)
            if not img_url:
                logger.error("Falha ao converter imagem para URL")
                return []

            # URL direta para o Google Lens com a imagem
            search_url = f"https://lens.google.com/uploadbyurl?url={img_url}"
            products = []

            logger.info(f"Buscando no Google Lens: {search_url}")

            for attempt in range(self.max_retries):
                try:
                    self.driver.delete_all_cookies()
                    self.driver.get(search_url)

                    # Tempo de espera maior para carregamento da página
                    logger.info("Aguardando carregamento da página...")
                    time.sleep(10)  # Aumentado para 10 segundos

                    # Verificar se a página foi carregada corretamente
                    page_source = self.driver.page_source
                    if "Google Lens" not in page_source:
                        logger.warning(f"Página do Google Lens não carregou corretamente (tentativa {attempt + 1})")
                        if attempt < self.max_retries - 1:
                            self._initialize_driver()
                            continue

                    # Tentar localizar o botão "Shopping" e clicar nele, se existir
                    try:
                        shopping_tab = self.driver.find_element(By.XPATH, "//div[contains(text(), 'Shopping')]")
                        shopping_tab.click()
                        time.sleep(5)  # Esperar o carregamento após clicar
                        logger.info("Clicou na aba Shopping")
                    except Exception as e:
                        logger.warning(f"Não foi possível encontrar a aba Shopping: {str(e)}")

                    # Salvar screenshot para debug
                    self.driver.save_screenshot(f'/tmp/lens_attempt_{attempt}.png')
                    logger.info(f"Screenshot salvo em /tmp/lens_attempt_{attempt}.png")

                    products = self._extract_products_selenium()
                    if products:
                        logger.info(f"Encontrados {len(products)} produtos")
                        break
                    else:
                        logger.warning(f"Nenhum produto encontrado na tentativa {attempt + 1}")

                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Tentativa {attempt + 1} falhou: {str(e)}")
                    if attempt < self.max_retries - 1:
                        self._initialize_driver()

            return products[:5]  # Limit results to reduce memory usage

        except Exception as e:
            logger.error(f"Busca de produtos falhou: {str(e)}")
            return []
        finally:
            self.cleanup()  # Ensure cleanup after each search

    def _extract_products_selenium(self):
        """Extrai produtos usando XPath"""
        products = []
        try:
            # Ajuste para aguardar o carregamento dos resultados (usando WebDriverWait)
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            # Esperar elementos de produtos carregarem
            wait = WebDriverWait(self.driver, 15)

            # Xpaths atualizados para o Google Lens (verifique a estrutura atual)
            product_containers = wait.until(EC.presence_of_all_elements_located(
                (By.XPATH, "//div[contains(@class, 'UAiK1e')]//div[contains(@class, 'Lv3Kxc')]")
            ))

            logger.info(f"Encontrados {len(product_containers)} produtos potenciais")

            for container in product_containers[:10]:
                try:
                    # Extrair título
                    title_element = container.find_element(By.XPATH, ".//div[contains(@class, 'AJB7ye')]")
                    title = title_element.text.strip() if title_element else None

                    # Extrair link
                    link_element = container.find_element(By.XPATH, ".//a")
                    link = link_element.get_attribute('href') if link_element else None

                    # Extrair preço
                    price_element = container.find_element(By.XPATH, ".//span[contains(@class, 'e10twf')]")
                    price_text = price_element.text.strip() if price_element else None
                    price = None

                    if price_text:
                        # Extrair números do preço
                        price_matches = re.findall(r'R\$\s*[\d.,]+|\d+[\d.,]*\s*reais', price_text)
                        if price_matches:
                            price_str = price_matches[0]
                            price = float(re.sub(r'[^\d,.]', '', price_str).replace(',', '.'))

                    # Extrair imagem
                    img_element = container.find_element(By.XPATH, ".//img")
                    img = img_element.get_attribute('src') if img_element else None

                    if title and link:
                        product = {
                            "nome": title,
                            "preco": price,
                            "link": link,
                            "imagem": img
                        }
                        products.append(product)
                        logger.info(f"Produto encontrado: {title}")

                except Exception as e:
                    logger.error(f"Erro ao extrair dados do produto: {str(e)}")
                    continue

            return products

        except Exception as e:
            logger.error(f"Erro ao extrair produtos: {str(e)}")
            # Salvar screenshot para debug
            try:
                self.driver.save_screenshot('/tmp/lens_error.png')
                logger.info("Screenshot salvo em /tmp/lens_error.png")
            except:
                pass
            return []


# Instância do ProdutoFinder
finder = ProdutoFinder()


# Função para obter uma conexão com o banco de dados
def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        return None


# Decorator para verificar se o usuário está logado
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

        # Validação simples (substitua por uma lógica de autenticação real)
        if username == 'admin' and password == 'admin123':
            session['logged_in'] = True  # Define a sessão como logada
            return redirect(url_for('lista_fichas'))
        else:
            return "Usuário ou senha inválidos", 401

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)  # Remove o status de logado da sessão
    return redirect(url_for('login'))


@app.route('/')
@login_required
def lista_fichas():
    """Página principal que lista todas as fichas com paginação"""
    status_filtro = request.args.get('status')

    # Parâmetros de paginação
    page = request.args.get('page', 1, type=int)  # Página atual (padrão: 1)
    per_page = 15  # Itens por página

    try:
        conn = get_db_connection()
        if not conn:
            return "Erro ao conectar ao banco de dados", 500

        cursor = conn.cursor(dictionary=True)

        # Consulta para contar o total de registros (para paginação)
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

        # Cálculo do offset para paginação
        offset = (page - 1) * per_page

        # Consulta SQL para listar as fichas com paginação
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

        # Calcular os valores para paginação
        start_page = page - 2 if page > 2 else 1
        end_page = start_page + 4
        if end_page > total_pages:
            end_page = total_pages
            start_page = end_page - 4 if end_page > 4 else 1

        # Passando dados de paginação para o template
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
    """Página de detalhes de uma ficha específica"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Erro ao conectar ao banco de dados", 500

        cursor = conn.cursor(dictionary=True)

        # Consulta SQL para obter detalhes de uma ficha específica
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

        dados_serializados = ficha['arquivo'].encode('utf-8')
        dados = phpserialize.loads(dados_serializados, decode_strings=True)
        ficha['arquivo_url'] = dados['file']['file_url'][0]

        cursor.close()

        if not ficha:
            conn.close()
            return "Ficha não encontrada", 404

        # Buscar produtos similares usando a imagem (se disponível)
        produtos_similares = []
        if ficha.get('arquivo_url'):
            try:
                arquivo_path = ficha['arquivo_url']
                # Se for uma URL, baixa a imagem
                if arquivo_path.startswith(('http://', 'https://')):
                    response = requests.get(arquivo_path)
                    if response.status_code == 200:
                        img = Image.open(io.BytesIO(response.content))
                        # Busca produtos similares usando a imagem
                        produtos_similares = finder.buscar_produtos(img)
                # Se for um caminho local
                else:
                    if os.path.exists(arquivo_path):
                        img = Image.open(arquivo_path)
                        produtos_similares = finder.buscar_produtos(img)
            except Exception as e:
                logger.error(f"Erro ao buscar produtos similares: {str(e)}")

        conn.close()

        # Cálculo do valor estimado e outras informações
        valor_estimado = float(ficha['valor']) if ficha.get('valor') else 0.0

        # Cálculo da demanda média e alta
        demanda_media = valor_estimado + (valor_estimado * 0.05)
        demanda_alta = valor_estimado + (valor_estimado * 0.10)

        # Adiciona os valores calculados à ficha
        ficha['valorEstimado'] = valor_estimado
        ficha['demandaMedia'] = demanda_media
        ficha['demandaAlta'] = demanda_alta
        ficha['produtos_similares'] = produtos_similares

        return render_template('detalhes_ficha.html', ficha=ficha)

    except Exception as e:
        logger.error(f"Erro ao exibir detalhes da ficha: {str(e)}")
        return f"Erro ao processar a solicitação: {str(e)}", 500


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

        # Atualizar o status na tabela
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


if __name__ == '__main__':
    app.run(debug=True)
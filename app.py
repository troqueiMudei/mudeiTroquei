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

# Configuração da conexão com o banco de dados MySQL - ORIGINAL
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
        precos = [self._safe_extract_price_from_string(p['preco']) for p in ficha.get('produtos_similares', []) if
                  self._safe_extract_price_from_string(p['preco']) > 0]
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


# Função para obter uma conexão com o banco de dados - ORIGINAL
def get_db_connection():
    max_retries = 3
    retry_delay = 5
    for attempt in range(max_retries):
        try:
            logger.info(f"Tentativa {attempt + 1} de conexão com o MySQL em {DB_CONFIG['host']}")
            # Adicionando parâmetros para evitar "Unread result found"
            connection = mysql.connector.connect(
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database'],
                connection_timeout=30,
                connect_timeout=30,
                consume_results=True,  # Importante para evitar "Unread result found"
                autocommit=True
            )
            # Teste de conexão mais robusto
            cursor = connection.cursor(buffered=True)  # Usando cursor buffered
            cursor.execute("SELECT 1")
            cursor.fetchall()  # Garantindo que todos os resultados são lidos
            cursor.close()
            logger.info("Conexão com MySQL estabelecida com sucesso")
            return connection
        except mysql.connector.Error as err:
            logger.error(f"Erro ao conectar ao MySQL (tentativa {attempt + 1}): {err}")
            if err.errno == mysql.connector.errorcode.ER_UNKNOWN_ERROR and "Unread result found" in str(err):
                logger.warning("Tentando reconectar após 'Unread result found'...")
                time.sleep(retry_delay)
                continue
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"Erro inesperado ao conectar ao MySQL: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    logger.error("Falha ao conectar ao MySQL após várias tentativas")
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
        # Consulta SQL para listar as fichas com paginação - ESTRUTURA ORIGINAL
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
    """Página de detalhes de uma ficha específica com busca de produtos similares"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Erro ao conectar ao banco de dados", 500
        cursor = conn.cursor(dictionary=True)
        # Consulta SQL para obter detalhes da ficha - ESTRUTURA ORIGINAL
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
        # Processar informação de arquivo (imagem)
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
        # Buscar produtos similares usando a imagem (se disponível)
        if ficha.get('arquivo_url'):
            print(f"\nIniciando busca para imagem: {ficha['arquivo_url']}")
            finder_instance = ProdutoFinder()
            try:
                produtos = finder_instance.buscar_produtos_por_url(ficha['arquivo_url'])
                ficha['produtos_similares'] = produtos or []  # Garante lista vazia se None
                # Debug adicional
                if not produtos:
                    print("Nenhum produto similar encontrado")
                else:
                    print(f"Encontrados {len(produtos)} produtos similares")
            except Exception as e:
                print(f"Erro na busca: {str(e)}")
                ficha['produtos_similares'] = []
            finally:
                finder_instance.cleanup()
        else:
            ficha['produtos_similares'] = []
            print("Nenhuma URL de imagem disponível para busca")
        # Cálculo do valor estimado e outras informações (com tratamento para valores nulos)
        try:
            valor_estimado = float(ficha.get('valor', '0'))
        except (ValueError, TypeError):
            valor_estimado = 0.0
        valor_estimado = valor_estimado * 1.05
        # Adiciona os valores calculados à ficha
        ficha['valorEstimado'] = float(valor_estimado)
        ficha['demandaMedia'] = float(valor_estimado * 1.05)  # +5%
        ficha['demandaAlta'] = float(valor_estimado * 1.10)  # +10%
        # Formatar data de compra para o formato brasileiro
        if ficha.get('dataDeCompra'):
            try:
                # Tenta parsear a data para formato brasileiro
                data_obj = datetime.strptime(ficha['dataDeCompra'], '%Y-%m-%d')
                ficha['dataDeCompra_br'] = data_obj.strftime('%d/%m/%Y')
            except ValueError:
                try:
                    # Tenta parsear caso já esteja no formato DD/MM/YYYY
                    datetime.strptime(ficha['dataDeCompra'], '%d/%m/%Y')
                    ficha['dataDeCompra_br'] = ficha['dataDeCompra']
                except ValueError:
                    ficha['dataDeCompra_br'] = ficha['dataDeCompra']
        else:
            ficha['dataDeCompra_br'] = None
        # Garantir valores padrão para dimensões
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


@app.route('/nova_ficha')
@login_required
def nova_ficha():
    """Exibe o formulário para cadastrar uma nova ficha"""
    return render_template('nova_ficha.html', bairros=BAIRROS)


@app.route('/preview_ficha', methods=['POST'])
@login_required
def preview_ficha():
    """Rota para visualizar os dados do formulário antes de cadastrar"""
    try:
        # Coleta dos dados do formulário - ADAPTADO PARA O TEMPLATE
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
        # Processar imagem
        if 'imagem' in request.files:
            imagem = request.files['imagem']
            if imagem.filename != '':
                try:
                    img = Image.open(imagem)
                    img_url = finder._convert_image_to_url(image=img)
                    form_data['imagem_url'] = img_url
                    # Buscar produtos similares
                    if img_url:
                        form_data['produtos_similares'] = finder.buscar_produtos_por_url(img_url)
                except Exception as e:
                    logger.error(f"Erro ao processar imagem: {str(e)}")
                    form_data['erro_imagem'] = str(e)
        # Converter bairro ID para nome
        form_data['bairro_nome'] = BAIRROS.get(form_data['bairro'], "Bairro não encontrado")
        # Formatar data
        if form_data['data_compra']:
            try:
                data_obj = datetime.strptime(form_data['data_compra'], '%Y-%m-%d')
                form_data['data_compra_br'] = data_obj.strftime('%d/%m/%Y')
            except ValueError:
                form_data['data_compra_br'] = form_data['data_compra']
        else:
            form_data['data_compra_br'] = "Não informada"
        # Calcular valores estimados com base nos itens similares
        form_data = finder.calcular_valores_estimados(form_data)
        return render_template('preview_ficha.html', ficha=form_data)
    except Exception as e:
        logger.error(f"Erro ao processar pré-visualização: {str(e)}")
        return render_template('erro.html', mensagem="Ocorreu um erro ao processar a pré-visualização"), 500


@app.route('/cadastrar_ficha', methods=['POST'])
@login_required
def cadastrar_ficha():
    """Rota para cadastrar a ficha após a pré-visualização"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Erro ao conectar ao banco de dados", 500
        cursor = conn.cursor()
        # Obter novo entry_id
        cursor.execute("SELECT MAX(entry_id) FROM frmt_form_entry_meta")
        max_id = cursor.fetchone()[0] or 0
        entry_id = max_id + 1

        # Mapear fields para meta_keys da estrutura original
        meta_data = [
            ('name-1', request.form.get('nome', '')),
            ('phone-1', request.form.get('telefone', '')),
            ('email-1', request.form.get('email', '')),
            ('text-1', request.form.get('descricao', '')),
            ('text-3', request.form.get('localCompra', '')),
            ('text-4', request.form.get('data_compra', '')),
            ('currency-1', request.form.get('valor_unitario', '')),
            ('text-2', request.form.get('marcas_uso', '')),
            ('textarea-1', request.form.get('descricaoItem', '')),
            ('number-1', request.form.get('altura', '')),
            ('number-2', request.form.get('largura', '')),
            ('number-3', request.form.get('profundidade', '')),
            ('radio-1', request.form.get('troca', '')),
            ('text-5', request.form.get('text5', '')),
            ('radio-2', request.form.get('possui_nota_fiscal', '')),
            ('radio-3', 'Pendente')
        ]

        # Adicionar campos específicos do novo formulário
        meta_data.extend([
            ('produto-1', request.form.get('produto', '')),
            ('marca-1', request.form.get('marca', '')),
            ('quantidade-1', request.form.get('quantidade', '')),
            ('bairro-1', request.form.get('bairro', '')),
            ('outro_bairro-1', request.form.get('outro_bairro', '')),
            ('voltagem-1', request.form.get('voltagem', '')),
            ('precisa_limpeza-1', request.form.get('precisa_limpeza', '')),
            ('precisa_desmontagem-1', request.form.get('precisa_desmontagem', '')),
            ('aceita_credito-1', request.form.get('aceita_credito', '')),
            ('tipo_reparo-1', request.form.get('tipo_reparo', '')),
            ('estado-1', json.dumps(request.form.getlist('estado[]')))
        ])

        # Para arquivo, serializar como phpserialize
        if request.form.get('imagem_url'):
            arquivo_data = phpserialize.dumps({'file': {'file_url': [request.form.get('imagem_url')]}})
            meta_data.append(('upload-1', arquivo_data.decode('utf-8')))

        # Inserir no banco
        for meta_key, meta_value in meta_data:
            cursor.execute(
                "INSERT INTO frmt_form_entry_meta (entry_id, meta_key, meta_value) VALUES (%s, %s, %s)",
                (entry_id, meta_key, meta_value)
            )
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('lista_fichas'))
    except Exception as e:
        logger.error(f"Erro ao cadastrar ficha: {str(e)}")
        return render_template('erro.html', mensagem="Ocorreu um erro ao cadastrar a ficha"), 500


if __name__ == '__main__':
    app.run(debug=True)
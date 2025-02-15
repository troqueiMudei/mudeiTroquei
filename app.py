import os
import re
import time
import requests
from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
from PIL import Image
import io
import base64
import logging
import json
from datetime import datetime
from functools import wraps
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'sua_chave_secreta_aqui')

# Configuração do MySQL
app.config['MYSQL_HOST'] = 'viaduct.proxy.rlwy.net'  # Apenas o hostname
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'SOiZeRqyiKiUqqCIcdMrGncUJzzRrIji'
app.config['MYSQL_DB'] = 'railway'
app.config['MYSQL_PORT'] = 24171  # Porta externa

# Adicionar logs para debug
logger.info(f"MySQL Host: {app.config['MYSQL_HOST']}")
logger.info(f"MySQL User: {app.config['MYSQL_USER']}")
logger.info(f"MySQL Database: {app.config['MYSQL_DB']}")
logger.info(f"MySQL Port: {app.config['MYSQL_PORT']}")

mysql = MySQL(app)

logging.basicConfig(level=logging.DEBUG)
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


# Classe para buscar produtos por imagem
class ProdutoFinder:
    def __init__(self):
        self.driver = None
        self.max_retries = 3
        self.page_load_timeout = 40
        self._initialize_driver()

    def _initialize_driver(self):
        chrome_options = Options()

        # Configurações essenciais para Docker
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        # Configurações para melhorar a estabilidade
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-infobars')

        # Configurações de proxy (adicione se necessário)
        chrome_options.add_argument('--proxy-server="direct://"')
        chrome_options.add_argument('--proxy-bypass-list=*')

        # Configurações de performance
        prefs = {
            'profile.managed_default_content_settings.images': 2,
            'profile.default_content_settings.images': 2,
            'disk-cache-size': 4096,
            'profile.password_manager_enabled': False,
            'profile.default_content_settings.popups': 2,
            'download.prompt_for_download': False,
            'download.default_directory': '/tmp/downloads',
            'javascript.enabled': True
        }
        chrome_options.add_experimental_option('prefs', prefs)

        for attempt in range(3):
            try:
                service = Service(
                    executable_path='/usr/local/bin/chromedriver',
                    log_path='/tmp/chromedriver.log'
                )

                self.driver = webdriver.Chrome(
                    service=service,
                    options=chrome_options
                )

                # Configurar timeouts mais longos
                self.driver.set_page_load_timeout(self.page_load_timeout)
                self.driver.implicitly_wait(20)

                # Testar a conexão com retry
                max_test_attempts = 3
                for test_attempt in range(max_test_attempts):
                    try:
                        self.driver.get('about:blank')
                        return True
                    except Exception as e:
                        if test_attempt == max_test_attempts - 1:
                            raise
                        time.sleep(2)
                        continue

            except Exception as e:
                logger.error(f"Tentativa {attempt + 1} de inicialização falhou: {str(e)}")
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None

                if attempt == 2:
                    logger.error("Falha ao inicializar Chrome driver após todas as tentativas")
                    return False

                time.sleep(3)  # Aumentado o tempo de espera entre tentativas

        return False

    def __del__(self):
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error closing Chrome driver: {str(e)}")

    def _convert_image_to_url(self, image):
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

    def buscar_produtos(self, imagem):
        if not self.driver:
            logger.error("Chrome driver não inicializado, tentando reinicializar")
            self._initialize_driver()
            if not self.driver:
                logger.error("Falha ao reinicializar Chrome driver")
                return []

        try:
            img_url = self._convert_image_to_url(imagem)
            if not img_url:
                raise Exception("Não foi possível processar a imagem")

            logger.info("Iniciando busca reversa de imagem")
            search_url = f"https://lens.google.com/uploadbyurl?url={img_url}"

            for attempt in range(self.max_retries):
                try:
                    # Limpar cookies e cache antes de cada tentativa
                    self.driver.delete_all_cookies()

                    # Tentar carregar a página com retry
                    load_attempts = 3
                    for load_attempt in range(load_attempts):
                        try:
                            self.driver.get(search_url)
                            break
                        except Exception as e:
                            if load_attempt == load_attempts - 1:
                                raise
                            time.sleep(2)
                            continue

                    # Esperar mais tempo para a página carregar
                    time.sleep(8)

                    products = self._extract_products_selenium()
                    if products:
                        return products

                    if attempt < self.max_retries - 1:
                        logger.warning(f"Nenhum produto encontrado na tentativa {attempt + 1}, tentando novamente...")
                        time.sleep(3)
                        continue

                except Exception as e:
                    logger.error(f"Erro na tentativa {attempt + 1}: {str(e)}")
                    if attempt < self.max_retries - 1:
                        self._initialize_driver()
                        time.sleep(3)
                        continue

            logger.warning("Nenhum produto encontrado após todas as tentativas")
            return []

        except Exception as e:
            logger.error(f"Erro na busca de produtos: {str(e)}")
            return []

        finally:
            try:
                if self.driver:
                    self.driver.delete_all_cookies()
            except:
                pass

    def _extract_products_selenium(self):
        """Extrai produtos usando XPath"""
        products = []
        try:
            # Lista de XPaths para tentar encontrar resultados
            xpaths = [
                "//div[contains(@class, 'isv-r')]",  # Resultados do Google Lens
                "//div[@class='g' or contains(@class, 'g-card')]",  # Resultados normais do Google
                "//div[.//h3 or .//a[@href]]",  # Qualquer div que contenha um título ou link
                "//div[contains(@style, 'background-image')]",  # Divs com imagens de fundo
                "//a[.//img]"  # Links que contêm imagens
            ]

            result_elements = []
            for xpath in xpaths:
                try:
                    logger.info(f"Tentando XPath: {xpath}")
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    if elements:
                        logger.info(f"Encontrados {len(elements)} elementos com XPath {xpath}")
                        result_elements.extend(elements)
                        break
                except Exception as e:
                    logger.warning(f"XPath {xpath} falhou: {str(e)}")
                    continue

            # Remove elementos duplicados
            result_elements = list(set(result_elements))

            for element in result_elements[:10]:
                try:
                    # Tenta diferentes XPaths para título
                    title = None
                    title_xpaths = [
                        ".//h3",
                        ".//div[contains(@class, 'title')]",
                        ".//a",
                        ".//span[string-length(text()) > 10]"
                    ]

                    for xpath in title_xpaths:
                        try:
                            title_element = element.find_element(By.XPATH, xpath)
                            title = title_element.text.strip()
                            if title:
                                break
                        except:
                            continue

                    if not title:
                        continue

                    # Tenta encontrar link
                    link = None
                    try:
                        link_element = element.find_element(By.XPATH, ".//a")
                        link = link_element.get_attribute('href')
                    except:
                        try:
                            # Tenta encontrar o link no próprio elemento
                            link = element.get_attribute('href')
                        except:
                            continue

                    # Tenta encontrar preço
                    price = None
                    try:
                        # Procura por texto que pareça preço
                        price_text = element.text
                        price_matches = re.findall(r'R\$\s*[\d.,]+|\d+[\d.,]*\s*reais', price_text)
                        if price_matches:
                            price_str = price_matches[0]
                            price = float(re.sub(r'[^\d,.]', '', price_str).replace(',', '.'))
                    except:
                        pass

                    # Tenta encontrar imagem
                    img = None
                    try:
                        img_element = element.find_element(By.XPATH, ".//img")
                        img = img_element.get_attribute('src')
                    except:
                        try:
                            # Tenta encontrar imagem de fundo
                            style = element.get_attribute('style')
                            if style and 'background-image' in style:
                                img = re.findall(r'url\(["\']?(.*?)["\']?\)', style)[0]
                        except:
                            pass

                    if title and link:  # Requisitos mínimos
                        product = {
                            "nome": title,
                            "preco": price,
                            "link": link,
                            "imagem": img
                        }
                        products.append(product)
                        logger.info(f"Produto extraído: {title}")

                except Exception as e:
                    logger.error(f"Erro ao extrair produto individual: {str(e)}")
                    continue

            return products

        except Exception as e:
            logger.error(f"Erro ao extrair produtos: {str(e)}")
            return []


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
            return redirect(url_for('lista_cadastros'))
        else:
            return "Usuário ou senha inválidos", 401

    return render_template('login.html')


# Instância do ProdutoFinder
finder = ProdutoFinder()


@app.route('/logout')
def logout():
    session.pop('logged_in', None)  # Remove o status de logado da sessão
    return redirect(url_for('login'))


@app.route('/', methods=['GET', 'POST'])
def upload_produto():
    if request.method == 'POST':
        logger.info("Recebida requisição POST")

        # Coleta dos dados do formulário
        form_data = {
            'nome': request.form['nome'],
            'cpf': request.form['cpf'],
            'telefone': request.form['telefone'],
            'email': request.form['email'],
            'produto': request.form['produto'],
            'marca': request.form['marca'],
            'dtCompra': request.form['data_compra'],
            'valor': float(request.form['valor_unitario']) if request.form['valor_unitario'] else 0.0,
            'marcaUso': request.form['marcas_uso'],
            'descricao': request.form['descricao'],
            'altura': float(request.form['altura']) if request.form['altura'] else 0.0,
            'largura': float(request.form['largura']) if request.form['largura'] else 0.0,
            'profundidade': float(request.form['profundidade']) if request.form['profundidade'] else 0.0,
            'quantidade': float(request.form['quantidade']) if request.form['quantidade'] else 0.0,
            'outroBairro': request.form.get('outro_bairro', ''),
            'voltagem': request.form['voltagem'],
            'tipoEstado': request.form['tipo_reparo'],
            'bairro': request.form['bairro'],
            'novo': 1 if 'novo' in request.form.getlist('estado[]') else 0,
            'usado': 1 if 'usado' in request.form.getlist('estado[]') else 0,
            'troca': request.form['aceita_credito'],
            'nf': request.form['possui_nota_fiscal'],
            'sujo': request.form['precisa_limpeza'],
            'mofo': 1 if 'possui_mofo' in request.form.getlist('estado[]') else 0,
            'cupim': 1 if 'possui_cupim' in request.form.getlist('estado[]') else 0,
            'trincado': 1 if 'esta_trincado' in request.form.getlist('estado[]') else 0,
            'desmontagem': request.form['precisa_desmontagem'],
            'status': 'Análise',  # Status padrão
            'urgente': 'não',
        }

        # Processamento da imagem
        if 'imagem' in request.files:
            imagem = request.files['imagem']
            img = Image.open(imagem)
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='JPEG')
            img_str = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            form_data['foto1'] = img_str

            # Busca de produtos usando a imagem
            produtos_encontrados = finder.buscar_produtos(img)
            links_produto = json.dumps([{"link": p['link'], "valor": p['preco'], "imagem": p['imagem']} for p in produtos_encontrados])
            fotos_produto = json.dumps([p['imagem'] for p in produtos_encontrados])

            form_data['linksProduto'] = links_produto
            form_data['fotosProduto'] = fotos_produto

        # Inserção no banco de dados
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO fichas (
                nome, cpf, telefone, email, produto, desmontagem, marca, dtCompra, valor, valorEstimado,
                marcaUso, descricao, altura, largura, profundidade, foto1, status, urgente, quantidade,
                outroBairro, voltagem, bairro, tipoEstado, novo, usado, troca, nf, sujo, mofo, cupim,
                trincado, linksProduto, fotosProduto
            ) VALUES (
                %(nome)s, %(cpf)s, %(telefone)s, %(email)s, %(produto)s, %(desmontagem)s, %(marca)s,
                %(dtCompra)s, %(valor)s, %(valor)s, %(marcaUso)s, %(descricao)s, %(altura)s, %(largura)s,
                %(profundidade)s, %(foto1)s, %(status)s, %(urgente)s, %(quantidade)s, %(outroBairro)s,
                %(voltagem)s, %(bairro)s, %(tipoEstado)s, %(novo)s, %(usado)s, %(troca)s, %(nf)s, %(sujo)s,
                %(mofo)s, %(cupim)s, %(trincado)s, %(linksProduto)s, %(fotosProduto)s
            )
        """, form_data)
        mysql.connection.commit()
        cur.close()

        return render_template('upload.html')

    return render_template('upload.html')


@app.route('/lista')
@login_required
def lista_cadastros():
    status_filtro = request.args.get('status')
    cur = mysql.connection.cursor()

    if status_filtro:
        cur.execute("SELECT * FROM fichas WHERE status = %s ORDER BY id DESC", (status_filtro,))
    else:
        cur.execute("SELECT * FROM fichas ORDER BY id DESC")

    fichas = cur.fetchall()
    cur.close()
    return render_template('lista.html', fichas=fichas)

@app.route('/detalhes/<int:id>')
@login_required
def detalhes_ficha(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM fichas WHERE id = %s", (id,))
    ficha = cur.fetchone()
    cur.close()

    # Decodifica os links e fotos dos produtos
    ficha['linksProduto'] = json.loads(ficha['linksProduto']) if ficha['linksProduto'] else []
    ficha['fotosProduto'] = json.loads(ficha['fotosProduto']) if ficha['fotosProduto'] else []

    # Cálculo do valor estimado
    valor_estimado = float(ficha['valor'])

    if ficha['desmontagem'] == 'Sim':
        valor_estimado -= 50.00

    if ficha['sujo'] == 'Sim':
        valor_estimado -= 30.00

    # Cálculo da demanda média e alta
    demanda_media = valor_estimado + (valor_estimado * 0.05)
    demanda_alta = valor_estimado + (valor_estimado * 0.10)

    # Adiciona os valores calculados à ficha
    ficha['valorEstimado'] = valor_estimado
    ficha['demandaMedia'] = demanda_media
    ficha['demandaAlta'] = demanda_alta

    # Converter o número do bairro para o nome do bairro
    ficha['bairro_nome'] = BAIRROS.get(int(ficha['bairro']), "Bairro não encontrado")

    # Converter a data para o formato brasileiro (DD/MM/AAAA)
    if ficha['dtCompra']:
        data_compra = datetime.strptime(ficha['dtCompra'], '%Y-%m-%d')
        ficha['dtCompra_br'] = data_compra.strftime('%d/%m/%Y')
    else:
        ficha['dtCompra_br'] = "Data não informada"

    return render_template('detalhes.html', ficha=ficha)

@app.route('/atualizar_status/  <int:id>', methods=['POST'])
@login_required
def atualizar_status(id):
    novo_status = request.form['status']
    cur = mysql.connection.cursor()
    cur.execute("UPDATE fichas SET status = %s WHERE id = %s", (novo_status, id))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('detalhes_ficha', id=id))


def create_tables():
    try:
        cur = mysql.connection.cursor()

        # Criar tabela fichas se não existir
        cur.execute("""
        CREATE TABLE IF NOT EXISTS fichas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nome VARCHAR(255),
            cpf VARCHAR(14),
            telefone VARCHAR(20),
            email VARCHAR(255),
            produto VARCHAR(255),
            desmontagem VARCHAR(3),
            marca VARCHAR(255),
            dtCompra DATE,
            valor DECIMAL(10,2),
            valorEstimado DECIMAL(10,2),
            marcaUso VARCHAR(255),
            descricao TEXT,
            altura DECIMAL(10,2),
            largura DECIMAL(10,2),
            profundidade DECIMAL(10,2),
            foto1 LONGTEXT,
            status VARCHAR(50),
            urgente VARCHAR(3),
            quantidade DECIMAL(10,2),
            outroBairro VARCHAR(255),
            voltagem VARCHAR(50),
            bairro VARCHAR(50),
            tipoEstado VARCHAR(50),
            novo TINYINT(1),
            usado TINYINT(1),
            troca VARCHAR(3),
            nf VARCHAR(3),
            sujo VARCHAR(3),
            mofo TINYINT(1),
            cupim TINYINT(1),
            trincado TINYINT(1),
            linksProduto TEXT,
            fotosProduto TEXT
        )
        """)

        mysql.connection.commit()
        logger.info("Tabelas criadas/verificadas com sucesso")
    except Exception as e:
        logger.error(f"Erro ao criar tabelas: {str(e)}")
    finally:
        if 'cur' in locals():
            cur.close()


def check_chrome_version():
    try:
        chrome_version = os.popen('google-chrome --version').read().strip()
        logger.info(f"Chrome version: {chrome_version}")
        chromedriver_version = os.popen('chromedriver --version').read().strip()
        logger.info(f"ChromeDriver version: {chromedriver_version}")
    except Exception as e:
        logger.error(f"Error checking versions: {str(e)}")


@app.route('/test-db')
def test_db():
    try:
        cur = mysql.connection.cursor()
        cur.execute('SELECT 1')
        result = cur.fetchone()
        cur.close()
        return {
            'status': 'success',
            'message': 'Conexão com banco de dados estabelecida',
            'config': {
                'host': app.config['MYSQL_HOST'],
                'port': app.config['MYSQL_PORT'],
                'database': app.config['MYSQL_DB']
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'config': {
                'host': app.config['MYSQL_HOST'],
                'port': app.config['MYSQL_PORT'],
                'database': app.config['MYSQL_DB']
            }
        }


if __name__ == '__main__':
    with app.app_context():
        create_tables()
    app.run(debug=True)
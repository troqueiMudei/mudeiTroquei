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
import MySQLdb.cursors

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
        self.page_load_timeout = 90

    def _initialize_driver(self):
        chrome_options = Options()

        # Configurações básicas
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')

        # Configurações para evitar problemas com localStorage
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')

        # User agent mais realista
        chrome_options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36')

        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        try:
            service = Service(
                executable_path='/usr/local/bin/chromedriver',
                log_path='/dev/null'
            )

            self.driver = webdriver.Chrome(
                service=service,
                options=chrome_options
            )

            self.driver.set_page_load_timeout(self.page_load_timeout)
            self.driver.implicitly_wait(30)

            return True
        except Exception as e:
            logger.error(f"Driver initialization failed: {str(e)}")
            if self.driver:
                self.driver.quit()
            return False

    def _wait_for_page_load(self):
        """Espera a página carregar completamente"""
        try:
            # Espera inicial
            time.sleep(20)

            # Espera o estado 'complete' do documento
            self.driver.execute_script("return document.readyState") == "complete"

            # Verifica se há elementos básicos na página
            basic_selectors = ['div', 'a', 'img']
            for selector in basic_selectors:
                elements = self.driver.find_elements(By.TAG_NAME, selector)
                if elements:
                    return True

            return False
        except Exception as e:
            logger.error(f"Erro ao esperar carregamento da página: {str(e)}")
            return False

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

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.delete_all_cookies()
                self.driver.quit()
            except Exception as e:
                logger.error(f"Erro na limpeza: {str(e)}")
            finally:
                self.driver = None

    def buscar_produtos(self, imagem):
        try:
            if not self.driver and not self._initialize_driver():
                return []

            img_url = self._convert_image_to_url(imagem)
            if not img_url:
                return []

            search_url = f"https://lens.google.com/uploadbyurl?url={img_url}"
            products = []

            for attempt in range(self.max_retries):
                try:
                    logger.info(f"Tentativa {attempt + 1} de buscar produtos")

                    # Remover limpeza de localStorage e sessionStorage
                    self.driver.delete_all_cookies()

                    # Navegar para a URL
                    self.driver.get(search_url)

                    # Esperar a página carregar
                    time.sleep(20)  # Espera fixa inicial

                    # Tentar diferentes estratégias de busca
                    selectors = [
                        "//div[contains(@class, 'UAiK1e')]",
                        "//div[contains(@class, 'IZE3Td')]",
                        "//a[contains(@href, 'google')]",
                        "//div[contains(@class, 'kqKHvb')]"
                    ]

                    for selector in selectors:
                        try:
                            elements = WebDriverWait(self.driver, 10).until(
                                EC.presence_of_all_elements_located((By.XPATH, selector))
                            )

                            for element in elements:
                                try:
                                    text = element.text.strip()
                                    href = element.get_attribute('href')

                                    if text and href:
                                        products.append({
                                            "nome": text,
                                            "preco": None,
                                            "link": href,
                                            "imagem": None
                                        })
                                except Exception as e:
                                    logger.error(f"Erro ao processar elemento: {str(e)}")
                                    continue

                        except Exception as e:
                            logger.error(f"Erro com selector {selector}: {str(e)}")
                            continue

                    if products:
                        break

                except Exception as e:
                    logger.error(f"Erro na tentativa {attempt + 1}: {str(e)}")
                    if attempt < self.max_retries - 1:
                        time.sleep(10)
                        self._initialize_driver()

            return products[:5]

        except Exception as e:
            logger.error(f"Erro geral na busca de produtos: {str(e)}")
            return []
        finally:
            self.cleanup()

    def _extract_products_selenium(self):
        products = []
        try:
            # Esperar página carregar completamente
            time.sleep(15)

            # Novo conjunto de seletores mais específicos
            selectors = [
                "//div[contains(@class, 'UAiK1e')]",  # Seletor específico do Google Lens
                "//div[contains(@class, 'IZE3Td')]",  # Outro seletor comum
                "//div[contains(@class, 'RJuLyc')]",  # Container de resultados
                "//a[contains(@class, 'VZqTOd')]",  # Links de produtos
                "//div[contains(@class, 'kqKHvb')]"  # Container de itens
            ]

            for selector in selectors:
                try:
                    # Usar JavaScript para verificar elementos
                    elements = self.driver.execute_script(f"""
                        return document.evaluate(
                            "{selector}",
                            document,
                            null,
                            XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
                            null
                        );
                    """)

                    if elements and elements.snapshotLength > 0:
                        for i in range(elements.snapshotLength):
                            element = elements.snapshotItem(i)

                            # Extrair informações usando JavaScript
                            product_info = self.driver.execute_script("""
                                function extractInfo(element) {
                                    let title = '';
                                    let link = '';

                                    // Tentar diferentes maneiras de obter o título
                                    const possibleTitleElements = element.querySelectorAll('h3, .title, a');
                                    for (const el of possibleTitleElements) {
                                        if (el.textContent.trim()) {
                                            title = el.textContent.trim();
                                            break;
                                        }
                                    }

                                    // Tentar obter o link
                                    const linkElement = element.querySelector('a');
                                    if (linkElement) {
                                        link = linkElement.href;
                                    }

                                    return {title, link};
                                }
                                return extractInfo(arguments[0]);
                            """, element)

                            if product_info['title'] and product_info['link']:
                                products.append({
                                    "nome": product_info['title'],
                                    "preco": None,
                                    "link": product_info['link'],
                                    "imagem": None
                                })

                        if products:
                            break

                except Exception as e:
                    logger.error(f"Erro ao extrair com selector {selector}: {str(e)}")
                    continue

            return products[:5]  # Limitar a 5 resultados

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

    # Usar DictCursor para retornar resultados como dicionários
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

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
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM fichas WHERE id = %s", (id,))
    ficha = cur.fetchone()
    cur.close()

    if not ficha:
        return "Ficha não encontrada", 404

    # Decodifica os links e fotos dos produtos
    ficha['linksProduto'] = json.loads(ficha['linksProduto']) if ficha['linksProduto'] else []
    ficha['fotosProduto'] = json.loads(ficha['fotosProduto']) if ficha['fotosProduto'] else []

    # Cálculo do valor estimado
    valor_estimado = float(ficha['valor']) if ficha['valor'] is not None else 0.0

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
    ficha['bairro_nome'] = BAIRROS.get(int(ficha['bairro']) if ficha['bairro'] else 0, "Bairro não encontrado")

    # Converter a data para o formato brasileiro (DD/MM/AAAA)
    if ficha['dtCompra']:
        data_compra = datetime.strptime(str(ficha['dtCompra']), '%Y-%m-%d')
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
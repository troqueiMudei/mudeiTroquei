import os
import re
import time
import requests
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
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
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'uma_chave_segura_aqui')  # Chave secreta para criptografar a sessão

# Configuração do SQLAlchemy com PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://root:KJl6miHOiN6TXJg8p6ihHq5LbjQ8g65v@dpg-cuh5e7btq21c73f7j630-a/mudeitroquei_znar'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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

# Modelo da tabela Ficha
class Ficha(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(14), nullable=False)
    telefone = db.Column(db.String(15), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    produto = db.Column(db.String(100), nullable=False)
    marca = db.Column(db.String(100), nullable=False)
    dtCompra = db.Column(db.Date, nullable=False)
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    marcaUso = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    altura = db.Column(db.Numeric(10, 2), nullable=False)
    largura = db.Column(db.Numeric(10, 2), nullable=False)
    profundidade = db.Column(db.Numeric(10, 2), nullable=False)
    quantidade = db.Column(db.Numeric(10, 2), nullable=False)
    outroBairro = db.Column(db.String(100), nullable=True)
    voltagem = db.Column(db.String(50), nullable=False)
    tipoEstado = db.Column(db.String(50), nullable=False)
    bairro = db.Column(db.Integer, nullable=False)
    novo = db.Column(db.Boolean, nullable=False, default=False)
    usado = db.Column(db.Boolean, nullable=False, default=False)
    troca = db.Column(db.String(50), nullable=False)
    nf = db.Column(db.String(50), nullable=False)
    sujo = db.Column(db.String(50), nullable=False)
    mofo = db.Column(db.Boolean, nullable=False, default=False)
    cupim = db.Column(db.Boolean, nullable=False, default=False)
    trincado = db.Column(db.Boolean, nullable=False, default=False)
    desmontagem = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    urgente = db.Column(db.String(50), nullable=False)
    foto1 = db.Column(db.Text, nullable=True)
    linksProduto = db.Column(db.Text, nullable=True)
    fotosProduto = db.Column(db.Text, nullable=True)

# Classe para buscar produtos por imagem
class ProdutoFinder:
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 10)

    def __del__(self):
        try:
            self.driver.quit()
        except:
            pass

    def _convert_image_to_url(self, image):
        try:
            if image.mode != 'RGB':
                image = image.convert('RGB')

            img_buffer = io.BytesIO()
            image.save(img_buffer, format='JPEG', quality=95)
            img_buffer.seek(0)

            files = {'image': ('image.jpg', img_buffer, 'image/jpeg')}

            response = requests.post(
                'https://api.imgbb.com/1/upload',
                params={'key': '8234882d2cc5bc9c7f2f239283951076'},
                files=files
            )

            if response.status_code == 200:
                url = response.json()['data']['url']
                logger.info(f"Imagem convertida para URL: {url}")
                return url
            else:
                logger.error(f"Erro no upload da imagem: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Erro ao converter imagem: {str(e)}")
            return None

    def buscar_produtos(self, imagem):
        try:
            img_url = self._convert_image_to_url(imagem)
            if not img_url:
                raise Exception("Não foi possível processar a imagem")

            logger.info("Iniciando busca reversa de imagem com Selenium")

            # URL de busca por imagem do Google Lens
            search_url = f"https://lens.google.com/uploadbyurl?url={img_url}"

            logger.info(f"Acessando URL: {search_url}")
            self.driver.get(search_url)

            # Aguarda mais tempo para a página carregar
            time.sleep(7)

            # Salva screenshot para debug
            self.driver.save_screenshot('debug_page.png')
            logger.info("Screenshot salvo como debug_page.png")

            # Salva HTML para debug
            with open('page_source.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            logger.info("HTML salvo como page_source.html")

            # Tenta encontrar resultados
            products = self._extract_products_selenium()

            if not products:
                logger.warning("Nenhum produto encontrado")
                return []

            return products

        except Exception as e:
            logger.error(f"Erro na busca de produtos: {str(e)}")
            return []

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
            'dtCompra': datetime.strptime(request.form['data_compra'], '%Y-%m-%d'),
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
            'bairro': int(request.form['bairro']),
            'novo': 'novo' in request.form.getlist('estado[]'),
            'usado': 'usado' in request.form.getlist('estado[]'),
            'troca': request.form['aceita_credito'],
            'nf': request.form['possui_nota_fiscal'],
            'sujo': request.form['precisa_limpeza'],
            'mofo': 'possui_mofo' in request.form.getlist('estado[]'),
            'cupim': 'possui_cupim' in request.form.getlist('estado[]'),
            'trincado': 'esta_trincado' in request.form.getlist('estado[]'),
            'desmontagem': request.form['precisa_desmontagem'],
            'status': 'Análise',  # Status padrão
            'urgente': 'não',
        }

        # Log dos dados do formulário
        logger.info(f"Dados do formulário: {form_data}")

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
        try:
            nova_ficha = Ficha(**form_data)
            db.session.add(nova_ficha)
            db.session.commit()
            logger.info("Ficha inserida com sucesso.")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao inserir ficha: {str(e)}. Detalhes: {e.__class__.__name__}, {e.args}")
            return "Erro ao salvar os dados. Tente novamente.", 500

        return render_template('upload.html')

    return render_template('upload.html')

@app.route('/lista')
@login_required
def lista_cadastros():
    status_filtro = request.args.get('status')
    if status_filtro:
        fichas = Ficha.query.filter_by(status=status_filtro).order_by(Ficha.id.desc()).all()
    else:
        fichas = Ficha.query.order_by(Ficha.id.desc()).all()

    return render_template('lista.html', fichas=fichas)

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            logger.info("Tabelas criadas com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao criar tabelas: {str(e)}")
    app.run(debug=True)
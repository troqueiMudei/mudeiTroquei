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
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36'
        ]

    def _convert_image_to_url(self, image=None, image_url=None, image_data=None):
        """
        Converte uma imagem para URL usando o serviço imgbb
        Aceita PIL.Image, URL ou dados binários da imagem
        """
        try:
            if image is not None:
                # Se recebemos uma imagem PIL
                if image.mode != 'RGB':
                    image = image.convert('RGB')

                # Reduzir o tamanho da imagem para melhorar o desempenho
                max_size = (800, 800)
                image.thumbnail(max_size, Image.LANCZOS)

                img_buffer = io.BytesIO()
                image.save(img_buffer, format='JPEG', quality=85)
                img_buffer.seek(0)
                files = {'image': ('image.jpg', img_buffer, 'image/jpeg')}

            elif image_data is not None:
                # Se recebemos dados binários da imagem
                files = {'image': ('image.jpg', image_data, 'image/jpeg')}

            elif image_url is not None:
                # Se recebemos uma URL
                try:
                    # Tenta baixar a imagem da URL com headers adequados
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
                        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                        'Referer': 'https://mude.ind.br/'
                    }

                    response = requests.get(image_url, headers=headers, timeout=20, allow_redirects=True)
                    if response.status_code != 200:
                        logger.error(f"Erro ao baixar imagem da URL para upload: {response.status_code}")
                        return image_url  # Retorna a URL original caso falhe

                    # Upload dos dados baixados
                    files = {'image': ('image.jpg', response.content, 'image/jpeg')}
                except Exception as e:
                    logger.error(f"Erro ao processar URL da imagem: {str(e)}")
                    return image_url  # Retorna a URL original caso falhe
            else:
                logger.error("Nenhum tipo de entrada de imagem válida.")
                return None

            # Upload para o ImgBB
            retries = 3
            for attempt in range(retries):
                try:
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
                        logger.error(f"Erro no upload da imagem: {response.status_code} - {response.text}")
                        if attempt < retries - 1:
                            time.sleep(2)
                            continue
                except Exception as e:
                    logger.error(f"Tentativa {attempt + 1} falhou: {str(e)}")
                    if attempt < retries - 1:
                        time.sleep(2)
                        continue

            # Se chegou aqui e temos uma URL original, retorne ela
            if image_url:
                return image_url

            return None

        except Exception as e:
            logger.error(f"Erro ao converter imagem: {str(e)}")
            # Se temos uma URL original, retorne ela mesmo em caso de erro
            if image_url:
                return image_url
            return None

    def _initialize_driver(self):
        import random

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

        # User agent rotativo mais realista
        user_agent = random.choice(self.user_agents)
        chrome_options.add_argument(f'--user-agent={user_agent}')

        # Configurações de idioma e janela
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
            'profile.default_content_settings.images': 1,  # Permitir imagens para o Google Lens funcionar
            'disk-cache-size': 1,
            'profile.password_manager_enabled': False,
            'profile.default_content_settings.popups': 2,
            'download.prompt_for_download': False,
            'download.default_directory': '/tmp/downloads'
        }
        chrome_options.add_experimental_option('prefs', prefs)

        try:
            # Usar o ChromeDriver mais recente, com melhor compatibilidade
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
                    });

                    // Esconder o WebDriver completamente
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({state: Notification.permission}) :
                            originalQuery(parameters)
                    );
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

    def buscar_produtos_por_url(self, url):
        """Busca produtos diretamente usando a URL da imagem"""
        try:
            if not self.driver and not self._initialize_driver():
                logger.error("Falha ao inicializar o driver")
                return []

            # Primeiro tenta realocar a imagem para o ImgBB para evitar problemas de CORS
            img_url = self._convert_image_to_url(image_url=url)
            if not img_url:
                logger.error("Falha ao converter URL da imagem para serviço confiável")
                img_url = url  # usa a URL original se falhar

            # URL direta para o Google Lens com a imagem
            search_url = f"https://lens.google.com/uploadbyurl?url={img_url}"
            logger.info(f"Buscando no Google Lens: {search_url}")

            return self._executar_busca(search_url)

        except Exception as e:
            logger.error(f"Busca de produtos por URL falhou: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
        finally:
            self.cleanup()

    def buscar_produtos(self, imagem=None, url=None, image_data=None):
        """
        Busca produtos usando uma imagem, URL de imagem ou dados binários
        Parâmetros:
            imagem: objeto PIL.Image
            url: URL da imagem
            image_data: dados binários da imagem
        """
        try:
            # Verifique qual método usar
            if url:
                return self.buscar_produtos_por_url(url)

            if not self.driver and not self._initialize_driver():
                logger.error("Falha ao inicializar o driver")
                return []

            # Converter a imagem para URL
            if imagem:
                img_url = self._convert_image_to_url(image=imagem)
            elif image_data:
                img_url = self._convert_image_to_url(image_data=image_data)
            else:
                logger.error("Nenhuma imagem ou URL fornecida para busca")
                return []

            if not img_url:
                logger.error("Falha ao converter imagem para URL")
                return []

            # URL para o Google Lens
            search_url = f"https://lens.google.com/uploadbyurl?url={img_url}"
            logger.info(f"Buscando no Google Lens: {search_url}")

            return self._executar_busca(search_url)

        except Exception as e:
            logger.error(f"Busca de produtos falhou: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
        finally:
            self.cleanup()

    def _executar_busca(self, search_url):
        """Método interno para executar a busca no Google Lens"""
        products = []

        for attempt in range(self.max_retries):
            try:
                self.driver.delete_all_cookies()
                self.driver.get(search_url)

                # Tempo de espera maior para carregamento da página
                logger.info("Aguardando carregamento da página...")
                time.sleep(10)  # Tempo de espera inicial

                # Verificar se a página foi carregada corretamente
                page_source = self.driver.page_source
                if "Google Lens" not in page_source:
                    logger.warning(f"Página do Google Lens não carregou corretamente (tentativa {attempt + 1})")
                    if attempt < self.max_retries - 1:
                        self._initialize_driver()
                        continue

                # Aguardar carregamento completo com WebDriverWait
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC

                try:
                    # Tentar localizar o botão "Shopping" e clicar nele, se existir
                    wait = WebDriverWait(self.driver, 15)
                    shopping_tab = wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Shopping')]"))
                    )
                    shopping_tab.click()
                    logger.info("Clicou na aba Shopping")
                    time.sleep(5)  # Esperar o carregamento após clicar
                except Exception as e:
                    logger.warning(f"Não foi possível encontrar a aba Shopping: {str(e)}")

                    # Tentar localizar a área de produtos mesmo sem a aba
                    try:
                        # Verificar se já estamos na seção de produtos
                        product_check = self.driver.find_elements(By.XPATH,
                                                                  "//div[contains(@class, 'UAiK1e')]//div[contains(@class, 'Lv3Kxc')]")
                        if product_check:
                            logger.info("Já estamos na seção de produtos")
                        else:
                            logger.warning("Não foi possível encontrar produtos nem a aba shopping")
                    except:
                        pass

                # Salvar screenshot para debug
                self.driver.save_screenshot(f'/tmp/lens_attempt_{attempt}.png')
                logger.info(f"Screenshot salvo em /tmp/lens_attempt_{attempt}.png")

                products = self._extract_products_selenium()
                if products:
                    logger.info(f"Encontrados {len(products)} produtos")
                    break
                else:
                    logger.warning(f"Nenhum produto encontrado na tentativa {attempt + 1}")

                    # Tentar métodos alternativos de extração
                    products = self._extract_products_alternate()
                    if products:
                        logger.info(f"Encontrados {len(products)} produtos usando método alternativo")
                        break

                time.sleep(2)
            except Exception as e:
                logger.error(f"Tentativa {attempt + 1} falhou: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                if attempt < self.max_retries - 1:
                    self._initialize_driver()

        return products[:5]  # Limit results to reduce memory usage

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

        if not ficha:
            cursor.close()
            conn.close()
            return "Ficha não encontrada", 404

        # Processa informação de arquivo (imagem)
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

        cursor.close()
        conn.close()

        # Formatar data de compra para o formato brasileiro (se disponível)
        if ficha.get('dataDeCompra'):
            try:
                # Tenta parsear a data para formato brasileiro
                data_obj = datetime.strptime(ficha['dataDeCompra'], '%Y-%m-%d')
                ficha['dataDeCompra_br'] = data_obj.strftime('%d/%m/%Y')
            except:
                try:
                    # Tenta parsear caso já esteja no formato DD/MM/YYYY
                    data_obj = datetime.strptime(ficha['dataDeCompra'], '%d/%m/%Y')
                    ficha['dataDeCompra_br'] = ficha['dataDeCompra']
                except:
                    ficha['dataDeCompra_br'] = ficha['dataDeCompra']
        else:
            ficha['dataDeCompra_br'] = None

        # Buscar produtos similares usando a imagem (se disponível)
        produtos_similares = []
        if ficha.get('arquivo_url'):
            try:
                arquivo_url = ficha['arquivo_url']
                logger.info(f"Buscando produtos similares para a imagem: {arquivo_url}")

                # Configurar headers para evitar o erro 406
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
                    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Referer': 'https://mude.ind.br/',  # Ajuste este valor para o domínio correto
                    'Connection': 'keep-alive',
                    'DNT': '1'
                }

                # Tenta baixar a imagem com as configurações corretas
                response = requests.get(arquivo_url, headers=headers, timeout=30, allow_redirects=True)

                # Verifica o status code
                logger.info(f"Status code da resposta: {response.status_code}")

                if response.status_code == 200:
                    img_bytes = io.BytesIO(response.content)
                    # Verifica se o conteúdo é realmente uma imagem
                    try:
                        img = Image.open(img_bytes)

                        # Redimensionar a imagem para otimizar a busca
                        max_size = (800, 800)
                        img.thumbnail(max_size, Image.LANCZOS)

                        # Busca produtos similares usando a imagem
                        produtos_similares = finder.buscar_produtos(img)
                        logger.info(f"Encontrados {len(produtos_similares)} produtos similares")
                    except Exception as img_error:
                        logger.error(f"Erro ao processar a imagem: {str(img_error)}")
                        # Tenta um método alternativo - usar a URL diretamente
                        try:
                            # Fazer upload da imagem para imgbb antes de usar no Google Lens
                            # para evitar problemas de cross-origin
                            response_content = response.content
                            files = {'image': ('image.jpg', response_content, 'image/jpeg')}
                            imgbb_response = requests.post(
                                'https://api.imgbb.com/1/upload',
                                params={'key': '8234882d2cc5bc9c7f2f239283951076'},
                                files=files,
                                timeout=30
                            )

                            if imgbb_response.status_code == 200:
                                img_url = imgbb_response.json()['data']['url']
                                logger.info(f"Imagem reupload com sucesso: {img_url}")

                                # Criar instância temporária do ProdutoFinder
                                temp_finder = ProdutoFinder()
                                search_url = f"https://lens.google.com/uploadbyurl?url={img_url}"
                                produtos_similares = temp_finder._extract_products_alternate()
                                logger.info(f"Método alternativo encontrou {len(produtos_similares)} produtos")
                        except Exception as alt_error:
                            logger.error(f"Método alternativo também falhou: {str(alt_error)}")
                else:
                    # Se o status não for 200, tente uma abordagem alternativa
                    logger.error(f"Falha ao baixar imagem. Status code: {response.status_code}")
                    logger.error(f"Resposta: {response.text[:200]}...")  # Loga os primeiros 200 caracteres da resposta

                    # Tenta usar a URL diretamente sem baixar a imagem
                    try:
                        logger.info("Tentando abordagem alternativa: usar a URL diretamente no Google Lens")
                        # Pode ser necessário fazer upload para um serviço terceiro que não tenha restrições
                        # ou tentar diretamente no Google Lens
                        direct_url = ficha['arquivo_url']

                        # Inicializar o driver e buscar com a URL direta
                        if not finder._initialize_driver():
                            logger.error("Falha ao inicializar o driver na abordagem alternativa")
                        else:
                            search_url = f"https://lens.google.com/uploadbyurl?url={direct_url}"
                            finder.driver.get(search_url)
                            time.sleep(10)  # Espera carregar
                            produtos_similares = finder._extract_products_alternate()
                            logger.info(f"Método direto encontrou {len(produtos_similares)} produtos")
                    except Exception as direct_error:
                        logger.error(f"Abordagem direta falhou: {str(direct_error)}")
            except Exception as e:
                logger.error(f"Erro ao buscar produtos similares: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())

        # Cálculo do valor estimado e outras informações
        valor_estimado = 0.0
        if ficha.get('valor'):
            try:
                # Trata formatação do valor (remove símbolos como R$ e converte vírgulas para pontos)
                valor_str = re.sub(r'[^\d,.]', '', ficha['valor']).replace(',', '.')
                valor_estimado = float(valor_str)
            except:
                valor_estimado = 0.0

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
        import traceback
        logger.error(traceback.format_exc())
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
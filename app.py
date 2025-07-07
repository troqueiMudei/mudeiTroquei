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

    def _convert_image_to_url(self, image=None, image_url=None, image_data=None):
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
                        timeout = 10 * (attempt + 1)
                        response = requests.get(
                            image_url,
                            headers=headers,
                            timeout=timeout,
                            allow_redirects=True
                        )
                        if response.status_code == 200:
                            break
                        else:
                            logger.warning(f"Attempt {attempt + 1}: Failed to download, status {response.status_code}")
                            time.sleep(2)
                    except Exception as req_error:
                        logger.warning(f"Attempt {attempt + 1} failed: {str(req_error)}")
                        if attempt < 2:
                            time.sleep(2)
                if response.status_code != 200:
                    logger.error(f"Error downloading image from URL: {response.status_code}")
                    try:
                        alt_headers = {
                            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
                        }
                        response = requests.get(image_url, headers=alt_headers, timeout=30)
                        if response.status_code != 200:
                            return image_url
                    except:
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
                    else:
                        logger.error(f"Error uploading image: {response.status_code} - {response.text}")
                        if attempt < retries - 1:
                            time.sleep(2)
                            continue
                except Exception as e:
                    logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt < retries - 1:
                        time.sleep(2)
                        continue
            if 'img_buffer' in locals():
                img_buffer.seek(0)
                data = img_buffer.getvalue()
            else:
                data = files['image'][1].read()
            encoded = base64.b64encode(data).decode('utf-8')
            return f"data:image/jpeg;base64,{encoded}"
        except Exception as e:
            logger.error(f"Error converting image: {str(e)}")
            if image_url:
                return image_url
            return None

    def _check_for_captcha(self):
        captcha_selectors = [
            "div#captcha",
            "div.recaptcha",
            "iframe[src*='recaptcha']",
            "div[class*='captcha']"
        ]
        for selector in captcha_selectors:
            try:
                if self.driver.find_elements(By.CSS_SELECTOR, selector):
                    return True
            except:
                continue
        return False

    def _extract_single_product_info(self, element):
        """Extract all product information from a single element"""
        produto = {
            "nome": "Produto similar",
            "preco": "Preço não disponível",
            "url": "#",
            "img": ""
        }

        # Extract product name
        name_selectors = [
            ".//div[contains(@class, 'zLvTHf')]",
            ".//div[contains(@class, 'bONr3b')]",
            ".//h3",
            ".//h4",
            ".//div[contains(@class, 'sh-np__product-title')]",
            ".//div[contains(@class, 'BXIkFb')]",
            ".//div[contains(@class, 'pymv4e')]",
            ".//div[contains(@class, 'UAQDqe')]"
        ]
        for selector in name_selectors:
            try:
                name_element = element.find_element(By.XPATH, selector)
                name = name_element.text.strip()
                if name:
                    produto["nome"] = name
                    logger.info(f"Nome encontrado: {name}")
                    break
            except:
                continue

        # Extract price
        price_selectors = [
            ".//span[contains(@class, 'price')]",
            ".//span[contains(@class, 'e10twf')]",
            ".//span[contains(@class, 'a8Pemb')]",
            ".//span[contains(@class, 'T14wmb')]",
            ".//div[contains(@class, 'NRRPPb')]",
            ".//span[contains(@class, 'sh-np__product-price')]",
            ".//span[@aria-label='Price']",
            ".//div[contains(@class, 'price-container')]",
            ".//span[contains(text(), 'R$')]"  # Adicionado para preços em reais
        ]
        for selector in price_selectors:
            try:
                price_element = element.find_element(By.XPATH, selector)
                price = price_element.text.strip()
                if price:
                    produto["preco"] = price
                    logger.info(f"Preço encontrado com seletor {selector}: {price}")
                    break
            except Exception as e:
                logger.warning(f"Falha ao extrair preço com seletor {selector}: {str(e)}")
                continue

        # Extract URL
        url_selectors = [
            ".//a[contains(@href, '/shopping/product')]",
            ".//a[contains(@class, 'shntl')]",
            ".//a[contains(@class, 'sh-np__click-target')]",
            ".//a[contains(@class, 'UAQDqe')]"
        ]
        for selector in url_selectors:
            try:
                url_element = element.find_element(By.XPATH, selector)
                url = url_element.get_attribute('href')
                if url and not any(term in url.lower() for term in ['review', 'ratings', 'lens.google.com']):
                    try:
                        response = requests.get(url, allow_redirects=True, timeout=5)
                        final_url = response.url
                        if not any(term in final_url.lower() for term in ['review', 'ratings']):
                            produto["url"] = final_url
                            logger.info(f"URL final após redirecionamento: {final_url}")
                        else:
                            produto["url"] = url
                    except:
                        produto["url"] = url
                    logger.info(f"URL extraído: {produto['url']}")
                    break
            except:
                continue

        # Extract image
        img_selectors = [
            ".//img",
            ".//div[contains(@class, 'cOPFNb')]//img",
            ".//div[contains(@class, 'eUQRje')]//img"
        ]
        for selector in img_selectors:
            try:
                img_element = element.find_element(By.XPATH, selector)
                img_src = img_element.get_attribute('src')
                if img_src:
                    produto["img"] = img_src
                    logger.info(f"Imagem extraída: {img_src}")
                    break
            except:
                continue

        return produto

    def _extract_products_comprehensive(self):
        """Método robusto para extrair produtos"""
        produtos = []
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class, 'sh-dgr__grid-result') or contains(@class, 'Lv3Kxc')]"))
            )
            selectors = [
                "//div[contains(@class, 'sh-dgr__grid-result')]",
                "//div[contains(@class, 'sh-dlr__list-result')]",
                "//div[contains(@class, 'pla-unit')]",
                "//div[contains(@class, 'UAiK1e')]//div[contains(@class, 'Lv3Kxc')]",
                "//div[contains(@class, 'PJLMUc')]",
                "//a[contains(@class, 'UAQDqe')]",
                "//div[@data-product]",
                "//div[contains(@class, 'commercial-unit')]",
                "//div[@role='listitem']"
            ]
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        logger.info(f"Encontrados {len(elements)} elementos com seletor: {selector}")
                        for element in elements[:5]:
                            try:
                                produto = self._extract_single_product_info(element)
                                if (produto["nome"] and
                                    produto["url"] != "#" and
                                    not any(term in produto["url"].lower() for term in ['review', 'ratings', 'lens.google.com'])):
                                    produtos.append(produto)
                            except Exception as e:
                                logger.warning(f"Erro ao extrair produto: {str(e)}")
                                continue
                        if produtos:
                            break
                except Exception as e:
                    logger.warning(f"Erro com seletor {selector}: {str(e)}")
                    continue
            if not produtos:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
                produtos = self._extract_with_javascript()
        except Exception as e:
            logger.error(f"Erro na extração: {str(e)}")
            produtos = self._extract_with_javascript()
        return produtos[:5]

    def _extract_with_javascript(self):
        """Fallback com JavaScript para extração mais robusta"""
        try:
            return self.driver.execute_script("""
                const results = [];
                const container = document.querySelector('div.srKDX.cvP2Ce');
                if (container) {
                    const products = container.querySelectorAll('div.kb0PBd.cvP2Ce');
                    products.forEach((product, index) => {
                        if (index >= 5) return;
                        try {
                            const nameEl = product.querySelector("div[role='heading']");
                            const priceEl = product.querySelector("span[aria-hidden='true'], span[class*='price'], div[class*='price']");
                            const linkEl = product.querySelector("a:not([href*='review']):not([href*='ratings'])");
                            const imgEl = product.querySelector("img");
                            if (nameEl && linkEl) {
                                results.push({
                                    nome: nameEl.innerText.trim() || 'Produto similar',
                                    preco: priceEl?.innerText.trim() || 'Preço não disponível',
                                    url: linkEl.href || '#',
                                    img: imgEl?.src || ''
                                });
                            }
                        } catch (e) {
                            console.error('Error extracting product:', e);
                        }
                    });
                }
                return results;
            """) or []
        except Exception as e:
            logger.error(f"Erro na extração com JavaScript: {str(e)}")
            return []

    def buscar_produtos_por_url(self, image_url):
        """Busca produtos no Google Lens focando na extração direta dos elementos"""
        logger.info(f"\n=== Iniciando busca para imagem: {image_url} ===")
        if not self._initialize_driver():
            logger.error("Falha ao inicializar o driver")
            return []
        try:
            encoded_url = urllib.parse.quote(image_url)
            search_url = f"https://lens.google.com/uploadbyurl?url={encoded_url}"
            logger.info(f"\nURL de busca no Google Lens: {search_url}")
            self.driver.get(search_url)
            time.sleep(8)
            current_url = self.driver.current_url
            logger.info(f"\nURL atual após redirecionamento: {current_url}")
            try:
                shopping_tab = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Shopping')]"))
                )
                shopping_tab.click()
                time.sleep(3)
            except:
                logger.warning("Aba Shopping não encontrada, continuando com extração direta")
            produtos = self._extract_products_comprehensive()
            logger.info(f"\n=== Resultados encontrados ===")
            for i, p in enumerate(produtos, 1):
                logger.info(f"{i}. {p.get('nome', '')} | {p.get('preco', '')} | {p.get('url', '')}")
            return produtos
        except Exception as e:
            logger.error(f"\nErro durante a busca: {str(e)}")
            return []
        finally:
            self.cleanup()

    def cleanup(self):
        """Encerra o driver de forma segura"""
        try:
            if self.driver:
                self.driver.quit()
                logger.info("Driver encerrado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao encerrar driver: {str(e)}")
        finally:
            self.driver = None

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
                    produto = self._extract_single_product_info(product)
                    if (produto["nome"] and
                        produto["url"] != "#" and
                        not any(term in produto["url"].lower() for term in ['review', 'ratings', 'lens.google.com'])):
                        produtos.append(produto)
                        if len(produtos) >= 5:
                            break
                except Exception as e:
                    logger.warning(f"Erro ao extrair produto: {str(e)}")
                    continue
            return produtos
        except Exception as e:
            logger.error(f"Erro na extração da página do Lens: {str(e)}")
            return []

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
                        logger.info(f"Iniciando busca por produtos similares para URL: {img_url}")
                        form_data['produtos_similares'] = finder.buscar_produtos_por_url(img_url)
                        logger.info(f"Produtos encontrados: {len(form_data['produtos_similares'])}")
                        for i, produto in enumerate(form_data['produtos_similares'], 1):
                            logger.info(f"Produto {i}: {produto['nome']} | Preço: {produto['preco']} | URL: {produto['url']}")
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
        # Aqui você colocaria a lógica para inserir no banco de dados
        # Similar ao que você já tem na rota de upload_produto do código antigo

        # Após cadastrar, redireciona para a lista de fichas
        return redirect(url_for('lista_fichas'))

    except Exception as e:
        logger.error(f"Erro ao cadastrar ficha: {str(e)}")
        return render_template('erro.html', mensagem="Ocorreu um erro ao cadastrar a ficha"), 500

if __name__ == '__main__':
    app.run(debug=True)
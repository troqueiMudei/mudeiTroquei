import os
import re
import random
import urllib
from telnetlib import EC
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
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
import phpserialize
import math
import urllib.parse
from selenium.webdriver.support.wait import WebDriverWait
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

    def _fetch_price_from_url(self, product_url):
        """Tenta extrair o preço diretamente da página do produto usando requests."""
        try:
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.google.com/'
            }
            response = requests.get(product_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Seletores comuns para preços em páginas de varejo
            price_selectors = [
                'span[class*="price"], span[class*="preco"], span[class*="valor"]',
                'div[class*="price"], div[class*="preco"], div[class*="valor"]',
                'span:contains("R$"), div:contains("R$")',
                'meta[property="og:price:amount"]',
                'span[itemprop="price"]',
                '[data-testid="price-value"]',
                'span[class*="final-price"], span[class*="current-price"]'
            ]

            for selector in price_selectors:
                try:
                    element = soup.select_one(selector)
                    if element:
                        price_text = element.get('content') or element.text.strip()
                        if price_text and self._is_valid_price_text(price_text):
                            logger.info(f"Preço encontrado na URL {product_url}: {price_text}")
                            return price_text
                except:
                    continue

            # Fallback: busca por regex no texto da página
            price_match = re.search(r'R\$\s*[\d.,]+|\$\s*[\d.,]+', soup.text)
            if price_match:
                logger.info(f"Preço extraído via regex na URL {product_url}: {price_match.group(0)}")
                return price_match.group(0)

            logger.warning(f"Preço não encontrado na URL {product_url}")
            return "Preço não disponível"
        except Exception as e:
            logger.error(f"Erro ao buscar preço na URL {product_url}: {str(e)}")
            return "Preço não disponível"

    def _extract_products_robust(self):
        """Método robusto para extrair produtos com múltiplas estratégias"""
        try:
            # Espera até que a página esteja completamente carregada
            time.sleep(5)
            # Primeiro tenta extrair via JavaScript (mais confiável)
            produtos = self._extract_with_javascript()
            if produtos:
                return produtos
            # Se JavaScript não retornou resultados, tenta XPath
            selectors = [
                "//div[contains(@class, 'sh-dgr__grid-result')]",  # Google Shopping
                "//div[contains(@class, 'Lv3Kxc')]",  # Google Lens
                "//div[contains(@class, 'PJLMUc')]",  # Alternativo 1
                "//a[contains(@class, 'UAQDqe')]",  # Alternativo 2
                "//div[@data-product]",  # Genérico
                "//div[contains(@class, 'commercial-unit')]"
            ]
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        produtos = []
                        for element in elements[:5]:  # Limita a 5 resultados
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
        """Extrai URL do elemento de forma segura, filtrando links internos do Google."""
        try:
            link = element.find_element(By.XPATH,
                                        ".//a[not(contains(@href, 'google.com') or contains(@href, 'lens.google'))]")
            url = link.get_attribute('href')
            if url and url != "#" and not url.startswith(('javascript:', 'about:')):
                logger.info(f"URL válida extraída: {url}")
                return url
            logger.warning("URL inválida ou interna do Google encontrada")
            return "#"
        except:
            logger.error("Erro ao extrair URL")
            return "#"

    def _safe_extract_price(self, element):
        """Extrai preço do elemento de forma robusta."""
        try:
            # Seletores simplificados e comuns para preços no Google Lens/Shopping
            price_selectors = [
                ".//span[contains(@class, 'a8Pemb')]",  # Preço principal no Google Shopping
                ".//span[@aria-hidden='true']",
                ".//span[contains(text(), 'R$') or contains(text(), '$')]",
                ".//div[contains(@class, 'price') or contains(@class, 'offer')]"
            ]

            for selector in price_selectors:
                try:
                    el = element.find_element(By.XPATH, selector)
                    price_text = el.text.strip()
                    if price_text and self._is_valid_price_text(price_text):
                        logger.info(f"Preço encontrado: {price_text}")
                        return price_text
                except:
                    continue

            # Busca no texto completo como fallback
            full_text = element.text
            price_match = re.search(r'R\$\s*[\d.,]+|\$\s*[\d.,]+', full_text)
            if price_match:
                logger.info(f"Preço extraído via regex: {price_match.group(0)}")
                return price_match.group(0)

            logger.warning("Preço não encontrado no elemento")
            return "Preço não disponível"
        except Exception as e:
            logger.error(f"Erro ao extrair preço: {str(e)}")
            return "Preço não disponível"

    def _is_valid_price_text(self, text):
        """NOVA FUNÇÃO: Verifica se o texto é um preço válido"""
        if not text:
            return False

        # Padrões de preço
        price_patterns = [
            r'R\$\s*[\d.,]+',
            r'\$\s*[\d.,]+',
            r'€\s*[\d.,]+',
            r'£\s*[\d.,]+',
            r'[\d.,]+\s*reais?',
            r'[\d]+[.,][\d]+',  # Números com vírgula ou ponto
        ]

        for pattern in price_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def _convert_image_to_url(self, image=None, image_url=None, image_data=None):
        """
        Improved: Convert an image to URL using the imgbb service
        Accepts PIL.Image, URL or binary image data
        """
        try:
            if image is not None:
                # If we received a PIL image
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                # Optimize image for better Google Lens processing
                # Not too small as it needs details, not too large to avoid upload issues
                optimal_size = (1000, 1000)
                image.thumbnail(optimal_size, Image.LANCZOS)
                # Enhance image contrast slightly for better recognition
                from PIL import ImageEnhance
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.2)
                # Sharpen image slightly
                from PIL import ImageFilter
                image = image.filter(ImageFilter.SHARPEN)
                img_buffer = io.BytesIO()
                image.save(img_buffer, format='JPEG', quality=90)  # Higher quality for better recognition
                img_buffer.seek(0)
                files = {'image': ('image.jpg', img_buffer, 'image/jpeg')}
            elif image_data is not None:
                # If we received binary image data
                try:
                    # Try to process the binary data to enhance it
                    img = Image.open(io.BytesIO(image_data))
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    # Optimize size
                    optimal_size = (1000, 1000)
                    img.thumbnail(optimal_size, Image.LANCZOS)
                    # Enhance image
                    from PIL import ImageEnhance
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(1.2)
                    # Sharpen
                    from PIL import ImageFilter
                    img = img.filter(ImageFilter.SHARPEN)
                    # Save to buffer
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format='JPEG', quality=90)
                    img_buffer.seek(0)
                    files = {'image': ('image.jpg', img_buffer, 'image/jpeg')}
                except Exception as img_error:
                    # Fall back to direct binary data if processing fails
                    logger.warning(f"Failed to process image data: {str(img_error)}")
                    files = {'image': ('image.jpg', image_data, 'image/jpeg')}
            elif image_url is not None:
                # If we received a URL
                try:
                    # Try to download the image from URL with appropriate headers
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
                        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                        'Referer': 'https://mude.ind.br/',
                        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                    }
                    # Try multiple times with increasing timeouts
                    for attempt in range(3):
                        try:
                            timeout = 10 * (attempt + 1)  # 10, 20, 30 seconds
                            response = requests.get(
                                image_url,
                                headers=headers,
                                timeout=timeout,
                                allow_redirects=True
                            )
                            if response.status_code == 200:
                                break
                            else:
                                logger.warning(
                                    f"Attempt {attempt + 1}: Failed to download, status {response.status_code}")
                                time.sleep(2)
                        except Exception as req_error:
                            logger.warning(f"Attempt {attempt + 1} failed: {str(req_error)}")
                            if attempt < 2:  # Don't sleep on last attempt
                                time.sleep(2)
                    if response.status_code != 200:
                        logger.error(f"Error downloading image from URL: {response.status_code}")
                        # Try alternative URL processing
                        try:
                            # Try a different approach - use requests with a different user agent
                            alt_headers = {
                                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
                            }
                            response = requests.get(image_url, headers=alt_headers, timeout=30)
                            if response.status_code != 200:
                                return image_url  # Return original URL if all fails
                        except:
                            return image_url  # Return original URL if fails
                    # Try to process the downloaded image
                    try:
                        img = Image.open(io.BytesIO(response.content))
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        # Optimize size
                        optimal_size = (1000, 1000)
                        img.thumbnail(optimal_size, Image.LANCZOS)
                        # Enhance image
                        from PIL import ImageEnhance
                        enhancer = ImageEnhance.Contrast(img)
                        img = enhancer.enhance(1.2)
                        # Sharpen
                        from PIL import ImageFilter
                        img = img.filter(ImageFilter.SHARPEN)
                        # Save to buffer
                        img_buffer = io.BytesIO()
                        img.save(img_buffer, format='JPEG', quality=90)
                        img_buffer.seek(0)
                        files = {'image': ('image.jpg', img_buffer, 'image/jpeg')}
                    except Exception as proc_error:
                        # Fall back to direct binary data if processing fails
                        logger.warning(f"Failed to process downloaded image: {str(proc_error)}")
                        files = {'image': ('image.jpg', response.content, 'image/jpeg')}
                except Exception as e:
                    logger.error(f"Error processing image URL: {str(e)}")
                    return image_url  # Return original URL if all fails
            else:
                logger.error("No valid image input provided.")
                return None
            # Try multiple image hosting services in case one fails
            # First try ImgBB
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
            # If ImgBB fails, try a fallback approach
            try:
                # Create a new buffer with the image data
                if 'img_buffer' in locals():
                    img_buffer.seek(0)
                    data = img_buffer.getvalue()
                else:
                    data = files['image'][1].read()
                # Try base64 encoding approach
                import base64
                encoded = base64.b64encode(data).decode('utf-8')
                # Return data URI format - many search engines can handle this format
                return f"data:image/jpeg;base64,{encoded}"
            except Exception as fallback_error:
                logger.error(f"Fallback approach failed: {str(fallback_error)}")
            # If we have an original URL, return it
            if image_url:
                return image_url
            return None
        except Exception as e:
            logger.error(f"Error converting image: {str(e)}")
            # If we have an original URL, return it on error
            if image_url:
                return image_url
            return None

    def _extract_products_selenium(self):
        """Método robusto para extração de produtos em 2025."""
        try:
            logger.info(f"URL atual: {self.driver.current_url}")
            # Aumentar tempo de espera para carregamento inicial
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            logger.info("Página carregada, iniciando rolagem")

            # Rolagem progressiva para carregar todos os elementos
            for y in range(0, 2000, 500):
                self.driver.execute_script(f"window.scrollTo(0, {y});")
                time.sleep(3)

            # Tenta clicar na aba Shopping
            try:
                shopping_tab = WebDriverWait(self.driver, 15).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//*[contains(text(), 'Shopping') or contains(text(), 'Compras')]"))
                )
                self.driver.execute_script("arguments[0].click();", shopping_tab)
                time.sleep(5)
                logger.info("Aba Shopping clicada com sucesso")
            except Exception as e:
                logger.warning(f"Não encontrou aba Shopping: {str(e)}")

            produtos = []
            # Seletores atualizados para 2025
            selectors = [
                "div.sh-dgr__grid-result",  # Google Shopping
                "div.srKDX.cvP2Ce div.kb0PBd.cvP2Ce",  # Google Lens
                "div.pla-unit-container",  # PLA units
                "div[role='listitem']",  # List items genéricos
                "div.g, div.mnr-c"  # Resultados genéricos do Google
            ]

            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        logger.info(f"Encontrados {len(elements)} elementos com seletor: {selector}")
                        for element in elements[:5]:
                            try:
                                produto = {
                                    "nome": self._safe_extract_text(element),
                                    "preco": self._safe_extract_price(element),
                                    "url": self._safe_extract_url(element),
                                    "img": self._safe_extract_img(element)
                                }
                                if produto["nome"] and produto["url"] != "#":
                                    produtos.append(produto)
                                    logger.info(
                                        f"Produto extraído: {produto['nome']} | Preço: {produto['preco']} | URL: {produto['url']}")
                            except Exception as e:
                                logger.warning(f"Erro ao extrair produto: {str(e)}")
                                continue
                        if produtos:
                            break
                except Exception as e:
                    logger.warning(f"Seletor {selector} falhou: {str(e)}")
                    continue

            if not produtos:
                logger.info("Nenhum produto encontrado via seletores, tentando JavaScript...")
                produtos = self._extract_with_javascript()

            logger.info(f"Total de produtos encontrados: {len(produtos)}")
            return produtos[:5]
        except Exception as e:
            logger.error(f"Erro na extração principal: {str(e)}")
            return []

    def _extract_products_alternative(self):
        """Método alternativo quando o principal falha"""
        try:
            # Tenta encontrar elementos de forma mais genérica
            produtos = []
            elements = self.driver.find_elements(By.CSS_SELECTOR, "div[role='listitem'], div[role='article']")
            for element in elements[:5]:  # Limita a 5 itens
                try:
                    produto = {
                        "nome": element.find_element(By.CSS_SELECTOR, "[role='heading']").text,
                        "preco": self._safe_extract_price(element),  # Usa o método corrigido
                        "url": element.find_element(By.CSS_SELECTOR, "a").get_attribute("href"),
                        "img": element.find_element(By.CSS_SELECTOR, "img").get_attribute("src")
                    }
                    produtos.append(produto)
                except:
                    continue
            return produtos if produtos else []
        except:
            return []

    def fallback_search_by_image_description(self, image_path=None, description=None):
        """
        Fallback method that uses text search instead of image search
        Extracts features from the image and searches for those terms
        Args:
            image_path: Path to image file
            description: Description of the product if available
        Returns:
            List of product dictionaries
        """
        try:
            search_terms = []
            # If we have a description, use that first
            if description and len(description) > 5:
                search_terms.append(description)
            # Try to extract information from the image if available
            if image_path:
                try:
                    # Try to use basic image processing to extract color information
                    img = Image.open(image_path)
                    # Get dominant color
                    from collections import Counter
                    img = img.convert('RGB').resize((100, 100))
                    pixels = list(img.getdata())
                    counter = Counter(pixels)
                    dominant_color = counter.most_common(1)[0][0]
                    r, g, b = dominant_color
                    # Convert RGB to basic color name
                    color_map = {
                        (0, 0, 0): "preto",
                        (255, 255, 255): "branco",
                        (255, 0, 0): "vermelho",
                        (0, 255, 0): "verde",
                        (0, 0, 255): "azul",
                        (255, 255, 0): "amarelo",
                        (255, 165, 0): "laranja",
                        (128, 0, 128): "roxo",
                        (165, 42, 42): "marrom",
                        (192, 192, 192): "prata",
                        (255, 192, 203): "rosa"
                    }
                    # Find closest color by Euclidean distance
                    min_distance = float('inf')
                    closest_color = "colorido"
                    for rgb, name in color_map.items():
                        distance = ((r - rgb[0]) ** 2 + (g - rgb[1]) ** 2 + (b - rgb[2]) ** 2) ** 0.5
                        if distance < min_distance:
                            min_distance = distance
                            closest_color = name
                    basic_description = f"{closest_color}"
                    search_terms.append(basic_description)
                    # Add some common search terms that might help
                    if description and "móvel" in description.lower():
                        search_terms.append("móvel decoração casa")
                    elif description and "roupa" in description.lower():
                        search_terms.append("roupas moda")
                    else:
                        search_terms.append("produto similar")
                except Exception as img_error:
                    logger.error(f"Error extracting image info: {str(img_error)}")
                    search_terms.append("produto similar")
            # Use the search terms to perform a Google Shopping search
            produtos = []
            # Select best search term
            search_query = search_terms[0]
            # Try to execute a Google Shopping search
            shopping_url = f"https://www.google.com/search?q={search_query}&tbm=shop"
            if not self.driver and not self._initialize_driver():
                logger.error("Failed to initialize driver for fallback search")
                return []
            try:
                self.driver.get(shopping_url)
                time.sleep(5)
                # Extract products using our comprehensive extraction function
                produtos = self._extract_products_comprehensive()
                if not produtos:
                    # If no results, try the second search term if available
                    if len(search_terms) > 1:
                        search_query = search_terms[1]
                        shopping_url = f"https://www.google.com/search?q={search_query}&tbm=shop"
                        self.driver.get(shopping_url)
                        time.sleep(5)
                        produtos = self._extract_products_comprehensive()
                return produtos[:5]  # Return up to 5 products
            except Exception as e:
                logger.error(f"Error in fallback search: {str(e)}")
                return []
        except Exception as e:
            logger.error(f"Failed to perform fallback search: {str(e)}")
            return []

    def _extract_products_alternate(self):
        """Método alternativo para extrair produtos do Google Lens"""
        if not self.driver or not self._initialize_driver():
            logger.error("Driver não inicializado para extração alternativa")
            return []
        try:
            produtos = []
            # Aguardar um pouco para garantir que a página carregou
            time.sleep(5)
            # Tentar vários seletores diferentes
            selectors = [
                "//div[contains(@class, 'sh-dgr__grid-result')]",  # Google Shopping
                "//div[contains(@class, 'Lv3Kxc')]",  # Google Lens
                "//div[contains(@class, 'PJLMUc')]",  # Alternativo 1
                "//a[contains(@class, 'UAQDqe')]",  # Alternativo 2
                "//div[@data-product]"  # Seletores genéricos
            ]
            for selector in selectors:
                try:
                    elements = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_all_elements_located((By.XPATH, selector))
                    )
                    if elements:
                        logger.info(f"Encontrados {len(elements)} elementos com {selector}")
                        for element in elements[:5]:  # Limitar a 5 resultados
                            try:
                                produto = {
                                    "nome": self._safe_extract_text(element, [
                                        ".//h3", ".//h4",
                                        ".//div[contains(@class, 'title')]",
                                        ".//div[contains(@class, 'header')]"
                                    ]),
                                    "preco": self._safe_extract_price(element),  # Usa método corrigido
                                    "url": self._safe_extract_attr(element, "href", [
                                        ".//a"
                                    ]),
                                    "img": self._safe_extract_attr(element, "src", [
                                        ".//img"
                                    ])
                                }
                                if produto["nome"] and produto["url"]:
                                    produtos.append(produto)
                            except Exception as e:
                                logger.warning(f"Erro ao extrair produto: {str(e)}")
                                continue
                        if produtos:  # Se encontrou produtos, para de tentar outros seletores
                            break
                except Exception as e:
                    logger.warning(f"Seletor {selector} não encontrado: {str(e)}")
                    continue
            return produtos[:5]  # Retorna no máximo 5 produtos
        except Exception as e:
            logger.error(f"Erro na extração alternativa: {str(e)}")
            return []

    def _safe_extract_attr(self, element, selector, attribute):
        """Extrai atributo de forma segura"""
        try:
            el = element.find_element(By.CSS_SELECTOR, selector)
            return el.get_attribute(attribute)
        except:
            return "#"

    def _safe_extract_text(self, element):
        """Extrai texto do elemento de forma segura"""
        try:
            # Tenta vários seletores possíveis para o nome
            for selector in [".//h3", ".//h4", ".//div[contains(@class, 'title')]",
                             ".//div[contains(@class, 'header')]"]:
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

    def _process_image(self, image_url):
        """Processa a imagem para otimizar a busca"""
        try:
            # Baixa a imagem com headers personalizados
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': 'https://www.google.com/'
            }
            response = requests.get(image_url, headers=headers, timeout=15)
            response.raise_for_status()
            # Processa a imagem com PIL
            img = Image.open(io.BytesIO(response.content))
            # Converte para RGB se necessário
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # Otimiza tamanho e qualidade
            img.thumbnail((800, 800), Image.LANCZOS)
            # Melhora contraste e nitidez
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.2)
            img = img.filter(ImageFilter.SHARPEN)
            # Salva em buffer
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='JPEG', quality=85)
            img_buffer.seek(0)
            return img_buffer
        except Exception as e:
            logger.error(f"Erro ao processar imagem: {str(e)}")
            return None

    def _upload_image(self, image_buffer):
        """Faz upload da imagem para um serviço temporário"""
        try:
            files = {'image': ('optimized_image.jpg', image_buffer, 'image/jpeg')}
            # Tenta primeiro com ImgBB
            response = requests.post(
                'https://api.imgbb.com/1/upload',
                params={'key': '8234882d2cc5bc9c7f2f239283951076'},
                files=files,
                timeout=20
            )
            if response.status_code == 200:
                return response.json()['data']['url']
            # Fallback para outros serviços
            response = requests.post(
                'https://tmpfiles.org/api/v1/upload',
                files={'file': files['image']},
                timeout=20
            )
            if response.status_code == 200:
                return response.json()['data']['url']
            return None
        except Exception as e:
            logger.error(f"Erro no upload da imagem: {str(e)}")
            return None

    def buscar_produtos_por_imagem(self, image_url):
        """Busca produtos similares por URL de imagem com fallback"""
        logger.info(f"Iniciando busca para imagem: {image_url}")
        # Primeiro tenta com Selenium
        produtos = self._buscar_com_selenium(image_url)
        if not produtos:
            logger.info("Nenhum produto encontrado via Selenium, tentando API alternativa")
            produtos = self.buscar_produtos_alternativo(image_url)
        return produtos[:5]  # Limita a 5 resultados

    def _extrair_produtos_avancado(self):
        """Método robusto para extração de produtos com múltiplas estratégias"""
        produtos = []
        # Estratégia 1: Seletores atualizados para Google Shopping 2025
        selectors = [
            "//div[contains(@class, 'sh-dgr__grid-result')]",
            "//div[contains(@class, 'sh-dlr__list-result')]",
            "//div[contains(@class, 'pla-unit')]",
            "//div[contains(@class, 'Lv3Kxc')]",
            "//a[contains(@href, '/shopping/product/')]"
        ]
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                if elements:
                    for element in elements[:5]:  # Limita a 5 itens
                        try:
                            produto = {
                                "nome": self._extrair_texto(element, [
                                    ".//h3", ".//h4",
                                    ".//div[contains(@class, 'title')]",
                                    ".//div[contains(@class, 'header')]"
                                ]),
                                "preco": self._safe_extract_price(element),  # Usa método corrigido
                                "url": self._extrair_atributo(element, "href", [
                                    ".//a"
                                ]),
                                "img": self._extrair_atributo(element, "src", [
                                    ".//img"
                                ])
                            }
                            if produto["nome"] and produto["url"]:
                                produtos.append(produto)
                        except:
                            continue
                    if produtos:
                        break
            except:
                continue
        # Estratégia 2: Fallback com JavaScript
        if not produtos:
            produtos = self._extrair_com_javascript()
        return produtos

    def _extrair_com_javascript(self):
        """Fallback com extração via JavaScript"""
        try:
            return self.driver.execute_script("""
                const results = [];
                const containers = document.querySelectorAll(
                    'div.sh-dgr__grid-result, div.sh-dlr__list-result, div.pla-unit, div.Lv3Kxc'
                );
                containers.forEach(container => {
                    try {
                        const titleEl = container.querySelector('h3, h4, [class*="title"], [class*="header"]');

                        // CORREÇÃO: Busca melhorada por preços
                        let price = 'Preço não disponível';
                        const priceSelectors = [
                            '[class*="price"]', 
                            'span[class*="e10twf"]', 
                            'span[class*="a8Pemb"]',
                            'span[aria-hidden="true"]',
                            '.notranslate',
                            'span:contains("R$")',
                            'div:contains("R$")'
                        ];

                        for (const selector of priceSelectors) {
                            const priceEl = container.querySelector(selector);
                            if (priceEl && priceEl.innerText && priceEl.innerText.trim()) {
                                const priceText = priceEl.innerText.trim();
                                if (priceText.match(/[R$€£¥₹]|\\d+[.,]\\d+|\\d+/)) {
                                    price = priceText;
                                    break;
                                }
                            }
                        }

                        const linkEl = container.querySelector('a');
                        const imgEl = container.querySelector('img');
                        if (titleEl || linkEl) {
                            results.push({
                                nome: titleEl?.innerText?.trim() || 'Produto similar',
                                preco: price,
                                url: linkEl?.href || '#',
                                img: imgEl?.src || ''
                            });
                        }
                    } catch (e) {
                        console.error('Error extracting product:', e);
                    }
                });
                return results.slice(0, 5);  // Retorna no máximo 5 produtos
            """) or []
        except:
            return []

    def _extrair_texto(self, element, selectors):
        for selector in selectors:
            try:
                el = element.find_element(By.XPATH, selector)
                text = el.text.strip()
                if text:
                    return text
            except:
                continue
        return "Produto similar"

    def _extrair_atributo(self, element, attr, selectors):
        for selector in selectors:
            try:
                el = element.find_element(By.XPATH, selector)
                value = el.get_attribute(attr)
                if value:
                    return value
            except:
                continue
        return "#"

    def _initialize_driver(self):
        """Inicializa o WebDriver com opções otimizadas para Docker."""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--headless")  # Modo headless para Docker
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(f"user-agent={random.choice(self.user_agents)}")

        # Adicionar argumentos para evitar detecção
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        try:
            service = Service(executable_path='/usr/bin/chromedriver')
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            # Configurar implicit wait para aguardar elementos
            self.driver.implicitly_wait(10)
            logger.info("WebDriver inicializado com sucesso")
            return True
        except Exception as e:
            logger.error(f"Falha ao inicializar o WebDriver: {str(e)}")
            return False

    def buscar_produtos_alternativo(self, image_url):
        """Método alternativo usando APIs de pesquisa por imagem"""
        try:
            # 1. Upload da imagem para um serviço temporário
            uploaded_url = self._upload_image_to_temp_service(image_url)
            if not uploaded_url:
                return []
            # 2. Usar o SerpAPI para pesquisa por imagem
            params = {
                "engine": "google_lens",
                "url": uploaded_url,
                "api_key": os.getenv("SERPAPI_KEY")
            }
            response = requests.get("https://serpapi.com/search", params=params)
            results = response.json().get("visual_matches", [])
            produtos = []
            for item in results[:5]:  # Limitar a 5 resultados
                produtos.append({
                    "nome": item.get("title", "Produto similar"),
                    "preco": item.get("price", "Preço não disponível"),
                    "url": item.get("link", "#"),
                    "img": item.get("thumbnail", "")
                })
            return produtos
        except Exception as e:
            logger.error(f"Erro na busca alternativa: {str(e)}")
            return []

    def _generate_search_terms(self, image_url):
        """Gera termos de busca baseados na imagem"""
        # Implemente sua lógica para gerar termos descritivos
        # Pode usar análise de imagem ou metadados
        return ["produto similar", "item relacionado", "produto genérico"]

    def __del__(self):
        self.cleanup()

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

    def _try_extract_main_method(self):
        """Método principal de extração"""
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'sh-dgr__grid-result')]"))
            )
            produtos = []
            items = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'sh-dgr__grid-result')]")[:5]
            for item in items:
                try:
                    produto = {
                        'nome': item.find_element(By.XPATH, ".//h3").text,
                        'preco': self._safe_extract_price(item),  # Usa método corrigido
                        'url': item.find_element(By.XPATH, ".//a").get_attribute('href'),
                        'img': item.find_element(By.XPATH, ".//img").get_attribute('src')
                    }
                    produtos.append(produto)
                except:
                    continue
            return produtos
        except:
            return []

    def _extract_products_from_current_url(self, current_url):
        """Extrai produtos diretamente da URL atual do Google Lens"""
        produtos = []
        try:
            # Analisar a URL para extrair parâmetros relevantes
            parsed_url = urllib.parse.urlparse(current_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            # Se a URL contiver parâmetros de pesquisa, podemos usá-los
            if 'url' in query_params:
                image_url = query_params['url'][0]
                print(f"\nExtraindo produtos para imagem: {image_url}")
                # Aqui você pode implementar lógica específica baseada na URL
                # Por exemplo, fazer uma nova busca ou parsear a página atual
                # Método genérico para extrair produtos da página atual
                produtos = self._extract_products_selenium()
                # Se ainda não encontrou, tenta um fallback
                if not produtos:
                    produtos = self._extract_products_alternative()
            return produtos
        except Exception as e:
            print(f"\nErro ao extrair produtos da URL: {str(e)}")
            return []

    def _extract_from_lens_page(self):
        """Extrai produtos diretamente da página do Google Lens, filtrando links do próprio domínio"""
        produtos = []
        try:
            # Espera até que os resultados estejam carregados
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.srKDX.cvP2Ce"))
            )
            # Encontra o container principal
            container = self.driver.find_element(By.CSS_SELECTOR, "div.srKDX.cvP2Ce")
            # Extrai os produtos dentro do container
            product_elements = container.find_elements(By.CSS_SELECTOR, "div.kb0PBd.cvP2Ce")[
                               :10]  # Aumentei para 10 resultados
            for product in product_elements:
                try:
                    produto = {
                        "nome": self._safe_extract(product, "div[role='heading']"),
                        "preco": self._safe_extract_price(product),  # Usa método corrigido
                        "url": self._safe_extract_attr(product, "a", "href"),
                        "img": self._safe_extract_attr(product, "img", "src")
                    }
                    # Filtra URLs do Google Lens e outras URLs internas
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
                        # Limita a 5 resultados válidos após filtro
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
        """Busca produtos no Google Lens com extração direta."""
        logger.info(f"\n=== Iniciando busca para imagem: {image_url} ===")
        if not self._initialize_driver():
            logger.error("Falha ao inicializar o driver")
            return []
        try:
            encoded_url = urllib.parse.quote(image_url)
            search_url = f"https://lens.google.com/uploadbyurl?url={encoded_url}"
            logger.info(f"URL de busca no Google Lens: {search_url}")

            # Tentar até 3 vezes para lidar com falhas de rede ou captcha
            for attempt in range(self.max_retries):
                try:
                    self.driver.get(search_url)
                    WebDriverWait(self.driver, 30).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
                    )
                    logger.info("Página do Google Lens carregada")
                    break
                except Exception as e:
                    logger.warning(f"Tentativa {attempt + 1} falhou: {str(e)}")
                    if attempt == self.max_retries - 1:
                        logger.error("Falha após várias tentativas")
                        return []
                    time.sleep(5)

            # Tenta clicar na aba Shopping
            try:
                shopping_tab = WebDriverWait(self.driver, 15).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//*[contains(text(), 'Shopping') or contains(text(), 'Compras')]"))
                )
                self.driver.execute_script("arguments[0].click();", shopping_tab)
                time.sleep(5)
                logger.info("Aba Shopping clicada com sucesso")
            except Exception as e:
                logger.warning(f"Não encontrou aba Shopping: {str(e)}")

            produtos = self._extract_products_selenium()
            if not produtos:
                logger.info("Nenhum produto encontrado via Selenium, tentando alternativa...")
                produtos = self._extract_products_alternative()

            logger.info(f"\n=== Resultados encontrados: {len(produtos)} ===")
            for i, p in enumerate(produtos, 1):
                logger.info(f"{i}. {p.get('nome', '')} | {p.get('preco', '')} | {p.get('url', '')}")
            return produtos
        except Exception as e:
            logger.error(f"Erro durante a busca: {str(e)}")
            return []
        finally:
            self.cleanup()
            logger.info("\n=== Busca concluída ===")

    def _extract_products_from_lens_url(self, lens_url):
        """Método especializado para extrair produtos de uma URL do Google Lens"""
        try:
            # Parse da URL para extrair a imagem original
            parsed = urllib.parse.urlparse(lens_url)
            params = urllib.parse.parse_qs(parsed.query)
            image_url = params.get('url', [None])[0]
            if not image_url:
                return []
            # Inicializa o driver se necessário
            if not self.driver and not self._initialize_driver():
                return []
            # Acessa a URL do Lens
            self.driver.get(lens_url)
            time.sleep(5)
            # Tenta encontrar a aba Shopping
            try:
                shopping_tab = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Shopping')]"))
                )
                shopping_tab.click()
                time.sleep(3)
            except:
                pass
            # Extrai os produtos
            return self._extract_products_comprehensive()
        except Exception as e:
            logger.error(f"Erro ao extrair produtos da URL do Lens: {str(e)}")
            return []

    def _try_google_shopping_fallback(self, image_url):
        """Fallback direto para Google Shopping"""
        try:
            shopping_url = f"https://www.google.com/searchbyimage?&image_url={urllib.parse.quote(image_url)}&tbm=shop"
            self.driver.get(shopping_url)
            produtos = []
            items = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'sh-dgr__grid-result')]")[:3]
            for item in items:
                try:
                    produtos.append({
                        'nome': item.find_element(By.XPATH, ".//h3").text,
                        'preco': self._safe_extract_price(item),  # Usa método corrigido
                        'url': item.find_element(By.XPATH, ".//a").get_attribute('href'),
                        'img': item.find_element(By.XPATH, ".//img").get_attribute('src')
                    })
                except:
                    continue
            return produtos
        except:
            return []

    def _extract_with_js(self):
        """Fallback com JavaScript"""
        try:
            return self.driver.execute_script("""
                return Array.from(document.querySelectorAll('div.sh-dgr__grid-result')).slice(0,5).map(item => {
                    try {
                        // CORREÇÃO: Busca melhorada por preços
                        let price = 'Preço não disponível';
                        const priceSelectors = [
                            '[class*="price"]',
                            'span[aria-hidden="true"]',
                            '.e10twf',
                            '.a8Pemb',
                            '.notranslate'
                        ];

                        for (const selector of priceSelectors) {
                            const priceEl = item.querySelector(selector);
                            if (priceEl && priceEl.innerText && priceEl.innerText.trim()) {
                                const priceText = priceEl.innerText.trim();
                                if (priceText.match(/[R$€£¥₹]|\\d+[.,]\\d+|\\d+/)) {
                                    price = priceText;
                                    break;
                                }
                            }
                        }

                        return {
                            nome: item.querySelector('h3')?.innerText || 'Produto similar',
                            preco: price,
                            url: item.querySelector('a')?.href || '#',
                            img: item.querySelector('img')?.src || ''
                        }
                    } catch(e) { return null }
                }).filter(Boolean)
            """)
        except:
            return []

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

    def _check_for_captcha(self):
        """Verifica se há captcha na página"""
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

    def _extract_with_javascript(self):
        """Fallback com extração via JavaScript."""
        try:
            produtos = self.driver.execute_script("""
                const results = [];
                const containers = document.querySelectorAll(
                    'div.sh-dgr__grid-result, div.srKDX.cvP2Ce div.kb0PBd.cvP2Ce, div.pla-unit-container, div[role="listitem"], div.g, div.mnr-c'
                );
                containers.forEach(container => {
                    try {
                        const titleEl = container.querySelector('h3, h4, [class*="title"], [class*="header"], div[role="heading"]');
                        let price = 'Preço não disponível';
                        const priceSelectors = [
                            'span[class*="price"], span[class*="preco"], span[class*="valor"]',
                            'span.a8Pemb, span[aria-hidden="true"]',
                            'span:contains("R$"), div:contains("R$")',
                            'meta[property="og:price:amount"]',
                            '[itemprop="price"]'
                        ];
                        for (const selector of priceSelectors) {
                            const priceEl = container.querySelector(selector);
                            if (priceEl && priceEl.innerText && priceEl.innerText.trim()) {
                                const priceText = priceEl.innerText.trim();
                                if (priceText.match(/[R$€£¥₹]|\\d+[.,]\\d+|\\d+/)) {
                                    price = priceText;
                                    break;
                                }
                            }
                        }
                        const linkEl = container.querySelector('a:not([href*="google.com"], [href*="lens.google"])');
                        const imgEl = container.querySelector('img');
                        if (titleEl || linkEl) {
                            results.push({
                                nome: titleEl?.innerText?.trim() || 'Produto similar',
                                preco: price,
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
            logger.info(f"Extraídos {len(produtos)} produtos via JavaScript")
            return produtos
        except Exception as e:
            logger.error(f"Erro na extração via JavaScript: {str(e)}")
            return []

    def _extract_attribute_with_retry(self, element, attr, selectors, retries=3):
        """Tenta extrair atributo com múltiplas tentativas"""
        for _ in range(retries):
            for selector in selectors:
                try:
                    el = element.find_element(By.XPATH, selector)
                    if el.is_displayed():
                        value = el.get_attribute(attr)
                        if value:
                            return value
                except:
                    continue
            time.sleep(1)
        return "#"

    def _extract_products_comprehensive(self):
        """Método mais robusto para extrair produtos"""
        produtos = []
        try:
            # Aguardar mais tempo para carregar os resultados
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class, 'sh-dgr__grid-result') or contains(@class, 'Lv3Kxc')]"))
            )
            # Tentar vários seletores atualizados (maio/2025)
            selectors = [
                # Seletores para Google Shopping
                "//div[contains(@class, 'sh-dgr__grid-result')]",
                "//div[contains(@class, 'sh-dlr__list-result')]",
                "//div[contains(@class, 'pla-unit')]",
                # Seletores para Google Lens
                "//div[contains(@class, 'UAiK1e')]//div[contains(@class, 'Lv3Kxc')]",
                "//div[contains(@class, 'PJLMUc')]",
                "//a[contains(@class, 'UAQDqe')]",
                # Novos seletores alternativos
                "//div[@data-product]",
                "//div[contains(@class, 'commercial-unit')]",
                "//div[@role='listitem']"
            ]
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        logger.info(f"Encontrados {len(elements)} elementos com seletor: {selector}")
                        for element in elements[:5]:  # Limitar a 5 resultados
                            try:
                                produto = {
                                    "nome": self._extract_with_retry(element, [
                                        ".//h3", ".//h4",
                                        ".//div[contains(@class, 'title')]",
                                        ".//div[contains(@class, 'header')]"
                                    ]),
                                    "preco": self._safe_extract_price(element),  # Usa método corrigido
                                    "url": self._extract_attribute_with_retry(element, "href", [
                                        ".//a"
                                    ]),
                                    "img": self._extract_attribute_with_retry(element, "src", [
                                        ".//img"
                                    ])
                                }
                                if produto["nome"] and produto["url"]:
                                    produtos.append(produto)
                            except Exception as e:
                                logger.warning(f"Erro ao extrair produto: {str(e)}")
                                continue
                        if produtos:
                            break
                except Exception as e:
                    logger.warning(f"Erro com seletor {selector}: {str(e)}")
                    continue
            # Se ainda não encontrou, tentar rolar a página
            if not produtos:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
                produtos = self._extract_with_javascript()
        except Exception as e:
            logger.error(f"Erro na extração: {str(e)}")
            # Tentar fallback com JavaScript
            produtos = self._extract_with_javascript()
        return produtos or []

    def _extract_products(self):
        """Extrai produtos com múltiplas estratégias"""
        try:
            # Método 1: Seletores convencionais
            produtos = []
            items = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'sh-dgr__grid-result')]")[:5]
            for item in items:
                try:
                    produto = {
                        'nome': item.find_element(By.XPATH, ".//h3").text,
                        'preco': self._safe_extract_price(item),  # Usa método corrigido
                        'url': item.find_element(By.XPATH, ".//a").get_attribute('href'),
                        'img': item.find_element(By.XPATH, ".//img").get_attribute('src')
                    }
                    produtos.append(produto)
                except Exception as e:
                    print(f"Erro ao extrair produto: {str(e)}")
                    continue
            if produtos:
                return produtos
            # Método 2: JavaScript como fallback
            return self.driver.execute_script("""
                return Array.from(document.querySelectorAll('div.sh-dgr__grid-result')).slice(0,5).map(item => {
                    // CORREÇÃO: Busca melhorada por preços
                    let price = 'Preço não disponível';
                    const priceSelectors = [
                        '[class*="price"]',
                        'span[aria-hidden="true"]',
                        '.e10twf',
                        '.a8Pemb',
                        '.notranslate'
                    ];

                    for (const selector of priceSelectors) {
                        const priceEl = item.querySelector(selector);
                        if (priceEl && priceEl.innerText && priceEl.innerText.trim()) {
                            const priceText = priceEl.innerText.trim();
                            if (priceText.match(/[R$€£¥₹]|\\d+[.,]\\d+|\\d+/)) {
                                price = priceText;
                                break;
                            }
                        }
                    }

                    return {
                        nome: item.querySelector('h3')?.innerText || 'Produto',
                        preco: price,
                        url: item.querySelector('a')?.href || '#',
                        img: item.querySelector('img')?.src || ''
                    }
                }).filter(p => p.nome && p.url);
            """) or []
        except Exception as e:
            print(f"Erro na extração: {str(e)}")
            return []

    def _extract_with_retry(self, element, selectors, retries=3):
        """Tenta extrair texto com múltiplas tentativas"""
        for _ in range(retries):
            for selector in selectors:
                try:
                    el = element.find_element(By.XPATH, selector)
                    if el.is_displayed():
                        text = el.text.strip()
                        if text:
                            return text
                except:
                    continue
            time.sleep(1)
        return "Produto similar"

    def _extract_text(self, element, selectors):
        """Extrai texto de um elemento usando múltiplos seletores"""
        for selector in selectors:
            try:
                el = element.find_element(By.XPATH, selector)
                text = el.text.strip()
                if text:
                    return text
            except:
                continue
        return None

    def _extract_attribute(self, element, attr, selectors):
        """Extrai atributo de um elemento usando múltiplos seletores"""
        for selector in selectors:
            try:
                el = element.find_element(By.XPATH, selector)
                value = el.get_attribute(attr)
                if value:
                    return value
            except:
                continue
        return None

    def _extract_single_product_info(self, element):
        """Extract all product information from a single element"""
        produto = {
            "nome": "Produto similar",
            "preco": "Preço não disponível",
            "url": "#",
            "img": ""
        }
        # Extract product name - try multiple selectors
        name_selectors = [
            ".//div[contains(@class, 'zLvTHf')]",
            ".//div[contains(@class, 'bONr3b')]",
            ".//h3",
            ".//h4",
            ".//div[contains(@class, 'sh-np__product-title')]",
            ".//div[contains(@class, 'BXIkFb')]",
            ".//div[contains(@class, 'pymv4e')]",
            ".//div[contains(@class, 'UAQDqe')]",
        ]
        for selector in name_selectors:
            try:
                name_element = element.find_element(By.XPATH, selector)
                name = name_element.text.strip()
                if name:
                    produto["nome"] = name
                    break
            except:
                continue
        # Extract price - CORREÇÃO: usa o método melhorado
        produto["preco"] = self._safe_extract_price(element)
        # Extract URL
        try:
            if element.tag_name == 'a':
                produto["url"] = element.get_attribute('href')
            else:
                url_element = element.find_element(By.XPATH, ".//a")
                produto["url"] = url_element.get_attribute('href')
        except:
            pass
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
                    break
            except:
                continue
        return produto

    def _executar_busca(self, search_url):
        """Método interno para executar a busca no Google Lens"""
        products = []
        for attempt in range(self.max_retries):
            try:
                self.driver.delete_all_cookies()
                # Aumente o tempo de espera inicial aqui (altere de 5 para 10)
                print(f"\nTentativa {attempt + 1} - Acessando URL...")
                self.driver.get(search_url)
                time.sleep(10)  # Alterado de 5 para 10 segundos
                # Adicione a rolagem da página aqui
                print("Rolando página para carregar mais resultados...")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                time.sleep(2)  # Espera após rolagem
                # Verifique se há captcha
                if self._check_for_captcha():
                    print("Captcha detectado! Tentando contornar...")
                    time.sleep(15)  # Espera adicional para captcha
                # Restante do código existente...
                page_source = self.driver.page_source
                # Tenta encontrar e clicar na aba Shopping
                try:
                    shopping_tab = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Shopping')]"))
                    )
                    shopping_tab.click()
                    time.sleep(8)  # Espera após clicar na aba
                    # Adicione outra rolagem após mudar de aba
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/4);")
                    time.sleep(2)
                except Exception as e:
                    print(f"Não encontrou aba Shopping: {str(e)}")
                # Debug - salvar screenshot
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.driver.save_screenshot(f"debug_{timestamp}.png")
                # Extrai os produtos
                products = self._extract_products_selenium()
                if products:
                    print(f"Encontrados {len(products)} produtos na tentativa {attempt + 1}")
                    break
            except Exception as e:
                print(f"Tentativa {attempt + 1} falhou: {str(e)}")
                if attempt < self.max_retries - 1:
                    self._initialize_driver()
        return products[:5]  # Limita a 5 resultados


finder = ProdutoFinder()


# Função para obter uma conexão com o banco de dados
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
    """Página de detalhes de uma ficha específica com busca de produtos similares"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Erro ao conectar ao banco de dados", 500
        cursor = conn.cursor(dictionary=True)
        # Consulta SQL para obter detalhes da ficha
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
            finder = ProdutoFinder()
            try:
                produtos = finder.buscar_produtos_por_url(ficha['arquivo_url'])
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
                finder.cleanup()
        else:
            ficha['produtos_similares'] = []
            print("Nenhuma URL de imagem disponível para busca")
        # ficha['produtos_similares'] = produtos_similares or []
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

        # Processar imagem
        if 'imagem' in request.files:
            imagem = request.files['imagem']
            if imagem.filename != '':
                try:
                    img = Image.open(imagem)
                    img_url = finder._convert_image_to_url(image=img)
                    form_data['imagem_url'] = img_url
                    logger.info(f"Imagem convertida para URL: {img_url}")
                    if img_url:
                        produtos = finder.buscar_produtos_por_url(img_url)
                        form_data['produtos_similares'] = produtos or []
                        logger.info(f"Produtos encontrados: {len(produtos)}")
                        # Log detalhado dos produtos
                        for i, p in enumerate(produtos, 1):
                            logger.info(f"Produto {i}: {p['nome']} | Preço: {p['preco']} | URL: {p['url']}")
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
        # Calcular valores estimados
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

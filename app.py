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
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
import math
from urllib.parse import quote
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
        """Extrai URL do elemento de forma segura"""
        try:
            # Tenta encontrar um link
            try:
                if element.tag_name == 'a':
                    return element.get_attribute('href')
            except:
                pass
            # Tenta encontrar um link dentro do elemento
            try:
                link = element.find_element(By.XPATH, ".//a")
                return link.get_attribute('href')
            except:
                pass
            return "#"
        except:
            return "#"

    def _safe_extract_price(self, element):
        """Extrai preço do elemento de forma robusta"""
        try:
            price_selectors = [
                ".//span[contains(@class, 'price') or contains(@class, 'a8Pemb') or contains(@class, 'e10twf') or contains(@class, 'T14wmb') or contains(@class, 'O8U6h') or contains(@class, 'NRRPPb') or contains(@class, 'notranslate') or contains(text(), 'R$') or contains(text(), '$') or contains(text(), '€') or contains(text(), '£')]",
                ".//div[contains(@class, 'price') or contains(text(), 'R$') or contains(text(), '$') or contains(text(), '€') or contains(text(), '£')]",
                ".//span[@aria-hidden='true']",
                ".//span[contains(@class, 'currency') or contains(@class, 'value')]",
                ".//div[contains(@class, 'sh-price') or contains(@class, 'pla-unit-price')]",
                ".//span[contains(@class, 'formatted-price') or contains(@class, 'offer-price')]",
                ".//div[contains(@class, 'price-container') or contains(@class, 'price-block')]",
                ".//span[contains(@class, 'a8Pemb') and contains(@class, 'OFFNJ')]"
            ]

            for selector in price_selectors:
                try:
                    el = element.find_element(By.XPATH, selector)
                    price_text = el.text.strip()
                    if price_text and self._is_valid_price_text(price_text):
                        logger.info(f"Preço encontrado: {price_text} (seletor: {selector})")
                        return price_text
                except Exception as e:
                    logger.debug(f"Seletor {selector} falhou: {str(e)}")
                    continue

            try:
                full_text = element.text
                price_pattern = r'(?:R\$|\$|€|£|USD|BRL)?\s*[\d,.]+(?:[,.]\d{2})?'
                matches = re.findall(price_pattern, full_text, re.IGNORECASE)
                for match in matches:
                    if self._is_valid_price_text(match):
                        logger.info(f"Preço encontrado no texto completo: {match}")
                        return match
            except Exception as e:
                logger.debug(f"Falha na busca por texto completo: {str(e)}")

            logger.warning("Nenhum preço válido encontrado")
            return "Preço não disponível"
        except Exception as e:
            logger.error(f"Erro geral na extração de preço: {str(e)}")
            return "Preço não disponível"

    def _is_valid_price_text(self, text):
        """Verifica se o texto é um preço válido em reais (R$) ou dólares ($)"""
        if not text or not isinstance(text, str):
            return False

        # Aceita preços com R$ ou $ (para conversão)
        if 'R$' in text or '$' in text and not any(sym in text for sym in ['€', '£', 'EUR', 'GBP']):
            price_patterns = [
                r'(?:R\$|\$)?\s*[\d,.]+(?:[,.]\d{2})?',
                r'[\d]+[.,][\d]+(?:\s*(?:R\$|\$))?',
                r'[\d]+(?:\s*(?:reais|BRL|dólares|USD))',
                r'(?:de|por)\s*(?:R\$|\$)\s*[\d,.]+',
                r'[\d,.]+(?:\s*(?:reais|dólares))?',
            ]
            for pattern in price_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
        return False

    def _convert_image_to_url(self, image=None, image_url=None, image_data=None):
        """
        Converte uma imagem para URL usando o serviço imgbb
        Aceita PIL.Image, URL ou dados binários
        """
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
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
                        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                        'Referer': 'https://mude.ind.br/',
                        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                    }
                    for attempt in range(3):
                        try:
                            timeout = 10 * (attempt + 1)
                            response = requests.get(image_url, headers=headers, timeout=timeout, allow_redirects=True)
                            if response.status_code == 200:
                                break
                            else:
                                logger.warning(
                                    f"Attempt {attempt + 1}: Failed to download, status {response.status_code}")
                                time.sleep(2)
                        except Exception as req_error:
                            logger.warning(f"Attempt {attempt + 1} failed: {str(req_error)}")
                            if attempt < 2:
                                time.sleep(2)
                    if response.status_code != 200:
                        logger.error(f"Error downloading image from URL: {response.status_code}")
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
                except Exception as e:
                    logger.error(f"Error processing image URL: {str(e)}")
                    return image_url
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

            try:
                if 'img_buffer' in locals():
                    img_buffer.seek(0)
                    data = img_buffer.getvalue()
                else:
                    data = files['image'][1].read()
                encoded = base64.b64encode(data).decode('utf-8')
                return f"data:image/jpeg;base64,{encoded}"
            except Exception as fallback_error:
                logger.error(f"Fallback approach failed: {str(fallback_error)}")
            if image_url:
                return image_url
            return None
        except Exception as e:
            logger.error(f"Error converting image: {str(e)}")
            if image_url:
                return image_url
            return None

    def _extract_products_selenium(self, search_query):
        """Extrai produtos da página, limitando a sites brasileiros comerciais com preços em reais,
        excluindo redes sociais, Amazon e itens sem preço"""
        products = []
        try:
            brazilian_domains = [
                '.com.br', 'mercadolivre.com.br', 'americanas.com.br', 'magazinevoce.com.br',
                'submarino.com.br', 'shoptime.com.br', 'casasbahia.com.br', 'pontofrio.com.br'
            ]

            product_elements = self.driver.find_elements(By.XPATH,
                                                         "//div[contains(@class, 'sh-dgr__grid-result')] | //div[contains(@class, 'pla-unit')]")
            for element in product_elements:
                try:
                    name_element = element.find_element(By.XPATH, ".//h3 | .//span[contains(@class, 'title')]")
                    name = name_element.text.strip()
                    price_text = self._safe_extract_price(element)
                    url_element = element.find_element(By.XPATH, ".//a[@href]")
                    url = url_element.get_attribute('href')

                    is_brazilian = any(domain in url.lower() for domain in brazilian_domains)
                    if is_brazilian and name and price_text != "Preço não disponível" and self._is_valid_price_text(
                            price_text):
                        price_value = self._safe_extract_price_from_string(price_text)
                        img = element.find_elements(By.XPATH, ".//img")
                        img_url = img[0].get_attribute('src') if img else None
                        products.append({
                            'nome': name,
                            'preco': f"R$ {price_value:.2f}",
                            'url': url,
                            'img': img_url
                        })
                        logger.info(f"Produto brasileiro encontrado: {name} - {url} - Preço: R$ {price_value:.2f}")
                    else:
                        logger.debug(f"URL ou preço ignorado (não brasileiro ou sem preço): {url} - {price_text}")
                except Exception as e:
                    logger.debug(f"Erro ao extrair produto: {str(e)}")
                    continue
        except Exception as e:
            logger.error(f"Erro geral na extração de produtos: {str(e)}")

        return products[:5]

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
        chrome_options = Options()
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

    def buscar_produtos_alternativo(self, image_url):
        """Método alternativo usando APIs de pesquisa por imagem"""
        try:
            # Upload da imagem para um serviço temporário
            uploaded_url = self._upload_image_to_temp_service(image_url)
            if not uploaded_url:
                logger.warning("Falha ao fazer upload da imagem para serviço temporário")
                return []
            # Configurar parâmetros da SerpAPI
            params = {
                "engine": "google_lens",
                "url": uploaded_url,
                "api_key": os.getenv("SERPAPI_KEY", "sua_chave_aqui")  # Substitua pela sua chave
            }
            response = requests.get("https://serpapi.com/search", params=params, timeout=20)
            if response.status_code != 200:
                logger.error(f"Erro na SerpAPI: {response.status_code} - {response.text}")
                return []
            results = response.json().get("visual_matches", [])
            produtos = []
            for item in results[:5]:  # Limitar a 5 resultados
                price = item.get("price", {}).get("value", "Preço não disponível")
                if isinstance(price, dict):
                    price = price.get("value", "Preço não disponível")
                produtos.append({
                    "nome": item.get("title", "Produto similar"),
                    "preco": price,
                    "url": item.get("link", "#"),
                    "img": item.get("thumbnail", "")
                })
            logger.info(f"SerpAPI retornou {len(produtos)} produtos")
            return produtos
        except Exception as e:
            logger.error(f"Erro na busca alternativa com SerpAPI: {str(e)}")
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
                logger.info("Driver encerrado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao encerrar driver: {str(e)}")
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
        """Busca produtos similares por URL de imagem com fallback"""
        logger.info(f"Iniciando busca para imagem: {image_url}")
        if not self._initialize_driver():
            return []
        try:
            encoded_url = urllib.parse.quote(image_url)
            search_url = f"https://lens.google.com/uploadbyurl?url={encoded_url}"
            return self._executar_busca(search_url, image_url)
        except Exception as e:
            logger.error(f"Erro durante a busca: {str(e)}")
            return []
        finally:
            self.cleanup()

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
        try:
            return self.driver.find_element(By.ID, 'recaptcha') is not None
        except:
            return False

    def _extract_with_javascript(self):
        """Fallback com extração via JavaScript"""
        try:
            return self.driver.execute_script("""
                const results = [];
                const containers = document.querySelectorAll('div.sh-dgr__grid-result, div.sh-dlr__list-result, div.pla-unit, div.Lv3Kxc, div.kb0PBd.cvP2Ce');
                containers.forEach(container => {
                    try:
                        const titleEl = container.querySelector('h3, h4, [class*="title"], [class*="header"], div[role="heading"]');

                        // Busca robusta por preços
                        let price = 'Preço não disponível';
                        const priceSelectors = [
                            'span[class*="price"], span.a8Pemb, span.e10twf, span.T14wmb, span.O8U6h, span.NRRPPb, span.notranslate',
                            'span[aria-hidden="true"]',
                            'span:contains("R$"), div:contains("R$")',
                            'span:contains("$"), div:contains("$")',
                            'span:contains("€"), div:contains("€")',
                            'span:contains("£"), div:contains("£")',
                            '[class*="price-container"], [class*="price-block"]'
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
                return results.slice(0, 5);
            """) or []
        except Exception as e:
            logger.error(f"Erro na extração com JavaScript: {str(e)}")
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
        """Método interno para executar a busca no Google Lens, limitado ao Brasil"""
        products = []
        for attempt in range(self.max_retries):
            try:
                self.driver.delete_all_cookies()
                if '?' in search_url:
                    search_url += '&gl=br&hl=pt-BR'
                else:
                    search_url += '?gl=br&hl=pt-BR'
                print(f"\nTentativa {attempt + 1} - Acessando URL: {search_url}")
                self.driver.get(search_url)
                time.sleep(10)
                for y in [500, 1000, 1500, 2000]:
                    self.driver.execute_script(f"window.scrollTo(0, {y});")
                    time.sleep(2)
                if self._check_for_captcha():
                    print("Captcha detectado! Tentando contornar...")
                    time.sleep(20)
                try:
                    shopping_tab = WebDriverWait(self.driver, 20).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//div[.//text()[contains(., 'Shopping') or contains(., 'Compras')]]"))
                    )
                    shopping_tab.click()
                    time.sleep(10)
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                    time.sleep(3)
                except Exception as e:
                    print(f"Não encontrou aba Shopping: {str(e)}")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.driver.save_screenshot(f"debug_{timestamp}.png")
                products = self._extract_products_selenium()
                if products:
                    print(f"Encontrados {len(products)} produtos na tentativa {attempt + 1}")
                    break
            except Exception as e:
                print(f"Tentativa {attempt + 1} falhou: {str(e)}")
                if attempt < self.max_retries - 1:
                    self._initialize_driver()
        return products

    def _safe_extract_price_from_string(self, price_str):
        """
        Extrai e converte um preço de uma string para um float em reais,
        aceitando preços com R$ ou $ (convertendo $ para R$ multiplicando por 5.5).
        """
        if not price_str or price_str.strip() == "" or price_str == "Preço não disponível":
            return 0.0

        is_negative = price_str.startswith('-')
        price_str = price_str.replace('-', '').strip()

        convert_to_reais = False
        if 'R$' in price_str:
            price_str = price_str.replace('R$', '').strip()
        elif '$' in price_str:
            price_str = price_str.replace('$', '').strip()
            convert_to_reais = True
        else:
            logger.warning(f"Preço ignorado (moeda inválida detectada): {price_str}")
            return 0.0

        price_str = ''.join(c for c in price_str if c.isdigit() or c in '.,')
        dot_pos = price_str.rfind('.')
        comma_pos = price_str.rfind(',')

        if dot_pos == -1 and comma_pos == -1:
            number_str = price_str
        elif dot_pos == -1:
            number_str = price_str.replace('.', '').replace(',', '.')
        elif comma_pos == -1:
            number_str = price_str.replace(',', '')
        else:
            if dot_pos > comma_pos:
                number_str = price_str.replace(',', '')
            else:
                number_str = price_str.replace('.', '').replace(',', '.')

        try:
            number = float(number_str)
            if is_negative:
                number = -number
            if convert_to_reais:
                number = number * 5.5
                logger.info(f"Convertido de $ {number / 5.5:.2f} para R$ {number:.2f}")
            return number
        except ValueError:
            return 0.0

    def calcular_valores_estimados(self, ficha):
        """Calcula os valores estimados com base nos itens similares"""
        precos = []
        for produto in ficha.get('produtos_similares', []):
            preco = self._safe_extract_price_from_string(produto.get('preco', ''))
            if preco > 0:
                precos.append(preco)

        if precos:
            media_precos = sum(precos) / len(precos)
            valor_de_mercado = media_precos * 0.5
        else:
            valor_de_mercado = 0.0

        if valor_de_mercado == 0.0:
            valor_base = float(ficha.get('valor', 0))
        else:
            valor_base = valor_de_mercado

        valores = {
            'valorDeMercado': {
                'base': valor_base,
                'imposto': valor_base * 0.06,
                'comissao': valor_base * 0.15,
                'cartaoCredito': valor_base * 0.05
            },
            'valorEstimado': {
                'base': valor_base * 1.05,
                'imposto': (valor_base * 1.05) * 0.06,
                'comissao': (valor_base * 1.05) * 0.15,
                'cartaoCredito': (valor_base * 1.05) * 0.05
            },
            'demandaMedia': {
                'base': valor_base * 1.05 * 1.05,
                'imposto': (valor_base * 1.05 * 1.05) * 0.06,
                'comissao': (valor_base * 1.05 * 1.05) * 0.15,
                'cartaoCredito': (valor_base * 1.05 * 1.05) * 0.05
            },
            'demandaAlta': {
                'base': valor_base * 1.05 * 1.10,
                'imposto': (valor_base * 1.05 * 1.10) * 0.06,
                'comissao': (valor_base * 1.05 * 1.10) * 0.15,
                'cartaoCredito': (valor_base * 1.05 * 1.10) * 0.05
            }
        }

        for tipo in valores:
            valores[tipo]['totalDespesas'] = (
                    valores[tipo]['imposto'] +
                    valores[tipo]['comissao'] +
                    valores[tipo]['cartaoCredito']
            )
            valores[tipo]['totalFinal'] = (
                    valores[tipo]['base'] - valores[tipo]['totalDespesas']
            )

        ficha['valoresEstimados'] = valores
        ficha['valorOriginal'] = float(ficha.get('valor', 0))

        return ficha

    def _buscar_com_selenium(self, image_url):
        """Busca com Selenium"""
        if not self._initialize_driver():
            return []
        try:
            encoded_url = quote(image_url)
            search_url = f"{self.base_url}{encoded_url}"
            self.driver.get(search_url)
            time.sleep(5)
            return self._extract_products_robust()
        except Exception as e:
            logger.error(f"Erro na busca com Selenium: {str(e)}")
            return []
        finally:
            self.cleanup()

    def _upload_image_to_temp_service(self, image_url):
        """Upload para serviço temporário"""
        image_buffer = self._process_image(image_url)
        if image_buffer:
            return self._upload_image(image_buffer)
        return None

finder = ProdutoFinder()

@app.route('/nova_ficha')
def nova_ficha():
    """Exibe o formulário para cadastrar uma nova ficha"""
    return render_template('form_ficha.html', bairros=BAIRROS)


@app.route('/preview_ficha', methods=['POST'])
def preview_ficha():
    """Rota para visualizar os dados do formulário antes de cadastrar"""
    try:
        # Coleta dos dados do formulário
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
                        produtos = finder.buscar_produtos_por_url(img_url)
                        form_data['produtos_similares'] = produtos or []  # Garante lista vazia se None
                        # Debug adicional
                        if not produtos:
                            print("Nenhum produto similar encontrado")
                        else:
                            print(f"Encontrados {len(produtos)} produtos similares")
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
def cadastrar_ficha():
    """Rota para cadastrar a ficha após a pré-visualização"""
    try:
        # Para fins de teste, não insere no banco, apenas simula sucesso
        return "Ficha cadastrada com sucesso (simulação para teste)!"
    except Exception as e:
        logger.error(f"Erro ao cadastrar ficha: {str(e)}")
        return render_template('erro.html', mensagem="Ocorreu um erro ao cadastrar a ficha"), 500


if __name__ == '__main__':
    app.run(debug=True)
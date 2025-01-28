import os
import re

from flask import Flask, render_template, request
from PIL import Image
import io
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


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
def _extract_products_selenium(self):
    """Extrai produtos usando XPath"""
    products = []
    try:
        # Lista de XPaths para tentar encontrar resultados
        xpaths = [
            "//div[contains(@class, 'isv-r')]",
            "//div[@class='g' or contains(@class, 'g-card')]",
            "//div[.//h3 or .//a[@href]]",
            "//div[contains(@style, 'background-image')]",
            "//a[.//img]"
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

        result_elements = list(set(result_elements))

        for element in result_elements[:10]:
            try:
                # Extração do título (mantido como estava)
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

                # Extração do link (mantido como estava)
                link = None
                try:
                    link_element = element.find_element(By.XPATH, ".//a")
                    link = link_element.get_attribute('href')
                except:
                    try:
                        link = element.get_attribute('href')
                    except:
                        continue

                # Melhorada extração do preço
                price = None
                try:
                    price_text = element.text
                    # Padrão mais abrangente para preços
                    price_matches = re.findall(r'R?\$?\s*(\d+[.,]\d{2}|\d+[.,]\d{3}|\d+)', price_text)
                    if price_matches:
                        price_str = price_matches[0]
                        # Remove todos os caracteres não numéricos exceto '.' e ','
                        price_str = re.sub(r'[^\d,.]', '', price_str)
                        # Substitui vírgula por ponto se houver
                        if ',' in price_str:
                            price_str = price_str.replace('.', '').replace(',', '.')
                        try:
                            price = float(price_str)
                        except ValueError:
                            price = None
                except Exception as e:
                    logger.warning(f"Erro ao extrair preço: {str(e)}")
                    price = None

                # Extração da imagem (mantido como estava)
                img = None
                try:
                    img_element = element.find_element(By.XPATH, ".//img")
                    img = img_element.get_attribute('src')
                except:
                    try:
                        style = element.get_attribute('style')
                        if style and 'background-image' in style:
                            img = re.findall(r'url\(["\']?(.*?)["\']?\)', style)[0]
                    except:
                        pass

                if title and link:  # Requisitos mínimos
                    product = {
                        "nome": title,
                        "preco": price,  # Agora será None se não encontrar preço válido
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

app = Flask(__name__)
finder = ProdutoFinder()


@app.route('/', methods=['GET', 'POST'])
def upload_produto():
    if request.method == 'POST':
        logger.info("Recebida requisição POST")

        if 'imagem' not in request.files:
            logger.error("Nenhuma imagem enviada")
            return "Nenhuma imagem enviada", 400

        imagem = request.files['imagem']

        if imagem.filename == '':
            logger.error("Nenhum arquivo selecionado")
            return "Nenhum arquivo selecionado", 400

        try:
            img = Image.open(imagem)
            logger.info(f"Imagem aberta com sucesso: {img.format} {img.size}")

            resultados = finder.buscar_produtos(img)

            # Log dos resultados antes de renderizar
            logger.debug(f"Resultados obtidos: {json.dumps(resultados, ensure_ascii=False)}")

            if not resultados:
                logger.warning("Nenhum produto encontrado")
                return "Nenhum produto encontrado", 404

            # Validação extra dos resultados
            resultados_validados = []
            for produto in resultados:
                if isinstance(produto.get('preco'), (float, int, type(None))):
                    resultados_validados.append(produto)
                else:
                    logger.warning(f"Produto com preço inválido removido: {produto}")

            return render_template('resultados.html', resultados={"produtos": resultados_validados})

        except Exception as e:
            logger.error(f"Erro ao processar requisição: {str(e)}", exc_info=True)
            return f"Erro ao processar requisição: {str(e)}", 500

    return render_template('upload.html')

if __name__ == '__main__':
    app.run(debug=True)
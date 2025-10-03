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
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
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

    def _initialize_driver(self):
        """Inicializa o WebDriver com opções otimizadas"""
        chrome_options = Options()
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
            self.driver.set_page_load_timeout(30)
            return True
        except Exception as e:
            logger.error(f"Falha ao inicializar o WebDriver: {str(e)}")
            return False

    def _process_image(self, image_url):
        """Processa a imagem para otimizar a busca"""
        try:
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': 'https://www.google.com/'
            }
            response = requests.get(image_url, headers=headers, timeout=15)
            response.raise_for_status()
            img = Image.open(io.BytesIO(response.content))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((800, 800), Image.LANCZOS)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.2)
            img = img.filter(ImageFilter.SHARPEN)
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='JPEG', quality=85)
            img_buffer.seek(0)
            return img_buffer
        except Exception as e:
            logger.error(f"Erro ao processar imagem: {str(e)}")
            return None

    def _convert_image_to_url(self, image=None, image_url=None, image_data=None):
        """Converte uma imagem para URL usando o serviço imgbb"""
        try:
            if image is not None:
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                image.thumbnail((1000, 1000), Image.LANCZOS)
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.2)
                image = image.filter(ImageFilter.SHARPEN)
                img_buffer = io.BytesIO()
                image.save(img_buffer, format='JPEG', quality=90)
                img_buffer.seek(0)
                files = {'image': ('image.jpg', img_buffer, 'image/jpeg')}
            elif image_data is not None:
                img = Image.open(io.BytesIO(image_data))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.thumbnail((1000, 1000), Image.LANCZOS)
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.2)
                img = img.filter(ImageFilter.SHARPEN)
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='JPEG', quality=90)
                img_buffer.seek(0)
                files = {'image': ('image.jpg', img_buffer, 'image/jpeg')}
            elif image_url is not None:
                img_buffer = self._process_image(image_url)
                if not img_buffer:
                    return image_url
                files = {'image': ('image.jpg', img_buffer, 'image/jpeg')}
            else:
                return None

            response = requests.post(
                'https://api.imgbb.com/1/upload',
                params={'key': '8234882d2cc5bc9c7f2f239283951076'},
                files=files,
                timeout=30
            )
            if response.status_code == 200 and 'data' in response.json():
                return response.json()['data']['url']
            return None
        except Exception as e:
            logger.error(f"Erro ao converter imagem para URL: {str(e)}")
            return image_url if image_url else None

    def _safe_extract_price(self, element):
        """Extrai preço do elemento de forma robusta"""
        try:
            price_selectors = [
                ".//span[contains(@class, 'price') or contains(@class, 'a8Pemb') or contains(@class, 'e10twf') or contains(@class, 'T14wmb') or contains(@class, 'O8U6h') or contains(@class, 'NRRPPb') or contains(text(), 'R$')]",
                ".//div[contains(@class, 'price') or contains(text(), 'R$')]",
                ".//span[@aria-hidden='true']",
                ".//span[contains(@class, 'currency') or contains(@class, 'value')]"
            ]
            for selector in price_selectors:
                try:
                    el = element.find_element(By.XPATH, selector)
                    price_text = el.text.strip()
                    if price_text and self._is_valid_price_text(price_text):
                        return price_text
                except:
                    continue
            full_text = element.text
            price_pattern = r'(?:R\$|\$)\s*[\d,.]+(?:[,.]\d{2})?'
            matches = re.findall(price_pattern, full_text, re.IGNORECASE)
            return matches[0] if matches else "Preço não disponível"
        except Exception as e:
            logger.debug(f"Erro na extração de preço: {str(e)}")
            return "Preço não disponível"

    def _is_valid_price_text(self, text):
        """Verifica se o texto é um preço válido"""
        if not text:
            return False
        return bool(re.match(r'(?:R\$|\$)?\s*[\d,.]+(?:[,.]\d{2})?', text, re.IGNORECASE))

    def _extract_products_comprehensive(self):
        """Método robusto para extrair produtos"""
        produtos = []
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class, 'sh-dgr__grid-result') or contains(@class, 'Lv3Kxc')]")
                )
            )
            selectors = [
                "//div[contains(@class, 'sh-dgr__grid-result')]",
                "//div[contains(@class, 'sh-dlr__list-result')]",
                "//div[contains(@class, 'pla-unit')]",
                "//div[contains(@class, 'Lv3Kxc')]",
                "//div[@data-product]"
            ]
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
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
                            except:
                                continue
                        if produtos:
                            break
                except:
                    continue
            if not produtos:
                produtos = self._extract_with_javascript()
            return produtos[:5]
        except Exception as e:
            logger.error(f"Erro na extração de produtos: {str(e)}")
            return []

    def _safe_extract_text(self, element):
        """Extrai texto do elemento de forma segura"""
        try:
            selectors = [
                ".//h3", ".//h4",
                ".//div[contains(@class, 'title')]",
                ".//div[contains(@class, 'header')]"
            ]
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

    def _safe_extract_url(self, element):
        """Extrai URL do elemento de forma segura"""
        try:
            if element.tag_name == 'a':
                return element.get_attribute('href')
            link = element.find_element(By.XPATH, ".//a")
            return link.get_attribute('href')
        except:
            return "#"

    def _safe_extract_img(self, element):
        """Extrai imagem do elemento de forma segura"""
        try:
            img = element.find_element(By.XPATH, ".//img")
            return img.get_attribute('src')
        except:
            return ""

    def _extract_with_javascript(self):
        """Extrai produtos usando JavaScript como fallback"""
        try:
            return self.driver.execute_script("""
                const results = [];
                const containers = document.querySelectorAll('div.sh-dgr__grid-result, div.sh-dlr__list-result, div.pla-unit, div.Lv3Kxc');
                containers.forEach(container => {
                    try:
                        const titleEl = container.querySelector('h3, h4, [class*="title"], [class*="header"]');
                        let price = 'Preço não disponível';
                        const priceSelectors = [
                            'span[class*="price"], span.a8Pemb, span.e10twf',
                            'span[aria-hidden="true"]',
                            'span:contains("R$"), div:contains("R$")'
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
        except:
            return []

    def _executar_busca(self, search_url):
        """Executa a busca no Google Lens"""
        products = []
        for attempt in range(self.max_retries):
            try:
                self.driver.delete_all_cookies()
                search_url = f"{search_url}&gl=br&hl=pt-BR"
                logger.info(f"Tentativa {attempt + 1} - Acessando URL: {search_url}")
                self.driver.get(search_url)
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(5)
                try:
                    shopping_tab = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//*[contains(text(), 'Shopping') or contains(text(), 'Compras')]"))
                    )
                    shopping_tab.click()
                    time.sleep(5)
                except:
                    logger.warning("Aba Shopping não encontrada, continuando com página atual")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(3)
                products = self._extract_products_comprehensive()
                if products:
                    logger.info(f"Encontrados {len(products)} produtos na tentativa {attempt + 1}")
                    break
            except Exception as e:
                logger.error(f"Tentativa {attempt + 1} falhou: {str(e)}")
                if attempt < self.max_retries - 1:
                    self._initialize_driver()
        return products

    def buscar_produtos_por_url(self, image_url, fallback_query=None):
        """Busca produtos similares por URL de imagem com fallback"""
        logger.info(f"Iniciando busca para imagem: {image_url}")
        if not self._initialize_driver():
            return []
        try:
            encoded_url = quote(image_url, safe=':/?=&')
            search_url = f"{self.base_url}{encoded_url}"
            products = self._executar_busca(search_url)
            # Forçar pelo menos 3 itens
            retries = 0
            while len(products) < 3 and retries < 3:
                retries += 1
                logger.info(f"Produtos encontrados: {len(products)}. Tentando novamente para alcançar pelo menos 3...")
                time.sleep(5)  # Espera antes de tentar novamente
                products += self._executar_busca(search_url)  # Tenta novamente
                products = list({p['url']: p for p in products}.values())  # Remove duplicados
            # Se ainda menos que 3, usar fallback por texto se query fornecido
            if len(products) < 3 and fallback_query:
                logger.info("Usando fallback de busca por texto...")
                text_products = self._search_by_text(fallback_query)
                products += text_products
                products = list({p['url']: p for p in products}.values())[:5]
            # Se ainda menos que 3, adicionar itens dummy para teste
            if len(products) < 3:
                logger.info("Adicionando itens dummy para teste, pois nenhum produto foi encontrado")
                dummy_products = [
                    {
                        "nome": "Armário de Madeira para Quarto",
                        "preco": "R$ 1.500,00",
                        "url": "https://www.example.com/armario1",
                        "img": "https://i.ibb.co/SXrpFcG5/image.jpg"
                    },
                    {
                        "nome": "Armário Modulado MDF",
                        "preco": "R$ 1.200,00",
                        "url": "https://www.example.com/armario2",
                        "img": "https://i.ibb.co/SXrpFcG5/image.jpg"
                    },
                    {
                        "nome": "Armário Usado em Bom Estado",
                        "preco": "R$ 800,00",
                        "url": "https://www.example.com/armario3",
                        "img": "https://i.ibb.co/SXrpFcG5/image.jpg"
                    }
                ]
                products += dummy_products[:3 - len(products)]
            return products
        except Exception as e:
            logger.error(f"Erro durante a busca: {str(e)}")
            return []
        finally:
            self.cleanup()

    def _search_by_text(self, query):
        """Busca produtos por texto no Google Shopping"""
        if not self._initialize_driver():
            return []
        try:
            search_url = "https://www.google.com/search?tbm=shop&q=" + quote(query) + "&gl=br&hl=pt-BR"
            logger.info(f"Busca por texto: {search_url}")
            self.driver.get(search_url)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(5)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            return self._extract_products_comprehensive()
        except Exception as e:
            logger.error(f"Erro na busca por texto: {str(e)}")
            return []
        finally:
            self.cleanup()

    def buscar_produtos(self, imagem=None, url=None, image_data=None):
        """Busca produtos usando uma imagem, URL de imagem ou dados binários"""
        try:
            if url:
                return self.buscar_produtos_por_url(url)
            if not self._initialize_driver():
                logger.error("Falha ao inicializar o driver")
                return []
            img_url = self._convert_image_to_url(image=imagem, image_data=image_data)
            if not img_url:
                logger.error("Falha ao converter imagem para URL")
                return []
            return self.buscar_produtos_por_url(img_url)
        except Exception as e:
            logger.error(f"Busca de produtos falhou: {str(e)}")
            return []
        finally:
            self.cleanup()

    def _safe_extract_price_from_string(self, price_str):
        """Extrai e converte um preço de uma string para um float"""
        if not price_str or price_str == "Preço não disponível":
            return 0.0
        price_str = price_str.replace('R$', '').replace('$', '').strip()
        price_str = re.sub(r'[^\d,.]', '', price_str)
        try:
            number = float(price_str.replace(',', '.'))
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
            valor_de_mercado = float(ficha.get('valor', 0))

        valores = {
            'valorDeMercado': {
                'base': valor_de_mercado,
                'imposto': valor_de_mercado * 0.06,
                'comissao': valor_de_mercado * 0.15,
                'cartaoCredito': valor_de_mercado * 0.05
            },
            'valorEstimado': {
                'base': valor_de_mercado * 1.05,
                'imposto': (valor_de_mercado * 1.05) * 0.06,
                'comissao': (valor_de_mercado * 1.05) * 0.15,
                'cartaoCredito': (valor_de_mercado * 1.05) * 0.05
            },
            'demandaMedia': {
                'base': valor_de_mercado * 1.05 * 1.05,
                'imposto': (valor_de_mercado * 1.05 * 1.05) * 0.06,
                'comissao': (valor_de_mercado * 1.05 * 1.05) * 0.15,
                'cartaoCredito': (valor_de_mercado * 1.05 * 1.05) * 0.05
            },
            'demandaAlta': {
                'base': valor_de_mercado * 1.05 * 1.10,
                'imposto': (valor_de_mercado * 1.05 * 1.10) * 0.06,
                'comissao': (valor_de_mercado * 1.05 * 1.10) * 0.15,
                'cartaoCredito': (valor_de_mercado * 1.05 * 1.10) * 0.05
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

finder = ProdutoFinder()

@app.route('/nova_ficha')
def nova_ficha():
    """Exibe o formulário para cadastrar uma nova ficha"""
    return render_template('form_ficha.html', bairros=BAIRROS)

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
        if 'imagem' in request.files and request.files['imagem'].filename:
            imagem = request.files['imagem']
            try:
                img = Image.open(imagem)
                img_url = finder._convert_image_to_url(image=img)
                form_data['imagem_url'] = img_url
                if img_url:
                    fallback_query = form_data['produto'] + " " + form_data['descricao']
                    produtos = finder.buscar_produtos_por_url(img_url, fallback_query=fallback_query)
                    form_data['produtos_similares'] = produtos or []
                    logger.info(f"Encontrados {len(produtos)} produtos similares")
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
        form_data = finder.calcular_valores_estimados(form_data)
        return render_template('preview_ficha.html', ficha=form_data)
    except Exception as e:
        logger.error(f"Erro ao processar pré-visualização: {str(e)}")
        return render_template('erro.html', mensagem="Ocorreu um erro ao processar a pré-visualização"), 500

@app.route('/cadastrar_ficha', methods=['POST'])
def cadastrar_ficha():
    """Rota para cadastrar a ficha após a pré-visualização"""
    try:
        return "Ficha cadastrada com sucesso (simulação para teste)!"
    except Exception as e:
        logger.error(f"Erro ao cadastrar ficha: {str(e)}")
        return render_template('erro.html', mensagem="Ocorreu um erro ao cadastrar a ficha"), 500

if __name__ == '__main__':
    app.run(debug=True)
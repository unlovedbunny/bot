import os
import time
import json
import logging
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

# Dependências de Terceiros
from playwright.sync_api import sync_playwright, Page, BrowserContext
import google.generativeai as genai

# Módulo local de geração de currículo (HTML → PDF)
from gerador_curriculo import gerar_curriculo_pdf

# ==============================================================================
# CONFIGURAÇÃO INICIAL
# ==============================================================================

# Carrega variáveis de ambiente do arquivo .env local
load_dotenv()

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuração da API do Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Modelo recomendado para tarefas rápidas de texto
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    logger.warning("GEMINI_API_KEY não encontrada no .env.")

# Credenciais do LinkedIn
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "False").lower() == "true"


# ==============================================================================
# MÓDULO DE IA (GEMINI)
# ==============================================================================

def analisar_vaga_com_ia(descricao_vaga: str, curriculo_texto_base: str) -> Optional[Dict[str, Any]]:
    """
    Envia a descrição da vaga e o currículo base para o Gemini analisar e adaptar.
    
    Args:
        descricao_vaga (str): Texto com a descrição completa da vaga.
        curriculo_texto_base (str): Suas experiências atuais para a IA ter como base (não inventar).
        
    Returns:
        dict: Dicionário contendo 'match' (bool) e 'resumo_adaptado' (str), ou None em caso de erro.
    """
    if not GEMINI_API_KEY:
        logger.error("API Key do Gemini não configurada. Não é possível analisar a vaga.")
        return None

    prompt = f"""
    Você é um especialista em RH e engenheiro de software.
    Avalie a seguinte DESCRIÇÃO DA VAGA em relação ao MEU CURRÍCULO BASE.

    MEU CURRÍCULO BASE (Use estritamente como fonte de verdade, não invente habilidades que não estão aqui):
    {curriculo_texto_base}

    DESCRIÇÃO DA VAGA:
    {descricao_vaga}

    Tarefas:
    1. Determine se o meu perfil dá 'match' com essa vaga (se as habilidades core convergem).
    2. Se for um match, reescreva um Resumo Profissional focado em destacar APENAS as minhas 
       experiências do 'Currículo Base' que são relevantes para as palavras-chave exigidas na vaga.

    Retorne o resultado ESTRITAMENTE em formato JSON com esta estrutura:
    {{
        "match": true ou false,
        "resumo_adaptado": "O texto do resumo adaptado para a vaga, ou vazio se match for false."
    }}
    Não retorne formatação markdown, apenas o JSON puro.
    """

    try:
        response = model.generate_content(prompt)
        # Limpando possíveis formatações markdown do retorno do Gemini (ex: ```json ... ```)
        texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
        resultado_json = json.loads(texto_limpo)
        return resultado_json
    except Exception as e:
        logger.error(f"Erro na análise do Gemini: {e}")
        return None


# ==============================================================================
# MÓDULO DE GERAÇÃO DE CURRÍCULO (HTML → PDF via Playwright)
# ==============================================================================
# A geração de currículo agora está no arquivo gerador_curriculo.py
# Função importada: gerar_curriculo_pdf(resumo_ia, output_pdf_path, ...)


# ==============================================================================
# MÓDULO DE LOG E REGISTRO
# ==============================================================================

def salvar_historico(id_vaga: str, nome_vaga: str, empresa: str, resumo_desc: str) -> None:
    """
    Salva o log da vaga processada no formato especificado.
    
    Args:
        id_vaga (str): Código ou ID extraído da URL/página.
        nome_vaga (str): Título da vaga.
        empresa (str): Nome da empresa.
        resumo_desc (str): Pequeno resumo da descrição.
    """
    arquivo_log = "historico_vagas.txt"
    try:
        # Pega a quantidade atual de linhas para determinar o Número da vaga (simples)
        num = 1
        if os.path.exists(arquivo_log):
            with open(arquivo_log, 'r', encoding='utf-8') as f:
                num = sum(1 for _ in f) + 1
                
        linha = f"Vaga [{num}] - {nome_vaga} - {empresa} - {id_vaga} - {resumo_desc}\n"
        
        with open(arquivo_log, 'a', encoding='utf-8') as f:
            f.write(linha)
        logger.info(f"Vaga {id_vaga} registrada no histórico.")
    except Exception as e:
        logger.error(f"Erro ao salvar histórico: {e}")


# ==============================================================================
# MÓDULO DE SCRAPING E APLICAÇÃO (PLAYWRIGHT)
# ==============================================================================

def realizar_login(page: Page) -> bool:
    """Faz o login seguro no LinkedIn."""
    if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
        logger.error("Credenciais do LinkedIn não encontradas no .env")
        return False
        
    try:
        logger.info("Navegando para a página de login...")
        page.goto("https://www.linkedin.com/login", timeout=60000)
        
        page.fill("#username", LINKEDIN_EMAIL)
        page.fill("#password", LINKEDIN_PASSWORD)
        page.click("button[type='submit']")
        
        # Espera o feed carregar para confirmar o login
        page.wait_for_selector(".global-nav", timeout=30000)
        logger.info("Login realizado com sucesso.")
        return True
    except Exception as e:
        logger.error(f"Falha ao realizar login: {e}")
        return False

def buscar_vagas(page: Page, keywords: str) -> List[Dict[str, str]]:
    """
    Pesquisa por vagas e extrai os links e informações básicas.
    AVISO: Os seletores HTML mudam frequentemente. Ajuste se necessário.
    """
    vagas_encontradas = []
    try:
        # A URL de busca do LinkedIn Job Search pode receber os parâmetros diretamente
        url_busca = f"https://www.linkedin.com/jobs/search/?keywords={keywords}&f_AL=true" # f_AL=true força "Easy Apply"
        logger.info(f"Buscando vagas para: {keywords} (Com filtro Easy Apply)")
        page.goto(url_busca, timeout=60000)
        
        # Espera a lista de vagas carregar
        page.wait_for_selector(".jobs-search-results__list-item", timeout=15000)
        
        # Extrai os cards de vagas
        # IMPORTANTE: Estes seletores são propensos a mudança pelo LinkedIn
        cards = page.locator(".jobs-search-results__list-item").all()
        
        for idx, card in enumerate(cards[:5]):  # Limitando a 5 vagas por rodada para segurança
            # Clica no card para carregar a descrição ao lado
            card.scroll_into_view_if_needed()
            card.click()
            time.sleep(2) # Pequeno atraso humanizado
            
            # Extração de dados da tela lateral (Job details)
            titulo_loc = page.locator(".jobs-details-top-card__job-title")
            empresa_loc = page.locator(".jobs-details-top-card__company-info a").first
            
            titulo = titulo_loc.inner_text().strip() if titulo_loc.is_visible() else f"Vaga_Desconhecida_{idx}"
            empresa = empresa_loc.inner_text().strip() if empresa_loc.is_visible() else "Empresa Desconhecida"
            
            # Pega a URL atual que tem o ID da vaga
            url_atual = page.url
            id_vaga = url_atual.split("view/")[-1].split("/")[0] if "view/" in url_atual else str(idx)
            
            # Extrai descrição
            desc_loc = page.locator("#job-details")
            descricao = desc_loc.inner_text().strip() if desc_loc.is_visible() else ""
            
            vagas_encontradas.append({
                "id": id_vaga,
                "titulo": titulo,
                "empresa": empresa,
                "descricao": descricao,
                "url": url_atual
            })
            
        logger.info(f"Encontrou {len(vagas_encontradas)} vagas processáveis.")
        return vagas_encontradas
        
    except Exception as e:
        logger.error(f"Erro ao buscar vagas: {e}")
        return vagas_encontradas

def aplicar_vaga(page: Page, caminho_curriculo_adaptado: str) -> bool:
    """
    Tenta preencher o formulário Easy Apply.
    MUITO CUIDADO: Este fluxo é complexo e varia muito de empresa para empresa.
    """
    try:
        # Procura botão Easy Apply
        btn_apply = page.locator("button.jobs-apply-button")
        if not btn_apply.is_visible():
            logger.info("Botão Easy Apply não encontrado.")
            return False
            
        btn_apply.click()
        time.sleep(2)
        
        # Fluxo de modal de candidatura (Este é um fluxo genérico e PODE FALHAR dependendo do formulário)
        # 1. Próximo, Próximo... até achar upload de currículo ou Finalizar
        tentativas = 0
        while tentativas < 10:
            # Verifica se há input de file (upload de currículo)
            input_file = page.locator("input[type='file']")
            if input_file.is_visible():
                logger.info("Fazendo upload do currículo adaptado...")
                input_file.set_input_files(caminho_curriculo_adaptado)
                time.sleep(1)
            
            # Botão Avançar / Revisar / Submeter
            btn_next = page.locator("button[aria-label='Continue to next step']")
            btn_review = page.locator("button[aria-label='Review your application']")
            btn_submit = page.locator("button[aria-label='Submit application']")
            
            if btn_submit.is_visible() and btn_submit.is_enabled():
                # AQUI É ONDE ELE REALMENTE APLICA
                logger.info("Botão SUBMIT encontrado. Enviando aplicação...")
                # btn_submit.click() # DESCOMENTE PARA APLICAR DE VERDADE
                logger.warning("[MODO DE SEGURANÇA] btn_submit.click() comentado. Aplicação simulada.")
                time.sleep(2)
                
                # Botão fechar modal após sucesso
                btn_close = page.locator("button[aria-label='Dismiss']")
                if btn_close.is_visible():
                    btn_close.click()
                return True
                
            elif btn_review.is_visible() and btn_review.is_enabled():
                btn_review.click()
            elif btn_next.is_visible() and btn_next.is_enabled():
                btn_next.click()
            else:
                logger.warning("Nenhum botão de avançar encontrado ou formulário complexo.")
                # Tenta fechar o modal
                page.locator("button[aria-label='Dismiss']").click()
                page.locator("button[data-control-name='discard_application_confirm_btn']").click()
                break
                
            time.sleep(1.5)
            tentativas += 1
            
        return False
        
    except Exception as e:
        logger.error(f"Erro durante fluxo Easy Apply: {e}")
        return False


# ==============================================================================
# ORQUESTRADOR PRINCIPAL
# ==============================================================================

def main():
    # 1. Defina as palavras-chave que você quer buscar
    keywords_pesquisa = "Python Automation Developer"
    
    # 2. Defina o seu Currículo Base (Isso seria melhor lido de um arquivo texto ou do próprio docx)
    curriculo_base_texto = """
    Engenheiro de Software Sênior com 6 anos de experiência.
    Especialista em Python, automação de processos, web scraping (Playwright/Selenium).
    Experiência com integrações de IA (OpenAI, Gemini), criação de pipelines de dados.
    """
    
    output_pdf_path = "curriculo_adaptado.pdf"

    with sync_playwright() as p:
        # Lança o navegador
        browser = p.chromium.launch(headless=HEADLESS_MODE)
        context = browser.new_context(
            # Disfarça o Playwright definindo um User-Agent comum
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Fluxo de Automação
        if realizar_login(page):
            vagas = buscar_vagas(page, keywords_pesquisa)
            
            for vaga in vagas:
                logger.info(f"\n--- Processando Vaga: {vaga['titulo']} na {vaga['empresa']} ---")
                
                # Análise da IA
                logger.info("Enviando para o Gemini avaliar o Match...")
                resultado_ia = analisar_vaga_com_ia(vaga['descricao'][:3000], curriculo_base_texto) # Limite de caracteres p/ prompt
                
                if not resultado_ia:
                    continue
                    
                is_match = resultado_ia.get('match', False)
                resumo_ia = resultado_ia.get('resumo_adaptado', "")
                
                if is_match:
                    logger.info("✅ DEU MATCH! Adaptando currículo...")
                    sucesso_pdf = gerar_curriculo_pdf(
                        resumo_ia=resumo_ia,
                        output_pdf_path=output_pdf_path,
                    )
                    
                    if sucesso_pdf:
                        logger.info("Tentando aplicar para a vaga...")
                        aplicado = aplicar_vaga(page, output_pdf_path)
                        status_aplic = "Aplicado" if aplicado else "Erro_Formulario"
                    else:
                        status_aplic = "Erro_PDF"
                else:
                    logger.info("❌ NÃO DEU MATCH. Pulando vaga.")
                    status_aplic = "No_Match"
                
                # Log no arquivo txt
                resumo_pequeno = resumo_ia[:100].replace("\n", " ") + "..." if resumo_ia else "Sem resumo."
                salvar_historico(vaga['id'], vaga['titulo'], vaga['empresa'], f"[{status_aplic}] {resumo_pequeno}")
                
                # Pausa para evitar bloqueios do LinkedIn
                logger.info("Aguardando 10 segundos antes da próxima vaga...")
                time.sleep(10)
                
        else:
            logger.error("Abortando script devido a falha no login.")
            
        browser.close()

if __name__ == "__main__":
    main()

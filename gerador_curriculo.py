"""
Módulo de Geração de Currículo em PDF via HTML + Playwright.
Substitui o antigo módulo baseado em python-docx por uma abordagem mais
poderosa: HTML/CSS template → renderização Playwright → exportação PDF.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

# ==============================================================================
# HELPERS PARA GERAÇÃO DE SNIPPETS HTML
# ==============================================================================

def _gerar_entry_html(
    titulo: str,
    subtitulo: str,
    periodo: str,
    local: str,
    itens: List[str],
    nota: str = ""
) -> str:
    """
    Gera o bloco HTML de uma entrada de experiência/educação.
    
    Args:
        titulo: Cargo ou grau acadêmico.
        subtitulo: Empresa ou instituição.
        periodo: Intervalo de datas (ex: 'Jan 2020 — Presente').
        local: Cidade / País.
        itens: Lista de bullet points descrevendo a atuação.
        nota: Texto opcional de observação.
        
    Returns:
        String HTML pronta para injeção no template.
    """
    lista_html = "".join(f"<li>{item}</li>" for item in itens) if itens else ""
    nota_html = f'<p class="entry-note">{nota}</p>' if nota else ""

    return f"""
    <div class="entry">
        <div class="entry-header">
            <div class="entry-title">{titulo}</div>
            <div class="entry-subtitle">{subtitulo}</div>
        </div>
        <div class="entry-meta">
            <span class="meta-item">
                <svg viewBox="0 0 24 24"><path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2z"/></svg>
                {periodo}
            </span>
            <span class="meta-item">
                <svg viewBox="0 0 24 24"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zM7 9c0-2.76 2.24-5 5-5s5 2.24 5 5c0 2.88-2.88 7.19-5 9.88C9.92 16.21 7 11.85 7 9z"/><circle cx="12" cy="9" r="2.5"/></svg>
                {local}
            </span>
        </div>
        <div class="entry-body">
            <ul>{lista_html}</ul>
        </div>
        {nota_html}
    </div>"""


def _gerar_projeto_html(nome: str, descricao: str) -> str:
    """Gera o bloco HTML de um projeto."""
    return f"""
    <div class="project-entry">
        <div class="project-name">{nome}</div>
        <p class="project-desc">{descricao}</p>
    </div>"""


def _gerar_skill_dots_html(nome: str, nivel: int, max_dots: int = 5) -> str:
    """
    Gera um item de skill com bolinhas visuais (estilo alta-typst).
    
    Args:
        nome: Nome da habilidade (ex: 'Python').
        nivel: Nível de 1 a max_dots.
        max_dots: Total de bolinhas (padrão 5).
    """
    dots = ""
    for i in range(max_dots):
        css_class = "skill-dot filled" if i < nivel else "skill-dot"
        dots += f'<span class="{css_class}"></span>'

    return f"""
    <div class="skill-item">
        <span class="skill-name">{nome}</span>
        <span class="skill-dots">{dots}</span>
    </div>"""


def _gerar_certificacao_html(nome: str, emissor: str) -> str:
    """Gera o bloco HTML de uma certificação."""
    return f"""
    <div class="entry" style="margin-bottom: 2mm;">
        <div class="entry-title" style="font-size: 9pt;">{nome}</div>
        <div class="entry-subtitle" style="font-size: 8pt;">{emissor}</div>
    </div>"""


# ==============================================================================
# DADOS DO CURRÍCULO — EDITE AQUI COM SEUS DADOS REAIS
# ==============================================================================

def carregar_dados_curriculo() -> Dict[str, Any]:
    """
    Retorna os dados do currículo para preencher o template.
    Edite este dicionário com suas informações reais.
    As chaves de API e credenciais NÃO ficam aqui — apenas dados do CV.
    
    Returns:
        Dicionário com todas as seções do currículo.
    """
    return {
        "nome_completo": "Seu Nome Completo",
        "email": "seu.email@exemplo.com",
        "localizacao": "São Paulo, Brasil",
        "telefone": "(11) 99999-9999",
        "linkedin_url": "linkedin.com/in/seuperfil",
        
        # O resumo_ia será substituído dinamicamente pela IA quando houver match
        "resumo_padrao": "Engenheiro de Software com experiência em desenvolvimento de aplicações web, automação de processos e integração de APIs de IA.",

        "experiencias": [
            {
                "titulo": "Engenheiro de Software Sênior",
                "subtitulo": "Empresa Exemplo S.A.",
                "periodo": "Jan 2021 — Presente",
                "local": "São Paulo, BR",
                "itens": [
                    "Desenvolvimento de microsserviços em Python (FastAPI, Django).",
                    "Automação de pipelines CI/CD com GitHub Actions.",
                    "Integração de modelos de IA (OpenAI, Gemini) em produtos internos.",
                ],
            },
            {
                "titulo": "Desenvolvedor Python Pleno",
                "subtitulo": "Outra Empresa Ltda.",
                "periodo": "Mar 2019 — Dez 2020",
                "local": "Remoto",
                "itens": [
                    "Web scraping e automação com Selenium e Playwright.",
                    "Criação de dashboards analíticos com Pandas e Plotly.",
                ],
            },
        ],

        "educacao": [
            {
                "titulo": "Bacharelado em Ciência da Computação",
                "subtitulo": "Universidade Exemplo",
                "periodo": "2015 — 2019",
                "local": "São Paulo, BR",
                "itens": [],
            },
        ],

        "idiomas": [
            {
                "titulo": "Português",
                "subtitulo": "Nativo",
                "periodo": "",
                "local": "",
                "itens": [],
            },
            {
                "titulo": "Inglês",
                "subtitulo": "Avançado (C1)",
                "periodo": "",
                "local": "",
                "itens": [],
            },
        ],

        "projetos": [
            {
                "nome": "Bot de Automação LinkedIn",
                "descricao": "Script Python que busca vagas, analisa com IA Gemini e adapta currículos automaticamente.",
            },
            {
                "nome": "Pipeline de Dados em Tempo Real",
                "descricao": "Sistema de ingestão e processamento de eventos com Kafka e Python.",
            },
        ],

        "skills": [
            {"nome": "Python", "nivel": 5},
            {"nome": "JavaScript", "nivel": 4},
            {"nome": "SQL / PostgreSQL", "nivel": 4},
            {"nome": "Docker", "nivel": 4},
            {"nome": "Git", "nivel": 5},
            {"nome": "Playwright", "nivel": 4},
            {"nome": "FastAPI / Django", "nivel": 4},
            {"nome": "Machine Learning", "nivel": 3},
        ],

        "certificacoes": [
            {"nome": "Google Cloud Professional Data Engineer", "emissor": "Google Cloud"},
            {"nome": "AWS Certified Solutions Architect", "emissor": "Amazon Web Services"},
        ],
    }


# ==============================================================================
# FUNÇÃO PRINCIPAL DE GERAÇÃO
# ==============================================================================

def gerar_curriculo_pdf(
    resumo_ia: str = "",
    output_pdf_path: str = "curriculo_adaptado.pdf",
    template_html_path: str = "curriculo_template.html",
    dados_override: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Gera o currículo em PDF preenchendo o template HTML e renderizando via Playwright.
    
    Args:
        resumo_ia: Resumo profissional gerado pela IA. Se vazio, usa o resumo padrão.
        output_pdf_path: Caminho de saída do PDF.
        template_html_path: Caminho do arquivo HTML do template.
        dados_override: Dicionário opcional para sobrescrever dados do currículo.
        
    Returns:
        True se o PDF foi gerado com sucesso, False caso contrário.
    """
    try:
        dados = carregar_dados_curriculo()
        if dados_override:
            dados.update(dados_override)

        # Lê o template HTML
        if not os.path.exists(template_html_path):
            logger.error(f"Template HTML não encontrado: {template_html_path}")
            return False

        with open(template_html_path, 'r', encoding='utf-8') as f:
            html = f.read()

        # ---- Preenche dados estáticos ----
        html = html.replace("{{NOME_COMPLETO}}", dados["nome_completo"])
        html = html.replace("{{EMAIL}}", dados["email"])
        html = html.replace("{{LOCALIZACAO}}", dados["localizacao"])
        html = html.replace("{{TELEFONE}}", dados["telefone"])
        html = html.replace("{{LINKEDIN_URL}}", dados["linkedin_url"])

        # Resumo: IA tem prioridade, senão usa o padrão
        resumo_final = resumo_ia if resumo_ia else dados.get("resumo_padrao", "")
        html = html.replace("{{RESUMO_IA}}", resumo_final)

        # ---- Gera seções dinâmicas ----
        
        # Experiências
        exp_html = ""
        for exp in dados.get("experiencias", []):
            exp_html += _gerar_entry_html(
                exp["titulo"], exp["subtitulo"],
                exp["periodo"], exp["local"], exp["itens"]
            )
        html = html.replace("{{EXPERIENCIAS}}", exp_html)

        # Educação
        edu_html = ""
        for edu in dados.get("educacao", []):
            edu_html += _gerar_entry_html(
                edu["titulo"], edu["subtitulo"],
                edu["periodo"], edu["local"], edu["itens"]
            )
        html = html.replace("{{EDUCACAO}}", edu_html)

        # Idiomas (reutiliza entry mas sem meta de datas/local)
        idiomas_html = ""
        for idioma in dados.get("idiomas", []):
            idiomas_html += f"""
            <div class="entry" style="margin-bottom: 2mm;">
                <div class="entry-title" style="font-size: 9pt;">{idioma['titulo']}</div>
                <div class="entry-subtitle" style="font-size: 8pt;">{idioma['subtitulo']}</div>
            </div>"""
        html = html.replace("{{IDIOMAS}}", idiomas_html)

        # Projetos
        proj_html = ""
        for proj in dados.get("projetos", []):
            proj_html += _gerar_projeto_html(proj["nome"], proj["descricao"])
        html = html.replace("{{PROJETOS}}", proj_html)

        # Skills com bolinhas
        skills_html = ""
        for skill in dados.get("skills", []):
            skills_html += _gerar_skill_dots_html(skill["nome"], skill["nivel"])
        html = html.replace("{{SKILLS}}", skills_html)

        # Certificações
        cert_html = ""
        for cert in dados.get("certificacoes", []):
            cert_html += _gerar_certificacao_html(cert["nome"], cert["emissor"])
        html = html.replace("{{CERTIFICACOES}}", cert_html)

        # ---- Renderiza HTML → PDF via Playwright ----
        abs_output = os.path.abspath(output_pdf_path)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Carrega o HTML diretamente no navegador
            page.set_content(html, wait_until="networkidle")

            # Exporta como PDF tamanho A4
            page.pdf(
                path=abs_output,
                format="A4",
                print_background=True,
                margin={
                    "top": "0mm",
                    "bottom": "0mm",
                    "left": "0mm",
                    "right": "0mm",
                },
            )
            browser.close()

        logger.info(f"✅ Currículo PDF gerado com sucesso: {abs_output}")
        return True

    except Exception as e:
        logger.error(f"Erro ao gerar currículo PDF: {e}")
        return False


# ==============================================================================
# EXECUÇÃO DIRETA (teste isolado)
# ==============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Teste: gera um PDF com o resumo padrão
    sucesso = gerar_curriculo_pdf(
        resumo_ia="Profissional de tecnologia com sólida experiência em Python e automação, buscando novos desafios na área de engenharia de software.",
        output_pdf_path="curriculo_teste.pdf",
    )
    
    if sucesso:
        print("PDF de teste gerado: curriculo_teste.pdf")
    else:
        print("Falha ao gerar o PDF.")

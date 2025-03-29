import os
import requests
import tempfile
import re
from PyPDF2 import PdfReader
import sqlite3
import json
from datetime import datetime, timedelta
import pandas as pd

from flask import Flask, request, jsonify
from flask_admin import Admin, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_sqlalchemy import SQLAlchemy

import requests
import logging
import time
import json
import pdfplumber
import openai
import re

# Importar funções de integração com Monday.com
from monday_integration import (
    cadastrar_candidato_monday,
    registrar_pagamento_candidato,
    verificar_status_assinatura,
    cadastrar_empresa_monday,
    aprovar_empresa,
    publicar_vaga,
    listar_vagas,
    candidatar_vaga,
    buscar_candidatos_vaga,
    registrar_contratacao,
    registrar_pagamento_contratacao
)

app = Flask(__name__)

# === CONFIGURAÇÃO DO BANCO DE DADOS ===
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mais_emprego.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'maisemprego_secret_key'
db = SQLAlchemy(app)

# === CONFIGURAÇÕES ===

# OpenAI
openai.api_key = "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"
OPENAI_WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"
OPENAI_GPT_URL = "https://api.openai.com/v1/chat/completions"

# Maytapi (WhatsApp)
MAYTAPI_INSTANCE_ID = "ab1bd395-c474-4760-8f9a-4aedbeb38dfe"
MAYTAPI_PHONE_ID = "77364"
MAYTAPI_KEY = "aef85e2d-5bbf-4a44-bd72-f8f84e968c32"
MAYTAPI_URL = f"https://api.maytapi.com/api/{MAYTAPI_INSTANCE_ID}/{MAYTAPI_PHONE_ID}/sendMessage"

# Monday.com
MONDAY_API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjQ4NjE3ODgxNywiYWFpIjoxMSwidWlkIjo3MzU3NzU1NCwiaWFkIjoiMjAyNS0wMy0xNlQyMDowMDo1Ni4wMDBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6OTY5Njg1MCwicmduIjoidXNlMSJ9.4lPDhuGVImkBTf9l2BH12F_dPQP6bKq4EKfIlz54PNY"
CANDIDATOS_BOARD_ID = "8812301302"
EMPRESAS_BOARD_ID = "8812301317"
VAGAS_BOARD_ID = "8812301333"
CANDIDATURAS_BOARD_ID = "8812301347"
CONTRATACOES_BOARD_ID = "8812301363"
MONDAY_API_URL = "https://api.monday.com/v2"

# Logger customizado com nome "wp"
logger = logging.getLogger("wp")
logging.basicConfig(level=logging.INFO)

# === PERSONALIDADES PARA IA ===

# Personalidade para candidatos (linguagem mais direta e simples)
PERSONALIDADE_CANDIDATO = """
Você é I.Atomos, o assistente virtual da empresa de recrutamento. 
Use linguagem simples, direta e clara. Evite termos técnicos complexos.
Comunique-se de forma concisa, com frases curtas e objetivas.
Foque em explicar os passos de forma prática e acessível.
Seu objetivo é ajudar candidatos a enviarem currículos e, após isso, orientá-los sobre a possibilidade de ativar o cadastro por R$10,00 para ter prioridade nas indicações.
Nunca prometa emprego garantido, apenas explique que o cadastro ativo aumenta as chances.
Mantenha um tom positivo e respeitoso, compreendendo a situação de quem busca emprego.
"""

# Personalidade para empresas (linguagem mais técnica e profissional)
PERSONALIDADE_EMPRESA = """
Você é I.Atomos, o assistente de gestão de recrutamento.
Use linguagem mais formal e técnica, adequada ao contexto empresarial.
Comunique-se de forma profissional, detalhada e precisa.
Explique os processos de forma estruturada e com terminologia de RH.
Seu objetivo é auxiliar recrutadores a publicarem vagas e encontrarem os candidatos mais compatíveis.
Informe sobre o modelo de pagamento: R$80,00 por contratação realizada.
Mantenha um tom consultivo e profissional, demonstrando conhecimento do mercado de trabalho.
"""

# Personalidade original para compatibilidade
PERSONALIDADE_MAIS_EMPREGO = """
Você é I.Atomos, a assistente virtual oficial da Mais Emprego, uma empresa especializada em conectar candidatos a oportunidades de trabalho. Siga estas diretrizes em sua comunicação:

# OBJETIVO GERAL
Seu objetivo é criar uma experiência positiva que resulte em:
1. Recebimento do currículo do candidato
2. Explicação clara do serviço oferecido
3. Conversão para o plano pago de R$10,00 (apenas quando apropriado)

# ETAPAS DO ATENDIMENTO

## 1. PRIMEIRO CONTATO
- Seja acolhedora, educada e demonstre empatia com quem busca emprego
- Use linguagem simples, próxima e respeitosa
- Apresente-se como I.Atomos da Mais Emprego
- Explique brevemente que a Mais Emprego conecta candidatos com oportunidades de trabalho
- Pergunte como pode ajudar o candidato hoje

## 2. RECEBIMENTO DO CURRÍCULO
- Solicite o currículo em formato PDF
- Quando receber, agradeça e confirme que foi processado com sucesso
- Explique que o currículo foi incluído no banco de talentos gratuito
- Mencione que há diferentes níveis de serviço disponíveis

## 3. EXPLICAÇÃO DO SERVIÇO
- Explique que o cadastro básico é gratuito, mas tem visibilidade limitada 
- Explique o funcionamento do plano ATIVO: "Com o cadastro ATIVO, seu currículo recebe destaque no nosso sistema e é enviado preferencialmente às empresas parceiras que buscam profissionais com seu perfil"
- Cite os benefícios: maior visibilidade, prioridade nas indicações, acesso a vagas exclusivas, análise personalizada do currículo
- Use exemplos práticos: "Imagine ter seu currículo entre os primeiros a serem vistos pelos recrutadores em vez de ficar no meio de centenas de outros"

## 4. CONVERSÃO PARA O PLANO PAGO
- Apenas quando o candidato demonstrar interesse ou perguntar como ter mais chances, informe sobre a taxa de ativação
- Seja transparente sobre o valor: "A ativação do cadastro prioritário tem uma pequena taxa única de R$10,00"
- Explique que é um valor único (não mensal) para cobrir os custos do serviço premium
- Esclareça que não há garantias de contratação, mas que o sistema aumenta significativamente as chances

## 5. PROCESSO DE PAGAMENTO
- Se o candidato concordar, forneça os dados do PIX: chave 65999526005
- Solicite o comprovante de pagamento pelo mesmo canal
- Confirme o recebimento e explique os próximos passos

# REGRAS IMPORTANTES
- Nunca prometa garantias de emprego
- Não fale sobre taxas ou pagamentos no primeiro contato, a menos que o candidato pergunte
- Mantenha tom positivo e motivador, entendendo o momento delicado de quem busca emprego
- Adapte sua comunicação ao nível de interesse do candidato
- Responda perguntas diretas com transparência
- Se o candidato rejeitar o plano pago, assegure que o currículo permanecerá no banco de dados gratuito
- Evite pressionar; foque em informar e esclarecer o valor do serviço
"""

# === MODELOS DE BANCO DE DADOS ===

class Candidato(db.Model):
    __tablename__ = 'candidatos'
    
    chat_id = db.Column(db.String(50), primary_key=True)
    nome = db.Column(db.String(100))
    estagio = db.Column(db.Integer, default=1)
    data_primeiro_contato = db.Column(db.String(30))
    data_ultimo_contato = db.Column(db.String(30))
    curriculo_enviado = db.Column(db.Integer, default=0)
    monday_id = db.Column(db.String(50))
    historico = db.Column(db.Text)
    comprovante_enviado = db.Column(db.Integer, default=0)
    ativado = db.Column(db.Integer, default=0)
    
    mensagens = db.relationship('Mensagem', backref='candidato', lazy='dynamic')

class Mensagem(db.Model):
    __tablename__ = 'mensagens'
    
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(50), db.ForeignKey('candidatos.chat_id'))
    data = db.Column(db.String(30))
    tipo = db.Column(db.String(20))
    mensagem = db.Column(db.Text)
    resposta = db.Column(db.Text)

class Empresa(db.Model):
    __tablename__ = 'empresas'
    
    chat_id = db.Column(db.String(50), primary_key=True)
    nome = db.Column(db.String(100))
    cnpj = db.Column(db.String(20))
    razao_social = db.Column(db.String(100))
    nome_fantasia = db.Column(db.String(100))
    email = db.Column(db.String(100))
    endereco = db.Column(db.Text)
    monday_id = db.Column(db.String(50))
    estagio = db.Column(db.Integer, default=1)
    estagio_vaga = db.Column(db.Integer, default=0)
    dados_vaga = db.Column(db.Text)
    data_cadastro = db.Column(db.String(30))


# === FUNÇÕES GERAIS ===

def obter_resposta_chatgpt(mensagem, personalidade=PERSONALIDADE_MAIS_EMPREGO):
    headers = {"Authorization": f"Bearer {openai.api_key}", "Content-Type": "application/json"}
    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": personalidade},
            {"role": "user", "content": mensagem}
        ],
        "max_tokens": 300,
        "temperature": 0.6
    }
    resposta = requests.post(OPENAI_GPT_URL, headers=headers, json=data)
    return resposta.json().get("choices", [{}])[0].get("message", {}).get("content", "⚠️ Erro ao obter resposta.")

def obter_resposta_chatgpt_com_contexto(mensagem, instrucao, estagio, tipo_usuario="candidato"):
    """
    Versão aprimorada que considera o estágio da conversa e tipo de usuário
    """
    # Selecionar personalidade base de acordo com tipo de usuário
    personalidade_base = PERSONALIDADE_CANDIDATO if tipo_usuario == "candidato" else PERSONALIDADE_EMPRESA
    
    headers = {"Authorization": f"Bearer {openai.api_key}", "Content-Type": "application/json"}
    
    # Construir histórico de contexto baseado no estágio
    contexto_mensagens = []
    
    if tipo_usuario == "candidato":
        if estagio == 2:
            contexto_mensagens.append({
                "role": "system", 
                "content": "O candidato já enviou o currículo. É um bom momento para mencionar sutilmente os benefícios da ativação do cadastro."
            })
        elif estagio == 3:
            contexto_mensagens.append({
                "role": "system", 
                "content": "O candidato está considerando ativar o cadastro. Enfatize os benefícios e o valor do investimento."
            })
        elif estagio == 4:
            contexto_mensagens.append({
                "role": "system", 
                "content": "O candidato está no processo de pagamento. Incentive-o a concluir o processo e enviar o comprovante."
            })
        elif estagio == 5:
            contexto_mensagens.append({
                "role": "system", 
                "content": "O candidato é um cliente pago. Ofereça um atendimento premium e mantenha-o motivado na busca por emprego."
            })
    else:  # empresa
        if estagio >= 6:
            contexto_mensagens.append({
                "role": "system", 
                "content": "A empresa está cadastrada. Mantenha um tom profissional e ofereça ajuda para publicar vagas ou gerenciar candidatos."
            })
    
    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": personalidade_base},
            *contexto_mensagens,
            {"role": "user", "content": mensagem}
        ],
        "max_tokens": 300,
        "temperature": 0.6
    }
    
    resposta = requests.post(OPENAI_GPT_URL, headers=headers, json=data)
    return resposta.json().get("choices", [{}])[0].get("message", {}).get("content", "⚠️ Erro ao obter resposta.")

def baixar_audio(url):
    resposta = requests.get(url, stream=True)
    if resposta.status_code == 200:
        with open("audio.oga", "wb") as f:
            for chunk in resposta.iter_content(1024):
                f.write(chunk)
        return "audio.oga"
    return None

def transcrever_audio(caminho_audio):
    headers = {"Authorization": f"Bearer {openai.api_key}"}
    files = {"file": open(caminho_audio, "rb")}
    data = {"model": "whisper-1"}
    resposta = requests.post(OPENAI_WHISPER_URL, headers=headers, files=files, data=data)
    return resposta.json().get("text", None)

def extrair_texto_do_pdf(url_pdf):
    caminho_pdf = f"cv_{int(time.time())}.pdf"
    response = requests.get(url_pdf)
    with open(caminho_pdf, "wb") as f:
        f.write(response.content)
    with pdfplumber.open(caminho_pdf) as pdf:
        texto = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
    return texto

def enviar_mensagem_whatsapp(numero, mensagem):
    data = {"to_number": numero, "message": mensagem, "type": "text"}
    headers = {"x-maytapi-key": MAYTAPI_KEY, "Content-Type": "application/json"}
    requests.post(MAYTAPI_URL, headers=headers, json=data)


# === FUNÇÕES DE CONTROLE DE USUÁRIOS ===

def verificar_tipo_usuario(chat_id):
    """
    Verifica se um número está cadastrado como candidato ou empresa
    """
    empresa = Empresa.query.get(chat_id)
    if empresa:
        return "empresa"
    
    # Verificar na tabela de usuários
    try:
        conn = sqlite3.connect('mais_emprego.db')
        cursor = conn.cursor()
        cursor.execute("SELECT tipo FROM usuarios WHERE chat_id=?", (chat_id,))
        resultado = cursor.fetchone()
        conn.close()
        
        if resultado and resultado[0] == "empresa":
            return "empresa"
    except Exception as e:
        logger.error(f"Erro ao verificar tipo de usuário: {e}")
    
    return "candidato"


# === FUNÇÕES DE CONTROLE DE ESTÁGIO DO CANDIDATO ===

def atualizar_candidato(chat_id, nome=None, estagio=None, curriculo_enviado=None, monday_id=None, comprovante_enviado=None, ativado=None):
    """
    Atualiza ou cria um candidato no banco de dados
    """
    candidato = Candidato.query.get(chat_id)
    agora = datetime.now().isoformat()
    
    if candidato:
        # Atualiza candidato existente
        if nome:
            candidato.nome = nome
        if estagio:
            candidato.estagio = estagio
        if curriculo_enviado is not None:
            candidato.curriculo_enviado = curriculo_enviado
        if monday_id:
            candidato.monday_id = monday_id
        if comprovante_enviado is not None:
            candidato.comprovante_enviado = comprovante_enviado
        if ativado is not None:
            candidato.ativado = ativado
            
        candidato.data_ultimo_contato = agora
    else:
        # Cria novo candidato
        candidato = Candidato(
            chat_id=chat_id,
            nome=nome or "Desconhecido",
            estagio=estagio or 1,
            data_primeiro_contato=agora,
            data_ultimo_contato=agora,
            curriculo_enviado=curriculo_enviado or 0,
            monday_id=monday_id or "",
            comprovante_enviado=comprovante_enviado or 0,
            ativado=ativado or 0
        )
        db.session.add(candidato)
    
    db.session.commit()
    return candidato

def obter_candidato(chat_id):
    """
    Obtém um candidato do banco de dados
    """
    candidato = Candidato.query.get(chat_id)
    if candidato:
        return {
            'chat_id': candidato.chat_id,
            'nome': candidato.nome,
            'estagio': candidato.estagio,
            'data_primeiro_contato': candidato.data_primeiro_contato,
            'data_ultimo_contato': candidato.data_ultimo_contato,
            'curriculo_enviado': candidato.curriculo_enviado,
            'monday_id': candidato.monday_id,
            'historico': candidato.historico,
            'comprovante_enviado': candidato.comprovante_enviado,
            'ativado': candidato.ativado
        }
    return None

def registrar_mensagem(chat_id, tipo, mensagem, resposta):
    """
    Registra uma mensagem no histórico
    """
    nova_mensagem = Mensagem(
        chat_id=chat_id,
        data=datetime.now().isoformat(),
        tipo=tipo,
        mensagem=mensagem,
        resposta=resposta
    )
    db.session.add(nova_mensagem)
    db.session.commit()

def obter_historico_mensagens(chat_id, limite=5):
    """
    Obtém as últimas mensagens do candidato
    """
    mensagens = Mensagem.query.filter_by(chat_id=chat_id).order_by(Mensagem.id.desc()).limit(limite).all()
    return [
        {
            'data': msg.data,
            'tipo': msg.tipo,
            'mensagem': msg.mensagem,
            'resposta': msg.resposta
        }
        for msg in reversed(mensagens)
    ]

def avaliar_momento_ativacao(chat_id):
    """
    Determina se é um bom momento para sugerir a ativação
    """
    candidato = obter_candidato(chat_id)
    if not candidato:
        return False
    
    # Se já enviou currículo mas ainda não está ativado
    if candidato['curriculo_enviado'] == 1 and candidato['ativado'] == 0:
        mensagens = obter_historico_mensagens(chat_id)
        
        # Se tiver trocado ao menos 3 mensagens após enviar currículo
        if len(mensagens) >= 3:
            return True
    
    return False


# === FUNÇÕES DE EMPRESAS ===

def criar_empresa(chat_id, nome, estagio=1):
    """
    Cria um novo registro de empresa no banco de dados
    """
    empresa = Empresa.query.get(chat_id)
    agora = datetime.now().isoformat()
    
    if not empresa:
        # Cria nova empresa
        empresa = Empresa(
            chat_id=chat_id, 
            nome=nome, 
            estagio=estagio, 
            data_cadastro=agora,
            estagio_vaga=0,
            dados_vaga=json.dumps({})
        )
        db.session.add(empresa)
        
        # Marcar como empresa na tabela de usuários
        try:
            conn = sqlite3.connect('mais_emprego.db')
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                chat_id TEXT PRIMARY KEY,
                tipo TEXT
            )
            ''')
            
            cursor.execute('''
            INSERT OR REPLACE INTO usuarios (
                chat_id, tipo
            ) VALUES (?, ?)
            ''', (chat_id, "empresa"))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"❌ Erro ao registrar usuário: {e}")
        
        db.session.commit()
        return empresa
    
    return empresa

def obter_empresa(chat_id):
    """
    Obtém dados de uma empresa do banco de dados
    """
    empresa = Empresa.query.get(chat_id)
    if empresa:
        return {
            'chat_id': empresa.chat_id,
            'nome': empresa.nome,
            'cnpj': empresa.cnpj,
            'razao_social': empresa.razao_social,
            'nome_fantasia': empresa.nome_fantasia,
            'email': empresa.email,
            'endereco': empresa.endereco,
            'monday_id': empresa.monday_id,
            'estagio': empresa.estagio,
            'estagio_vaga': empresa.estagio_vaga,
            'dados_vaga': json.loads(empresa.dados_vaga) if empresa.dados_vaga else {},
            'data_cadastro': empresa.data_cadastro
        }
    return None

def atualizar_empresa(chat_id, **kwargs):
    """
    Atualiza dados de uma empresa no banco de dados
    """
    empresa = Empresa.query.get(chat_id)
    if not empresa:
        return False
    
    for key, value in kwargs.items():
        if key == 'dados_vaga':
            empresa.dados_vaga = json.dumps(value)
        else:
            setattr(empresa, key, value)
    
    db.session.commit()
    return True

def validate_cnpj(cnpj):
    """
    Validação básica de CNPJ
    """
    # Remover caracteres não numéricos
    cnpj = re.sub(r'[^0-9]', '', cnpj)
    
    # Verificar se tem 14 dígitos
    if len(cnpj) != 14:
        return False
    
    # Verificação simplificada - em produção, fazer validação completa
    return True


# === FUNÇÕES DE PROCESSAMENTO DE MENSAGENS ===

def processar_mensagem_candidato(chat_id, nome, mensagem, tipo_mensagem, texto_mensagem):
    """
    Processa mensagens de candidatos (usando o fluxo já existente)
    """
    # Obter ou criar candidato
    candidato = obter_candidato(chat_id)
    if not candidato:
        atualizar_candidato(chat_id, nome=nome)
        candidato = {"estagio": 1, "curriculo_enviado": 0}
        logger.info(f"👤 Novo candidato registrado: {nome}")
    
    estagio_atual = candidato.get("estagio", 1)
    logger.info(f"📊 Estágio atual: {estagio_atual}")
    
    # Processar mensagem de acordo com o tipo
    if tipo_mensagem == "document":
        logger.info(f"📎 Documento recebido: {mensagem.get('filename', 'documento')}")
        
        # Verificar se é um PDF (currículo)
        filename = mensagem.get("filename", "").lower()
        if ".pdf" in filename or mensagem.get("mimetype") == "application/pdf":
            # Lógica de processamento de currículo
            url_pdf = mensagem.get("url")
            logger.info(f"📄 Processando currículo: {url_pdf}")
            
            try:
                texto = extrair_texto_do_pdf(url_pdf)
                
                email_match = re.search(r"[\w\.-]+@[\w\.-]+", texto)
                email = email_match.group(0) if email_match else ""
                
                fone_match = re.search(r"\(?\d{2}\)?\s?9?\d{4}[\-\s]?\d{4}", texto)
                telefone = fone_match.group(0) if fone_match else chat_id
                
                endereco_match = re.search(r"(Rua|Avenida|Travessa|Alameda|Rodovia)[^\n]{0,100}\d+", texto, re.IGNORECASE)
                endereco = endereco_match.group(0) if endereco_match else ""
                
                logger.info(f"📋 Dados extraídos - Email: {email}, Telefone: {telefone}")
                
                # Enviar para o Monday e obter ID
                monday_id = cadastrar_candidato_monday(
                    nome, email, telefone, endereco, texto, url_pdf, 
                    mensagem.get("filename", "curriculo.pdf")
                )
                
                # Atualizar cadastro do candidato
                atualizar_candidato(
                    chat_id, 
                    estagio=2,  # Avançar para o estágio "Enviou currículo"
                    curriculo_enviado=1,
                    monday_id=monday_id
                )
                
                # Resposta positiva
                resposta = (
                    "📄 Currículo recebido com sucesso! Seu perfil já está em nosso banco de talentos.\n\n"
                    "Sabia que você pode aumentar suas chances de ser indicado para vagas? "
                    "Candidatos com cadastro ATIVO têm prioridade nas indicações e acesso a vagas exclusivas. "
                    "Quer saber como ativar seu cadastro?"
                )
            except Exception as e:
                logger.error(f"❌ Erro ao processar currículo: {e}")
                resposta = (
                    "Encontrei um problema ao processar seu currículo. "
                    "Poderia tentar enviá-lo novamente? "
                    "Por favor, certifique-se de que é um arquivo PDF válido."
                )
        else:
            # Resposta para um documento que não é um currículo
            resposta = (
                "Obrigada pelo documento! Estou aqui principalmente para ajudar com seu cadastro "
                "para vagas de emprego. Você gostaria de enviar seu currículo em formato PDF? "
                "Assim posso incluí-lo em nosso banco de talentos."
            )
    
    elif tipo_mensagem == "image":
        # Verificar se é um possível comprovante de pagamento
        if candidato.get("estagio", 0) >= 4:
            logger.info("🧾 Possível comprovante de pagamento recebido")
            url_imagem = mensagem.get("url")
            
            # Registrar comprovante
            if candidato.get("monday_id"):
                try:
                    # Processar pagamento (valor fixo R$10,00)
                    sucesso, msg = processar_pagamento_candidato(chat_id, url_imagem)
                    
                    if sucesso:
                        resposta = (
                            "✅ *Pagamento recebido com sucesso!* \n\n"
                            "Seu cadastro na Mais Emprego agora está *ATIVO*! 🎉\n\n"
                            "A partir de agora, seu currículo receberá prioridade em nossas indicações. "
                            "Você poderá receber contatos de empresas interessadas no seu perfil a qualquer momento.\n\n"
                            "Estamos torcendo pelo seu sucesso profissional! Se tiver qualquer dúvida, estou à disposição."
                        )
                    else:
                        resposta = f"Tivemos um problema ao processar seu pagamento. {msg}"
                except Exception as e:
                    logger.error(f"❌ Erro ao registrar comprovante: {e}")
                    resposta = "Tivemos um problema ao processar seu comprovante. Por favor, tente novamente ou entre em contato com nosso suporte."
            else:
                resposta = "Não conseguimos localizar seu cadastro. Por favor, entre em contato com nosso suporte."
       else:
            logger.info("🖼️ Imagem recebida (não-comprovante)")
            # Resposta para uma imagem quando não estamos esperando um comprovante
            resposta = (
                "Recebi sua imagem! Estou aqui para ajudar com sua busca por oportunidades de emprego. "
                "Você gostaria de enviar seu currículo ou tem alguma pergunta sobre nossos serviços?"
            )
    
    elif tipo_mensagem == "ptt":
        logger.info("🎤 Áudio recebido, transcrevendo...")
        try:
            caminho = baixar_audio(mensagem.get("url"))
            texto = transcrever_audio(caminho)
            logger.info(f"🔊 Áudio transcrito: {texto[:100]}...")
            
            # Processar a mensagem de áudio como texto
            resposta = processar_texto_candidato(chat_id, texto, candidato, estagio_atual)
        except Exception as e:
            logger.error(f"❌ Erro ao transcrever áudio: {e}")
            resposta = (
                "Desculpe, tive dificuldade para entender o áudio. "
                "Poderia repetir sua mensagem em texto? Estou aqui para ajudar com sua busca por emprego."
            )
    
    else:  # Texto ou outros tipos
        if tipo_mensagem == "text":
            logger.info(f"💬 Texto recebido: {texto_mensagem[:100]}...")
            resposta = processar_texto_candidato(chat_id, texto_mensagem, candidato, estagio_atual)
        else:
            logger.info(f"❓ Tipo de mensagem não processado: {tipo_mensagem}")
            resposta = (
                "Olá! Estou aqui para ajudar com sua busca por oportunidades de emprego. "
                "Você gostaria de enviar seu currículo ou tem alguma pergunta sobre nossos serviços?"
            )
    
    # Registrar a interação
    tipo_conteudo = tipo_mensagem
    conteudo_mensagem = texto_mensagem
    if tipo_mensagem == "document" and ".pdf" in mensagem.get("filename", "").lower():
        tipo_conteudo = "curriculo"
        conteudo_mensagem = mensagem.get("filename", "curriculo.pdf")
    elif tipo_mensagem == "ptt":
        conteudo_mensagem = texto  # Texto transcrito
    elif tipo_mensagem == "image" and candidato.get("estagio", 0) >= 4:
        tipo_conteudo = "comprovante"
        conteudo_mensagem = "Comprovante de pagamento"
    
    registrar_mensagem(chat_id, tipo_conteudo, conteudo_mensagem, resposta)
    
    # Enviar resposta
    logger.info(f"📤 Enviando resposta para {chat_id}")
    enviar_mensagem_whatsapp(chat_id, resposta)
    return True

def processar_texto_candidato(chat_id, texto, candidato, estagio_atual):
    """
    Processa mensagens de texto do candidato com base no estágio atual
    """
    # Se não tiver enviado currículo ainda
    if candidato.get("curriculo_enviado") == 0:
        if re.search(r"curriculo|cv|currículo", texto, re.IGNORECASE):
            return (
                "Ótimo! Por favor, envie seu currículo em formato PDF. "
                "Assim que recebermos, irei incluí-lo em nosso banco de talentos e "
                "explicar como funciona o processo de indicação para vagas."
            )
        else:
            # Usar o GPT para responder ao primeiro contato
            return obter_resposta_chatgpt(texto, PERSONALIDADE_CANDIDATO)
    
    # Se já enviou currículo mas ainda não ativou
    elif estagio_atual == 2:
        # Verificar se demonstrou interesse na ativação ou é um bom momento para oferecer
        if re.search(r"ativar|ativação|como funciona|valor|custo|taxa|pago|r\$|prioridade", texto, re.IGNORECASE) or avaliar_momento_ativacao(chat_id):
            # Atualizar estágio
            atualizar_candidato(chat_id, estagio=3)  # Avançar para explicação do serviço
            
            return (
                "A Mais Emprego oferece o cadastro ATIVO, que dá prioridade ao seu currículo nas indicações de vagas. 🌟\n\n"
                "Com ele, você ganha:\n"
                "• Prioridade nas indicações para vagas compatíveis\n"
                "• Destaque no banco de talentos (seu currículo aparece primeiro)\n"
                "• Acesso a vagas exclusivas de nossos parceiros\n\n"
                "A ativação do cadastro tem uma taxa única de *R$10,00* (não é mensalidade). "
                "Gostaria de ativar seu cadastro para aumentar suas chances?"
            )
        else:
            # Usar o GPT com sutileza sobre ativação
            return obter_resposta_chatgpt_com_contexto(texto, PERSONALIDADE_CANDIDATO, estagio_atual, "candidato")
    
    # Se já recebeu explicação sobre ativação
    elif estagio_atual == 3:
        if re.search(r"sim|quero|ativar|como pago|onde pago|pix", texto, re.IGNORECASE):
            # Atualizar para estágio de pagamento
            atualizar_candidato(chat_id, estagio=4)
            
            return (
                "📢 *Ativação do Cadastro na Mais Emprego*\n\n"
                "Para ativar seu cadastro e começar a receber indicações prioritárias de vagas, "
                "basta realizar um *PIX no valor de R$ 10,00* para a chave abaixo:\n\n"
                "🔑 *Chave PIX:* 65999526005\n\n"
                "Depois de realizar o pagamento, envie o *comprovante aqui mesmo*. "
                "Assim que recebermos, sua ativação será processada em até 24 horas. ✅"
            )
        elif re.search(r"não|nao|caro|sem dinheiro|não posso|não tenho", texto, re.IGNORECASE):
            return (
                "Entendo completamente! O cadastro básico continua ativo gratuitamente. "
                "Seu currículo permanece em nosso banco de talentos e pode ser indicado para vagas compatíveis. "
                "Se mudar de ideia no futuro, é só me avisar. Estou aqui para ajudar em sua busca por oportunidades!"
            )
        else:
            # Continuar explicando benefícios
            return obter_resposta_chatgpt_com_contexto(texto, PERSONALIDADE_CANDIDATO, estagio_atual, "candidato")
    
    # Se está no processo de pagamento
    elif estagio_atual == 4:
        if re.search(r"paguei|fiz.*pix|transferi|enviei", texto, re.IGNORECASE):
            return (
                "Obrigada! Por favor, envie o comprovante do pagamento (pode ser um print ou foto). "
                "Assim que recebermos, iremos ativar seu cadastro prioritário imediatamente. "
                "Caso já tenha enviado o comprovante, aguarde alguns instantes enquanto processamos."
            )
        else:
            # Incentivar conclusão do pagamento
            return obter_resposta_chatgpt_com_contexto(texto, PERSONALIDADE_CANDIDATO, estagio_atual, "candidato")
    
    # Se já está com cadastro ativo
    elif estagio_atual == 5:
        # Verificar comandos específicos
        if re.search(r"vagas|oportunidades|trabalho|emprego", texto, re.IGNORECASE):
            # Listar vagas disponíveis
            try:
                vagas = listar_vagas()
                
                if not vagas:
                    return "No momento não temos vagas disponíveis que correspondam ao seu perfil. Assim que surgirem novas oportunidades, você receberá uma notificação!"
                
                mensagem_vagas = "📋 *Vagas disponíveis para você:*\n\n"
                
                for i, vaga in enumerate(vagas[:5], 1):  # Limitar a 5 vagas
                    mensagem_vagas += f"{i}. *{vaga['titulo']}*\n"
                    mensagem_vagas += f"   {vaga['empresa']['nome']}\n"
                    if 'salario' in vaga:
                        mensagem_vagas += f"   💰 R$ {vaga['salario']:.2f}\n"
                    if 'local' in vaga:
                        mensagem_vagas += f"   📍 {vaga['local']}\n"
                    mensagem_vagas += "\n"
                
                mensagem_vagas += "Para se candidatar a alguma dessas vagas, responda com 'CANDIDATAR' seguido do número da vaga."
                
                return mensagem_vagas
            except Exception as e:
                logger.error(f"Erro ao listar vagas: {e}")
                return "Tivemos um problema ao buscar vagas disponíveis. Por favor, tente novamente mais tarde."
        
        elif re.search(r"candidatar\s*(\d+)", texto, re.IGNORECASE):
            # Processar candidatura
            match = re.search(r"candidatar\s*(\d+)", texto, re.IGNORECASE)
            if match:
                numero_vaga = int(match.group(1))
                
                try:
                    vagas = listar_vagas()
                    
                    if 1 <= numero_vaga <= len(vagas):
                        vaga_escolhida = vagas[numero_vaga - 1]
                        
                        monday_id = candidato.get("monday_id")
                        if not monday_id:
                            return "Não foi possível processar sua candidatura. Por favor, entre em contato com nosso suporte."
                        
                        sucesso, mensagem = candidatar_vaga(monday_id, vaga_escolhida['id'])
                        
                        if sucesso:
                            return f"✅ Candidatura realizada com sucesso para a vaga de {vaga_escolhida['titulo']}! A empresa receberá seu currículo e entrará em contato caso haja interesse."
                        else:
                            return f"Não foi possível concluir sua candidatura: {mensagem}"
                    else:
                        return "Número de vaga inválido. Por favor, verifique o número e tente novamente."
                except Exception as e:
                    logger.error(f"Erro ao processar candidatura: {e}")
                    return "Tivemos um problema ao processar sua candidatura. Por favor, tente novamente mais tarde."
        
        # Atendimento premium para cliente pago
        return obter_resposta_chatgpt_com_contexto(texto, PERSONALIDADE_CANDIDATO, estagio_atual, "candidato")
    
    # Fallback para outros casos
    return obter_resposta_chatgpt(texto, PERSONALIDADE_CANDIDATO)

def processar_mensagem_empresa(chat_id, nome, mensagem, tipo_mensagem, texto_mensagem):
    """
    Processa mensagens de empresas
    """
    # Obter ou criar empresa
    empresa = obter_empresa(chat_id)
    if not empresa:
        # Novo contato de empresa, iniciar cadastro
        mensagem_boas_vindas = (
            f"Olá! Sou I.Atomos, assistente de recrutamento. Bem-vindo ao nosso sistema de publicação de vagas. "
            f"Para começar, precisamos fazer seu cadastro. Por favor, informe o CNPJ da sua empresa."
        )
        enviar_mensagem_whatsapp(chat_id, mensagem_boas_vindas)
        criar_empresa(chat_id, nome, estagio=1)
        return True
    
    estagio_atual = empresa.get("estagio", 1)
    
    # Processar conforme o estágio do cadastro da empresa
    if estagio_atual == 1:  # Aguardando CNPJ
        if tipo_mensagem == "text" and validate_cnpj(texto_mensagem):
            atualizar_empresa(chat_id, cnpj=texto_mensagem, estagio=2)
            resposta = "CNPJ recebido. Agora, por favor, informe a Razão Social da empresa."
        else:
            resposta = "Por favor, informe um CNPJ válido no formato XX.XXX.XXX/XXXX-XX ou apenas os números."
            
    elif estagio_atual == 2:  # Aguardando Razão Social
        if tipo_mensagem == "text":
            atualizar_empresa(chat_id, razao_social=texto_mensagem, estagio=3)
            resposta = "Razão Social registrada. Agora, informe o Nome Fantasia da empresa."
            
    elif estagio_atual == 3:  # Aguardando Nome Fantasia
        if tipo_mensagem == "text":
            atualizar_empresa(chat_id, nome_fantasia=texto_mensagem, estagio=4)
            resposta = "Nome Fantasia registrado. Agora, informe o email de contato da empresa."
            
    elif estagio_atual == 4:  # Aguardando Email
        if tipo_mensagem == "text" and "@" in texto_mensagem:
            atualizar_empresa(chat_id, email=texto_mensagem, estagio=5)
            resposta = "Email registrado. Por último, informe o endereço completo da empresa."
        else:
            resposta = "Por favor, informe um email válido."
            
    elif estagio_atual == 5:  # Aguardando Endereço
        if tipo_mensagem == "text":
            # Concluir cadastro
            atualizar_empresa(chat_id, endereco=texto_mensagem, estagio=6)
            
            # Enviar para o Monday
            empresa_dados = obter_empresa(chat_id)
            monday_id = cadastrar_empresa_monday(
                empresa_dados.get("nome_fantasia", nome),
                empresa_dados.get("razao_social", ""),
                empresa_dados.get("cnpj", ""),
                empresa_dados.get("email", ""),
                chat_id,  # Telefone/WhatsApp
                empresa_dados.get("endereco", "")
            )
            
            # Atualizar com o ID do Monday
            if monday_id:
                atualizar_empresa(chat_id, monday_id=monday_id)
                
                # Aprovar automaticamente para demonstração
                aprovar_empresa(monday_id)
                
                resposta = (
                    "✅ *Cadastro finalizado com sucesso!*\n\n"
                    "Sua empresa foi aprovada em nosso sistema. Agora você pode publicar vagas "
                    "e receberá candidatos qualificados. Você paga apenas R$80,00 por contratação efetivada.\n\n"
                    "Para publicar uma vaga, envie a palavra *VAGA* e seguiremos com o processo."
                )
            else:
                resposta = "Ocorreu um erro ao finalizar seu cadastro. Nossa equipe foi notificada e entrará em contato em breve."
    
    elif estagio_atual >= 6:  # Empresa já cadastrada
        # Processar comandos específicos
        if tipo_mensagem == "text":
            texto_maiusculo = texto_mensagem.upper()
            
            if texto_maiusculo == "VAGA" or "PUBLICAR VAGA" in texto_maiusculo:
                # Iniciar publicação de vaga
                atualizar_empresa(chat_id, estagio_vaga=1)
                resposta = "Vamos publicar uma nova vaga! Por favor, informe o título da vaga."
                
            elif "CANDIDATO" in texto_maiusculo or "CANDIDATOS" in texto_maiusculo:
                # Listar candidatos das vagas
                empresa_dados = obter_empresa(chat_id)
                monday_id = empresa_dados.get("monday_id")
                
                if not monday_id:
                    resposta = "Não foi possível recuperar seus dados. Por favor, entre em contato com o suporte."
                    return enviar_mensagem_whatsapp(chat_id, resposta)
                
                # Buscar vagas da empresa
                try:
                    vagas = listar_vagas_empresa(monday_id)
                    
                    if not vagas or len(vagas) == 0:
                        resposta = "Você ainda não publicou nenhuma vaga. Envie a palavra VAGA para publicar sua primeira vaga."
                        return enviar_mensagem_whatsapp(chat_id, resposta)
                    
                    # Enviar lista de vagas
                    mensagem_vagas = "📋 *Suas vagas publicadas:*\n\n"
                    for i, vaga in enumerate(vagas, 1):
                        mensagem_vagas += f"{i}. {vaga['titulo']} - {vaga.get('num_candidatos', 0)} candidatos\n"
                    mensagem_vagas += "\nResponda com o número da vaga para ver os candidatos."
                    
                    atualizar_empresa(chat_id, estagio=7)  # Aguardando selecionar vaga
                    resposta = mensagem_vagas
                except Exception as e:
                    logger.error(f"Erro ao listar vagas da empresa: {e}")
                    resposta = "Tivemos um problema ao buscar suas vagas. Por favor, tente novamente mais tarde."
            
            elif re.match(r"^\d+$", texto_mensagem) and estagio_atual == 7:
                # Selecionou uma vaga para ver candidatos
                try:
                    numero_vaga = int(texto_mensagem)
                    empresa_dados = obter_empresa(chat_id)
                    monday_id = empresa_dados.get("monday_id")
                    
                    vagas = listar_vagas_empresa(monday_id)
                    
                    if 1 <= numero_vaga <= len(vagas):
                        vaga_escolhida = vagas[numero_vaga - 1]
                        
                        # Buscar candidatos
                        candidatos = buscar_candidatos_vaga(vaga_escolhida['id'])
                        
                        if not candidatos or len(candidatos) == 0:
                            resposta = f"Ainda não há candidatos para a vaga '{vaga_escolhida['titulo']}'."
                            atualizar_empresa(chat_id, estagio=6)  # Voltar para estágio normal
                            return enviar_mensagem_whatsapp(chat_id, resposta)
                        
                        # Enviar lista de candidatos
                        mensagem_candidatos = f"👥 *Candidatos para a vaga '{vaga_escolhida['titulo']}':*\n\n"
                        
                        for i, candidato in enumerate(candidatos, 1):
                            detalhes = candidato.get('detalhes', {})
                            mensagem_candidatos += f"{i}. {detalhes.get('nome', 'Candidato')}\n"
                            mensagem_candidatos += f"   📧 {detalhes.get('email', 'Email não informado')}\n"
                            mensagem_candidatos += f"   📱 {detalhes.get('telefone', 'Telefone não informado')}\n"
                            mensagem_candidatos += f"   ⭐ Compatibilidade: {candidato.get('compatibilidade', 0)}%\n\n"
                        
                        mensagem_candidatos += "Para contratar um candidato, responda com 'CONTRATAR' seguido do número do candidato."
                        
                        atualizar_empresa(chat_id, estagio=8)  # Aguardando seleção de candidato
                        resposta = mensagem_candidatos
                    else:
                        resposta = "Número de vaga inválido. Por favor, verifique o número e tente novamente."
                        
                except Exception as e:
                    logger.error(f"Erro ao listar candidatos: {e}")
                    resposta = "Tivemos um problema ao buscar os candidatos. Por favor, tente novamente mais tarde."
            
            elif re.search(r"contratar\s*(\d+)", texto_maiusculo) and estagio_atual == 8:
                # Contratar candidato
                match = re.search(r"contratar\s*(\d+)", texto_maiusculo)
                if match:
                    numero_candidato = int(match.group(1))
                    
                    try:
                        empresa_dados = obter_empresa(chat_id)
                        monday_id = empresa_dados.get("monday_id")
                        
                        # Aqui precisaria recuperar a vaga e o candidato
                        # Como é uma demonstração, vamos simplificar
                        resposta = (
                            "✅ *Solicitação de contratação registrada!*\n\n"
                            "Para confirmar a contratação e registrar o pagamento da taxa de R$80,00, "
                            "realize um PIX para a chave abaixo:\n\n"
                            "🔑 *Chave PIX:* 65999526005\n\n"
                            "Após o pagamento, envie o comprovante aqui mesmo. "
                            "Confirmaremos a contratação assim que recebermos."
                        )
                        
                        atualizar_empresa(chat_id, estagio=9)  # Aguardando comprovante
                    except Exception as e:
                        logger.error(f"Erro ao processar contratação: {e}")
                        resposta = "Tivemos um problema ao processar a contratação. Por favor, tente novamente mais tarde."
                else:
                    resposta = "Comando inválido. Para contratar, envie 'CONTRATAR' seguido do número do candidato."
            
            else:
                # Verificar se está em processo de publicação de vaga
                estagio_vaga = empresa.get("estagio_vaga", 0)
                if estagio_vaga > 0:
                    # Processar publicação de vaga
                    resposta = processar_publicacao_vaga(chat_id, texto_mensagem)
                else:
                    # Resposta padrão para empresa cadastrada
                    resposta = obter_resposta_chatgpt_com_contexto(texto_mensagem, PERSONALIDADE_EMPRESA, estagio_atual, "empresa")
        elif tipo_mensagem == "image" and estagio_atual == 9:
            # Comprovante de contratação
            url_imagem = mensagem.get("url")
            
            # Em uma implementação real, processaria o comprovante
            # e registraria a contratação no Monday
            
            resposta = (
                "✅ *Comprovante recebido e contratação confirmada!*\n\n"
                "A contratação foi registrada com sucesso. O candidato será notificado "
                "e colocado em contato direto com vocês para os próximos passos.\n\n"
                "Agradecemos a confiança em nossos serviços."
            )
            
            atualizar_empresa(chat_id, estagio=6)  # Voltar ao estado normal
        else:
            # Resposta padrão para tipos de mensagem não tratados
            resposta = (
                "Não entendi sua solicitação. Você pode:\n"
                "- Enviar 'VAGA' para publicar uma nova vaga\n"
                "- Enviar 'CANDIDATOS' para ver candidatos de suas vagas"
            )
    else:
        # Fallback para estágios não tratados
        resposta = "Não entendi sua solicitação. Por favor, tente novamente."
    
    # Enviar resposta
    enviar_mensagem_whatsapp(chat_id, resposta)
    return True

def processar_publicacao_vaga(chat_id, texto_mensagem):
    """
    Processa a publicação de uma vaga por etapas
    """
    empresa = obter_empresa(chat_id)
    if not empresa:
        return "Erro ao recuperar dados da empresa. Por favor, entre em contato com o suporte."
    
    estagio_vaga = empresa.get("estagio_vaga", 0)
    dados_vaga = empresa.get("dados_vaga", {})
    
    if estagio_vaga == 1:  # Aguardando título
        dados_vaga["titulo"] = texto_mensagem
        atualizar_empresa(chat_id, dados_vaga=dados_vaga, estagio_vaga=2)
        return "Ótimo! Agora, descreva detalhadamente as responsabilidades e atividades da vaga."
    
    elif estagio_vaga == 2:  # Aguardando descrição
        dados_vaga["descricao"] = texto_mensagem
        atualizar_empresa(chat_id, dados_vaga=dados_vaga, estagio_vaga=3)
        return "Descrição registrada. Agora, informe os requisitos e qualificações necessárias para a vaga."
    
    elif estagio_vaga == 3:  # Aguardando requisitos
        dados_vaga["requisitos"] = texto_mensagem
        atualizar_empresa(chat_id, dados_vaga=dados_vaga, estagio_vaga=4)
        return "Requisitos registrados. Qual é o salário oferecido para esta vaga? (Informe apenas o valor numérico, ex: 3500)"
    
    elif estagio_vaga == 4:  # Aguardando salário
        try:
            salario = float(texto_mensagem.replace("R$", "").replace(".", "").replace(",", ".").strip())
            dados_vaga["salario"] = salario
            atualizar_empresa(chat_id, dados_vaga=dados_vaga, estagio_vaga=5)
            
            # Opções de tipo de contrato
            mensagem_tipos = (
                "Salário registrado. Qual o tipo de contrato?\n\n"
                "1. CLT\n"
                "2. PJ\n"
                "3. Temporário\n"
                "4. Estágio\n\n"
                "Responda com o número da opção."
            )
            return mensagem_tipos
        except:
            return "Por favor, informe apenas o valor numérico (ex: 3500)."
    
    elif estagio_vaga == 5:  # Aguardando tipo de contrato
        tipo_contrato = ""
        if texto_mensagem == "1" or "clt" in texto_mensagem.lower():
            tipo_contrato = "CLT"
        elif texto_mensagem == "2" or "pj" in texto_mensagem.lower():
            tipo_contrato = "PJ"
        elif texto_mensagem == "3" or "tempor" in texto_mensagem.lower():
            tipo_contrato = "Temporário"
        elif texto_mensagem == "4" or "est" in texto_mensagem.lower():
            tipo_contrato = "Estágio"
        
        if tipo_contrato:
            dados_vaga["tipo_contrato"] = tipo_contrato
            atualizar_empresa(chat_id, dados_vaga=dados_vaga, estagio_vaga=6)
            return "Tipo de contrato registrado. Por último, informe o local de trabalho (cidade/estado ou remoto)."
        else:
            return "Por favor, escolha uma das opções válidas (1 a 4)."
    
    elif estagio_vaga == 6:  # Aguardando local
        dados_vaga["local"] = texto_mensagem
        atualizar_empresa(chat_id, dados_vaga=dados_vaga, estagio_vaga=7)
        
        # Resumo da vaga para confirmação
        resumo = (
            "📋 *Resumo da vaga:*\n\n"
            f"*Título:* {dados_vaga.get('titulo')}\n"
            f"*Descrição:* {dados_vaga.get('descricao')}\n"
            f"*Requisitos:* {dados_vaga.get('requisitos')}\n"
            f"*Salário:* R$ {dados_vaga.get('salario', 0):.2f}\n"
            f"*Tipo de Contrato:* {dados_vaga.get('tipo_contrato')}\n"
            f"*Local:* {dados_vaga.get('local')}\n\n"
            "Para confirmar e publicar esta vaga, responda SIM.\n"
            "Para cancelar, responda NÃO."
        )
        return resumo
    
    elif estagio_vaga == 7:  # Aguardando confirmação
        if texto_mensagem.upper() == "SIM" or "sim" in texto_mensagem.lower():
            # Publicar a vaga no Monday
            empresa_dados = obter_empresa(chat_id)
            monday_id = empresa_dados.get("monday_id")
            
            if not monday_id:
                return "Erro ao recuperar dados da empresa. Por favor, entre em contato com o suporte."
            
            # Publicar vaga
            try:
                vaga_id = publicar_vaga(
                    monday_id,
                    dados_vaga.get("titulo", ""),
                    dados_vaga.get("descricao", ""),
                    dados_vaga.get("requisitos", ""),
                    dados_vaga.get("salario", 0),
                    dados_vaga.get("tipo_contrato", "CLT"),
                    dados_vaga.get("local", "")
                )
                
                if vaga_id:
                    # Resetar estágio
                    atualizar_empresa(chat_id, estagio_vaga=0, dados_vaga={})
                    
                    return (
                        "✅ *Vaga publicada com sucesso!*\n\n"
                        "Sua vaga já está disponível para candidatos. Você receberá notificações à medida que candidatos compatíveis se candidatarem.\n\n"
                        "Lembre-se: você só paga R$80,00 por contratação efetivada, via PIX."
                    )
                else:
                    return "Ocorreu um erro ao publicar sua vaga. Nossa equipe foi notificada e entrará em contato em breve."
            except Exception as e:
                logger.error(f"Erro ao publicar vaga: {e}")
                return "Tivemos um problema ao publicar sua vaga. Por favor, tente novamente mais tarde."
        
        elif texto_mensagem.upper() == "NÃO" or "nao" in texto_mensagem.lower() or "não" in texto_mensagem.lower():
            atualizar_empresa(chat_id, estagio_vaga=0, dados_vaga={})
            return "Publicação de vaga cancelada. Você pode iniciar novamente enviando a palavra VAGA."
        else:
            return "Por favor, responda SIM para confirmar ou NÃO para cancelar."
    
    # Fallback para outros estágios
    return "Ocorreu um erro no processo de publicação. Por favor, inicie novamente enviando a palavra VAGA."

def processar_pagamento_candidato(chat_id, url_comprovante):
    """
    Processa o pagamento de um candidato
    """
    candidato = obter_candidato(chat_id)
    if not candidato:
        return False, "Candidato não encontrado"
    
    monday_id = candidato.get("monday_id")
    if not monday_id:
        return False, "ID do Monday não encontrado"
    
    # Registrar pagamento (valor fixo R$10,00)
    success = registrar_pagamento_candidato(
        monday_id, 
        10.00,  # Novo valor fixo
        url_comprovante, 
        f"comprovante_{chat_id}.jpg"
    )
    
    if success:
        # Atualizar status do candidato
        atualizar_candidato(
            chat_id, 
            estagio=5,  # Avançar para "Cadastro Ativado"
            comprovante_enviado=1,
            ativado=1
        )
        
        return True, "Pagamento confirmado. Seu cadastro está ativo!"
    else:
        return False, "Erro ao processar pagamento"


# === ROTAS ===

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        user = data.get("user", {})
        chat_id = user.get("id", "").replace("@c.us", "")
        nome = user.get("name", "Desconhecido")
        mensagem = data.get("message", {})
        tipo_mensagem = mensagem.get("type")
        texto_mensagem = mensagem.get("text", "") if tipo_mensagem == "text" else ""
        
        logger.info(f"📩 Mensagem recebida de {nome} ({chat_id}): Tipo={tipo_mensagem}")
        
        # Verificar se é um candidato ou empresa
        tipo_usuario = verificar_tipo_usuario(chat_id)
        
        if tipo_usuario == "empresa":
            # Processar mensagem de empresa
            resultado = processar_mensagem_empresa(chat_id, nome, mensagem, tipo_mensagem, texto_mensagem)
        else:
            # Processar mensagem de candidato (fluxo padrão atual)
            resultado = processar_mensagem_candidato(chat_id, nome, mensagem, tipo_mensagem, texto_mensagem)
        
        return jsonify({"status": "ok"})
    
    except Exception as e:
        logger.error(f"❌ Erro no webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# === SETUP DAS VIEWS ADMIN ===

class CandidatoView(ModelView):
    column_list = ('nome', 'estagio', 'data_primeiro_contato', 'curriculo_enviado', 'ativado')
    column_searchable_list = ('nome', 'chat_id')
    column_filters = ('estagio', 'curriculo_enviado', 'ativado')
    
    def _estagio_formatado(view, context, model, name):
        estagios = {
            1: 'Primeiro Contato',
            2: 'Enviou Currículo',
            3: 'Explicação do Serviço',
            4: 'Processo de Pagamento',
            5: 'Cadastro Ativado'
        }
        return estagios.get(model.estagio, f"Estágio {model.estagio}")
    
    column_formatters = {
        'estagio': _estagio_formatado
    }

class MensagemView(ModelView):
    column_list = ('chat_id', 'data', 'tipo', 'mensagem')
    column_searchable_list = ('mensagem',)
    column_filters = ('tipo',)

class EmpresaView(ModelView):
    column_list = ('nome', 'cnpj', 'estagio', 'data_cadastro')
    column_searchable_list = ('nome', 'cnpj', 'chat_id')
    column_filters = ('estagio',)
    
    def _estagio_formatado(view, context, model, name):
        estagios = {
            1: 'Aguardando CNPJ',
            2: 'Aguardando Razão Social',
            3: 'Aguardando Nome Fantasia',
            4: 'Aguardando Email',
            5: 'Aguardando Endereço',
            6: 'Cadastro Completo',
            7: 'Selecionando Vaga',
            8: 'Selecionando Candidato',
            9: 'Aguardando Comprovante'
        }
        return estagios.get(model.estagio, f"Estágio {model.estagio}")
    
    column_formatters = {
        'estagio': _estagio_formatado
    }

# Dashboard com estatísticas
class DashboardView(BaseView):
    @expose('/')
    def index(self):
        stats = self._calcular_estatisticas()
        return self.render('admin/dashboard.html', stats=stats)
    
    def _calcular_estatisticas(self):
        total_candidatos = Candidato.query.count()
        cadastros_ativos = Candidato.query.filter_by(ativado=1).count()
        enviaram_curriculo = Candidato.query.filter_by(curriculo_enviado=1).count()
        total_empresas = Empresa.query.count()
        
        # Taxa de conversão
        taxa_conversao = (cadastros_ativos / enviaram_curriculo * 100) if enviaram_curriculo > 0 else 0
        
        # Estágios atuais
        estagios = {}
        for i in range(1, 6):
            estagios[i] = Candidato.query.filter_by(estagio=i).count()
        
        # Novos cadastros hoje
        hoje = datetime.now().date().isoformat()
        novos_hoje = Candidato.query.filter(Candidato.data_primeiro_contato.startswith(hoje)).count()
        
        # Ativações hoje
        ativacoes_hoje = 0
        candidatos_ativos = Candidato.query.filter_by(ativado=1).all()
        for c in candidatos_ativos:
            try:
                data_ativacao = datetime.fromisoformat(c.data_ultimo_contato).date()
                if data_ativacao == datetime.now().date():
                    ativacoes_hoje += 1
            except:
                pass
        
        return {
            'total_candidatos': total_candidatos,
            'cadastros_ativos': cadastros_ativos,
            'enviaram_curriculo': enviaram_curriculo,
            'total_empresas': total_empresas,
            'taxa_conversao': round(taxa_conversao, 2),
            'estagios': estagios,
            'novos_hoje': novos_hoje,
            'ativacoes_hoje': ativacoes_hoje
        }

# Inicializar Admin
admin = Admin(app, name='Mais Emprego', template_mode='bootstrap3')

# Adicionar views
admin.add_view(CandidatoView(Candidato, db.session, name='Candidatos'))
admin.add_view(EmpresaView(Empresa, db.session, name='Empresas'))
admin.add_view(MensagemView(Mensagem, db.session, name='Mensagens'))
admin.add_view(DashboardView(name='Dashboard'))

# === INICIALIZAÇÃO DA APLICAÇÃO ===

# Inicialização do banco de dados
def setup_database():
    with app.app_context():
        db.create_all()
        logger.info("🚀 Banco de dados inicializado")

# Iniciar aplicação
if __name__ == "__main__":
    setup_database()  # Inicializa o banco de dados antes de iniciar o app
    app.run(debug=True, host="0.0.0.0", port=5000)



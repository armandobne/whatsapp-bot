# monday_integration.py
import requests
import json
import logging
import os
import tempfile

# IDs dos boards do Monday
CANDIDATOS_BOARD_ID = "8812301302"
EMPRESAS_BOARD_ID = "8812301317"
VAGAS_BOARD_ID = "8812301333"
CANDIDATURAS_BOARD_ID = "8812301347"
CONTRATACOES_BOARD_ID = "8812301363"
MONDAY_API_URL = "https://api.monday.com/v2"

# Chave de API (será obtida do app.py)
MONDAY_API_KEY = ""

# Logger
logger = logging.getLogger("monday")

def set_api_key(api_key):
    """Define a chave de API para uso nas funções"""
    global MONDAY_API_KEY
    MONDAY_API_KEY = api_key

def cadastrar_candidato_monday(nome, email, telefone, endereco, texto_cv, url_cv, nome_arquivo):
    """
    Cadastra um candidato no Monday.com
    Retorna o ID do item criado ou None em caso de erro
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    # Preparar os valores das colunas
    column_values = {
        "email": {"email": email, "text": email},
        "phone": {"phone": telefone, "countryShortName": "BR"},
        "text": endereco,
        "long_text": texto_cv
    }

    # Converter para JSON
    column_values_str = json.dumps(column_values)

    # Query GraphQL para criar o item
    query = '''
    mutation ($boardId: ID!, $itemName: String!, $columnValues: JSON!) {
        create_item (
            board_id: $boardId,
            item_name: $itemName,
            column_values: $columnValues
        ) {
            id
        }
    }
    '''

    variables = {
        "boardId": CANDIDATOS_BOARD_ID,
        "itemName": nome,
        "columnValues": column_values_str
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result:
            logger.error(f"Erro ao cadastrar candidato no Monday: {result['errors']}")
            return None
            
        item_id = result.get("data", {}).get("create_item", {}).get("id")
        
        if item_id:
            # Anexar o currículo
            enviar_arquivo_para_monday(
                item_id=item_id,
                file_url=url_cv,
                nome_arquivo=nome_arquivo,
                board_id=CANDIDATOS_BOARD_ID,
                coluna_id="files"
            )
            
            logger.info(f"Candidato cadastrado com sucesso: ID {item_id}")
            return item_id
        else:
            logger.error("ID do item não encontrado na resposta do Monday")
            return None
    
    except Exception as e:
        logger.error(f"Exceção ao cadastrar candidato: {e}")
        return None

def registrar_pagamento_candidato(monday_id, valor, url_comprovante, nome_comprovante):
    """
    Registra o pagamento de um candidato no Monday.com
    Retorna True se bem-sucedido, False caso contrário
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    # Atualizar o status para "Ativa" e registrar o valor
    column_values = {
        "status": {"label": "Ativa"},
        "numbers": valor,
        "date4": {"date": ""}  # Data atual
    }

    column_values_str = json.dumps(column_values)

    query = '''
    mutation ($itemId: ID!, $boardId: ID!, $columnValues: JSON!) {
        change_multiple_column_values (
            item_id: $itemId,
            board_id: $boardId,
            column_values: $columnValues
        ) {
            id
        }
    }
    '''

    variables = {
        "itemId": monday_id,
        "boardId": CANDIDATOS_BOARD_ID,
        "columnValues": column_values_str
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result:
            logger.error(f"Erro ao registrar pagamento: {result['errors']}")
            return False
            
        # Anexar o comprovante
        if url_comprovante:
            enviar_arquivo_para_monday(
                item_id=monday_id,
                file_url=url_comprovante,
                nome_arquivo=nome_comprovante,
                board_id=CANDIDATOS_BOARD_ID,
                coluna_id="files1"  # Coluna para comprovantes
            )
            
        logger.info(f"Pagamento registrado para o candidato ID {monday_id}")
        return True
    
    except Exception as e:
        logger.error(f"Exceção ao registrar pagamento: {e}")
        return False

def verificar_status_assinatura(monday_id):
    """
    Verifica o status da assinatura de um candidato
    Retorna um dicionário com 'status' (str) e 'expira_em' (int, dias)
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    query = '''
    query ($itemId: ID!, $boardId: ID!) {
        items(ids: [$itemId], board_id: $boardId) {
            column_values {
                id
                text
                value
            }
        }
    }
    '''

    variables = {
        "itemId": monday_id,
        "boardId": CANDIDATOS_BOARD_ID
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result:
            logger.error(f"Erro ao verificar status: {result['errors']}")
            return {"status": "Erro", "expira_em": 0}
            
        column_values = result.get("data", {}).get("items", [{}])[0].get("column_values", [])
        
        status = "Pendente"
        expira_em = 0
        
        for col in column_values:
            if col["id"] == "status":
                status = col["text"]
            elif col["id"] == "date":
                # Cálculo dos dias até expirar (simplificado)
                # Em uma implementação completa, você calcularia a diferença de datas
                expira_em = 30  # Placeholder
                
        return {"status": status, "expira_em": expira_em}
    
    except Exception as e:
        logger.error(f"Exceção ao verificar status: {e}")
        return {"status": "Erro", "expira_em": 0}

def cadastrar_empresa_monday(nome, razao_social, cnpj, email, telefone, endereco):
    """
    Cadastra uma empresa no Monday.com
    Retorna o ID do item criado ou None em caso de erro
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    # Preparar os valores das colunas
    column_values = {
        "text": cnpj,
        "text1": razao_social,
        "email": {"email": email, "text": email},
        "phone": {"phone": telefone, "countryShortName": "BR"},
        "long_text": endereco,
        "status": {"label": "Pendente"},
        "date4": {"date": ""}  # Data atual
    }

    # Converter para JSON
    column_values_str = json.dumps(column_values)

    # Query GraphQL para criar o item
    query = '''
    mutation ($boardId: ID!, $itemName: String!, $columnValues: JSON!) {
        create_item (
            board_id: $boardId,
            item_name: $itemName,
            column_values: $columnValues
        ) {
            id
        }
    }
    '''

    variables = {
        "boardId": EMPRESAS_BOARD_ID,
        "itemName": nome,
        "columnValues": column_values_str
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result:
            logger.error(f"Erro ao cadastrar empresa no Monday: {result['errors']}")
            return None
            
        item_id = result.get("data", {}).get("create_item", {}).get("id")
        
        if item_id:
            logger.info(f"Empresa cadastrada com sucesso: ID {item_id}")
            return item_id
        else:
            logger.error("ID do item não encontrado na resposta do Monday")
            return None
    
    except Exception as e:
        logger.error(f"Exceção ao cadastrar empresa: {e}")
        return None

def aprovar_empresa(monday_id):
    """
    Aprova uma empresa no Monday.com
    Retorna True se bem-sucedido, False caso contrário
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    # Atualizar o status para "Aprovada"
    column_values = {
        "status": {"label": "Aprovada"}
    }

    column_values_str = json.dumps(column_values)

    query = '''
    mutation ($itemId: ID!, $boardId: ID!, $columnValues: JSON!) {
        change_multiple_column_values (
            item_id: $itemId,
            board_id: $boardId,
            column_values: $columnValues
        ) {
            id
        }
    }
    '''

    variables = {
        "itemId": monday_id,
        "boardId": EMPRESAS_BOARD_ID,
        "columnValues": column_values_str
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result:
            logger.error(f"Erro ao aprovar empresa: {result['errors']}")
            return False
            
        logger.info(f"Empresa ID {monday_id} aprovada com sucesso")
        return True
    
    except Exception as e:
        logger.error(f"Exceção ao aprovar empresa: {e}")
        return False

def publicar_vaga(empresa_id, titulo, descricao, requisitos, salario, tipo_contrato, local):
    """
    Publica uma vaga de emprego no Monday.com
    Retorna o ID da vaga criada ou None em caso de erro
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    # Preparar os valores das colunas
    column_values = {
        "connect_boards": {"linkedPulseIds": [{"linkedPulseId": empresa_id}]},
        "long_text": descricao,
        "long_text9": requisitos,
        "numbers": salario,
        "dropdown": {"labels": [tipo_contrato]},
        "text5": local,
        "date4": {"date": ""},  # Data atual
        "status": {"label": "Aberta"}
    }

    # Converter para JSON
    column_values_str = json.dumps(column_values)

    # Query GraphQL para criar o item
    query = '''
    mutation ($boardId: ID!, $itemName: String!, $columnValues: JSON!) {
        create_item (
            board_id: $boardId,
            item_name: $itemName,
            column_values: $columnValues
        ) {
            id
        }
    }
    '''

    variables = {
        "boardId": VAGAS_BOARD_ID,
        "itemName": titulo,
        "columnValues": column_values_str
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result:
            logger.error(f"Erro ao publicar vaga no Monday: {result['errors']}")
            return None
            
        item_id = result.get("data", {}).get("create_item", {}).get("id")
        
        if item_id:
            logger.info(f"Vaga publicada com sucesso: ID {item_id}")
            return item_id
        else:
            logger.error("ID do item não encontrado na resposta do Monday")
            return None
    
    except Exception as e:
        logger.error(f"Exceção ao publicar vaga: {e}")
        return None

def listar_vagas(limite=10):
    """
    Lista as vagas disponíveis no Monday.com
    Retorna uma lista de dicionários com os dados das vagas
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    query = '''
    query ($boardId: ID!) {
        boards(ids: [$boardId]) {
            items {
                id
                name
                column_values {
                    id
                    text
                    value
                }
            }
        }
    }
    '''

    variables = {
        "boardId": VAGAS_BOARD_ID
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result:
            logger.error(f"Erro ao listar vagas: {result['errors']}")
            return []
            
        items = result.get("data", {}).get("boards", [{}])[0].get("items", [])
        
        vagas = []
        for item in items:
            vaga = {
                "id": item["id"],
                "titulo": item["name"],
                "empresa": {"id": "", "nome": ""},
                "descricao": "",
                "requisitos": "",
                "salario": 0,
                "tipo_contrato": "",
                "local": "",
                "status": ""
            }
            
            for col in item["column_values"]:
                if col["id"] == "connect_boards" and col["value"]:
                    # Extrair ID da empresa
                    try:
                        empresa_data = json.loads(col["value"])
                        empresa_id = empresa_data["linkedPulseIds"][0]["linkedPulseId"]
                        vaga["empresa"]["id"] = empresa_id
                        # Idealmente, você buscaria o nome da empresa em outra chamada
                        vaga["empresa"]["nome"] = "Empresa"
                    except:
                        pass
                elif col["id"] == "long_text":
                    vaga["descricao"] = col["text"]
                elif col["id"] == "long_text9":
                    vaga["requisitos"] = col["text"]
                elif col["id"] == "numbers" and col["text"]:
                    try:
                        vaga["salario"] = float(col["text"])
                    except:
                        pass
                elif col["id"] == "dropdown":
                    vaga["tipo_contrato"] = col["text"]
                elif col["id"] == "text5":
                    vaga["local"] = col["text"]
                elif col["id"] == "status":
                    vaga["status"] = col["text"]
            
            # Só adicionar vagas ativas
            if vaga["status"] == "Aberta":
                vagas.append(vaga)
                
            # Limitar a quantidade de vagas
            if len(vagas) >= limite:
                break
                
        return vagas
    
    except Exception as e:
        logger.error(f"Exceção ao listar vagas: {e}")
        return []

def listar_vagas_empresa(empresa_id, limite=10):
    """
    Lista as vagas de uma empresa específica
    Retorna uma lista de dicionários com os dados das vagas
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    query = '''
    query ($boardId: ID!, $empresaId: [String]) {
        items_by_column_values(board_id: $boardId, column_id: "connect_boards", column_values: $empresaId) {
            id
            name
            column_values {
                id
                text
                value
            }
        }
    }
    '''

    variables = {
        "boardId": VAGAS_BOARD_ID,
        "empresaId": [empresa_id]
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result:
            logger.error(f"Erro ao listar vagas da empresa: {result['errors']}")
            return []
            
        items = result.get("data", {}).get("items_by_column_values", [])
        
        vagas = []
        for item in items:
            vaga = {
                "id": item["id"],
                "titulo": item["name"],
                "descricao": "",
                "requisitos": "",
                "salario": 0,
                "tipo_contrato": "",
                "local": "",
                "status": "",
                "num_candidatos": 0  # Número de candidatos será calculado em outra chamada
            }
            
            for col in item["column_values"]:
                if col["id"] == "long_text":
                    vaga["descricao"] = col["text"]
                elif col["id"] == "long_text9":
                    vaga["requisitos"] = col["text"]
                elif col["id"] == "numbers" and col["text"]:
                    try:
                        vaga["salario"] = float(col["text"])
                    except:
                        pass
                elif col["id"] == "dropdown":
                    vaga["tipo_contrato"] = col["text"]
                elif col["id"] == "text5":
                    vaga["local"] = col["text"]
                elif col["id"] == "status":
                    vaga["status"] = col["text"]
            
            # Contar candidatos (simplificado)
            vaga["num_candidatos"] = contar_candidatos_vaga(item["id"])
            
            vagas.append(vaga)
                
            # Limitar a quantidade de vagas
            if len(vagas) >= limite:
                break
                
        return vagas
    
    except Exception as e:
        logger.error(f"Exceção ao listar vagas da empresa: {e}")
        return []

def contar_candidatos_vaga(vaga_id):
    """
    Conta o número de candidatos para uma vaga
    Retorna o número de candidatos
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    query = '''
    query ($boardId: ID!, $vagaId: [String]) {
        items_by_column_values(board_id: $boardId, column_id: "connect_boards5", column_values: $vagaId) {
            id
        }
    }
    '''

    variables = {
        "boardId": CANDIDATURAS_BOARD_ID,
        "vagaId": [vaga_id]
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result:
            logger.error(f"Erro ao contar candidatos: {result['errors']}")
            return 0
            
        items = result.get("data", {}).get("items_by_column_values", [])
        return len(items)
    
    except Exception as e:
        logger.error(f"Exceção ao contar candidatos: {e}")
        return 0

def candidatar_vaga(candidato_id, vaga_id):
    """
    Registra a candidatura de um candidato a uma vaga
    Retorna (True, mensagem) se bem-sucedido, (False, erro) caso contrário
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    # Verificar se já existe candidatura
    query_check = '''
    query ($boardId: ID!, $candidatoId: [String], $vagaId: [String]) {
        items_by_multiple_column_values(board_id: $boardId, column_id: ["connect_boards", "connect_boards5"], column_values: [$candidatoId, $vagaId]) {
            id
        }
    }
    '''

    variables_check = {
        "boardId": CANDIDATURAS_BOARD_ID,
        "candidatoId": [candidato_id],
        "vagaId": [vaga_id]
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query_check, "variables": variables_check}
        )
        result = response.json()
        
        if "errors" in result:
            return False, "Erro ao verificar candidatura existente"
            
        items = result.get("data", {}).get("items_by_multiple_column_values", [])
        if items:
            return False, "Você já se candidatou a esta vaga"
    
    except Exception as e:
        return False, f"Erro ao verificar candidatura: {str(e)}"

    # Preparar os valores das colunas
    column_values = {
        "connect_boards": {"linkedPulseIds": [{"linkedPulseId": candidato_id}]},
        "connect_boards5": {"linkedPulseIds": [{"linkedPulseId": vaga_id}]},
        "date4": {"date": ""},  # Data atual
        "status": {"label": "Pendente"}
    }

    # Converter para JSON
    column_values_str = json.dumps(column_values)

    # Query GraphQL para criar o item
    query = '''
    mutation ($boardId: ID!, $itemName: String!, $columnValues: JSON!) {
        create_item (
            board_id: $boardId,
            item_name: $itemName,
            column_values: $columnValues
        ) {
            id
        }
    }
    '''

    variables = {
        "boardId": CANDIDATURAS_BOARD_ID,
        "itemName": f"Candidatura-{candidato_id}-{vaga_id}",
        "columnValues": column_values_str
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result:
            logger.error(f"Erro ao candidatar para vaga: {result['errors']}")
            return False, "Erro ao registrar candidatura"
            
        item_id = result.get("data", {}).get("create_item", {}).get("id")
        
        if item_id:
            logger.info(f"Candidatura registrada com sucesso: ID {item_id}")
            return True, "Candidatura registrada com sucesso"
        else:
            logger.error("ID do item não encontrado na resposta do Monday")
            return False, "Erro ao processar candidatura"
    
    except Exception as e:
        logger.error(f"Exceção ao candidatar para vaga: {e}")
        return False, f"Erro: {str(e)}"

def buscar_candidatos_vaga(vaga_id, limite=10):
    """
    Busca os candidatos para uma vaga específica
    Retorna uma lista de dicionários com os dados dos candidatos
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    query = '''
    query ($boardId: ID!, $vagaId: [String]) {
        items_by_column_values(board_id: $boardId, column_id: "connect_boards5", column_values: $vagaId) {
            id
            name
            column_values {
                id
                text
                value
            }
        }
    }
    '''

    variables = {
        "boardId": CANDIDATURAS_BOARD_ID,
        "vagaId": [vaga_id]
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result:
            logger.error(f"Erro ao buscar candidatos: {result['errors']}")
            return []
            
        items = result.get("data", {}).get("items_by_column_values", [])
        
        candidatos = []
        for item in items:
            candidato = {
                "id": item["id"],
                "candidato_id": "",
                "detalhes": {},
                "status": "",
                "data_candidatura": "",
                "compatibilidade": 0  # Vamos simular um valor de compatibilidade
            }
            
            for col in item["column_values"]:
                if col["id"] == "connect_boards" and col["value"]:
                    # Extrair ID do candidato
                    try:
                        candidato_data = json.loads(col["value"])
                        candidato_id = candidato_data["linkedPulseIds"][0]["linkedPulseId"]
                        candidato["candidato_id"] = candidato_id
                        # Buscar detalhes do candidato
                        candidato["detalhes"] = obter_detalhes_candidato(candidato_id)
                    except:
                        pass
                elif col["id"] == "status":
                    candidato["status"] = col["text"]
                elif col["id"] == "date4":
                    candidato["data_candidatura"] = col["text"]
            
            # Simular um valor de compatibilidade
            import random
            candidato["compatibilidade"] = random.randint(70, 99)
            
            candidatos.append(candidato)
                
            # Limitar a quantidade de candidatos
            if len(candidatos) >= limite:
                break
                
        # Ordenar por compatibilidade
        candidatos.sort(key=lambda x: x["compatibilidade"], reverse=True)
                
        return candidatos
    
    except Exception as e:
        logger.error(f"Exceção ao buscar candidatos: {e}")
        return []

def obter_detalhes_candidato(candidato_id):
    """
    Obtém os detalhes de um candidato
    Retorna um dicionário com os dados do candidato
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    query = '''
    query ($boardId: ID!, $itemId: [ID!]) {
        items(ids: $itemId, board_id: $boardId) {
            id
            name
            column_values {
                id
                text
                value
            }
        }
    }
    '''

    variables = {
        "boardId": CANDIDATOS_BOARD_ID,
        "itemId": [candidato_id]
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result or not result.get("data", {}).get("items"):
            return {"nome": "Candidato não encontrado"}
            
        item = result.get("data", {}).get("items", [{}])[0]
        
        detalhes = {
            "nome": item["name"],
            "email": "",
            "telefone": "",
            "endereco": "",
            "status_assinatura": "Pendente"
        }
        
        for col in item["column_values"]:
            if col["id"] == "email":
                detalhes["email"] = col["text"]
            elif col["id"] == "phone":
                detalhes["telefone"] = col["text"]
            elif col["id"] == "text":
                detalhes["endereco"] = col["text"]
            elif col["id"] == "status":
                detalhes["status_assinatura"] = col["text"]
                
        return detalhes
    
    except Exception as e:
        logger.error(f"Exceção ao obter detalhes do candidato: {e}")
        return {"nome": "Erro ao buscar candidato"}

def registrar_contratacao(empresa_id, candidato_id, vaga_id):
    """
    Registra a contratação de um candidato
    Retorna (True, id) se bem-sucedido, (False, erro) caso contrário
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    # Preparar os valores das colunas
    column_values = {
        "connect_boards": {"linkedPulseIds": [{"linkedPulseId": empresa_id}]},
        "connect_boards8": {"linkedPulseIds": [{"linkedPulseId": candidato_id}]},
        "connect_boards5": {"linkedPulseIds": [{"linkedPulseId": vaga_id}]},
        "date4": {"date": ""},  # Data atual
        "status": {"label": "Pendente"},
        "numbers": 80.00  # Valor fixo R$80,00
    }

    # Converter para JSON
    column_values_str = json.dumps(column_values)

    # Query GraphQL para criar o item
    query =

def registrar_contratacao(empresa_id, candidato_id, vaga_id):
    """
    Registra a contratação de um candidato
    Retorna (True, id) se bem-sucedido, (False, erro) caso contrário
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    # Preparar os valores das colunas
    column_values = {
        "connect_boards": {"linkedPulseIds": [{"linkedPulseId": empresa_id}]},
        "connect_boards8": {"linkedPulseIds": [{"linkedPulseId": candidato_id}]},
        "connect_boards5": {"linkedPulseIds": [{"linkedPulseId": vaga_id}]},
        "date4": {"date": ""},  # Data atual
        "status": {"label": "Pendente"},
        "numbers": 80.00  # Valor fixo R$80,00
    }

    # Converter para JSON
    column_values_str = json.dumps(column_values)

    # Query GraphQL para criar o item
    query = '''
    mutation ($boardId: ID!, $itemName: String!, $columnValues: JSON!) {
        create_item (
            board_id: $boardId,
            item_name: $itemName,
            column_values: $columnValues
        ) {
            id
        }
    }
    '''

    variables = {
        "boardId": CONTRATACOES_BOARD_ID,
        "itemName": f"Contratação-{empresa_id}-{candidato_id}",
        "columnValues": column_values_str
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result:
            logger.error(f"Erro ao registrar contratação: {result['errors']}")
            return False, "Erro ao registrar contratação"
            
        item_id = result.get("data", {}).get("create_item", {}).get("id")
        
        if item_id:
            logger.info(f"Contratação registrada com sucesso: ID {item_id}")
            
            # Atualizar status da vaga para "Em processo"
            atualizar_status_vaga(vaga_id, "Em processo")
            
            return True, item_id
        else:
            logger.error("ID do item não encontrado na resposta do Monday")
            return False, "Erro ao processar contratação"
    
    except Exception as e:
        logger.error(f"Exceção ao registrar contratação: {e}")
        return False, f"Erro: {str(e)}"

def registrar_pagamento_contratacao(contratacao_id, url_comprovante, nome_comprovante):
    """
    Registra o pagamento de uma contratação
    Retorna True se bem-sucedido, False caso contrário
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    # Atualizar o status para "Pago"
    column_values = {
        "status": {"label": "Pago"},
        "date9": {"date": ""}  # Data atual do pagamento
    }

    column_values_str = json.dumps(column_values)

    query = '''
    mutation ($itemId: ID!, $boardId: ID!, $columnValues: JSON!) {
        change_multiple_column_values (
            item_id: $itemId,
            board_id: $boardId,
            column_values: $columnValues
        ) {
            id
        }
    }
    '''

    variables = {
        "itemId": contratacao_id,
        "boardId": CONTRATACOES_BOARD_ID,
        "columnValues": column_values_str
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result:
            logger.error(f"Erro ao registrar pagamento da contratação: {result['errors']}")
            return False
            
        # Anexar o comprovante
        if url_comprovante:
            enviar_arquivo_para_monday(
                item_id=contratacao_id,
                file_url=url_comprovante,
                nome_arquivo=nome_comprovante,
                board_id=CONTRATACOES_BOARD_ID,
                coluna_id="files"  # Coluna para comprovantes
            )
            
        logger.info(f"Pagamento da contratação ID {contratacao_id} registrado com sucesso")
        
        # Buscar a vaga relacionada e atualizá-la para "Preenchida"
        vaga_id = buscar_vaga_da_contratacao(contratacao_id)
        if vaga_id:
            atualizar_status_vaga(vaga_id, "Preenchida")
        
        return True
    
    except Exception as e:
        logger.error(f"Exceção ao registrar pagamento da contratação: {e}")
        return False

def buscar_vaga_da_contratacao(contratacao_id):
    """
    Busca o ID da vaga associada a uma contratação
    Retorna o ID da vaga ou None em caso de erro
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    query = '''
    query ($boardId: ID!, $itemId: [ID!]) {
        items(ids: $itemId, board_id: $boardId) {
            column_values {
                id
                text
                value
            }
        }
    }
    '''

    variables = {
        "boardId": CONTRATACOES_BOARD_ID,
        "itemId": [contratacao_id]
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result:
            logger.error(f"Erro ao buscar vaga da contratação: {result['errors']}")
            return None
            
        column_values = result.get("data", {}).get("items", [{}])[0].get("column_values", [])
        
        for col in column_values:
            if col["id"] == "connect_boards5" and col["value"]:
                try:
                    vaga_data = json.loads(col["value"])
                    vaga_id = vaga_data["linkedPulseIds"][0]["linkedPulseId"]
                    return vaga_id
                except:
                    pass
                    
        return None
    
    except Exception as e:
        logger.error(f"Exceção ao buscar vaga da contratação: {e}")
        return None

def atualizar_status_vaga(vaga_id, status):
    """
    Atualiza o status de uma vaga
    Retorna True se bem-sucedido, False caso contrário
    """
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    # Atualizar o status da vaga
    column_values = {
        "status": {"label": status}
    }

    column_values_str = json.dumps(column_values)

    query = '''
    mutation ($itemId: ID!, $boardId: ID!, $columnValues: JSON!) {
        change_multiple_column_values (
            item_id: $itemId,
            board_id: $boardId,
            column_values: $columnValues
        ) {
            id
        }
    }
    '''

    variables = {
        "itemId": vaga_id,
        "boardId": VAGAS_BOARD_ID,
        "columnValues": column_values_str
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            headers=headers,
            json={"query": query, "variables": variables}
        )
        result = response.json()
        
        if "errors" in result:
            logger.error(f"Erro ao atualizar status da vaga: {result['errors']}")
            return False
            
        logger.info(f"Status da vaga ID {vaga_id} atualizado para '{status}'")
        return True
    
    except Exception as e:
        logger.error(f"Exceção ao atualizar status da vaga: {e}")
        return False

def enviar_arquivo_para_monday(item_id, file_url, nome_arquivo, board_id, coluna_id):
    """
    Envia um arquivo para uma coluna do Monday.com
    Retorna o resultado da operação ou None em caso de erro
    """
    endpoint = "https://api.monday.com/v2/file"
    headers = {
        "Authorization": MONDAY_API_KEY
    }

    try:
        # Faz o download do arquivo
        response = requests.get(file_url)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Erro ao baixar o arquivo: {e}")
        return None

    # Salva temporariamente
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(nome_arquivo)[1]) as tmp_file:
        tmp_file.write(response.content)
        tmp_file_path = tmp_file.name

    # Monta a query para o upload de arquivo
    query = f"""
    mutation ($file: File!) {{
        add_file_to_column (file: $file, item_id: {item_id}, column_id: "{coluna_id}") {{
            id
        }}
    }}
    """

    # Carrega o arquivo temporário e envia como multipart
    with open(tmp_file_path, 'rb') as file_data:
        multipart_data = {
            'query': (None, query),
            'variables[file]': (nome_arquivo, file_data),
        }
        try:
            res = requests.post(endpoint, headers=headers, files=multipart_data)
            logger.info(f"Upload de arquivo: {res.text}")
            result = res.json()
        except Exception as e:
            logger.error(f"Erro ao fazer upload do arquivo: {e}")
            result = None
        finally:
            os.unlink(tmp_file_path)  # Apaga o arquivo temporário

    return result
import os
import sys
import logging
from datetime import datetime
from sqlalchemy import text

# Adicionar o diretório atual ao path
sys.path.append(os.getcwd())

from app import app, db

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def add_encryption_columns():
    """
    Script para adicionar colunas de controle de criptografia às tabelas.
    Este script é executado uma única vez para preparar o banco de dados para
    a funcionalidade de criptografia.
    """
    logger.info("Iniciando migração das colunas para criptografia...")
    
    try:
        with app.app_context():
            # Obter a engine SQL e conexão direta para operações de DDL
            engine = db.engine
            connection = engine.connect()
            
            # Verificar se a coluna is_encrypted já existe na tabela email_data
            result = connection.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='email_data' AND column_name='is_encrypted'
            """))
            
            email_data_has_column = result.scalar() is not None
            
            # Adicionar coluna is_encrypted à tabela email_data
            if not email_data_has_column:
                logger.info("Adicionando coluna is_encrypted à tabela email_data")
                connection.execute(text("ALTER TABLE email_data ADD COLUMN is_encrypted BOOLEAN DEFAULT FALSE"))
                
            # Verificar se a coluna is_encrypted já existe na tabela email_account
            result = connection.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='email_account' AND column_name='is_encrypted'
            """))
            
            email_account_has_column = result.scalar() is not None
            
            # Adicionar coluna is_encrypted à tabela email_account
            if not email_account_has_column:
                logger.info("Adicionando coluna is_encrypted à tabela email_account")
                connection.execute(text("ALTER TABLE email_account ADD COLUMN is_encrypted BOOLEAN DEFAULT FALSE"))
            
            # Commit as alterações
            connection.commit()
            
            logger.info("Migração das colunas de criptografia concluída com sucesso!")
            
    except Exception as e:
        logger.error(f"Erro durante a migração das colunas para criptografia: {str(e)}")
        raise

if __name__ == "__main__":
    add_encryption_columns()
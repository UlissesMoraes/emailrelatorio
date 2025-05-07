import os
import sys
import logging
from sqlalchemy import text

# Adicionar o diretório atual ao path
sys.path.append(os.getcwd())

from app import app, db

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def alter_field_sizes():
    """
    Script para aumentar o tamanho dos campos para acomodar dados criptografados.
    Este script deve ser executado antes de criptografar os dados.
    """
    logger.info("Iniciando alteração do tamanho dos campos...")
    
    try:
        with app.app_context():
            engine = db.engine
            connection = engine.connect()
            
            # Aumentar o tamanho dos campos na tabela email_data
            logger.info("Alterando tipos e tamanhos dos campos na tabela email_data...")
            
            # Alterar campo subject
            connection.execute(text("ALTER TABLE email_data ALTER COLUMN subject TYPE VARCHAR(1024)"))
            
            # Alterar campo sender
            connection.execute(text("ALTER TABLE email_data ALTER COLUMN sender TYPE VARCHAR(1024)"))
            
            # Alterar campos nas contas de email
            logger.info("Alterando tipos e tamanhos dos campos na tabela email_account...")
            
            # Alterar campos de token
            connection.execute(text("ALTER TABLE email_account ALTER COLUMN refresh_token TYPE VARCHAR(1024)"))
            connection.execute(text("ALTER TABLE email_account ALTER COLUMN access_token TYPE VARCHAR(1024)"))
            
            # Commit alterações
            connection.commit()
            
            logger.info("Alteração do tamanho dos campos concluída com sucesso!")
            
    except Exception as e:
        logger.error(f"Erro durante a alteração do tamanho dos campos: {str(e)}")
        raise

if __name__ == "__main__":
    alter_field_sizes()
import os
import sys
from datetime import datetime, timedelta
import logging

# Adicionar o diretório atual ao path
sys.path.append(os.getcwd())

from app import app, db
from models import EmailData
from utils import Cryptography

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def encrypt_email_fields():
    """
    Script para criptografar campos sensíveis de email.
    Este script deve ser executado uma única vez para migrar dados existentes.
    """
    logger.info("Iniciando criptografia de campos sensíveis de email...")
    
    try:
        # Operar no contexto da aplicação
        with app.app_context():
            # Contar registros a serem processados
            total_records = EmailData.query.count()
            logger.info(f"Total de {total_records} registros a processar")
            
            # Processar em lotes para melhor performance e evitar sobrecarga de memória
            batch_size = 100
            processed = 0
            
            for offset in range(0, total_records, batch_size):
                batch = EmailData.query.order_by(EmailData.id).offset(offset).limit(batch_size).all()
                
                for email in batch:
                    # Criptografar campos sensíveis
                    if email.subject:
                        email.subject = Cryptography.encrypt(email.subject)
                    
                    if email.body_text:
                        email.body_text = Cryptography.encrypt(email.body_text)
                        
                    if email.body_html:
                        email.body_html = Cryptography.encrypt(email.body_html)
                    
                    # Opcionalmente, criptografar outros campos como remetente, destinatários
                    if email.sender:
                        email.sender = Cryptography.encrypt(email.sender)
                        
                    if email.recipients:
                        email.recipients = Cryptography.encrypt(email.recipients)
                        
                    if email.cc:
                        email.cc = Cryptography.encrypt(email.cc)
                        
                    if email.bcc:
                        email.bcc = Cryptography.encrypt(email.bcc)
                
                # Salvar as alterações em lote
                db.session.commit()
                
                processed += len(batch)
                logger.info(f"Processados {processed}/{total_records} registros")
            
            logger.info("Criptografia de emails concluída com sucesso!")
    
    except Exception as e:
        logger.error(f"Erro durante a criptografia de emails: {str(e)}")
        # Rollback em caso de erro
        db.session.rollback()
        raise

if __name__ == "__main__":
    encrypt_email_fields()
import os
import sys
from datetime import datetime, timedelta
import logging
import time

# Adicionar o diretório atual ao path
sys.path.append(os.getcwd())

from app import app, db
from models import EmailData, EmailAccount
from utils import Cryptography

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def encrypt_email_fields():
    """
    Script para criptografar campos sensíveis de email de forma otimizada.
    Este script deve ser executado uma única vez para migrar dados existentes.
    """
    logger.info("Iniciando criptografia de campos sensíveis de email...")
    
    try:
        # Operar no contexto da aplicação
        with app.app_context():
            # Primeiro, vamos encriptar os tokens de acesso
            logger.info("Criptografando tokens de acesso das contas de email...")
            encrypt_email_accounts_tokens()
            
            # Depois, encriptamos os dados de email em lotes menores
            logger.info("Criptografando dados de emails...")
            encrypt_email_data_batched()
            
            logger.info("Criptografia de emails concluída com sucesso!")
    
    except Exception as e:
        logger.error(f"Erro durante a criptografia de emails: {str(e)}")
        # Rollback em caso de erro
        db.session.rollback()
        raise

def encrypt_email_accounts_tokens():
    """Criptografar tokens de contas de email"""
    accounts = EmailAccount.query.all()
    
    logger.info(f"Total de {len(accounts)} contas de email para processar")
    count = 0
    
    for account in accounts:
        if not account.is_encrypted:
            # Salvar tokens atuais sem criptografia
            original_access_token = account._access_token
            original_refresh_token = account._refresh_token
            
            # Usar os setters para criptografar
            if original_access_token:
                account.access_token = original_access_token
            
            if original_refresh_token:
                account.refresh_token = original_refresh_token
                
            account.is_encrypted = True
            count += 1
            
            # Commit a cada 10 contas para não perder progresso
            if count % 10 == 0:
                db.session.commit()
                logger.info(f"Processadas {count}/{len(accounts)} contas de email")
    
    # Commit final
    db.session.commit()
    logger.info(f"Processadas {count}/{len(accounts)} contas de email")

def encrypt_email_data_batched():
    """Criptografar campos sensíveis de email em lotes pequenos"""
    total_records = EmailData.query.count()
    logger.info(f"Total de {total_records} registros de email para processar")
    
    # Processar em lotes menores (20 registros por vez) para melhor performance
    batch_size = 20
    offset = 0
    processed = 0
    errors = 0
    
    while offset < total_records:
        start_time = time.time()
        
        # Obter um lote de registros
        batch = EmailData.query.order_by(EmailData.id).offset(offset).limit(batch_size).all()
        
        for email in batch:
            try:
                if not email.is_encrypted:
                    # Salvar dados originais
                    original_subject = email._subject
                    original_sender = email._sender
                    original_recipients = email._recipients
                    original_cc = email._cc
                    original_bcc = email._bcc
                    original_body_text = email._body_text
                    original_body_html = email._body_html
                    
                    # Usar os setters para criptografar
                    if original_subject:
                        email.subject = original_subject
                        
                    if original_sender:
                        email.sender = original_sender
                        
                    if original_recipients:
                        email.recipients = original_recipients
                        
                    if original_cc:
                        email.cc = original_cc
                        
                    if original_bcc:
                        email.bcc = original_bcc
                        
                    if original_body_text:
                        email.body_text = original_body_text
                        
                    if original_body_html:
                        email.body_html = original_body_html
                        
                    email.is_encrypted = True
                    processed += 1
            except Exception as e:
                logger.error(f"Erro ao processar email ID {email.id}: {str(e)}")
                errors += 1
        
        # Commit após cada lote
        db.session.commit()
        
        # Avançar para o próximo lote
        offset += len(batch)
        
        # Calcular ritmo e tempo restante
        elapsed = time.time() - start_time
        emails_per_sec = len(batch) / elapsed if elapsed > 0 else 0
        remaining = total_records - offset
        time_left = remaining / emails_per_sec if emails_per_sec > 0 else "desconhecido"
        
        if isinstance(time_left, float):
            time_str = f"{time_left:.1f} segundos"
            if time_left > 60:
                time_str = f"{time_left/60:.1f} minutos"
        else:
            time_str = time_left
            
        logger.info(f"Processados {offset}/{total_records} emails ({emails_per_sec:.1f} emails/s, tempo restante ~{time_str})")
    
    logger.info(f"Criptografia concluída: {processed} emails criptografados, {errors} erros")

if __name__ == "__main__":
    encrypt_email_fields()
import imaplib
import email
import logging
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup

from app import db
from models import EmailData

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, account):
        self.account = account
        self.provider = account.provider
        self.email_address = account.email_address
        
        # Set up connection details based on provider
        if self.provider == 'gmail':
            self.imap_server = 'imap.gmail.com'
            self.smtp_server = 'smtp.gmail.com'
            self.smtp_port = 587
        elif self.provider == 'outlook':
            self.imap_server = 'outlook.office365.com'
            self.smtp_server = 'smtp.office365.com'
            self.smtp_port = 587
        elif self.provider == 'umbler':
            self.imap_server = 'mail.umbler.com'
            self.smtp_server = 'smtp.umbler.com'
            self.smtp_port = 587
            # Umbler requer configurações específicas para SSL/TLS
            self.imap_port = 993  # Porta IMAP com SSL
        else:
            raise ValueError(f"Unsupported email provider: {self.provider}")
    
    def get_folders(self, force_refresh=False):
        """
        List all available folders/mailboxes in the email account
        Returns a list of dictionaries with name and path of each folder
        
        Args:
            force_refresh: If True, always get fresh data instead of using cached
        """
        try:
            # Verify if we have stored folders first and we're not forcing refresh
            if not force_refresh and self.account.folders and len(self.account.folders) > 0:
                logger.info(f"Usando pastas armazenadas para a conta {self.account.id}")
                return self.account.folders
                
            # Connect to the IMAP server
            password = self.account.access_token
            
            if not password:
                logger.warning(f"Password not available for account {self.account.id}")
                raise ValueError("Não foi possível acessar a conta de email. Verifique suas credenciais.")
            
            # Log para depuração - verificar informações de conexão
            logger.info(f"Tentando conectar a {self.imap_server} com usuário {self.email_address}")
            logger.info(f"Tipo de provider: {self.provider}")
            
            # Criando a conexão IMAP segura
            if hasattr(self, 'imap_port'):
                mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            else:
                mail = imaplib.IMAP4_SSL(self.imap_server)
            
            # Tentando fazer login - pode falhar se as credenciais estiverem incorretas
            try:
                mail.login(self.email_address, password)
                logger.info(f"Login bem-sucedido para {self.email_address}")
            except Exception as e:
                logger.error(f"Erro de autenticação detalhado: {str(e)}")
                
                # Tentar mostrar informações adicionais de depuração
                if self.provider == 'gmail':
                    logger.info("Para o Gmail, verifique se você está usando uma senha de app válida e se o IMAP está ativado")
                    logger.info("A senha de app deve ser inserida sem espaços")
                elif self.provider == 'outlook':
                    logger.info("Para o Outlook, verifique se o IMAP está ativado na sua conta")
                elif self.provider == 'umbler':
                    logger.info("Para o Umbler, verifique se está usando a senha correta e se IMAP está ativado nas configurações do email")
                    logger.info("Para o Umbler é necessário habilitar o IMAP no painel de controle da conta de email")
                
                raise
            
            # List all mailboxes/folders
            response, folder_list = mail.list()
            
            if response != 'OK':
                logger.error(f"Failed to retrieve folders: {response}")
                raise Exception("Failed to retrieve email folders")
            
            folders = []
            default_folders = {
                'INBOX': 'Caixa de Entrada',
                '[Gmail]/Sent Mail': 'Enviados',
                '[Gmail]/Drafts': 'Rascunhos',
                '[Gmail]/Trash': 'Lixeira',
                '[Gmail]/Spam': 'Spam',
                '[Gmail]/Starred': 'Favoritos',
                '[Gmail]/Important': 'Importantes',
                '[Gmail]/All Mail': 'Todos os E-mails'
            }
            
            for folder_info in folder_list:
                # Decode folder info
                folder_info_decoded = folder_info.decode('utf-8')
                
                # Extract folder path using regex - melhorado para lidar com mais formatos
                # Formatos possíveis: 
                # - (\Noselect) "/" "INBOX/Sent Items"
                # - "/" "INBOX"
                
                try:
                    # Tenta extrair usando o padrão mais comum
                    match = re.search(r'"([^"]*)" "([^"]*)"$', folder_info_decoded)
                    
                    if match:
                        delimiter = match.group(1)
                        path = match.group(2)
                    else:
                        # Formato alternativo com flags (como \Noselect)
                        match = re.search(r'\(.*\) "([^"]*)" "([^"]*)"$', folder_info_decoded)
                        if match:
                            delimiter = match.group(1)
                            path = match.group(2)
                        else:
                            # Outro formato sem padrão claro
                            parts = folder_info_decoded.split('"')
                            if len(parts) >= 3:
                                # Última parte entre aspas é o caminho
                                path = parts[-2]
                                delimiter = "/" # assume-se / como padrão
                            else:
                                logger.warning(f"Não foi possível extrair pasta: {folder_info_decoded}")
                                continue
                    
                    # Skip certain Gmail system folders
                    if path.startswith('[Gmail]/All'):
                        continue
                        
                    # Get folder name (last part of the path)
                    if delimiter and delimiter in path:
                        name = path.split(delimiter)[-1]
                    else:
                        name = path
                        
                    # Garante que a pasta não tenha caracteres problemáticos
                    path = path.strip()
                except Exception as e:
                    logger.warning(f"Erro ao processar pasta: {str(e)} - {folder_info_decoded}")
                    continue
                
                # Use a friendly name for well-known folders
                if path in default_folders:
                    name = default_folders[path]
                elif name == 'INBOX':
                    name = 'Caixa de Entrada'
                
                # Add to folder list
                folders.append({
                    'name': name,
                    'path': path
                })
            
            # Logout and close connection
            mail.logout()
            
            # Store folders in account for future use
            if folders:
                self.account.folders = folders
                db.session.commit()
                
            return folders
            
        except Exception as e:
            logger.exception(f"Error getting folders: {str(e)}")
            # Return a minimal default set if we can't connect
            default_folders = [
                {'name': 'Caixa de Entrada', 'path': 'INBOX'}
            ]
            return default_folders
    
    def sync_emails(self, limit=100, folder='INBOX'):
        """
        Sync emails from the email account to the database
        Apenas e-mails do mês atual serão sincronizados.
        
        Args:
            limit: Maximum number of emails to sync
            folder: Email folder to sync from (default: 'INBOX')
            
        Returns:
            int: The number of new emails synced
        """
        try:
            password = self.account.access_token
            
            if not password:
                logger.warning(f"Senha não disponível para a conta {self.account.id}")
                raise ValueError("Não foi possível acessar a conta de email. Verifique suas credenciais.")
            
            # Log para depuração - verificar informações de conexão para sync_emails
            logger.info(f"[SYNC] Tentando conectar a {self.imap_server} com usuário {self.email_address}")
            logger.info(f"[SYNC] Tipo de provider: {self.provider}")
            
            # Connect to the IMAP server
            if hasattr(self, 'imap_port'):
                mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            else:
                mail = imaplib.IMAP4_SSL(self.imap_server)
            
            # Tentando fazer login - pode falhar se as credenciais estiverem incorretas
            try:
                mail.login(self.email_address, password)
                logger.info(f"[SYNC] Login bem-sucedido para {self.email_address}")
            except Exception as e:
                logger.error(f"[SYNC] Erro de autenticação detalhado: {str(e)}")
                
                # Tentar mostrar informações adicionais de depuração
                if self.provider == 'gmail':
                    logger.info("[SYNC] Para o Gmail, verifique se você está usando uma senha de app válida e se o IMAP está ativado")
                    logger.info("[SYNC] A senha de app deve ser inserida sem espaços")
                elif self.provider == 'outlook':
                    logger.info("[SYNC] Para o Outlook, verifique se o IMAP está ativado na sua conta")
                elif self.provider == 'umbler':
                    logger.info("[SYNC] Para o Umbler, verifique se está usando a senha correta e se IMAP está ativado nas configurações do email")
                    logger.info("[SYNC] Para o Umbler é necessário habilitar o IMAP no painel de controle da conta de email")
                
                raise
            
            # Select the mailbox/folder - tratando caracteres especiais e espaços
            try:
                # Sanitiza o nome da pasta para lidar com caracteres especiais
                sanitized_folder = folder.strip().replace('"', '\\"')
                
                # Se a pasta contém espaços ou caracteres especiais, colocamos entre aspas
                if re.search(r'[\s\W]', sanitized_folder) and not sanitized_folder.startswith('"'):
                    sanitized_folder = f'"{sanitized_folder}"'
                
                logger.debug(f"[SYNC] Selecionando pasta: {sanitized_folder}")
                response, data = mail.select(sanitized_folder, readonly=True)
                
                if response != 'OK':
                    # Tenta alternativa - usar a pasta INBOX como fallback
                    if folder.lower() != 'inbox':
                        logger.warning(f"Falha ao selecionar pasta {folder}, tentando INBOX como alternativa")
                        response, data = mail.select('INBOX', readonly=True)
                        
                        if response == 'OK':
                            folder = 'INBOX'  # Substitui a pasta para o restante do processo
                        else:
                            raise Exception(f"Não foi possível selecionar nenhuma pasta: {response}")
                    else:
                        logger.error(f"Falha ao selecionar pasta INBOX: {response}")
                        raise Exception(f"Falha ao selecionar pasta INBOX: {response}")
            except Exception as e:
                logger.error(f"Erro ao selecionar pasta: {str(e)}")
                raise Exception(f"Erro ao selecionar pasta {folder}: {str(e)}")
            
            # Calculate date for filtering (first day of current month)
            now = datetime.utcnow()
            first_day = now.replace(day=1).strftime("%d-%b-%Y")
            
            # Search for emails since the first day of the current month
            search_criteria = f'(SINCE {first_day})'
            response, message_nums = mail.search(None, search_criteria)
            
            if response != 'OK':
                logger.error(f"Failed to search for emails: {response}")
                raise Exception("Failed to search for emails")
            
            # Get list of message IDs
            message_nums = message_nums[0].split()
            
            # Limit the number of emails to fetch (most recent first)
            if len(message_nums) > limit:
                message_nums = message_nums[-limit:]
            
            new_emails_count = 0
            
            # Fetch each email and add to database
            for num in reversed(message_nums):  # Process from newest to oldest
                # Get email data
                response, msg_data = mail.fetch(num, '(RFC822)')
                
                if response != 'OK':
                    logger.warning(f"Failed to fetch email {num}: {response}")
                    continue
                
                # Parse the email
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # Extract email fields
                message_id = msg.get('Message-ID', '')
                
                # Verificar se este email já existe no banco de dados para evitar duplicação
                if message_id:
                    existing_email = EmailData.query.filter_by(
                        account_id=self.account.id,
                        message_id=message_id,
                        folder=folder
                    ).first()
                    
                    if existing_email:
                        # Email já existe, pular para o próximo
                        # Removendo log para melhorar desempenho
                        continue
                
                subject = msg.get('Subject', '(No Subject)')
                
                # Decode subject if needed
                if isinstance(subject, str) and '=?' in subject:
                    subject = email.header.decode_header(subject)[0][0]
                    if isinstance(subject, bytes):
                        subject = subject.decode('utf-8', errors='replace')
                
                # Get sender
                sender = msg.get('From', '')
                if isinstance(sender, str) and '=?' in sender:
                    sender = email.header.decode_header(sender)[0][0]
                    if isinstance(sender, bytes):
                        sender = sender.decode('utf-8', errors='replace')
                
                # Get recipients
                recipients = msg.get('To', '')
                if isinstance(recipients, str) and '=?' in recipients:
                    recipients = email.header.decode_header(recipients)[0][0]
                    if isinstance(recipients, bytes):
                        recipients = recipients.decode('utf-8', errors='replace')
                
                # Get CC recipients
                cc = msg.get('Cc', '')
                if isinstance(cc, str) and '=?' in cc:
                    cc = email.header.decode_header(cc)[0][0]
                    if isinstance(cc, bytes):
                        cc = cc.decode('utf-8', errors='replace')
                
                # Get BCC recipients
                bcc = msg.get('Bcc', '')
                if isinstance(bcc, str) and '=?' in bcc:
                    bcc = email.header.decode_header(bcc)[0][0]
                    if isinstance(bcc, bytes):
                        bcc = bcc.decode('utf-8', errors='replace')
                
                # Get date
                date_str = msg.get('Date', '')
                try:
                    # Parse email date format to datetime
                    # This is complex as email dates can be in various formats
                    from email.utils import parsedate_to_datetime
                    date = parsedate_to_datetime(date_str)
                except:
                    # Default to now if can't parse date
                    date = datetime.utcnow()
                
                # Get email body (plain text and HTML)
                body_text = None
                body_html = None
                
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get('Content-Disposition'))
                        
                        # Skip attachments
                        if 'attachment' in content_disposition:
                            continue
                        
                        # Get the plain text body
                        if content_type == 'text/plain':
                            body = part.get_payload(decode=True)
                            charset = part.get_content_charset()
                            if charset:
                                try:
                                    body_text = body.decode(charset, errors='replace')
                                except:
                                    body_text = body.decode('utf-8', errors='replace')
                            else:
                                body_text = body.decode('utf-8', errors='replace')
                        
                        # Get the HTML body
                        elif content_type == 'text/html':
                            body = part.get_payload(decode=True)
                            charset = part.get_content_charset()
                            if charset:
                                try:
                                    body_html = body.decode(charset, errors='replace')
                                except:
                                    body_html = body.decode('utf-8', errors='replace')
                            else:
                                body_html = body.decode('utf-8', errors='replace')
                else:
                    # Not multipart - get the payload directly
                    body = msg.get_payload(decode=True)
                    charset = msg.get_content_charset()
                    
                    if msg.get_content_type() == 'text/plain':
                        if charset:
                            try:
                                body_text = body.decode(charset, errors='replace')
                            except:
                                body_text = body.decode('utf-8', errors='replace')
                        else:
                            body_text = body.decode('utf-8', errors='replace')
                    elif msg.get_content_type() == 'text/html':
                        if charset:
                            try:
                                body_html = body.decode(charset, errors='replace')
                            except:
                                body_html = body.decode('utf-8', errors='replace')
                        else:
                            body_html = body.decode('utf-8', errors='replace')
                
                # If we have HTML but no plain text, extract from HTML
                if body_html and not body_text:
                    try:
                        soup = BeautifulSoup(body_html, 'html.parser')
                        body_text = soup.get_text()
                    except Exception as e:
                        logger.warning(f"Error extracting text from HTML: {str(e)}")
                
                # Determine if this is a sent email
                is_sent = self.email_address.lower() in sender.lower()
                
                # Limitando o tamanho de alguns campos para evitar problemas
                if subject and len(subject) > 1000:
                    subject = subject[:1000] + "..."
                
                if sender and len(sender) > 500:
                    sender = sender[:500]
                
                if recipients and len(recipients) > 5000:  
                    recipients = recipients[:5000] + "..."
                
                if cc and len(cc) > 2000:
                    cc = cc[:2000] + "..."
                    
                if bcc and len(bcc) > 2000:
                    bcc = bcc[:2000] + "..."
                
                # Limitar o tamanho do corpo do email
                if body_text and len(body_text) > 65000:
                    body_text = body_text[:65000] + "..."
                    
                if body_html and len(body_html) > 65000:
                    body_html = body_html[:65000] + "..."
                
                # Criar novo EmailData objeto com tratamento de erros
                try:
                    logger.info(f"Criando registro de email para message_id={message_id}")
                    email_data = EmailData(
                        account_id=self.account.id,
                        message_id=message_id,
                        folder=folder,  # Adicionar informação da pasta
                        subject=subject,
                        sender=sender,
                        recipients=recipients,
                        cc=cc,
                        bcc=bcc,
                        date=date,
                        body_text=body_text,
                        body_html=body_html,
                        is_sent=is_sent
                    )
                    logger.info("EmailData criado com sucesso")
                except Exception as e:
                    logger.error(f"Erro ao criar EmailData: {str(e)}")
                    # Criar registro mínimo em caso de erro
                    email_data = EmailData(
                        account_id=self.account.id,
                        message_id=message_id,
                        folder=folder,
                        subject=f"[Erro ao importar] {subject if subject else 'Sem assunto'}",
                        sender="erro@importacao.local",
                        recipients="",
                        date=date or datetime.utcnow(),
                        is_sent=is_sent
                    )
                
                # Add to database
                db.session.add(email_data)
                new_emails_count += 1
            
            # Commit all changes at once
            if new_emails_count > 0:
                db.session.commit()
            
            # Logout and close connection
            mail.logout()
            
            return new_emails_count
            
        except Exception as e:
            logger.exception(f"Error syncing emails: {str(e)}")
            # Make sure we don't leave pending transactions
            db.session.rollback()
            raise
    
    # Método para geração de emails de demonstração completamente removido
    def check_for_new_emails(self, folder='INBOX'):
        """
        Verifica se há novos emails na conta sem sincronizar todos os emails.
        Apenas verifica os mais recentes (últimos 10) para um processamento mais rápido.

        Args:
            folder: Pasta de email para verificar (padrão: 'INBOX')
            
        Returns:
            bool: True se novos emails foram encontrados, False caso contrário
        """
        try:
            # Usar a sincronização normal, mas limitar a apenas 10 emails recentes
            new_count = self.sync_emails(limit=10, folder=folder)
            return new_count > 0
        except Exception as e:
            logger.exception(f"Erro ao verificar por novos emails: {str(e)}")
            return False

    def _generate_demo_emails(self, folder='INBOX', limit=10):
        """
        Esta função foi completamente removida. 
        O sistema agora só trabalha com dados reais de email.
        A função permanece apenas para compatibilidade com código existente,
        mas retorna 0 e não executa nenhuma ação.
        """
        logger.warning("Tentativa de usar função _generate_demo_emails que foi removida")
        return 0
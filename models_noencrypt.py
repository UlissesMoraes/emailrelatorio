from datetime import datetime, timezone
from app import db, login_manager
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import event
from utils import Cryptography

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Organization(db.Model):
    """Modelo para representar diferentes empresas (multitenancy)"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    domain = db.Column(db.String(100), nullable=True)  # Domínio de email opcional para autenticação automática
    logo = db.Column(db.String(200), nullable=True)
    primary_color = db.Column(db.String(20), nullable=True, default="#3498db")  # Cor primária para tema
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relação com usuários
    users = db.relationship('User', backref='organization', lazy='dynamic')
    
    def __repr__(self):
        return f'<Organization {self.name}>'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_superadmin = db.Column(db.Boolean, default=False)  # Super admin pode gerenciar todas as organizações
    profile_image = db.Column(db.String(120), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    email_accounts = db.relationship('EmailAccount', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    reports = db.relationship('Report', backref='user', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.username}>'


class EmailAccount(db.Model):
    """
    Modelo de conta de email sem criptografia para simplificação.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    provider = db.Column(db.String(50), nullable=False)  # 'gmail', 'outlook', etc.
    email_address = db.Column(db.String(120), nullable=False)
    refresh_token = db.Column(db.String(1024), nullable=True)
    access_token = db.Column(db.String(1024), nullable=True)
    token_expiry = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_synced = db.Column(db.DateTime, nullable=True)
    folders = db.Column(JSON, nullable=True)  # Store email folders as JSON
    is_encrypted = db.Column(db.Boolean, default=False)  # Mantido para compatibilidade, mas sempre será False
    
    # Relationships
    email_data = db.relationship('EmailData', backref='account', lazy='dynamic', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<EmailAccount {self.email_address}>'
        
    def get_folders(self):
        """Return the list of folders as a list of dicts with name and path"""
        if not self.folders:
            return [{'name': 'Caixa de Entrada', 'path': 'INBOX'}]
        return self.folders


class EmailData(db.Model):
    """
    Modelo de dados de email sem criptografia para simplificar e garantir compatibilidade.
    A criptografia foi desativada para resolver problemas de compatibilidade.
    """
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('email_account.id'), nullable=False)
    message_id = db.Column(db.String(256), nullable=False)
    folder = db.Column(db.String(256), nullable=True, default='INBOX')  # Email folder path
    subject = db.Column(db.String(1024), nullable=True)  
    sender = db.Column(db.String(512), nullable=True)  
    recipients = db.Column(db.Text, nullable=True)  
    cc = db.Column(db.Text, nullable=True)  
    bcc = db.Column(db.Text, nullable=True)  
    date = db.Column(db.DateTime, nullable=True)
    body_text = db.Column(db.Text, nullable=True)  
    body_html = db.Column(db.Text, nullable=True)  
    is_sent = db.Column(db.Boolean, default=False)  # True if the email was sent by the user
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_encrypted = db.Column(db.Boolean, default=False)  # Mantido para compatibilidade, mas não utilizado
    
    def __repr__(self):
        return f'<EmailData {self.subject}>'


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'summary', 'detailed', etc.
    date_range_start = db.Column(db.DateTime, nullable=True)
    date_range_end = db.Column(db.DateTime, nullable=True)
    filters = db.Column(JSON, nullable=True)  # Store filters as JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_generated = db.Column(db.DateTime, default=datetime.utcnow)
    report_metadata = db.Column(JSON, nullable=True)  # Store additional report metadata as JSON
    
    def __repr__(self):
        return f'<Report {self.name}>'


class SupportTicket(db.Model):
    """Modelo para tickets de suporte"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='aberto')  # 'aberto', 'em_andamento', 'resolvido'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    messages = db.relationship('SupportMessage', backref='ticket', lazy='dynamic', cascade="all, delete-orphan", order_by="SupportMessage.created_at")
    user = db.relationship('User', backref='support_tickets')
    
    def __repr__(self):
        return f'<SupportTicket {self.id} - {self.subject}>'
    
    @property
    def last_message_time(self):
        last_message = self.messages.order_by(SupportMessage.created_at.desc()).first()
        return last_message.created_at if last_message else self.created_at
    
    
class SupportMessage(db.Model):
    """Modelo para mensagens nos tickets de suporte"""
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('support_ticket.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)
    
    # Relacionamento com o remetente
    sender = db.relationship('User', backref='sent_support_messages')
    
    def __repr__(self):
        return f'<SupportMessage {self.id} - Ticket {self.ticket_id}>'
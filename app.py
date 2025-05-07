import os
import logging

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
csrf = CSRFProtect()

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key_for_development")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///email_analyzer.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions with app
db.init_app(app)
login_manager.init_app(app)
# Mantemos a inicialização CSRF, mas desativamos a verificação
# para permitir que o token exista nos templates, mas não seja validado
csrf.init_app(app)
app.config['WTF_CSRF_ENABLED'] = False
app.config['WTF_CSRF_CHECK_DEFAULT'] = False
login_manager.login_view = 'login'

with app.app_context():
    # Import models to ensure tables are created
    import models
    
    # Create database tables
    db.create_all()
    
    # Agora importamos os modelos para uso
    from models import User, EmailAccount, EmailData, Report, Organization
    from werkzeug.security import generate_password_hash
    
    # Verificar se existe alguma organização, se não, criar a primeira
    try:
        org_exists = Organization.query.first()
        if not org_exists:
            default_org = Organization(
                name="Organização Padrão",
                primary_color="#3498db"
            )
            db.session.add(default_org)
            db.session.commit()
            logger.info("Criada organização padrão")
    except Exception as e:
        logger.warning(f"Erro ao verificar organizações: {str(e)}")
    
    # Verificar se existe algum usuário administrador, se não, criar o primeiro
    try:
        admin_exists = User.query.filter_by(is_admin=True).first()
        if not admin_exists:
            # Verificar se existe algum usuário que possa ser promovido a admin
            first_user = User.query.first()
            if first_user:
                # Promover o primeiro usuário existente a administrador
                first_user.is_admin = True
                first_user.is_superadmin = True
                
                # Verificar organização
                if not hasattr(first_user, 'organization_id') or first_user.organization_id is None:
                    default_org = Organization.query.first()
                    if default_org:
                        first_user.organization_id = default_org.id
                
                db.session.commit()
                logger.info(f"Usuário existente {first_user.username} promovido a administrador")
            else:
                # Buscar organização padrão
                default_org = Organization.query.first()
                org_id = default_org.id if default_org else None
                
                # Criar um usuário administrador padrão
                admin_user = User(
                    username="admin",
                    email="admin@example.com",
                    password_hash=generate_password_hash("admin123"),
                    is_admin=True,
                    is_superadmin=True,
                    organization_id=org_id
                )
                db.session.add(admin_user)
                db.session.commit()
                logger.info("Criado usuário administrador padrão. Email: admin@example.com, Senha: admin123")
    except Exception as e:
        logger.warning(f"Erro ao verificar usuários administradores: {str(e)}")
    
    # Import and register routes
    import routes

    logger.info("Application initialized successfully")

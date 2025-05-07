from app import app, db
import jinja2
import markupsafe
from flask_login import current_user
from models import SupportTicket, SupportMessage, Organization

# Importar todas as rotas
import routes

# Filtro para converter quebras de linha em <br> em templates
@app.template_filter('nl2br')
def nl2br(value):
    if isinstance(value, str):
        value = value.replace('\n', markupsafe.Markup('<br>'))
    return markupsafe.Markup(value)

# Função global para contar notificações não lidas
@app.context_processor
def utility_processor():
    def count_unread_notifications():
        """Conta o número total de mensagens não lidas em tickets de suporte para o usuário atual"""
        try:
            if not hasattr(current_user, 'is_authenticated') or not current_user.is_authenticated:
                return 0
            
            # Para usuários normais, contar apenas mensagens de seus próprios tickets
            if not current_user.is_admin:
                # Consulta otimizada usando subquery para contar mensagens não lidas nos tickets do usuário
                unread_count = SupportMessage.query.filter(
                    SupportMessage.ticket_id.in_(
                        db.session.query(SupportTicket.id).filter_by(user_id=current_user.id)
                    ),
                    SupportMessage.sender_id != current_user.id,
                    SupportMessage.read == False
                ).count()
            else:
                # Para administradores, contar todas as mensagens não lidas de tickets que não são deles
                unread_count = SupportMessage.query.filter(
                    SupportMessage.sender_id != current_user.id,
                    SupportMessage.read == False
                ).count()
            
            return unread_count
        except Exception as e:
            # Em caso de erro, retornar 0 para não quebrar a interface
            app.logger.error(f"Erro ao contar notificações: {str(e)}")
            return 0
    
    def get_user_organization():
        """Retorna a organização do usuário atual para exibir o logo"""
        try:
            if not hasattr(current_user, 'is_authenticated') or not current_user.is_authenticated:
                return None
            
            if not current_user.organization_id:
                return None
                
            # Carregar a organização do usuário
            return Organization.query.get(current_user.organization_id)
        except Exception as e:
            app.logger.error(f"Erro ao carregar organização: {str(e)}")
            return None
        
    return dict(
        count_unread_notifications=count_unread_notifications,
        user_organization=get_user_organization()
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

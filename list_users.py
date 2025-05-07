from app import app, db
from models import User

def list_users():
    """
    Script para listar todos os usuários e seus privilégios
    """
    with app.app_context():
        users = User.query.all()
        
        if not users:
            print("Não há usuários cadastrados no sistema")
            return
            
        print("\n=== USUÁRIOS CADASTRADOS NO SISTEMA ===")
        print(f"Total: {len(users)} usuário(s)")
        print("="*40)
        
        for user in users:
            print(f"ID: {user.id}")
            print(f"Nome: {user.username}")
            print(f"Email: {user.email}")
            print(f"Admin: {'Sim' if user.is_admin else 'Não'}")
            print(f"SuperAdmin: {'Sim' if hasattr(user, 'is_superadmin') and user.is_superadmin else 'Não'}")
            print(f"Organização: {user.organization_id if user.organization_id else 'Nenhuma'}")
            print("-"*40)

if __name__ == "__main__":
    list_users()
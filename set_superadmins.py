from app import app, db
from models import User

def set_superadmins():
    """
    Script para transformar os usuários Ulisses e Itamar em superadmins
    """
    with app.app_context():
        # Buscar os usuários pelos IDs conhecidos
        ulisses = User.query.filter_by(id=1).first()  # Ulisses Moraes
        itamar = User.query.filter_by(id=2).first()   # itamar
        
        # Verificar se os usuários foram encontrados
        if ulisses:
            print(f"Atualizando {ulisses.username} (ID: {ulisses.id})")
            ulisses.is_admin = True
            ulisses.is_superadmin = True
            ulisses.organization_id = None  # Superadmins não devem ter organização
        else:
            print("Usuário Ulisses não encontrado")
            
        if itamar:
            print(f"Atualizando {itamar.username} (ID: {itamar.id})")
            itamar.is_admin = True
            itamar.is_superadmin = True
            itamar.organization_id = None  # Superadmins não devem ter organização
        else:
            print("Usuário Itamar não encontrado")
        
        # Se algum usuário foi encontrado, salvamos as alterações
        if ulisses or itamar:
            db.session.commit()
            print("Alterações salvas com sucesso")
        else:
            print("Nenhum usuário foi atualizado")

if __name__ == "__main__":
    set_superadmins()
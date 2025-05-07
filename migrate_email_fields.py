from app import app, db
from flask_migrate import Migrate
from sqlalchemy import text

# Configurar a extensão migrate
migrate = Migrate(app, db)

def migrate_email_fields():
    """
    Script para migrar os campos de e-mail para tipos TEXT.
    Isto é necessário para lidar com e-mails que possuem listas extensas de destinatários.
    """
    with app.app_context():
        conn = db.engine.connect()
        
        try:
            # Iniciar uma transação
            trans = conn.begin()
            
            # Alterar tipo de coluna recipients para TEXT
            conn.execute(text("""
                ALTER TABLE email_data 
                ALTER COLUMN recipients TYPE TEXT;
            """))
            
            # Alterar tipo de coluna cc para TEXT
            conn.execute(text("""
                ALTER TABLE email_data 
                ALTER COLUMN cc TYPE TEXT;
            """))
            
            # Alterar tipo de coluna bcc para TEXT
            conn.execute(text("""
                ALTER TABLE email_data 
                ALTER COLUMN bcc TYPE TEXT;
            """))
            
            # Alterar tipo de coluna sender para ter mais espaço
            conn.execute(text("""
                ALTER TABLE email_data 
                ALTER COLUMN sender TYPE VARCHAR(256);
            """))
            
            # Confirmar as alterações
            trans.commit()
            print("Migração concluída com sucesso!")
            
        except Exception as e:
            # Reverter em caso de erro
            if 'trans' in locals() and trans.is_active:
                trans.rollback()
            print(f"Erro durante a migração: {str(e)}")
            raise
        finally:
            # Fechar a conexão
            conn.close()

if __name__ == '__main__':
    migrate_email_fields()
import os
import sys
from app import app, db
from sqlalchemy import text
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_organization_fields():
    """
    Script para adição da tabela organization e 
    atualização da tabela user com campos relacionados ao multitenancy.
    """
    try:
        logger.info("Iniciando migração para suporte a múltiplas organizações...")
        
        # Criar tabela organization se não existir
        with db.engine.connect() as conn:
            # Verificar se a tabela organization já existe
            result = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'organization')"))
            table_exists = result.scalar()
            
            if not table_exists:
                logger.info("Criando tabela 'organization'...")
                conn.execute(text("""
                CREATE TABLE organization (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    domain VARCHAR(100),
                    logo VARCHAR(200),
                    primary_color VARCHAR(20) DEFAULT '#3498db',
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
                """))
                conn.commit()
                logger.info("Tabela 'organization' criada com sucesso!")
            else:
                logger.info("Tabela 'organization' já existe, pulando criação.")
                
            # Verificar se a coluna organization_id existe na tabela user
            result = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'user' AND column_name = 'organization_id')"))
            column_exists = result.scalar()
            
            if not column_exists:
                logger.info("Adicionando coluna 'organization_id' à tabela 'user'...")
                conn.execute(text("ALTER TABLE \"user\" ADD COLUMN organization_id INTEGER REFERENCES organization(id)"))
                conn.commit()
                logger.info("Coluna 'organization_id' adicionada com sucesso!")
            else:
                logger.info("Coluna 'organization_id' já existe, pulando criação.")
                
            # Verificar se a coluna is_superadmin existe na tabela user
            result = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'user' AND column_name = 'is_superadmin')"))
            column_exists = result.scalar()
            
            if not column_exists:
                logger.info("Adicionando coluna 'is_superadmin' à tabela 'user'...")
                conn.execute(text("ALTER TABLE \"user\" ADD COLUMN is_superadmin BOOLEAN DEFAULT FALSE"))
                conn.commit()
                logger.info("Coluna 'is_superadmin' adicionada com sucesso!")
            else:
                logger.info("Coluna 'is_superadmin' já existe, pulando criação.")
            
            # Criar uma organização padrão para usuários existentes se necessário
            result = conn.execute(text("SELECT COUNT(*) FROM organization"))
            count = result.scalar()
            
            if count == 0:
                logger.info("Criando organização padrão...")
                conn.execute(text("INSERT INTO organization (name) VALUES ('Organização Padrão')"))
                conn.commit()
                org_id_result = conn.execute(text("SELECT id FROM organization ORDER BY id LIMIT 1"))
                org_id = org_id_result.scalar()
                
                # Atualizar usuários existentes para usar a organização padrão
                conn.execute(text(f"UPDATE \"user\" SET organization_id = {org_id} WHERE organization_id IS NULL"))
                conn.commit()
                logger.info(f"Organização padrão criada (ID: {org_id}) e usuários atualizados!")
                
            # Verificar se há usuários sem organização
            result = conn.execute(text("SELECT COUNT(*) FROM \"user\" WHERE organization_id IS NULL"))
            count = result.scalar()
            
            if count > 0:
                logger.info(f"Atualizando {count} usuários sem organização para usar a organização padrão...")
                org_id_result = conn.execute(text("SELECT id FROM organization ORDER BY id LIMIT 1"))
                org_id = org_id_result.scalar()
                conn.execute(text(f"UPDATE \"user\" SET organization_id = {org_id} WHERE organization_id IS NULL"))
                conn.commit()
                logger.info("Usuários atualizados com sucesso!")
            
            # Marcar o primeiro admin como superadmin (usando subconsulta para compatibilidade com PostgreSQL)
            conn.execute(text("""
                UPDATE "user" SET is_superadmin = TRUE 
                WHERE id = (SELECT id FROM "user" WHERE is_admin = TRUE ORDER BY id LIMIT 1)
            """))
            conn.commit()
            logger.info("Primeiro usuário admin marcado como superadmin.")
        
        logger.info("Migração concluída com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"Erro durante migração: {str(e)}")
        return False

if __name__ == "__main__":
    with app.app_context():
        success = migrate_organization_fields()
        if success:
            print("Migração concluída com sucesso!")
            sys.exit(0)
        else:
            print("Erro na migração. Verifique os logs para mais detalhes.")
            sys.exit(1)
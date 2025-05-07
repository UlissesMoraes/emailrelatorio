import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)

class Cryptography:
    """
    Classe para gerenciar criptografia e descriptografia de dados sensíveis.
    Utiliza criptografia simétrica Fernet (AES-128 em modo CBC com PKCS7).
    """
    
    # Chave mestra baseada em uma variável de ambiente ou em um valor padrão (deve ser alterado em produção)
    # Em produção, esta chave deve ser guardada em um local seguro, não no código
    MASTER_KEY = os.environ.get('EMAIL_ENCRYPTION_KEY', 'q7FyN8dX3p1aB9cE5hG2jK4mL6oP0rSt')
    
    # Variável de classe para armazenar a chave derivada em cache
    _cached_key = None
    
    @classmethod
    def _get_key(cls):
        """
        Gera uma chave de criptografia derivada da chave mestra usando PBKDF2.
        A chave é calculada apenas uma vez e depois armazenada em cache.
        """
        # Se já temos a chave em cache, retornar
        if cls._cached_key is not None:
            return cls._cached_key
            
        try:
            salt = b'email_encryption_salt'  # Em produção, o salt também deve ser armazenado com segurança
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            cls._cached_key = base64.urlsafe_b64encode(kdf.derive(cls.MASTER_KEY.encode()))
            return cls._cached_key
        except Exception as e:
            logger.error(f"Erro ao gerar chave de criptografia: {str(e)}")
            # Criamos uma chave de fallback para não parar a aplicação em caso de erro
            return Fernet.generate_key()
    
    @classmethod
    def encrypt(cls, data):
        """
        Criptografa dados usando Fernet (implementação de AES).
        
        Args:
            data: Dados a serem criptografados (str ou bytes)
            
        Returns:
            str: Dados criptografados em formato base64
        """
        if data is None:
            return None
        
        try:
            # Garantir que os dados estejam em bytes
            if isinstance(data, str):
                data = data.encode('utf-8')
                
            # Obter chave e configurar o mecanismo de criptografia
            key = cls._get_key()
            f = Fernet(key)
            
            # Criptografar os dados
            encrypted_data = f.encrypt(data)
            
            # Retornar o resultado como string base64
            return encrypted_data.decode('utf-8')
        except Exception as e:
            logger.error(f"Erro ao criptografar dados: {str(e)}")
            # Em caso de erro, retornar os dados originais para não perder informações
            # Em um ambiente de produção, você pode querer lidar com isso de forma diferente
            if isinstance(data, bytes):
                return data.decode('utf-8', errors='replace')
            return data
    
    @classmethod
    def decrypt(cls, encrypted_data):
        """
        Descriptografa dados que foram criptografados com o método encrypt.
        
        Args:
            encrypted_data: Dados criptografados (str em formato base64)
            
        Returns:
            str: Dados descriptografados
        """
        if encrypted_data is None:
            return None
            
        try:
            # Garantir que os dados estejam em bytes
            if isinstance(encrypted_data, str):
                encrypted_data = encrypted_data.encode('utf-8')
                
            # Obter chave e configurar o mecanismo de criptografia
            key = cls._get_key()
            f = Fernet(key)
            
            # Descriptografar os dados
            decrypted_data = f.decrypt(encrypted_data)
            
            # Retornar o resultado como string
            return decrypted_data.decode('utf-8')
        except Exception as e:
            logger.error(f"Erro ao descriptografar dados: {str(e)}")
            # Em caso de erro, retornar os dados criptografados
            # Em um ambiente de produção, você pode querer lidar com isso de forma diferente
            if isinstance(encrypted_data, bytes):
                return encrypted_data.decode('utf-8', errors='replace')
            return encrypted_data
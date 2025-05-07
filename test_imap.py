import imaplib
import sys
import os

def test_imap(email, password, provider):
    print(f'Testando conexão IMAP para {email} com provider {provider}')
    
    if provider == 'gmail':
        imap_server = 'imap.gmail.com'
    elif provider == 'outlook':
        imap_server = 'outlook.office365.com'
    else:
        print(f'Provedor não suportado: {provider}')
        return False
    
    print(f'Conectando a {imap_server}...')
    try:
        # Tenta estabelecer conexão
        mail = imaplib.IMAP4_SSL(imap_server)
        print('Conexão IMAP estabelecida')
        
        # Tenta autenticar
        print('Tentando login...')
        mail.login(email, password)
        print('Login bem-sucedido')
        
        # Lista pastas
        print('Listando pastas...')
        resp, data = mail.list()
        if resp == 'OK':
            print(f'Listou {len(data)} pastas')
            for i, folder in enumerate(data[:5]):  # Mostrar apenas primeiras 5 pastas
                print(f"  Pasta {i}: {folder}")
            
        # Fecha conexão
        mail.logout()
        print('Conexão encerrada')
        return True
    except Exception as e:
        print(f'Erro: {str(e)}')
        return False

# O script espera argumentos de linha de comando: email, senha e provedor
if len(sys.argv) != 4:
    print("Uso: python test_imap.py email senha provedor")
    print("Exemplo: python test_imap.py meuemail@gmail.com minhasenha gmail")
    sys.exit(1)

email = sys.argv[1]
password = sys.argv[2]
provider = sys.argv[3]

test_imap(email, password, provider)
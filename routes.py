import os
import logging
import time
import io
import re
from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, jsonify, session, send_file, abort
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from forms import LoginForm, RegistrationForm, EmailAccountForm, ReportForm, DeleteReportForm, UserAdminForm, DeleteUserForm, SupportTicketForm, SupportMessageForm, CloseTicketForm, ProfileForm, OrganizationForm
import tempfile
import json
from functools import wraps
from wtforms.validators import DataRequired, Length
from wtforms import SelectField, BooleanField
from PIL import Image, ImageFilter

from app import app, db
from models import User, EmailAccount, EmailData, Report, SupportTicket, SupportMessage, Organization
from email_service import EmailService
from report_generator import ReportGenerator
from simple_deep_report import SimpleDeepReport
from dalltor_report import DalltorReport

# Handler para erro 403 (Acesso Proibido)
@app.errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html', now=datetime.now()), 403

logger = logging.getLogger(__name__)

# Decorador para verificar se o usuário é administrador
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)  # Acesso proibido
        return f(*args, **kwargs)
    return decorated_function

# Home/Index route
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    # Redirecionar para página de login
    return redirect(url_for('login'))

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    register_form = RegistrationForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            # Verificação de domínio de e-mail para associação automática a organizações
            if not user.organization_id:
                # Extrair domínio do e-mail do usuário
                email_parts = user.email.split('@')
                if len(email_parts) == 2:
                    domain = email_parts[1]
                    # Procurar organização pelo domínio
                    org = Organization.query.filter_by(domain=domain).first()
                    if org:
                        user.organization_id = org.id
                        db.session.commit()
                        logger.info(f"Usuário {user.id} associado automaticamente à organização {org.id} pelo domínio")
                    elif Organization.query.count() == 1:
                        # Se só existe uma organização, associa a ela
                        org = Organization.query.first()
                        user.organization_id = org.id
                        db.session.commit()
                        
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('E-mail ou senha inválidos', 'danger')
    
    return render_template('login.html', form=form, register_form=register_form, now=datetime.now())

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegistrationForm()
    
    # Preencher as opções de organizações
    organizations = Organization.query.all()
    form.organization_id.choices = [(org.id, org.name) for org in organizations]
    
    if form.validate_on_submit():
        # Check if user already exists
        if User.query.filter_by(email=form.email.data).first():
            flash('E-mail já cadastrado', 'danger')
            return render_template('login.html', form=LoginForm(), register_form=form, active_tab='register', now=datetime.now())
        
        # Se o usuário marcou para criar uma nova organização
        organization_id = None
        if form.create_organization.data and form.organization_name.data:
            # Criar nova organização
            org = Organization(
                name=form.organization_name.data,
                domain=form.organization_domain.data,
                primary_color="#3498db"  # Cor padrão
            )
            db.session.add(org)
            db.session.flush()  # Para obter o ID da organização antes do commit
            organization_id = org.id
            logger.info(f"Nova organização criada: {org.name} (ID: {org.id})")
        elif form.organization_id.data:
            # Usar organização selecionada
            organization_id = form.organization_id.data
        else:
            # Se não informou organização, tentar encontrar pelo domínio do email
            email_parts = form.email.data.split('@')
            if len(email_parts) == 2:
                domain = email_parts[1]
                org = Organization.query.filter_by(domain=domain).first()
                if org:
                    organization_id = org.id
            
            # Se ainda não tem organização, usar a primeira disponível
            if organization_id is None and organizations:
                organization_id = organizations[0].id
        
        # Create new user
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            organization_id=organization_id
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Cadastro realizado com sucesso! Por favor, faça login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('login.html', form=LoginForm(), register_form=form, active_tab='register', now=datetime.now())

# Main application routes
@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's email accounts
    email_accounts = EmailAccount.query.filter_by(user_id=current_user.id).all()
    
    # Get stats for the dashboard
    email_count = EmailData.query.join(EmailAccount).filter(EmailAccount.user_id == current_user.id).count()
    
    # Get recent reports
    recent_reports = Report.query.filter_by(user_id=current_user.id).order_by(Report.created_at.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                           email_accounts=email_accounts, 
                           email_count=email_count,
                           recent_reports=recent_reports,
                           now=datetime.now())

@app.route('/add_email_account', methods=['GET', 'POST'])
@login_required
def add_email_account():
    form = EmailAccountForm()
    if form.validate_on_submit():
        # Create new email account
        email_account = EmailAccount(
            user_id=current_user.id,
            provider=form.provider.data,
            email_address=form.email_address.data,
            access_token=form.password.data,  # Armazenando a senha como access_token para funcionar com o EmailService
            refresh_token=form.refresh_token.data if hasattr(form, 'refresh_token') else None
        )
        db.session.add(email_account)
        db.session.commit()
        
        flash('Conta de e-mail adicionada com sucesso!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('add_email_account.html', form=form, now=datetime.now())

@app.route('/delete_email_account', methods=['POST'])
@login_required
def delete_email_account():
    account_id = request.form.get('account_id')
    
    if not account_id:
        flash('Nenhuma conta selecionada para exclusão.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Verify the account belongs to the current user
    account = EmailAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    
    try:
        # Get account email for confirmation message
        email_address = account.email_address
        
        # Delete the account (cascade will delete associated emails)
        db.session.delete(account)
        db.session.commit()
        
        flash(f'A conta {email_address} foi excluída com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Erro ao excluir conta de email: {str(e)}")
        flash(f'Erro ao excluir conta de email: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/email_folders/<int:account_id>')
@login_required
def email_folders(account_id):
    # Verify the account belongs to the current user
    account = EmailAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    
    # Get folders from the email service
    try:
        email_service = EmailService(account)
        # Force refresh para obter as pastas mais recentes
        folders = email_service.get_folders(force_refresh=True)
    except Exception as e:
        logger.exception("Error retrieving email folders")
        folders = account.get_folders() if account.folders else []
        flash(f'Erro ao obter pastas de e-mail: {str(e)}', 'danger')
    
    # Se não houver pastas, use as pastas padrão da demonstração
    if not folders:
        folders = [
            {"name": "Caixa de Entrada", "path": "INBOX"},
            {"name": "Enviados", "path": "Sent"},
            {"name": "Rascunhos", "path": "Drafts"},
            {"name": "Lixeira", "path": "Trash"},
            {"name": "Spam", "path": "Junk"},
            {"name": "Importante", "path": "Important"},
            {"name": "Arquivados", "path": "Archive"},
            {"name": "Trabalho", "path": "Work"},
            {"name": "Pessoal", "path": "Personal"}
        ]
        account.folders = folders
        db.session.commit()
        flash('Usando pastas de demonstração para visualização', 'info')
    
    return render_template('email_folders.html', account=account, folders=folders, now=datetime.now())

@app.route('/sync_emails/<int:account_id>', methods=['GET', 'POST'])
@login_required
def sync_emails(account_id):
    # Verify the account belongs to the current user
    account = EmailAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    
    # Get folder from request parameters if available
    folder = request.args.get('folder', 'INBOX')
    
    # Verificar se deve forçar limpeza dos emails existentes
    force_clear = request.args.get('force_clear', 'false') == 'true'
    
    # Verificar se deve sincronizar todas as pastas
    sync_all_folders = request.args.get('sync_all_folders', 'false') == 'true'
    
    try:
        # Create email service instance
        email_service = EmailService(account)
        
        # Sempre atualizar a lista de pastas com force_refresh
        folders = email_service.get_folders(force_refresh=True)
        logger.info(f"Pastas atualizadas para a conta {account.id}: {len(folders)} pastas")
        
        # Se solicitado, limpar emails existentes para forçar resincronização
        if force_clear:
            if sync_all_folders:
                logger.info(f"Limpando TODOS os emails existentes da conta {account.id}")
                email_count = EmailData.query.filter_by(account_id=account.id).count()
                EmailData.query.filter_by(account_id=account.id).delete()
                db.session.commit()
                flash(f'Todos os emails existentes foram limpos para sincronização completa ({email_count} emails)', 'info')
            else:
                logger.info(f"Limpando emails existentes da conta {account.id} da pasta {folder}")
                email_count = EmailData.query.filter_by(account_id=account.id, folder=folder).count()
                EmailData.query.filter_by(account_id=account.id, folder=folder).delete()
                db.session.commit()
                flash(f'Emails existentes da pasta "{folder}" foram limpos para sincronização completa ({email_count} emails)', 'info')
        
        total_synced = 0
        
        if sync_all_folders:
            # Sincronizar todas as pastas, exceto pastas de lixo e spam
            excluded_folders = ['Lixeira', 'Trash', 'Spam', 'Junk', '[Gmail]/Spam', '[Gmail]/Lixeira']
            
            for folder_info in folders:
                folder_path = folder_info.get('path')
                folder_name = folder_info.get('name')
                
                # Pular pastas excluídas
                if folder_path in excluded_folders or folder_name in excluded_folders:
                    logger.info(f"Pulando pasta excluída: {folder_path}")
                    continue
                
                # Pular a pasta "[Gmail]" que é uma pasta de contêiner, não uma pasta real
                if folder_path == '[Gmail]':
                    continue
                
                try:
                    logger.info(f"Sincronizando pasta: {folder_path}")
                    num_synced = email_service.sync_emails(folder=folder_path)
                    total_synced += num_synced
                    logger.info(f"Sincronizados {num_synced} emails da pasta {folder_path}")
                except Exception as e:
                    logger.error(f"Erro ao sincronizar pasta {folder_path}: {str(e)}")
                    flash(f'Erro ao sincronizar pasta "{folder_name}": {str(e)}', 'warning')
            
            flash(f'Sincronização de todas as pastas concluída. {total_synced} novos emails sincronizados.', 'success')
        else:
            # Sincronizar apenas a pasta selecionada
            # Sincronizar emails (apenas do mês atual)
            num_synced = email_service.sync_emails(folder=folder)
            total_synced = num_synced
            
            # Se chegou aqui, a sincronização foi bem-sucedida
            if num_synced > 0:
                flash(f'Sincronização concluída com sucesso! {num_synced} emails importados.', 'success')
            else:
                flash(f'Sincronização concluída, mas nenhum email novo encontrado na pasta {folder}.', 'info')
            
            # Update last synced timestamp
            account.last_synced = datetime.utcnow()
            db.session.commit()
            
    except ValueError as ve:
        if "Não foi possível acessar a conta de email" in str(ve):
            # Senha incorreta ou não disponível
            logger.warning("Falha na sincronização: credenciais inválidas ou ausentes")
            
            # Informar o usuário de que as credenciais são necessárias
            flash(f'Não foi possível acessar a conta de email. Por favor, verifique suas credenciais.', 'danger')
            
            # Update last failed timestamp
            account.last_synced = datetime.utcnow()
            db.session.commit()
        else:
            raise
    except Exception as e:
        logger.exception("Erro ao sincronizar emails")
        flash(f'Erro ao sincronizar emails: {str(e)}', 'danger')
    
    # Redirect to the referring page if available
    next_page = request.args.get('next') or url_for('dashboard', sync='completed')
    return redirect(next_page)

@app.route('/check_new_emails/<int:account_id>')
@login_required
def check_new_emails(account_id):
    """Verifica se há novos emails em uma conta específica (chamada via AJAX)"""
    # Verificar se a conta pertence ao usuário atual
    account = EmailAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    
    try:
        # Criar serviço de email
        email_service = EmailService(account)
        
        # Verificar por novos emails na caixa de entrada
        has_new_inbox_emails = email_service.check_for_new_emails(folder='INBOX')
        
        # Verificar também pasta de enviados
        has_new_sent_emails = email_service.check_for_new_emails(folder='[Gmail]/Sent Mail' if account.provider == 'gmail' else 'Sent')
        
        # Se encontrou novos emails em qualquer pasta
        has_new_emails = has_new_inbox_emails or has_new_sent_emails
        
        # Atualizar timestamp de última sincronização se novos emails foram encontrados
        if has_new_emails:
            account.last_synced = datetime.utcnow()
            db.session.commit()
        
        # Retornar resultado como JSON
        return jsonify({
            'success': True,
            'has_new_emails': has_new_emails,
            'inbox_updated': has_new_inbox_emails,
            'sent_updated': has_new_sent_emails,
            'account_id': account_id,
            'last_synced': account.last_synced.strftime('%d/%m/%Y %H:%M:%S') if account.last_synced else None
        })
        
    except Exception as e:
        logger.exception(f"Erro ao verificar novos emails: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/sync-all-folders/<int:account_id>')
@login_required
def sync_all_folders(account_id):
    """Sincroniza todas as pastas de emails de uma conta"""
    # Verificar se a conta pertence ao usuário atual
    account = EmailAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    
    # Verificar se deve limpar emails existentes antes da sincronização
    force_clear = request.args.get('force_clear', 'false') == 'true'
    
    try:
        # Criar instância do serviço de email
        email_service = EmailService(account)
        
        # Atualizar a lista de pastas com force_refresh para obter todas as pastas atualizadas
        folders = email_service.get_folders(force_refresh=True)
        logger.info(f"Iniciando sincronização de todas as pastas para a conta {account.id}: {len(folders)} pastas")
        
        # Se solicitado, limpar todos os emails existentes para esta conta
        if force_clear:
            logger.info(f"Limpando TODOS os emails existentes da conta {account.id}")
            email_count = EmailData.query.filter_by(account_id=account.id).count()
            EmailData.query.filter_by(account_id=account.id).delete()
            db.session.commit()
            flash(f'Todos os emails existentes foram limpos para sincronização completa ({email_count} emails)', 'info')
        
        total_synced = 0
        synced_folders = []
        failed_folders = []
        skipped_folders = []
        
        # Lista de pastas a ignorar
        ignored_folders = ['[Gmail]/Spam', 'Spam', 'Lixo Eletrônico', 'Junk']
        
        # Sincronizar cada pasta
        for folder_info in folders:
            folder_path = folder_info['path']
            folder_name = folder_info['name']
            
            # Verificar se é uma pasta que deve ser ignorada
            if any(ignored_folder in folder_path for ignored_folder in ignored_folders):
                logger.info(f"Ignorando pasta de spam: {folder_name} ({folder_path})")
                skipped_folders.append(folder_name)
                continue
                
            try:
                logger.info(f"Sincronizando pasta: {folder_name} ({folder_path})")
                num_synced = email_service.sync_emails(folder=folder_path)
                total_synced += num_synced
                
                if num_synced > 0:
                    synced_folders.append(f"{folder_name} ({num_synced})")
                
            except Exception as folder_error:
                logger.error(f"Erro ao sincronizar pasta {folder_name}: {str(folder_error)}")
                failed_folders.append(folder_name)
                continue  # Continuar com a próxima pasta mesmo se esta falhar
        
        # Atualizar timestamp de última sincronização
        account.last_synced = datetime.utcnow()
        db.session.commit()
        
        # Feedback ao usuário
        if total_synced > 0:
            if failed_folders:
                flash(f'Sincronização parcial concluída! {total_synced} emails importados de {len(synced_folders)} pastas. ' +
                      f'Falha em {len(failed_folders)} pastas. {len(skipped_folders)} pastas de spam ignoradas.', 'warning')
            else:
                flash(f'Sincronização completa concluída! {total_synced} emails importados de {len(synced_folders)} pastas. ' +
                      f'{len(skipped_folders)} pastas de spam ignoradas.', 'success')
        else:
            if failed_folders:
                flash(f'Sincronização concluída, mas nenhum email novo encontrado. ' +
                      f'Falha em {len(failed_folders)} pastas. {len(skipped_folders)} pastas de spam ignoradas.', 'warning')
            else:
                flash(f'Sincronização concluída, mas nenhum email novo encontrado. ' +
                      f'{len(skipped_folders)} pastas de spam ignoradas.', 'info')
        
        # Adicionar parâmetro para indicar sincronização concluída
        # Isso vai fazer o front-end forçar a atualização do cache
        return redirect(url_for('dashboard', sync='completed'))
        
    except Exception as e:
        logger.exception(f"Erro ao sincronizar todas as pastas: {str(e)}")
        flash(f'Erro ao sincronizar emails: {str(e)}', 'danger')
        return redirect(url_for('dashboard', sync='completed'))

@app.route('/reports')
@login_required
def reports():
    # Get all reports for the current user
    user_reports = Report.query.filter_by(user_id=current_user.id).order_by(Report.created_at.desc()).all()
    form = DeleteReportForm()  # Form para CSRF token
    
    return render_template('reports.html', reports=user_reports, now=datetime.now(), form=form)

@app.route('/create_report', methods=['GET', 'POST'])
@login_required
def create_report():
    form = ReportForm()
    
    # Populate the form's email account choices
    accounts = EmailAccount.query.filter_by(user_id=current_user.id).all()
    form.email_account.choices = [(account.id, account.email_address) for account in accounts]
    
    # For AJAX calls to get folders
    if request.method == 'GET' and 'get_folders' in request.args and request.args.get('account_id'):
        account_id = int(request.args.get('account_id'))
        account = EmailAccount.query.filter_by(id=account_id, user_id=current_user.id).first()
        if account:
            try:
                # Get real-time folders from the email service, forcing refresh
                email_service = EmailService(account)
                # Forçar atualização das pastas em tempo real
                folders = email_service.get_folders(force_refresh=True)
                return jsonify({'folders': folders})
            except Exception as e:
                logger.exception('Erro ao obter pastas em tempo real')
                # Fallback to stored folders if real-time retrieval fails
                folders = account.get_folders()
                return jsonify({'folders': folders})
        return jsonify({'folders': [{'name': 'Caixa de Entrada', 'path': 'INBOX'}]})
    
    # Set default folder choices
    selected_account = None
    if request.method == 'GET' and form.email_account.data:
        selected_account = EmailAccount.query.filter_by(id=form.email_account.data, user_id=current_user.id).first()
    elif request.method == 'POST' and form.email_account.data:
        selected_account = EmailAccount.query.filter_by(id=form.email_account.data, user_id=current_user.id).first()
    
    if selected_account:
        # Sempre usar as pastas armazenadas para evitar problemas de autenticação
        folders = selected_account.get_folders()
        
        # Se houver pastas armazenadas, usar
        if folders:
            logger.info(f"Usando pastas armazenadas para a conta {selected_account.email_address}")
        # Se não houver pastas armazenadas, adicionar a pasta padrão
        else:
            logger.info(f"Não há pastas armazenadas para a conta {selected_account.email_address}, usando pasta padrão")
            folders = [{'name': 'Caixa de Entrada', 'path': 'INBOX'}]
            
        form.email_folder.choices = [(folder['path'], folder['name']) for folder in folders]
    else:
        # Se não houver conta selecionada, usar pasta padrão
        form.email_folder.choices = [('INBOX', 'Caixa de Entrada')]
    
    if form.validate_on_submit():
        # Create new report
        report = Report(
            user_id=current_user.id,
            name=form.name.data,
            type=form.report_type.data,
            date_range_start=form.date_range_start.data,
            date_range_end=form.date_range_end.data,
            filters=json.dumps({
                'email_account_id': form.email_account.data,
                'email_folder': form.email_folder.data,
                'include_sent': form.include_sent.data,
                'include_received': form.include_received.data,
                'search_term': form.search_term.data if form.search_term.data else None,
                'group_by': form.group_by.data if form.report_type.data == 'detailed' else 'none'
            })
        )
        db.session.add(report)
        db.session.commit()
        
        flash('Relatório criado com sucesso!', 'success')
        return redirect(url_for('view_report', report_id=report.id))
    
    return render_template('create_report.html', form=form, now=datetime.now())

@app.route('/view_report/<int:report_id>')
@login_required
def view_report(report_id):
    # Verify the report belongs to the current user
    report = Report.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()
    
    # Parse filters
    filters = json.loads(report.filters) if report.filters else {}
    
    # Get email account if specified
    email_account = None
    if filters.get('email_account_id'):
        email_account = EmailAccount.query.filter_by(id=filters['email_account_id']).first()
    
    # Generate report data
    report_generator = ReportGenerator(report)
    report_data = report_generator.generate()
    
    return render_template('view_report.html', 
                          report=report, 
                          report_data=report_data, 
                          email_account=email_account,
                          now=datetime.now())

@app.route('/export_report/<int:report_id>/<format>')
@login_required
def export_report(report_id, format):
    # Verify the report belongs to the current user
    report = Report.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()
    
    try:
        # Log início da exportação para depuração
        logger.info(f"Iniciando exportação de relatório id={report_id}, formato={format}, usuário={current_user.id}")
        
        # Log do tipo de relatório 
        logger.info(f"Tipo de relatório: {report.type}, nome: {report.name}")
        
        # Verifica filtros configurados
        if report.filters:
            filters = json.loads(report.filters)
            logger.info(f"Filtros configurados: {filters}")
            
        # Verificar a organização do usuário para determinar o template a ser usado
        user_org = None
        if current_user.organization_id:
            user_org = Organization.query.get(current_user.organization_id)
            
        # Selecionar o gerador de relatórios apropriado com base na organização
        use_custom_template = False
        template_name = "padrão"
        
        # Forçar o uso do template Dalltor para todos os relatórios
        # Isso é temporário para diagnosticar o problema
        logger.info(f"FORÇA BRUTA: Usando template Dalltor para todas as organizações durante teste")
        report_generator = DalltorReport(report)
        use_custom_template = True
        template_name = "Dalltor"
        
        if format.lower() == 'pdf':
            # Generate PDF file
            logger.info(f"Iniciando geração do arquivo PDF com template {template_name if use_custom_template else 'padrão'}")
            pdf_file = report_generator.export_pdf()
            logger.info(f"PDF gerado com sucesso: {pdf_file}")
            
            return send_file(
                pdf_file,
                as_attachment=True,
                download_name=f"relatorio_{report.id}_{datetime.now().strftime('%Y%m%d')}.pdf",
                mimetype='application/pdf'
            )
        elif format.lower() == 'csv':
            # Generate CSV file
            logger.info("Iniciando geração do arquivo CSV")
            csv_file = report_generator.export_csv()
            logger.info(f"CSV gerado com sucesso: {csv_file}")
            
            return send_file(
                csv_file,
                as_attachment=True,
                download_name=f"relatorio_{report.id}_{datetime.now().strftime('%Y%m%d')}.csv",
                mimetype='text/csv'
            )
        else:
            logger.warning(f"Formato de exportação inválido: {format}")
            flash('Formato de exportação inválido', 'danger')
            return redirect(url_for('view_report', report_id=report.id))
            
    except Exception as e:
        logger.exception(f"Erro durante a exportação do relatório: {str(e)}")
        flash(f'Erro ao exportar relatório: {str(e)}', 'danger')
        return redirect(url_for('view_report', report_id=report.id))

@app.route('/delete_report/<int:report_id>', methods=['POST'])
@login_required
def delete_report(report_id):
    # Se for admin, pode excluir qualquer relatório; se não, apenas os próprios
    if current_user.is_admin:
        report = Report.query.filter_by(id=report_id).first_or_404()
    else:
        # Verificar se o relatório pertence ao usuário atual
        report = Report.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()
    
    try:
        # Registrar a exclusão
        logger.info(f"Excluindo relatório id={report_id}, nome='{report.name}', usuário={report.user_id} por {current_user.id} (admin: {current_user.is_admin})")
        
        # Obter a página de origem para redirecionamento após exclusão
        origem = request.form.get('origem') or request.args.get('origem', 'reports')
        
        # Excluir o relatório
        db.session.delete(report)
        db.session.commit()
        
        flash('Relatório excluído com sucesso', 'success')
        # Redirecionar para a página correta com base na origem
        if origem == 'admin_reports':
            return redirect(url_for('admin_reports'))
        else:
            return redirect(url_for('reports'))
        
    except Exception as e:
        logger.exception(f"Erro durante a exclusão do relatório: {str(e)}")
        flash(f'Erro ao excluir relatório: {str(e)}', 'danger')
        
        # Redirecionar para a página correta em caso de erro
        if origem == 'admin_reports':
            return redirect(url_for('admin_reports'))
        else:
            return redirect(url_for('reports'))

# API routes for AJAX calls
@app.route('/api/email_stats')
@login_required
def email_stats():
    """
    Rota altamente otimizada para fornecer estatísticas de e-mail para visualização em gráficos.
    Retorna dados em formato JSON para uso em JavaScript.
    
    Otimizações implementadas:
    - Consultas SQL consolidadas
    - Uso de subconsultas para reduzir número de operações
    - Limites mais restritivos para dados processados
    - Processamento mais eficiente de grandes conjuntos de dados
    - Cache na sessão para evitar recalcular em cada requisição
    - Expiração inteligente de cache baseada em última sincronização
    """
    # Performance melhoria: registrar início para medição de tempo
    start_time = time.time()
    
    # Verificar atualização através de parâmetro force_refresh
    force_refresh = request.args.get('force_refresh', '0') == '1'
    account_id = request.args.get('account_id', type=int)
    
    # Chave de cache única para a sessão atual
    cache_key = f"email_stats_{current_user.id}_{account_id or 'all'}"
    
    # Verificar se há dados em cache e se são válidos
    if not force_refresh and cache_key in session:
        cache_data = session[cache_key]
        cache_time = cache_data.get('timestamp', 0)
        # Verificar se o cache ainda é válido (8 minutos)
        if time.time() - cache_time < 480:  # 8 minutos = 480 segundos
            # Atualizar estatísticas de uso do cache (para depuração)
            logger.info(f"Usando dados em cache para email_stats (economia de {time.time() - start_time:.2f}s)")
            return jsonify(cache_data['data'])
            
    # Se chegou aqui, precisamos gerar os dados
    # Get email stats for dashboard charts
    account_id = request.args.get('account_id', type=int)
    
    # Define o escopo da consulta base (com ou sem filtragem por conta)
    # Criar a subconsulta das contas do usuário (usada em várias consultas)
    user_account_ids = db.session.query(EmailAccount.id).filter(EmailAccount.user_id == current_user.id).subquery()
    
    if account_id:
        # Verify the account belongs to the current user
        account = EmailAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
        base_query = EmailData.query.filter(EmailData.account_id == account_id)
    else:
        base_query = EmailData.query.filter(EmailData.account_id.in_(user_account_ids))
    
    # Reduzir o conjunto de dados para processamento mais rápido
    # Limitando aos últimos 30 dias para todas as consultas
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    base_query = base_query.filter(EmailData.date >= thirty_days_ago)
    
    # Estrutura para armazenar estatísticas
    stats = {
        'daily_counts': [],
        'sent_vs_received': {'sent': 0, 'received': 0},
        'top_senders': [],
        'top_recipients': [],
        'folders_data': [],
        'hourly_activity': [],
        'contact_data': [],
        'word_cloud': [],
        'email_metrics': {},
        'activity_heatmap': []
    }
    
    # Consultas consolidadas para enviados vs recebidos (uma consulta só)
    sent_received_counts = db.session.query(
        EmailData.is_sent, db.func.count(EmailData.id).label('count')
    ).filter(
        EmailData.account_id == account_id if account_id else
        EmailData.account_id.in_(user_account_ids)
    ).group_by(
        EmailData.is_sent
    ).all()
    
    # Processar resultados da consulta consolidada
    for is_sent, count in sent_received_counts:
        if is_sent:
            stats['sent_vs_received']['sent'] = count
        else:
            stats['sent_vs_received']['received'] = count
    
    # Cálculo de contagem diária otimizado (uma consulta com agrupamento)
    today = datetime.utcnow().date()
    seven_days_ago = today - timedelta(days=6)
    
    daily_counts = db.session.query(
        db.func.date(EmailData.date).label('day'),
        db.func.count(EmailData.id).label('count')
    ).filter(
        EmailData.account_id == account_id if account_id else 
        EmailData.account_id.in_(user_account_ids),
        EmailData.date >= seven_days_ago
    ).group_by(
        db.func.date(EmailData.date)
    ).all()
    
    # Processamento mais eficiente para preparar dados diários
    daily_data = {day.strftime('%Y-%m-%d'): count for day, count in daily_counts}
    
    # Preenchimento dos 7 dias (incluindo zeros para dias sem emails)
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        stats['daily_counts'].append({
            'date': date_str,
            'count': daily_data.get(date_str, 0)
        })
    
    # Top senders - limitados a 5 para melhor performance
    top_senders = db.session.query(
        EmailData.sender, db.func.count(EmailData.id).label('count')
    ).filter(
        EmailData.account_id == account_id if account_id else
        EmailData.account_id.in_(user_account_ids),
        EmailData.is_sent == False
    ).group_by(
        EmailData.sender
    ).order_by(
        db.desc('count')
    ).limit(5).all()
    
    stats['top_senders'] = [{'sender': sender, 'count': count} for sender, count in top_senders]
    
    # Top recipients (limited to sent emails) - Otimizado para reduzir dados transferidos
    # Limitamos a busca a apenas 100 emails mais recentes para reduzir carga
    sent_emails = EmailData.query.filter(
        EmailData.account_id == account_id if account_id else 
        EmailData.account_id.in_(user_account_ids),
        EmailData.is_sent == True
    ).order_by(EmailData.date.desc()).limit(100).all()
    
    recipient_counts = {}
    
    for email in sent_emails:
        if email.recipients:
            for recipient in email.recipients.split(','):
                recipient = recipient.strip()
                if recipient:
                    recipient_counts[recipient] = recipient_counts.get(recipient, 0) + 1
    
    top_recipients = sorted(recipient_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    stats['top_recipients'] = [{'recipient': recipient, 'count': count} for recipient, count in top_recipients]
    
    # E-mails por pasta - Otimizado para usar a mesma subconsulta
    folder_counts = db.session.query(
        EmailData.folder, db.func.count(EmailData.id).label('count')
    ).filter(
        EmailData.account_id == account_id if account_id else
        EmailData.account_id.in_(user_account_ids),
        # Limitando a período recente para melhorar desempenho
        EmailData.date >= thirty_days_ago
    ).group_by(
        EmailData.folder
    ).order_by(
        db.desc('count')
    ).limit(5).all()
    
    stats['folders_data'] = [{'folder': folder or 'INBOX', 'count': count} for folder, count in folder_counts]
    
    # NOVOS GRÁFICOS:
    
    # 1. Atividade por hora do dia - Consulta SQL otimizada e limitada no tempo
    # Fazer uma única consulta agrupada em vez de 24 consultas individuais
    hour_stats = db.session.query(
        db.func.extract('hour', EmailData.date).label('hour'),
        db.func.count().label('count')
    ).filter(
        EmailData.account_id == account_id if account_id else 
        EmailData.account_id.in_(user_account_ids),
        EmailData.date != None,
        # Limitando dados aos últimos 30 dias
        EmailData.date >= thirty_days_ago
    ).group_by(
        db.func.extract('hour', EmailData.date)
    ).all()
    
    # Inicializar com zeros
    hours = list(range(24))
    hourly_counts = [0] * 24
    
    # Preencher com os resultados reais
    for hour, count in hour_stats:
        hourly_counts[int(hour)] = count
        
    # Formatar dados para o gráfico
    stats['hourly_activity'] = [
        {'hour': f"{hour:02d}:00", 'count': count} 
        for hour, count in zip(hours, hourly_counts)
    ]
    
    # 2. Dados para gráfico de bolhas (contatos mais ativos)
    # Juntar os dados de remetentes e destinatários
    contacts_data = {}
    
    # Processar os principais remetentes
    for sender_data in stats['top_senders']:
        sender = sender_data['sender']
        if sender not in contacts_data:
            contacts_data[sender] = {'label': sender, 'sent': 0, 'received': sender_data['count']}
        else:
            contacts_data[sender]['received'] = sender_data['count']
    
    # Processar os principais destinatários
    for recipient_data in stats['top_recipients']:
        recipient = recipient_data['recipient']
        if recipient not in contacts_data:
            contacts_data[recipient] = {'label': recipient, 'sent': recipient_data['count'], 'received': 0}
        else:
            contacts_data[recipient]['sent'] = recipient_data['count']
    
    # Converter para lista e selecionar os 10 contatos com maior volume total
    contact_list = list(contacts_data.values())
    contact_list.sort(key=lambda x: x['sent'] + x['received'], reverse=True)
    stats['contact_data'] = contact_list[:10]
    
    # 3. Nuvem de palavras baseada em assuntos de e-mails
    # Lista de palavras comuns que devem ser ignoradas (stop words em português)
    stop_words = ['de', 'a', 'o', 'que', 'e', 'do', 'da', 'em', 'um', 'para', 'com', 'não', 'uma', 'os', 'no', 
                 'se', 'na', 'por', 'mais', 'as', 'dos', 'como', 'mas', 'foi', 'ao', 'ele', 'das', 'seu',
                 're', 'fw', 'fwd', 'res']
    
    # Buscar assuntos de e-mails
    email_subjects = db.session.query(EmailData.subject).filter(
        EmailData.account_id == account_id if account_id else 
        EmailData.account_id.in_(
            db.session.query(EmailAccount.id).filter(EmailAccount.user_id == current_user.id)
        ),
        EmailData.subject != None,
        EmailData.subject != ''
    ).all()
    
    # Processar palavras
    word_counts = {}
    for subject_tuple in email_subjects:
        subject = subject_tuple[0]
        if subject:
            # Converter para minúsculas, remover pontuação e dividir em palavras
            words = ''.join(c if c.isalnum() else ' ' for c in subject.lower()).split()
            for word in words:
                if len(word) > 2 and word not in stop_words:  # Ignorar palavras muito curtas e stop words
                    word_counts[word] = word_counts.get(word, 0) + 1
    
    # Converter para o formato da nuvem de palavras
    word_cloud_data = [{'text': word, 'weight': count} for word, count in word_counts.items()]
    word_cloud_data.sort(key=lambda x: x['weight'], reverse=True)
    stats['word_cloud'] = word_cloud_data[:50]  # Limitar a 50 palavras mais frequentes
    
    # 4. Métricas para gráfico de radar
    # Coletar dados de diferentes métricas para visualização em radar
    
    # Calcular a proporção de emails com assunto
    total_emails = EmailData.query.filter(
        EmailData.account_id == account_id if account_id else 
        EmailData.account_id.in_(
            db.session.query(EmailAccount.id).filter(EmailAccount.user_id == current_user.id)
        )
    ).count()
    
    emails_with_subject = EmailData.query.filter(
        EmailData.account_id == account_id if account_id else 
        EmailData.account_id.in_(
            db.session.query(EmailAccount.id).filter(EmailAccount.user_id == current_user.id)
        ),
        EmailData.subject != None,
        EmailData.subject != ''
    ).count()
    
    # Calcular comprimento médio dos e-mails (em caracteres)
    avg_email_length = db.session.query(db.func.avg(db.func.length(EmailData.body_text))).filter(
        EmailData.account_id == account_id if account_id else 
        EmailData.account_id.in_(
            db.session.query(EmailAccount.id).filter(EmailAccount.user_id == current_user.id)
        ),
        EmailData.body_text != None
    ).scalar() or 0
    
    # Normalizar para escala de 0-100
    avg_length_normalized = min(100, max(0, int(avg_email_length / 500 * 100))) if avg_email_length else 0
    
    # Calcular tempos de resposta (assumindo thread de e-mail pelo assunto)
    response_times = []
    subjects = db.session.query(EmailData.subject, EmailData.date).filter(
        EmailData.account_id == account_id if account_id else 
        EmailData.account_id.in_(
            db.session.query(EmailAccount.id).filter(EmailAccount.user_id == current_user.id)
        ),
        EmailData.subject != None,
        EmailData.subject != ''
    ).order_by(EmailData.subject, EmailData.date).all()
    
    subject_timestamps = {}
    for subject, date in subjects:
        # Remover prefixos comuns de resposta/encaminhamento
        clean_subject = re.sub(r'^(RE|FW|FWD|RES):\s*', '', subject, flags=re.IGNORECASE)
        if clean_subject in subject_timestamps:
            # Calcular diferença em horas
            diff = (date - subject_timestamps[clean_subject]).total_seconds() / 3600
            if 0 < diff < 168:  # Considerar apenas respostas dentro de uma semana
                response_times.append(diff)
        else:
            subject_timestamps[clean_subject] = date
    
    # Calcular tempo médio de resposta em horas (ou 0 se não houver dados)
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    # Normalizar tempo de resposta (menor é melhor, max 100 para respostas imediatas)
    response_time_score = max(0, min(100, int(100 - (avg_response_time * 5)))) if avg_response_time > 0 else 0
    
    # Diversidade de contatos (baseado no número total de contatos únicos)
    # Otimização: usar consulta SQL direta para contar contatos únicos, em vez de Python
    unique_contacts_query = db.session.query(
        db.func.count(db.func.distinct(EmailData.sender))
    ).filter(
        EmailData.account_id == account_id if account_id else 
        EmailData.account_id.in_(
            db.session.query(EmailAccount.id).filter(EmailAccount.user_id == current_user.id)
        ),
        EmailData.sender != None,
        EmailData.sender != ''
    ).scalar()
    
    unique_contacts = unique_contacts_query or 0
    
    # Normalizar diversidade (máximo 100 para 50+ contatos)
    diversity_score = min(100, max(0, int(unique_contacts * 2)))
    
    # Proporção de e-mails com formato HTML (mais rico)
    emails_with_html = EmailData.query.filter(
        EmailData.account_id == account_id if account_id else 
        EmailData.account_id.in_(
            db.session.query(EmailAccount.id).filter(EmailAccount.user_id == current_user.id)
        ),
        EmailData.body_html != None,
        EmailData.body_html != ''
    ).count()
    
    html_ratio = int((emails_with_html / total_emails * 100) if total_emails > 0 else 0)
    
    # Adicionar métricas ao resultado
    stats['email_metrics'] = {
        'labels': [
            'Taxa de Resposta',
            'Comprimento Médio',
            'Diversidade de Contatos',
            'Uso de Assunto',
            'Conteúdo Rico (HTML)'
        ],
        'datasets': [
            {
                'label': 'Sua Pontuação',
                'data': [
                    response_time_score,
                    avg_length_normalized,
                    diversity_score,
                    int(emails_with_subject / total_emails * 100) if total_emails > 0 else 0,
                    html_ratio
                ]
            }
        ]
    }
    
    # 5. Mapa de calor de atividade por dia da semana e hora - Otimizado
    # Otimização: fazer uma única consulta SQL grupada e com dados recentes
    heatmap_counts = db.session.query(
        db.func.extract('dow', EmailData.date).label('day'),
        db.func.extract('hour', EmailData.date).label('hour'),
        db.func.count().label('count')
    ).filter(
        EmailData.account_id == account_id if account_id else 
        EmailData.account_id.in_(user_account_ids),
        EmailData.date != None,
        # Limitando a dados recentes para melhor performance
        EmailData.date >= thirty_days_ago
    ).group_by(
        db.func.extract('dow', EmailData.date),
        db.func.extract('hour', EmailData.date)
    ).all()
    
    # Inicializar matriz para o mapa de calor (7 dias x 24 horas) com zeros
    heatmap_matrix = [[0 for _ in range(24)] for _ in range(7)]
    
    # Preencher com os resultados reais
    for day_of_week, hour, count in heatmap_counts:
        day_index = int(day_of_week)
        # SQLite/Postgres: ajustar para que 0=Segunda, 6=Domingo
        day_index = (day_index - 1) % 7  
        hour_index = int(hour)
        
        if 0 <= day_index < 7 and 0 <= hour_index < 24:
            heatmap_matrix[day_index][hour_index] = count
    
    # Converter matriz 2D para array unidimensional 
    # (formato esperado pelo gráfico de calor - linha por linha)
    heatmap_data = []
    for day_data in heatmap_matrix:
        heatmap_data.extend(day_data)
    
    stats['activity_heatmap'] = heatmap_data
    
    # Registrar tempo de execução para logs de performance
    execution_time = time.time() - start_time
    logger.info(f"Tempo de execução email_stats: {execution_time:.2f} segundos")
    
    # Armazenar os dados em cache na sessão para usos futuros
    # Sempre armazenar em cache, mesmo consultas rápidas, para minimizar carga no servidor
    session[cache_key] = {
        'data': stats,
        'timestamp': time.time()
    }
    # Garantir que a sessão será salva
    session.modified = True
    logger.info(f"Dados armazenados em cache para {cache_key}")
    
    return jsonify(stats)
    
# Rotas de Administração
@app.route('/admin/organizations')
@login_required
@admin_required
def admin_organizations():
    """Lista e gerencia as organizações do sistema"""
    # Apenas superadmins podem ver todas as organizações
    if not current_user.is_superadmin:
        # Se for admin comum, redireciona para o dashboard
        return redirect(url_for('admin_dashboard'))
    
    organizations = Organization.query.order_by(Organization.name).all()
    
    return render_template('admin/organizations.html',
                          organizations=organizations,
                          now=datetime.now())

@app.route('/admin/organizations/new', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_new_organization():
    """Cria uma nova organização"""
    # Apenas superadmins podem criar organizações
    if not current_user.is_superadmin:
        abort(403)
    
    form = OrganizationForm()
    
    if form.validate_on_submit():
        # Verificar se já existe uma organização com este nome
        if Organization.query.filter_by(name=form.name.data).first():
            flash('Já existe uma organização com este nome.', 'danger')
            return render_template('admin/new_organization.html', form=form, now=datetime.now())
        
        # Processar e salvar o logo, se fornecido
        logo_path = None
        if form.logo.data:
            try:
                # Verificar se a pasta de upload existe
                upload_folder = os.path.join(app.static_folder, 'uploads/logos')
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                
                # Gerar nome único para o arquivo
                timestamp = int(time.time())
                safe_name = secure_filename(form.name.data)
                filename = f"logo_{safe_name}_{timestamp}.png"
                filepath = os.path.join(upload_folder, filename)
                
                # Salvar o arquivo
                form.logo.data.save(filepath)
                logo_path = f'uploads/logos/{filename}'
                
            except Exception as e:
                logger.exception(f"Erro ao salvar logo: {str(e)}")
                flash(f"Erro ao processar o logo: {str(e)}", 'warning')
        
        # Criar nova organização
        organization = Organization(
            name=form.name.data,
            domain=form.domain.data,
            primary_color=form.primary_color.data,
            logo=logo_path
        )
        db.session.add(organization)
        db.session.commit()
        
        flash('Organização criada com sucesso!', 'success')
        return redirect(url_for('admin_organizations'))
    
    return render_template('admin/new_organization.html', 
                          form=form,
                          now=datetime.now())

@app.route('/admin/organizations/edit/<int:org_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_organization(org_id):
    """Edita uma organização existente"""
    # Verificar permissões
    if not current_user.is_superadmin:
        abort(403)
    
    organization = Organization.query.get_or_404(org_id)
    form = OrganizationForm(obj=organization)
    
    if form.validate_on_submit():
        # Processar e salvar o logo, se fornecido
        if form.logo.data:
            try:
                # Verificar se a pasta de upload existe
                upload_folder = os.path.join(app.static_folder, 'uploads/logos')
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                
                # Gerar nome único para o arquivo
                timestamp = int(time.time())
                safe_name = secure_filename(form.name.data)
                filename = f"logo_{safe_name}_{timestamp}.png"
                filepath = os.path.join(upload_folder, filename)
                
                # Salvar o arquivo
                form.logo.data.save(filepath)
                organization.logo = f'uploads/logos/{filename}'
                
            except Exception as e:
                logger.exception(f"Erro ao salvar logo: {str(e)}")
                flash(f"Erro ao processar o logo: {str(e)}", 'warning')
        
        # Atualizar dados da organização
        organization.name = form.name.data
        organization.domain = form.domain.data
        organization.primary_color = form.primary_color.data
        db.session.commit()
        
        flash('Organização atualizada com sucesso!', 'success')
        return redirect(url_for('admin_organizations'))
    
    return render_template('admin/edit_organization.html', 
                          form=form, 
                          organization=organization,
                          now=datetime.now())

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Página principal do painel administrativo"""
    # Dados específicos da organização se for admin normal
    if not current_user.is_superadmin:
        # Filtrar dados apenas da organização do admin
        users_count = User.query.filter_by(organization_id=current_user.organization_id).count()
        email_accounts_count = EmailAccount.query.join(User).filter(
            User.organization_id == current_user.organization_id
        ).count()
        emails_count = EmailData.query.join(EmailAccount).join(User).filter(
            User.organization_id == current_user.organization_id
        ).count()
        reports_count = Report.query.join(User).filter(
            User.organization_id == current_user.organization_id
        ).count()
        
        # Últimos usuários cadastrados da organização
        recent_users = User.query.filter_by(organization_id=current_user.organization_id).order_by(
            User.created_at.desc()
        ).limit(5).all()
        
        # Obter detalhes da organização
        organization = Organization.query.filter_by(id=current_user.organization_id).first()
        
        return render_template('admin/dashboard.html', 
                          users_count=users_count,
                          email_accounts_count=email_accounts_count,
                          emails_count=emails_count,
                          reports_count=reports_count,
                          recent_users=recent_users,
                          organization=organization,
                          is_superadmin=False,
                          now=datetime.now())
    else:
        # Superadmin vê dados de todas as organizações
        users_count = User.query.count()
        email_accounts_count = EmailAccount.query.count()
        emails_count = EmailData.query.count()
        reports_count = Report.query.count()
        
        # Últimos usuários cadastrados (todos)
        recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
        
        # Contagem de organizações
        orgs_count = Organization.query.count()
        
        # Lista de organizações
        organizations = Organization.query.order_by(Organization.name).all()
        
        return render_template('admin/dashboard.html', 
                          users_count=users_count,
                          email_accounts_count=email_accounts_count,
                          emails_count=emails_count,
                          reports_count=reports_count,
                          recent_users=recent_users,
                          orgs_count=orgs_count,
                          organizations=organizations,
                          is_superadmin=True,
                          now=datetime.now())

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """Lista todos os usuários do sistema"""
    # Se for super admin, pode ver todos os usuários
    if current_user.is_superadmin:
        users = User.query.order_by(User.username).all()
    else:
        # Se for admin normal, só vê usuários da sua organização
        users = User.query.filter_by(organization_id=current_user.organization_id).order_by(User.username).all()
    
    organizations = Organization.query.order_by(Organization.name).all()
    delete_form = DeleteUserForm()
    
    return render_template('admin/users.html', 
                          users=users, 
                          organizations=organizations,
                          delete_form=delete_form,
                          is_superadmin=current_user.is_superadmin,
                          now=datetime.now())

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_user(user_id):
    """Edita um usuário existente"""
    user = User.query.get_or_404(user_id)
    
    # Admin normal só pode editar usuários da sua organização
    if not current_user.is_superadmin and user.organization_id != current_user.organization_id:
        abort(403)
    
    form = UserAdminForm(obj=user)
    
    # Preencher as opções de organizações
    organizations = Organization.query.order_by(Organization.name).all()
    form.organization_id.choices = [(org.id, org.name) for org in organizations]
    
    # Configurar valores iniciais
    if request.method == 'GET':
        form.organization_id.data = user.organization_id
        form.is_superadmin.data = user.is_superadmin if hasattr(user, 'is_superadmin') else False
    
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.is_admin = form.is_admin.data
        
        # Campos disponíveis apenas para superadmins
        if current_user.is_superadmin:
            # Definir a flag de superadmin
            user.is_superadmin = True if request.form.get('is_superadmin') == 'y' else False
            
            # Se for superadmin, não deve ter organização associada
            if user.is_superadmin:
                user.organization_id = None
            else:
                # Apenas usuários não-superadmin podem ter organização
                user.organization_id = form.organization_id.data
        
        # Atualizar senha apenas se fornecida
        if form.password.data:
            user.password_hash = generate_password_hash(form.password.data)
        
        db.session.commit()
        flash('Usuário atualizado com sucesso!', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin/edit_user.html', 
                          form=form, 
                          user=user,
                          now=datetime.now())

@app.route('/admin/users/new', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_new_user():
    """Cria um novo usuário"""
    form = UserAdminForm()
    
    # Adicionar campo de senha como obrigatório para usuários novos
    form.password.validators = [DataRequired(), Length(min=8)]
    
    # Para superadmin: adicionar todos os campos adicionais necessários
    if current_user.is_superadmin:
        # Se for superadmin, permite escolher qualquer organização
        organizations = Organization.query.order_by(Organization.name).all()
        form.organization_id.choices = [(org.id, org.name) for org in organizations]
        
        # Verificar se foi passada uma organização na URL
        org_id = request.args.get('org_id', type=int)
        if org_id and request.method == 'GET':
            form.organization_id.data = org_id
    
    if form.validate_on_submit():
        # Verificar se já existe um usuário com este email
        if User.query.filter_by(email=form.email.data).first():
            flash('Email já está em uso por outro usuário.', 'danger')
            return render_template('admin/new_user.html', form=form, now=datetime.now())
        
        # Definir a organização do usuário
        organization_id = None
        if current_user.is_superadmin and hasattr(form, 'organization_id'):
            organization_id = form.organization_id.data
        else:
            # Se não for superadmin, usa a organização do usuário atual
            organization_id = current_user.organization_id
        
        # Criar novo usuário
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            is_admin=form.is_admin.data,
            organization_id=organization_id
        )
        
        # Definir superadmin se o criador for superadmin e marcou a opção
        if current_user.is_superadmin:
            user.is_superadmin = True if request.form.get('is_superadmin') == 'y' else False
            
            # Se for superadmin, não deve ter organização associada
            if user.is_superadmin:
                user.organization_id = None
        
        db.session.add(user)
        db.session.commit()
        
        flash('Novo usuário criado com sucesso!', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin/new_user.html', 
                          form=form,
                          is_superadmin=current_user.is_superadmin,
                          now=datetime.now())

# Rota para mover usuários entre organizações
@app.route('/admin/users/move', methods=['POST'])
@login_required
@admin_required
def admin_move_user():
    """Move um usuário para outra organização"""
    # Verificar permissões - apenas superadmins podem mover usuários
    if not current_user.is_superadmin:
        abort(403)
        
    user_id = request.form.get('user_id', type=int)
    organization_id = request.form.get('organization_id', type=int)
    
    if not user_id or not organization_id:
        flash('Parâmetros inválidos para mover usuário.', 'danger')
        return redirect(url_for('admin_organizations'))
    
    # Buscar o usuário e a organização de destino
    user = User.query.get_or_404(user_id)
    organization = Organization.query.get_or_404(organization_id)
    
    # Obter o nome da organização atual para exibir na mensagem
    old_organization = Organization.query.get(user.organization_id)
    old_organization_name = old_organization.name if old_organization else "nenhuma"
    
    try:
        # Atualizar a organização do usuário
        user.organization_id = organization_id
        db.session.commit()
        
        flash(f'Usuário {user.username} movido com sucesso da organização {old_organization_name} para {organization.name}!', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Erro ao mover usuário: {str(e)}")
        flash(f'Erro ao mover usuário: {str(e)}', 'danger')
    
    return redirect(url_for('admin_organizations'))

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    """Exclui um usuário do sistema"""
    # Verificar se é admin normal e está tentando excluir usuário de outra organização
    user = User.query.get_or_404(user_id)
    
    if not current_user.is_superadmin and user.organization_id != current_user.organization_id:
        abort(403)
    
    # Não permitir exclusão do próprio usuário administrador
    if user.id == current_user.id:
        flash('Você não pode excluir sua própria conta de usuário.', 'danger')
        return redirect(url_for('admin_users'))
    
    # Executar a exclusão - sem verificação CSRF para facilitar operação
    try:
        username = user.username
        
        # Exclusão em cascade de todas as contas de email e emails
        db.session.delete(user)
        db.session.commit()
        
        flash(f'Usuário {username} excluído com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Erro ao excluir usuário: {str(e)}")
        flash(f'Erro ao excluir usuário: {str(e)}', 'danger')
    
    # Redirecionar de volta para a página de origem (lista de usuários ou lista de organizações)
    referer = request.headers.get('Referer', '')
    if 'admin/organizations' in referer:
        return redirect(url_for('admin_organizations'))
    else:
        return redirect(url_for('admin_users'))

@app.route('/admin/emails')
@login_required
@admin_required
def admin_emails():
    """Visualiza todos os emails de todos os usuários"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Iniciar a consulta padrão
    if current_user.is_superadmin:
        # Superadmin pode ver emails de todas as organizações
        emails_query = EmailData.query.join(EmailAccount).join(User).order_by(EmailData.date.desc())
        
        # Lista de usuários para o filtro (todos)
        users = User.query.order_by(User.username).all()
    else:
        # Admin normal só vê emails da sua organização
        emails_query = EmailData.query.join(EmailAccount).join(User).filter(
            User.organization_id == current_user.organization_id
        ).order_by(EmailData.date.desc())
        
        # Lista de usuários para o filtro (apenas da mesma organização)
        users = User.query.filter_by(organization_id=current_user.organization_id).order_by(User.username).all()
    
    # Filtro por usuário (opcional)
    user_id = request.args.get('user_id', type=int)
    if user_id:
        # Verificar se o usuário pode acessar este usuário
        user = User.query.get_or_404(user_id)
        if not current_user.is_superadmin and user.organization_id != current_user.organization_id:
            abort(403)  # Acesso negado se tentar acessar usuário de outra organização
            
        emails_query = emails_query.filter(EmailAccount.user_id == user_id)
    else:
        user = None
    
    # Aplicar paginação
    emails = emails_query.paginate(page=page, per_page=per_page)
    
    return render_template('admin/emails.html',
                          emails=emails,
                          users=users, 
                          current_user_filter=user,
                          is_superadmin=current_user.is_superadmin,
                          now=datetime.now())

@app.route('/admin/reports')
@login_required
@admin_required
def admin_reports():
    """Visualiza todos os relatórios de todos os usuários"""
    delete_form = DeleteReportForm()
    
    # Filtrar relatórios com base no tipo de administrador
    if current_user.is_superadmin:
        # Superadmin vê relatórios de todas as organizações
        reports = Report.query.join(User).order_by(Report.created_at.desc()).all()
    else:
        # Admin normal só vê relatórios da sua organização
        reports = Report.query.join(User).filter(
            User.organization_id == current_user.organization_id
        ).order_by(Report.created_at.desc()).all()
    
    return render_template('admin/reports.html',
                          reports=reports,
                          form=delete_form,
                          is_superadmin=current_user.is_superadmin,
                          now=datetime.now())

# Rotas de Suporte 
@app.route('/admin/support')
@login_required
@admin_required
def admin_support():
    """Página administrativa para gerenciar todos os tickets de suporte"""
    # Obter tickets de acordo com permissões de organização
    if current_user.is_superadmin:
        # Superadmin vê todos os tickets
        tickets_query = SupportTicket.query
    else:
        # Admin normal só vê tickets dos usuários da sua organização
        tickets_query = SupportTicket.query.join(User).filter(
            User.organization_id == current_user.organization_id
        )
    
    # Filtrar por status e ordenar
    open_tickets = tickets_query.filter_by(status='aberto').order_by(SupportTicket.updated_at.desc()).all()
    in_progress_tickets = tickets_query.filter_by(status='em_andamento').order_by(SupportTicket.updated_at.desc()).all()
    resolved_tickets = tickets_query.filter_by(status='resolvido').order_by(SupportTicket.updated_at.desc()).all()
    
    return render_template('admin/support.html',
                          open_tickets=open_tickets,
                          in_progress_tickets=in_progress_tickets,
                          resolved_tickets=resolved_tickets,
                          is_superadmin=current_user.is_superadmin,
                          now=datetime.now())

@app.route('/support')
@login_required
def support():
    """Página principal de suporte - lista os tickets do usuário"""
    tickets = SupportTicket.query.filter_by(user_id=current_user.id).order_by(SupportTicket.updated_at.desc()).all()
    
    # Se o usuário for admin, também ver tickets de outros usuários de acordo com permissões
    if current_user.is_admin:
        if current_user.is_superadmin:
            # Superadmin vê todos os tickets exceto os seus próprios (que já estão na lista acima)
            admin_tickets = SupportTicket.query.filter(
                SupportTicket.user_id != current_user.id
            ).order_by(SupportTicket.updated_at.desc()).all()
        else:
            # Admin normal só vê tickets de usuários da mesma organização
            admin_tickets = SupportTicket.query.join(User).filter(
                SupportTicket.user_id != current_user.id,
                User.organization_id == current_user.organization_id
            ).order_by(SupportTicket.updated_at.desc()).all()
    else:
        admin_tickets = []
    
    return render_template('support/index.html',
                           tickets=tickets,
                           admin_tickets=admin_tickets,
                           is_admin=current_user.is_admin,
                           is_superadmin=current_user.is_superadmin if current_user.is_admin else False,
                           now=datetime.now())

@app.route('/support/new', methods=['GET', 'POST'])
@login_required
def support_new():
    """Criar novo ticket de suporte"""
    form = SupportTicketForm()
    
    if form.validate_on_submit():
        # Criar novo ticket
        ticket = SupportTicket(
            user_id=current_user.id,
            subject=form.subject.data,
            status='aberto'
        )
        db.session.add(ticket)
        db.session.flush()  # Obter o ID do ticket antes do commit final
        
        # Adicionar a primeira mensagem
        message = SupportMessage(
            ticket_id=ticket.id,
            sender_id=current_user.id,
            message=form.message.data,
            read=False  # Não lida pelos administradores
        )
        db.session.add(message)
        db.session.commit()
        
        flash('Ticket de suporte criado com sucesso. Um administrador irá responder em breve.', 'success')
        return redirect(url_for('support_view', ticket_id=ticket.id))
    
    return render_template('support/new.html', form=form, now=datetime.now())

@app.route('/support/view/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
def support_view(ticket_id):
    """Visualizar um ticket de suporte específico"""
    # Verificar se o usuário é proprietário do ticket ou admin
    ticket = SupportTicket.query.get_or_404(ticket_id)
    
    # Verificar permissões
    if ticket.user_id != current_user.id:
        if not current_user.is_admin:
            abort(403)  # Acesso proibido para não admins
        
        # Para admins, verificar restrições de organização
        if not current_user.is_superadmin:
            # Admin normal só pode acessar tickets de usuários da mesma organização
            ticket_user = User.query.get(ticket.user_id)
            if ticket_user.organization_id != current_user.organization_id:
                abort(403)  # Acesso proibido para tickets de outras organizações
    
    # Formulário para nova mensagem
    form = SupportMessageForm()
    close_form = CloseTicketForm()
    close_form.ticket_id.data = ticket_id
    
    # Marcar mensagens como lidas
    messages = SupportMessage.query.filter_by(
        ticket_id=ticket_id,
        read=False
    ).filter(SupportMessage.sender_id != current_user.id).all()
    
    for message in messages:
        message.read = True
    db.session.commit()
    
    # Processar nova mensagem
    if form.validate_on_submit():
        message = SupportMessage(
            ticket_id=ticket_id,
            sender_id=current_user.id,
            message=form.message.data,
            read=False
        )
        
        # Se o ticket estava resolvido e o usuário enviou uma nova mensagem, reabri-lo
        if ticket.status == 'resolvido' and not current_user.is_admin:
            ticket.status = 'aberto'
            flash('O ticket foi reaberto com sua nova mensagem.', 'info')
        # Se o ticket estava aberto e um admin enviou mensagem, marcar como em andamento
        elif ticket.status == 'aberto' and current_user.is_admin:
            ticket.status = 'em_andamento'
        
        ticket.updated_at = datetime.utcnow()
        db.session.add(message)
        db.session.commit()
        
        flash('Mensagem enviada com sucesso!', 'success')
        return redirect(url_for('support_view', ticket_id=ticket_id))
    
    # Obter todas as mensagens
    messages = SupportMessage.query.filter_by(ticket_id=ticket_id).order_by(SupportMessage.created_at).all()
    
    return render_template('support/view.html',
                           ticket=ticket,
                           messages=messages,
                           form=form,
                           close_form=close_form,
                           now=datetime.now())

@app.route('/support/close', methods=['POST'])
@login_required
def support_close():
    """Fechar um ticket de suporte"""
    form = CloseTicketForm()
    
    if form.validate_on_submit():
        ticket_id = form.ticket_id.data
        ticket = SupportTicket.query.get_or_404(ticket_id)
        
        # Verificar permissões
        if ticket.user_id != current_user.id:
            if not current_user.is_admin:
                abort(403)  # Acesso proibido para não admins
            
            # Para admins, verificar restrições de organização
            if not current_user.is_superadmin:
                # Admin normal só pode acessar tickets de usuários da mesma organização
                ticket_user = User.query.get(ticket.user_id)
                if ticket_user.organization_id != current_user.organization_id:
                    abort(403)  # Acesso proibido para tickets de outras organizações
        
        ticket.status = 'resolvido'
        ticket.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('Ticket marcado como resolvido!', 'success')
        return redirect(url_for('support_view', ticket_id=ticket_id))
    else:
        flash('Erro ao fechar o ticket. Por favor, tente novamente.', 'danger')
        return redirect(url_for('support'))

# Rota de teste para o caso de mostrarmos na homepage   
@app.route('/test-tickets')
def test_tickets():
    """Rota para testar tickets sem precisar de login"""
    tickets = SupportTicket.query.all()
    result = []
    
    for ticket in tickets:
        result.append({
            'id': ticket.id,
            'subject': ticket.subject,
            'status': ticket.status,
            'unread_messages': SupportMessage.query.filter(
                SupportMessage.ticket_id == ticket.id,
                SupportMessage.read.is_(False)
            ).count()
        })
    
    return jsonify(result)
    
    
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Página de edição de perfil do usuário"""
    form = ProfileForm()
    
    # Preencher o formulário com os dados atuais do usuário
    if request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    
    if form.validate_on_submit():
        try:
            # Verificar se o usuário alterou a senha
            if form.current_password.data and form.new_password.data:
                # Verificar se a senha atual está correta
                if check_password_hash(current_user.password_hash, form.current_password.data):
                    current_user.password_hash = generate_password_hash(form.new_password.data)
                else:
                    flash('Senha atual incorreta', 'danger')
                    return render_template('profile.html', form=form, now=datetime.now())
            
            # Verificar se o nome de usuário já existe (se foi alterado)
            if form.username.data != current_user.username:
                existing_user = User.query.filter_by(username=form.username.data).first()
                if existing_user:
                    flash('Este nome de usuário já está em uso', 'danger')
                    return render_template('profile.html', form=form, now=datetime.now())
                current_user.username = form.username.data
            
            # Verificar se o email já existe (se foi alterado)
            if form.email.data != current_user.email:
                existing_email = User.query.filter_by(email=form.email.data).first()
                if existing_email:
                    flash('Este email já está em uso', 'danger')
                    return render_template('profile.html', form=form, now=datetime.now())
                current_user.email = form.email.data
            
            # Processar a imagem de perfil, se fornecida
            if form.profile_image.data:
                try:
                    # Verificar se a pasta de upload existe
                    upload_folder = os.path.join(app.static_folder, 'uploads')
                    if not os.path.exists(upload_folder):
                        os.makedirs(upload_folder)
                    
                    # Processar a imagem com Pillow para garantir boa qualidade
                    timestamp = int(time.time())
                    
                    # Vamos simplesmente usar o upload direto como arquivo final
                    # Isso evita processamento excessivo que pode degradar a qualidade
                    filename = secure_filename(f"profile_{current_user.id}_{timestamp}.png")
                    filepath = os.path.join(upload_folder, filename)
                    
                    # Salvamos o arquivo original
                    form.profile_image.data.save(filepath)
                    
                    print(f"Imagem salva diretamente em: {filepath}")
                    
                    # Vamos verificar se precisamos de processamento mínimo
                    # Apenas para validar que é uma imagem válida
                    try:
                        with Image.open(filepath) as img:
                            # Verificamos apenas se a imagem é válida
                            img_width, img_height = img.size
                            print(f"Imagem validada: {img_width}x{img_height}, formato: {img.format}, modo: {img.mode}")
                            
                            # Se a imagem for muito grande, aí sim redimensionamos
                            # Mas mantemos como PNG para evitar perda de qualidade
                            if img_width > 1200 or img_height > 1200:
                                print("Imagem muito grande, redimensionando")
                                
                                # Redimensionar para no máximo 1200x1200 mantendo proporção
                                img.thumbnail((1200, 1200), Image.LANCZOS if hasattr(Image, 'LANCZOS') else Image.ANTIALIAS)
                                
                                # Salvar de volta no mesmo local
                                img.save(filepath, format='PNG', compress_level=1)
                    except Exception as img_error:
                        print(f"Aviso: Falha ao validar imagem: {str(img_error)}")
                        # Continuamos mesmo se houver falha na validação
                    
                    # Atualizar o caminho da imagem no banco de dados
                    # Se já existia uma imagem anterior, registrar para remoção posterior
                    old_image_path = None
                    if current_user.profile_image:
                        old_image_path = os.path.join(app.static_folder, current_user.profile_image)
                    
                    # Atribuir o novo caminho da imagem
                    current_user.profile_image = f"uploads/{filename}"
                    
                    print(f"Imagem de perfil atualizada e otimizada: {current_user.profile_image}")
                    
                    # Remover a imagem antiga após confirmar que a nova foi salva
                    if old_image_path and os.path.exists(old_image_path) and old_image_path != filepath:
                        try:
                            os.remove(old_image_path)
                            print(f"Imagem antiga removida: {old_image_path}")
                        except Exception as e:
                            print(f"Erro ao remover imagem antiga: {str(e)}")
                except Exception as img_error:
                    print(f"Erro ao processar imagem de perfil: {str(img_error)}")
                    logger.exception(f"Erro ao processar imagem de perfil: {str(img_error)}")
                    flash('Erro ao processar imagem de perfil. Tente novamente com outra imagem.', 'warning')
            
            # Salvar alterações
            db.session.commit()
            flash('Perfil atualizado com sucesso', 'success')
            return redirect(url_for('profile'))
            
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Erro ao atualizar perfil: {str(e)}")
            flash(f'Erro ao atualizar perfil: {str(e)}', 'danger')
    
    return render_template('profile.html', form=form, now=datetime.now())

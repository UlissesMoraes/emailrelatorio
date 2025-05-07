import io
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timedelta
from collections import Counter

import pandas as pd
from bs4 import BeautifulSoup

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_CENTER

from app import db
from models import EmailAccount, EmailData, Report

# Configuração do logging
logger = logging.getLogger(__name__)


class ReportGenerator:
    def __init__(self, report):
        """Initialize the report generator with a report object"""
        self.report = report
    
    def generate(self):
        """Generate report data based on the report settings"""
        logger.info(f"Gerando relatório: {self.report.name}, tipo: {self.report.type}")
        
        # Default filter: Filter by report date range if available
        filters = self.report.filters or {}
        query = db.session.query(EmailData)
        
        # Verifica se filters é um dicionário antes de usá-lo
        if not isinstance(filters, dict):
            logger.warning(f"filters não é um dicionário: {type(filters)}")
            if isinstance(filters, str):
                try:
                    # Tenta converter string para dicionário
                    filters = json.loads(filters)
                    logger.info(f"Convertido filters para dicionário: {filters}")
                except Exception as e:
                    logger.error(f"Erro ao converter filters para dicionário: {e}")
                    filters = {}
            else:
                filters = {}
        
        # Filter by email account if specified
        account_id = None
        try:
            if isinstance(filters, dict) and filters.get('email_account_id'):
                account_id = filters.get('email_account_id')
                query = query.filter(EmailData.account_id == account_id)
            else:
                # If no specific account is selected, filter by user's accounts
                user_accounts = EmailAccount.query.filter_by(user_id=self.report.user_id).all()
                account_ids = [account.id for account in user_accounts]
                query = query.filter(EmailData.account_id.in_(account_ids))
        except Exception as e:
            logger.error(f"Erro ao filtrar por conta de email: {e}")
            # Fallback: filtrar por contas do usuário
            user_accounts = EmailAccount.query.filter_by(user_id=self.report.user_id).all()
            account_ids = [account.id for account in user_accounts]
            query = query.filter(EmailData.account_id.in_(account_ids))
        
        # Filter by email folder if specified
        try:
            if isinstance(filters, dict) and filters.get('email_folder'):
                folder = filters.get('email_folder')
                logger.info(f"Filtrando por pasta de email: {folder}")
                
                # Tratar casos especiais de pastas
                if folder and (folder.upper() == 'INBOX' or folder == 'Caixa de Entrada'):
                    # Considerar como INBOX qualquer pasta que contenha Inbox ou Caixa de Entrada (case insensitive)
                    query = query.filter(
                        db.or_(
                            EmailData.folder == folder,
                            EmailData.folder.ilike('%inbox%'),
                            EmailData.folder.ilike('%caixa%entrada%'),
                            EmailData.folder == None,  # E-mails sem pasta especificada
                            EmailData.folder == ''     # E-mails com pasta vazia
                        )
                    )
                elif folder and folder.startswith('[Gmail]/'):
                    # Detectar se é uma pasta "Todos os e-mails" - tratamento especial
                    if "todos" in folder.lower():
                        # Caso especial: Para "Todos os e-mails", vamos buscar de TODAS as pastas para essa conta
                        account_id = filters.get('email_account_id')
                        if account_id:
                            # Não aplicamos filtro de pasta, apenas limitamos a busca à conta selecionada
                            logger.info(f"Pasta especial 'Todos os e-mails' detectada - buscando em todas as pastas da conta {account_id}")
                            # Removemos qualquer filtro de pasta que possa ter sido aplicado anteriormente
                            query = db.session.query(EmailData).filter(EmailData.account_id == account_id)
                        else:
                            logger.warning("Pasta 'Todos os e-mails' detectada, mas nenhuma conta especificada")
                    else:
                        # Outras pastas do Gmail ainda recebem tratamento especial
                        query = query.filter(
                            db.or_(
                                EmailData.folder == folder,
                                EmailData.folder.ilike(f'%{folder}%')
                            )
                        )
                        logger.info(f"Filtrando por pasta especial Gmail: {folder}")
                        
                    # Verificar quantidade de emails após aplicar filtros para depuração
                    if filters.get('email_account_id'):
                        account_id = filters.get('email_account_id')
                        all_emails_count = db.session.query(EmailData.id).filter(EmailData.account_id == account_id).count()
                        logger.info(f"DEBUG - Total de emails na conta {account_id}: {all_emails_count}")
                    
                    count_exact = db.session.query(EmailData.id).filter(EmailData.folder == folder).count()
                    count_like = db.session.query(EmailData.id).filter(EmailData.folder.ilike(f'%{folder}%')).count()
                    logger.info(f"DEBUG - Quantidade de emails com correspondência exata para {folder}: {count_exact}")
                    logger.info(f"DEBUG - Quantidade de emails com correspondência parcial para {folder}: {count_like}")
                else:
                    # Para outras pastas, fazer correspondência exata
                    query = query.filter(EmailData.folder == folder)
        except Exception as e:
            logger.error(f"Erro ao filtrar por pasta de email: {e}")
            # Se houver erro no filtro de pasta, não aplicar nenhum filtro
        
        # Filter by date range
        if self.report.date_range_start:
            query = query.filter(EmailData.date >= self.report.date_range_start)
        if self.report.date_range_end:
            # Add one day to include the end date fully
            end_date = self.report.date_range_end + timedelta(days=1)
            query = query.filter(EmailData.date < end_date)
        
        # Filter by search term if specified
        try:
            if isinstance(filters, dict) and filters.get('search_term'):
                search_term = f"%{filters.get('search_term')}%"
                query = query.filter(
                    (EmailData.subject.ilike(search_term)) |
                    (EmailData.body_text.ilike(search_term)) |
                    (EmailData.sender.ilike(search_term)) |
                    (EmailData.recipients.ilike(search_term))
                )
        except Exception as e:
            logger.error(f"Erro ao filtrar por termo de busca: {e}")
        
        # Filter sent/received emails
        try:
            include_flags = []
            if isinstance(filters, dict):
                if filters.get('include_sent'):
                    include_flags.append(True)
                if filters.get('include_received'):
                    include_flags.append(False)
            
            if include_flags:
                query = query.filter(EmailData.is_sent.in_(include_flags))
        except Exception as e:
            logger.error(f"Erro ao filtrar emails enviados/recebidos: {e}")
        
        # Execute query
        emails = query.order_by(EmailData.date.desc()).all()
        
        # Generate report based on type
        if self.report.type == 'summary':
            data = self._generate_summary_report(emails)
        else:
            data = self._generate_detailed_report(emails)
        
        return data
    
    def _generate_summary_report(self, emails):
        """Generate a summary report"""
        data = {}
        
        # Total counts
        total_emails = len(emails)
        total_sent = sum(1 for email in emails if email.is_sent)
        total_received = total_emails - total_sent
        
        data['total_emails'] = total_emails
        data['total_sent'] = total_sent
        data['total_received'] = total_received
        
        # Calculate metrics
        if not emails:
            return data
        
        # Top senders
        sender_counter = Counter()
        for email in emails:
            if not email.is_sent:  # Only count received emails for sender stats
                sender = email.sender or "Desconhecido"
                sender_counter[sender] += 1
        
        # Get top 10 senders
        top_senders = [{'sender': sender, 'count': count} for sender, count in sender_counter.most_common(10)]
        data['top_senders'] = top_senders
        
        # Top recipients
        recipient_counter = Counter()
        for email in emails:
            if email.is_sent:  # Only count sent emails for recipient stats
                recipients = email.recipients.split(',') if email.recipients else []
                for recipient in recipients:
                    if recipient.strip():
                        recipient_counter[recipient.strip()] += 1
        
        # Get top 10 recipients
        top_recipients = [{'recipient': recipient, 'count': count} for recipient, count in recipient_counter.most_common(10)]
        data['top_recipients'] = top_recipients
        
        # Common subjects
        subject_counter = Counter()
        for email in emails:
            if email.subject:
                # Remove common prefixes like Re:, Fwd:, etc.
                clean_subject = re.sub(r'^(Re:|Fwd:|FW:|RE:|FWD:)\s*', '', email.subject, flags=re.IGNORECASE)
                subject_counter[clean_subject] += 1
        
        # Get top 15 subjects
        common_subjects = [{'subject': subject, 'count': count} for subject, count in subject_counter.most_common(15)]
        data['common_subjects'] = common_subjects
        
        # Activity by date
        date_counter = Counter()
        for email in emails:
            if email.date:
                date_str = email.date.strftime('%Y-%m-%d')
                date_counter[date_str] += 1
        
        # Format dates to show only the most recent 30 days
        sorted_dates = sorted(date_counter.items())
        data['by_date'] = {date: count for date, count in sorted_dates[-30:]}
        
        # Ensure data is in the right format for volume over time charts
        if len(date_counter) > 0:
            data['volume_over_time'] = {
                'labels': list(data['by_date'].keys()),
                'values': list(data['by_date'].values())
            }
        
        # Calculate average emails per day
        if len(date_counter) > 0:
            data['avg_per_day'] = total_emails / len(date_counter)
        
        # Hourly activity
        hourly_activity = [0] * 24
        for email in emails:
            if email.date:
                hour = email.date.hour
                hourly_activity[hour] += 1
        
        data['hourly_activity'] = {
            'labels': [f"{h}:00" for h in range(24)],
            'values': hourly_activity
        }
        
        # Weekday activity
        weekday_activity = [0] * 7
        for email in emails:
            if email.date:
                weekday = email.date.weekday()
                weekday_activity[weekday] += 1
        
        data['weekday_activity'] = {
            'labels': ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'],
            'values': weekday_activity
        }
        
        # Proteger contra possíveis erros em common_subjects
        try:
            if 'common_subjects' in data and isinstance(data['common_subjects'], list):
                # Certifica que common_subjects é uma lista de dicionários
                common_subjects_dict = {}
                for item in data['common_subjects']:
                    if isinstance(item, dict) and 'subject' in item and 'count' in item:
                        common_subjects_dict[item['subject']] = item['count']
                
                # Criar common_words a partir do dicionário
                data['common_words'] = [
                    {'text': k, 'weight': v} 
                    for k, v in sorted(common_subjects_dict.items(), key=lambda x: x[1], reverse=True)
                ][:50]
            else:
                # Se não houver dados válidos, cria uma lista vazia
                data['common_words'] = []
        except Exception as e:
            logger.error(f"Erro ao processar common_words: {str(e)}")
            data['common_words'] = []
        
        return data
    
    def _generate_detailed_report(self, emails):
        """Generate a detailed report"""
        emails_data = []
        processed_message_ids = set()  # Para rastrear message_ids já processados
        
        # Logging para depuração
        logger.info(f"Gerando relatório detalhado com {len(emails)} emails.")
        
        for email in emails:
            # Verifica se o message_id já foi processado para evitar duplicatas
            if email.message_id in processed_message_ids:
                continue
            
            processed_message_ids.add(email.message_id)
            
            # Formatação da data para exibição
            date_str = ""
            if email.date:
                date_str = email.date.strftime('%d/%m/%Y %H:%M')
            
            # Log para depuração
            logger.info(f"Processando email ID {email.id}, Assunto: {email.subject}, Pasta: {email.folder}")
            
            # Dados do email para o relatório
            email_data = {
                'id': email.id,
                'subject': email.subject,
                'sender': email.sender,
                'recipients': email.recipients,
                'cc': email.cc,
                'date': date_str,
                'body_text': email.body_text,
                'body_html': email.body_html,
                'is_sent': email.is_sent,
                'folder': email.folder
            }
            emails_data.append(email_data)
        
        # Ordenar emails por data decrescente (mais recentes primeiro)
        emails_data.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # Aplicar limite de 40 emails
        emails_data = emails_data[:40]
        
        return {
            'emails': emails_data,
            'total': len(emails_data)
        }
    
    def export_pdf(self):
        """Export the report as a PDF file with simplified formatting"""
        try:
            # Generate report data
            report_data = self.generate()
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_path = temp_file.name
            
            # Configure styles
            styles = getSampleStyleSheet()
            
            # Create the document
            doc = SimpleDocTemplate(
                temp_path, 
                pagesize=A4,
                rightMargin=1.5*cm, 
                leftMargin=1.5*cm,
                topMargin=2*cm, 
                bottomMargin=2*cm
            )
            
            # Elements to add to the PDF
            elements = []
            
            # Add title
            if self.report.type == 'summary':
                title = f"Relatório Resumido: {self.report.name}"
            else:
                title = f"Relatório Detalhado: {self.report.name}"
                
            elements.append(Paragraph(title, styles['Title']))
            
            # Add date range
            if self.report.date_range_start and self.report.date_range_end:
                start_date = self.report.date_range_start.strftime('%d/%m/%Y')
                end_date = self.report.date_range_end.strftime('%d/%m/%Y')
                elements.append(Paragraph(f"Período: {start_date} a {end_date}", styles['Normal']))
            
            elements.append(Spacer(1, 0.5*cm))
            
            # Add content based on report type
            if self.report.type == 'summary':
                # Estatísticas básicas
                elements.append(Paragraph("Estatísticas Gerais", styles['Heading1']))
                elements.append(Paragraph(f"Total de e-mails: {report_data.get('total_emails', 0)}", styles['Normal']))
                elements.append(Paragraph(f"E-mails enviados: {report_data.get('total_sent', 0)}", styles['Normal']))
                elements.append(Paragraph(f"E-mails recebidos: {report_data.get('total_received', 0)}", styles['Normal']))
                
                if 'avg_per_day' in report_data:
                    elements.append(Paragraph(f"Média diária: {report_data['avg_per_day']:.1f}", styles['Normal']))
                
                elements.append(Spacer(1, 0.5*cm))
                
                # Principais remetentes
                if report_data.get('top_senders'):
                    elements.append(Paragraph("Principais Remetentes", styles['Heading2']))
                    
                    # Criar dados para tabela
                    senders_data = [["Remetente", "Quantidade"]]
                    for sender in report_data.get('top_senders', [])[:10]:
                        senders_data.append([sender.get('sender', ''), str(sender.get('count', 0))])
                    
                    # Criar tabela
                    if len(senders_data) > 1:
                        table = Table(senders_data, colWidths=[12*cm, 3*cm])
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                            ('ALIGN', (-1, 1), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ]))
                        elements.append(table)
                    else:
                        elements.append(Paragraph("Nenhum dado disponível", styles['Normal']))
                    
                    elements.append(Spacer(1, 0.5*cm))
                
                # Principais destinatários
                if report_data.get('top_recipients'):
                    elements.append(Paragraph("Principais Destinatários", styles['Heading2']))
                    
                    # Criar dados para tabela
                    recipients_data = [["Destinatário", "Quantidade"]]
                    for recipient in report_data.get('top_recipients', [])[:10]:
                        recipients_data.append([recipient.get('recipient', ''), str(recipient.get('count', 0))])
                    
                    # Criar tabela
                    if len(recipients_data) > 1:
                        table = Table(recipients_data, colWidths=[12*cm, 3*cm])
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                            ('ALIGN', (-1, 1), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ]))
                        elements.append(table)
                    else:
                        elements.append(Paragraph("Nenhum dado disponível", styles['Normal']))
                    
                    elements.append(Spacer(1, 0.5*cm))
                
                # Assuntos comuns
                if report_data.get('common_subjects'):
                    elements.append(Paragraph("Assuntos Comuns", styles['Heading2']))
                    
                    # Criar dados para tabela
                    subjects_data = [["Assunto", "Quantidade"]]
                    for subject in report_data.get('common_subjects', [])[:15]:
                        subjects_data.append([subject.get('subject', '')[:50], str(subject.get('count', 0))])
                    
                    # Criar tabela
                    if len(subjects_data) > 1:
                        table = Table(subjects_data, colWidths=[12*cm, 3*cm])
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                            ('ALIGN', (-1, 1), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ]))
                        elements.append(table)
                    else:
                        elements.append(Paragraph("Nenhum dado disponível", styles['Normal']))
            else:
                # Relatório detalhado - agrupado por remetente
                emails = report_data.get('emails', [])
                elements.append(Paragraph(f"Total de emails: {len(emails)}", styles['Normal']))
                elements.append(Spacer(1, 0.5*cm))
                
                # Se não temos emails, mostramos mensagem
                if not emails:
                    elements.append(Paragraph("Nenhum email encontrado para os critérios selecionados.", styles['Normal']))
                else:
                    # Verificar modo de agrupamento nas configurações do relatório
                    group_mode = 'sender'  # Modo padrão: agrupar por remetente
                    group_title = "Remetente"
                    
                    if hasattr(self.report, 'filters') and self.report.filters:
                        try:
                            filters = json.loads(self.report.filters)
                            if 'group_by' in filters:
                                group_mode = filters['group_by']
                        except:
                            # Se falhar a leitura de filtros, usa o padrão
                            logger.warning("Falha ao ler filtros de relatório para agrupamento")
                    
                    # Agrupar emails conforme configuração
                    emails_by_group = {}
                    
                    if group_mode == 'recipient':
                        # Agrupar por destinatário
                        group_title = "Destinatário"
                        for email in emails:
                            recipient = email.get('recipients', 'Destinatário Desconhecido')
                            # Se tiver múltiplos destinatários, pega o primeiro
                            if ',' in recipient:
                                recipient = recipient.split(',')[0].strip()
                            if recipient not in emails_by_group:
                                emails_by_group[recipient] = []
                            emails_by_group[recipient].append(email)
                    elif group_mode == 'none':
                        # Sem agrupamento - criar um único grupo "Todos os Emails"
                        emails_by_group = {"Todos os Emails": emails}
                        group_title = "Grupo"
                    else:
                        # Padrão: agrupar por remetente
                        for email in emails:
                            sender = email.get('sender', 'Remetente Desconhecido')
                            if sender not in emails_by_group:
                                emails_by_group[sender] = []
                            emails_by_group[sender].append(email)
                    
                    # Contagem total de grupos
                    total_groups = len(emails_by_group)
                    elements.append(Paragraph(f"Emails agrupados por {total_groups} {group_title.lower()}s", styles['Heading2']))
                    elements.append(Spacer(1, 0.5*cm))
                    
                    # Índice no início do documento para facilitar navegação
                    elements.append(Paragraph(f"Índice de {group_title}s:", styles['Heading2']))
                    
                    # Criar lista numerada de grupos
                    for idx, (group_name, group_emails) in enumerate(emails_by_group.items(), 1):
                        elements.append(Paragraph(
                            f"{idx}. {group_name} ({len(group_emails)} emails)",
                            styles['Normal']
                        ))
                    
                    elements.append(Spacer(1, 0.5*cm))
                    elements.append(PageBreak())
                    
                    # Agora, para cada grupo, processamos seus emails
                    for idx, (group_name, group_emails) in enumerate(emails_by_group.items(), 1):
                        # Título da seção deste grupo
                        elements.append(Paragraph(
                            f"{group_title} {idx}/{total_groups}: {group_name}",
                            styles['Heading1']
                        ))
                        elements.append(Paragraph(
                            f"Total de emails deste {group_title.lower()}: {len(group_emails)}",
                            styles['Normal']
                        ))
                        elements.append(Spacer(1, 0.5*cm))
                        
                        # Limitar número de emails por grupo (máximo 5 por grupo)
                        emails_to_show = group_emails[:5]
                        
                        # Para cada email deste grupo
                        for i, email in enumerate(emails_to_show):
                            # Adicionar uma quebra de página se não for o primeiro email do grupo
                            if i > 0:
                                elements.append(PageBreak())
                            
                            # Título do email
                            elements.append(Paragraph(f"Email #{i+1} de {group_name}", styles['Heading2']))
                            
                            # Metadados do email em formato de tabela
                            metadata = [
                                ["Assunto:", email.get('subject', '(Sem assunto)')],
                                ["De:", email.get('sender', 'Não especificado')],
                                ["Para:", email.get('recipients', 'Não especificado')],
                                ["Data:", email.get('date', '')],
                                ["Pasta:", email.get('folder', 'INBOX')]
                            ]
                            
                            # Se tiver CC, adiciona
                            if email.get('cc'):
                                metadata.append(["CC:", email.get('cc', '')])
                            
                            # Tabela de metadados
                            meta_table = Table(metadata, colWidths=[2.5*cm, 14*cm])
                            meta_table.setStyle(TableStyle([
                                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                                ('BACKGROUND', (0, 0), (0, -1), colors.whitesmoke),
                                ('PADDING', (0, 0), (-1, -1), 6),
                            ]))
                            
                            elements.append(meta_table)
                            elements.append(Spacer(1, 0.5*cm))
                            
                            # Título do conteúdo
                            elements.append(Paragraph("Conteúdo do Email:", styles['Heading3']))
                            
                            try:
                                # Extrair texto do corpo do email
                                body_text = email.get('body_text', '') or '(Sem conteúdo)'
                                
                                # Limpar o texto para evitar problemas
                                body_text = body_text.replace('\r', '')
                                
                                # Se o texto for muito longo, limitar para evitar problemas no PDF
                                if len(body_text) > 15000:
                                    body_text = body_text[:15000] + "\n\n[Conteúdo truncado... texto muito grande]"
                                
                                # Dividir por quebras de linha e criar parágrafos para cada bloco
                                # Agrupar linhas em blocos de parágrafos - divide por linhas em branco
                                paragraphs = re.split(r'\n\s*\n', body_text)
                                
                                for p in paragraphs:
                                    if p.strip():  # Se não for uma linha vazia
                                        # Substituir quebras de linha simples por <br/>
                                        p_with_breaks = p.replace('\n', '<br/>')
                                        elements.append(Paragraph(p_with_breaks, styles['Normal']))
                                        elements.append(Spacer(1, 0.2*cm))
                            
                            except Exception as content_error:
                                logger.error(f"Erro ao processar conteúdo: {str(content_error)}")
                                elements.append(Paragraph("Erro ao processar o conteúdo deste email.", styles['Normal']))
                            
                            # Adicionar espaço após o corpo do email
                            elements.append(Spacer(1, 0.8*cm))
                        
                        # Se tiver mais emails do que mostramos
                        if len(group_emails) > 5:
                            elements.append(Paragraph(
                                f"Nota: Exibindo apenas 5 dos {len(group_emails)} emails deste {group_title.lower()}. Para visualizar todos, acesse o sistema.",
                                styles['Normal']
                            ))
                        
                        # Adicionar quebra de página após cada remetente exceto o último
                        if idx < total_groups:
                            elements.append(PageBreak())
            
            # Add footer
            elements.append(Spacer(1, 1*cm))
            footer_text = f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | © Sistema de Gerenciamento de Relatórios"
            elements.append(Paragraph(footer_text, styles['Normal']))
            
            # Build the PDF
            doc.build(elements)
            
            return temp_path
            
        except Exception as e:
            logger.exception(f"Erro ao exportar PDF: {str(e)}")
            
            # Fallback para CSV se PDF falhar
            try:
                logger.info("Usando CSV como fallback para falha no PDF")
                return self.export_csv()
            except Exception as csv_error:
                logger.exception(f"Falha também no fallback CSV: {str(csv_error)}")
                raise e
    
    def export_csv(self):
        """Export the report as a CSV file"""
        try:
            # Generate report data - se ocorrer erro, tente uma versão simplificada
            try:
                report_data = self.generate()
            except Exception as gen_error:
                logger.error(f"Erro ao gerar dados do relatório: {str(gen_error)}")
                # Fallback simplificado - apenas um dicionário vazio
                report_data = {
                    'total_emails': 0,
                    'total_sent': 0,
                    'total_received': 0,
                    'emails': [],
                    'total': 0
                }
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w') as temp_file:
                # Create a string buffer para construir o CSV manualmente, sem pandas
                buffer = io.StringIO()
                
                # Adicionar cabeçalho básico
                buffer.write(f"Relatório de E-mails - {self.report.name}\n")
                buffer.write(f"Tipo: {self.report.type}\n")
                buffer.write(f"Exportado em: {datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')}\n\n")
                
                # Adicionar conteúdo com base no tipo de relatório
                if self.report.type == 'summary':
                    # Estatísticas básicas
                    buffer.write("ESTATÍSTICAS GERAIS\n")
                    buffer.write("Métrica,Quantidade\n")
                    buffer.write(f"Total de E-mails,{report_data.get('total_emails', 0)}\n")
                    buffer.write(f"E-mails Enviados,{report_data.get('total_sent', 0)}\n")
                    buffer.write(f"E-mails Recebidos,{report_data.get('total_received', 0)}\n\n")
                    
                    # Remetentes principais
                    buffer.write("PRINCIPAIS REMETENTES\n")
                    buffer.write("Remetente,Quantidade\n")
                    top_senders = report_data.get('top_senders', [])
                    if top_senders and isinstance(top_senders, list):
                        for sender in top_senders[:10]:
                            if isinstance(sender, dict):
                                sender_name = sender.get('sender', 'Desconhecido')
                                count = sender.get('count', 0)
                                buffer.write(f"{sender_name},{count}\n")
                    buffer.write("\n")
                    
                    # Destinatários principais
                    buffer.write("PRINCIPAIS DESTINATÁRIOS\n")
                    buffer.write("Destinatário,Quantidade\n")
                    top_recipients = report_data.get('top_recipients', [])
                    if top_recipients and isinstance(top_recipients, list):
                        for recipient in top_recipients[:10]:
                            if isinstance(recipient, dict):
                                recipient_name = recipient.get('recipient', 'Desconhecido')
                                count = recipient.get('count', 0)
                                buffer.write(f"{recipient_name},{count}\n")
                    buffer.write("\n")
                    
                    # Assuntos comuns
                    buffer.write("ASSUNTOS COMUNS\n")
                    buffer.write("Assunto,Quantidade\n")
                    common_subjects = report_data.get('common_subjects', [])
                    if common_subjects and isinstance(common_subjects, list):
                        for subject in common_subjects[:10]:
                            if isinstance(subject, dict):
                                subject_text = subject.get('subject', 'Sem assunto')
                                count = subject.get('count', 0)
                                buffer.write(f"{subject_text},{count}\n")
                    
                else:
                    # Relatório detalhado - agrupado por remetente
                    emails = report_data.get('emails', [])
                    total_emails = len(emails)
                    buffer.write(f"Total de e-mails: {total_emails}\n\n")
                    
                    # Verificar modo de agrupamento nas configurações do relatório
                    group_mode = 'sender'  # Modo padrão: agrupar por remetente
                    group_title = "Remetente"
                    
                    if hasattr(self.report, 'filters') and self.report.filters:
                        try:
                            filters = json.loads(self.report.filters)
                            if 'group_by' in filters:
                                group_mode = filters['group_by']
                        except:
                            # Se falhar a leitura de filtros, usa o padrão
                            logger.warning("Falha ao ler filtros de relatório para agrupamento em CSV")
                    
                    # Agrupar emails conforme configuração
                    emails_by_group = {}
                    
                    if group_mode == 'recipient':
                        # Agrupar por destinatário
                        group_title = "Destinatário"
                        for email in emails:
                            if not isinstance(email, dict):
                                continue
                                
                            recipient = email.get('recipients', 'Destinatário Desconhecido')
                            # Se tiver múltiplos destinatários, pega o primeiro
                            if ',' in recipient:
                                recipient = recipient.split(',')[0].strip()
                            if recipient not in emails_by_group:
                                emails_by_group[recipient] = []
                            emails_by_group[recipient].append(email)
                    elif group_mode == 'none':
                        # Sem agrupamento - criar um único grupo "Todos os Emails"
                        emails_by_group = {"Todos os Emails": emails}
                        group_title = "Grupo"
                    else:
                        # Padrão: agrupar por remetente
                        for email in emails:
                            if not isinstance(email, dict):
                                continue
                                
                            sender = email.get('sender', 'Remetente Desconhecido')
                            if sender not in emails_by_group:
                                emails_by_group[sender] = []
                            emails_by_group[sender].append(email)
                    
                    # Escrever índice de grupos
                    total_grupos = len(emails_by_group)
                    buffer.write(f"EMAILS AGRUPADOS POR {total_grupos} {group_title.upper()}S\n")
                    buffer.write("=" * 80 + "\n\n")
                    
                    # Adicionar índice
                    buffer.write(f"ÍNDICE DE {group_title.upper()}S:\n")
                    for idx, (group_name, group_emails) in enumerate(emails_by_group.items(), 1):
                        buffer.write(f"{idx}. {group_name} ({len(group_emails)} emails)\n")
                    buffer.write("\n\n")
                    
                    # Para cada grupo, adicionar seus emails
                    for idx, (group_name, group_emails) in enumerate(emails_by_group.items(), 1):
                        buffer.write("=" * 80 + "\n")
                        buffer.write(f"{group_title.upper()} {idx}/{total_grupos}: {group_name}\n")
                        buffer.write(f"Total de emails deste {group_title.lower()}: {len(group_emails)}\n")
                        buffer.write("-" * 80 + "\n\n")
                        
                        # Adicionar cada email deste grupo
                        for i, email in enumerate(group_emails[:5]):  # Limite de 5 emails por grupo
                            buffer.write("-" * 60 + "\n")
                            buffer.write(f"E-MAIL #{i+1} DE {group_name}\n")
                            buffer.write("-" * 60 + "\n")
                            
                            # Metadados do email
                            subject = email.get('subject', '(Sem assunto)')
                            sender = email.get('sender', 'Remetente Desconhecido')
                            recipients = email.get('recipients', '')
                            date = email.get('date', '')
                            folder = email.get('folder', '')
                            
                            buffer.write(f"Assunto: {subject}\n")
                            buffer.write(f"De: {sender}\n")
                            buffer.write(f"Para: {recipients}\n")
                            buffer.write(f"Data: {date}\n")
                            buffer.write(f"Pasta: {folder}\n")
                            
                            # Conteúdo do email
                            buffer.write("-" * 40 + "\n")
                            buffer.write("CORPO DO EMAIL:\n\n")
                            
                            # Extrair texto simples
                            body_text = email.get('body_text', '') or '(Sem conteúdo)'
                            # Limitar o tamanho para evitar possíveis problemas
                            if len(body_text) > 10000:
                                body_text = body_text[:10000] + "...\n[Conteúdo truncado]"
                                
                            buffer.write(body_text + "\n\n")
                        
                        # Se tiver mais emails do que o limite
                        if len(group_emails) > 5:
                            buffer.write(f"\nNota: Exibindo apenas 5 dos {len(group_emails)} emails deste {group_title.lower()}.\n")
                            
                        buffer.write("\n" + "=" * 80 + "\n\n")
                
                # Gravar o conteúdo no arquivo
                temp_file.write(buffer.getvalue())
            
            return temp_file.name
            
        except Exception as e:
            logger.exception(f"Erro ao exportar CSV: {str(e)}")
            
            # Criar um arquivo CSV extremamente simples em caso de falha
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w') as simple_file:
                    simple_file.write(f"Relatório de E-mails - {self.report.name}\n")
                    simple_file.write(f"Exportado em: {datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')}\n\n")
                    simple_file.write("Ocorreu um erro ao gerar o relatório completo.\n")
                    simple_file.write(f"Erro: {str(e)}\n")
                    return simple_file.name
            except Exception:
                # Se até isso falhar, levanta o erro original
                raise e
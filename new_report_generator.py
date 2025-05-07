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
        
        # Filter by email account if specified
        if 'email_account_id' in filters and filters.get('email_account_id'):
            account_id = filters.get('email_account_id')
            query = query.filter(EmailData.account_id == account_id)
        else:
            # If no specific account is selected, filter by user's accounts
            user_accounts = EmailAccount.query.filter_by(user_id=self.report.user_id).all()
            account_ids = [account.id for account in user_accounts]
            query = query.filter(EmailData.account_id.in_(account_ids))
        
        # Filter by email folder if specified
        if 'email_folder' in filters and filters.get('email_folder'):
            folder = filters.get('email_folder')
            query = query.filter(EmailData.folder == folder)
        
        # Filter by date range
        if self.report.date_range_start:
            query = query.filter(EmailData.date >= self.report.date_range_start)
        if self.report.date_range_end:
            # Add one day to include the end date fully
            end_date = self.report.date_range_end + timedelta(days=1)
            query = query.filter(EmailData.date < end_date)
        
        # Filter by search term if specified
        if 'search_term' in filters and filters.get('search_term'):
            search_term = f"%{filters.get('search_term')}%"
            query = query.filter(
                (EmailData.subject.ilike(search_term)) |
                (EmailData.body_text.ilike(search_term)) |
                (EmailData.sender.ilike(search_term)) |
                (EmailData.recipients.ilike(search_term))
            )
        
        # Filter sent/received emails
        include_flags = []
        if 'include_sent' in filters and filters.get('include_sent'):
            include_flags.append(True)
        if 'include_received' in filters and filters.get('include_received'):
            include_flags.append(False)
        
        if include_flags:
            query = query.filter(EmailData.is_sent.in_(include_flags))
        
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
        
        # Keep the common subjects
        data['common_words'] = [{'text': k, 'weight': v} for k, v in sorted(data['common_subjects'].items(), key=lambda x: x[1], reverse=True)][:50]
        
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
                # Relatório detalhado
                emails = report_data.get('emails', [])
                elements.append(Paragraph(f"Total de emails: {len(emails)}", styles['Normal']))
                elements.append(Spacer(1, 0.5*cm))
                
                # Tabela de emails
                if emails:
                    # Primeiro criamos apenas uma tabela com metadados (sem conteúdo do email)
                    data = [["#", "Assunto", "Remetente", "Data"]]
                    
                    for i, email in enumerate(emails):
                        # Limitar tamanho dos textos para evitar problemas
                        subject = email.get('subject', '(Sem assunto)')
                        if len(subject) > 40:
                            subject = subject[:37] + '...'
                        
                        sender = email.get('sender', 'Não especificado')
                        if len(sender) > 30:
                            sender = sender[:27] + '...'
                        
                        data.append([
                            str(i+1),
                            subject,
                            sender,
                            email.get('date', '')
                        ])
                    
                    # Criar tabela
                    table = Table(data, colWidths=[1*cm, 8*cm, 5*cm, 3*cm])
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('PADDING', (0, 0), (-1, -1), 6),
                    ]))
                    
                    elements.append(table)
                    elements.append(Spacer(1, 0.5*cm))
                    
                    # Adicionar uma nota sobre visualização detalhada
                    elements.append(Paragraph(
                        "Nota: Para visualizar o conteúdo completo dos emails, acesse-os diretamente no sistema.",
                        styles['Normal']
                    ))
                else:
                    elements.append(Paragraph("Nenhum email encontrado para os critérios selecionados.", styles['Normal']))
            
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
            # Generate report data
            report_data = self.generate()
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w') as temp_file:
                # Create a pandas DataFrame based on report type
                if self.report.type == 'summary':
                    # For summary reports, create multiple sections
                    buffer = io.StringIO()
                    
                    # Write header information
                    buffer.write(f"Relatório Resumido de E-mails - {self.report.name}\n")
                    buffer.write(f"Exportado em: {datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')}\n\n")
                    
                    # Estatísticas gerais
                    buffer.write("ESTATÍSTICAS GERAIS\n")
                    pd.DataFrame({
                        'Métrica': ['Total de E-mails', 'E-mails Enviados', 'E-mails Recebidos'],
                        'Quantidade': [
                            report_data.get('total_emails', 0),
                            report_data.get('total_sent', 0),
                            report_data.get('total_received', 0)
                        ]
                    }).to_csv(buffer, index=False)
                    
                    # Remetentes
                    buffer.write("\n\nPRINCIPAIS REMETENTES\n")
                    if report_data.get('top_senders'):
                        df = pd.DataFrame(report_data['top_senders'])
                        if 'sender' in df.columns and 'count' in df.columns:
                            df = df.rename(columns={'sender': 'Remetente', 'count': 'Quantidade'})
                        df.to_csv(buffer, index=False)
                    
                    # Destinatários
                    buffer.write("\n\nPRINCIPAIS DESTINATÁRIOS\n")
                    if report_data.get('top_recipients'):
                        df = pd.DataFrame(report_data['top_recipients'])
                        if 'recipient' in df.columns and 'count' in df.columns:
                            df = df.rename(columns={'recipient': 'Destinatário', 'count': 'Quantidade'})
                        df.to_csv(buffer, index=False)
                    
                    # Assuntos
                    buffer.write("\n\nASSUNTOS COMUNS\n")
                    if report_data.get('common_subjects'):
                        df = pd.DataFrame(report_data['common_subjects'])
                        if 'subject' in df.columns and 'count' in df.columns:
                            df = df.rename(columns={'subject': 'Assunto', 'count': 'Quantidade'})
                        df.to_csv(buffer, index=False)
                    
                    # Salvar no arquivo temporário
                    temp_file.write(buffer.getvalue())
                    
                else:
                    # For detailed reports, export only the essential email data
                    buffer = io.StringIO()
                    if report_data.get('emails'):
                        # Write header information
                        buffer.write(f"Relatório Detalhado de E-mails - {self.report.name}\n")
                        buffer.write(f"Total de e-mails: {report_data.get('total', 0)}\n")
                        buffer.write(f"Exportado em: {datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')}\n\n")
                        
                        # Write detailed content of each email directly
                        for i, email in enumerate(report_data.get('emails', [])):
                            buffer.write("=" * 80 + "\n")
                            buffer.write(f"E-MAIL #{i+1}\n")
                            buffer.write("-" * 80 + "\n")
                            buffer.write(f"Assunto: {email.get('subject', '(Sem assunto)')}\n")
                            buffer.write(f"De: {email.get('sender', '')}\n")
                            buffer.write(f"Para: {email.get('recipients', '')}\n")
                            buffer.write(f"Data: {email.get('date', '')}\n")
                            buffer.write(f"Pasta: {email.get('folder', '')}\n")
                            
                            buffer.write("-" * 40 + "\n")
                            buffer.write("CORPO DO EMAIL:\n\n")
                            
                            # Usar texto simples para CSV
                            body_text = email.get('body_text', '') or '(Sem conteúdo)'
                            
                            # Adicionar o texto sem modificações
                            buffer.write(body_text + "\n")
                            buffer.write("=" * 80 + "\n\n")
                    
                    # Salvar no arquivo temporário
                    temp_file.write(buffer.getvalue())
            
            return temp_file.name
            
        except Exception as e:
            logger.exception(f"Erro ao exportar CSV: {str(e)}")
            raise
import io
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timedelta
from collections import Counter

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm, inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas

from app import db
from models import EmailAccount, EmailData, Report, Organization

# Configuração do logging
logger = logging.getLogger(__name__)

class SimpleDeepReport:
    def __init__(self, report):
        """Initialize the report generator with a report object"""
        self.report = report
        
        # Define estilos personalizados para o relatório (mais simples)
        self.styles = getSampleStyleSheet()
        
        # Criando estilos personalizados para corresponder ao modelo
        self.styles.add(ParagraphStyle(
            name='DeepTitle',
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=20,
            textColor=colors.HexColor('#00658D'),  # Azul da Deep Logística
            alignment=TA_LEFT,
            spaceAfter=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='DeepHeading',
            fontName='Helvetica-Bold',
            fontSize=14,
            leading=18,
            textColor=colors.HexColor('#00658D'),  # Azul da Deep Logística
            alignment=TA_LEFT,
            spaceAfter=10
        ))
        
        self.styles.add(ParagraphStyle(
            name='DeepNormal',
            fontName='Helvetica',
            fontSize=12,
            leading=14,
            textColor=colors.black,
            alignment=TA_LEFT,
            spaceAfter=6
        ))
        
        self.styles.add(ParagraphStyle(
            name='DeepListItem',
            fontName='Helvetica',
            fontSize=12,
            leading=14,
            textColor=colors.black,
            alignment=TA_LEFT,
            leftIndent=20,
            spaceAfter=3
        ))
    
    def generate(self):
        """Generate report data based on the report settings"""
        # Usamos o gerador original para obter os dados
        from report_generator import ReportGenerator
        original_generator = ReportGenerator(self.report)
        return original_generator.generate()
        
    def export_pdf(self):
        """Export the report as a PDF file with Deep Logística template (simplified)"""
        try:
            # Generate report data
            report_data = self.generate()
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_path = temp_file.name
            
            # Path para o template de fundo da Deep Logística
            template_path = os.path.join('static', 'img', 'deep_template.png')
            
            # Verificar se o arquivo existe
            if not os.path.exists(template_path):
                logger.warning(f"Arquivo de template não encontrado: {template_path}")
                template_path = None
                
            # Create the document with margens ajustadas para o template Deep Logística
            doc = SimpleDocTemplate(
                temp_path, 
                pagesize=A4,
                rightMargin=1.5*cm,  # Margem direita reduzida
                leftMargin=2.5*cm,   # Margem esquerda ajustada para 2.5cm conforme solicitado pelo cliente
                topMargin=3.5*cm,    # Margem superior aumentada para dar espaço ao logo
                bottomMargin=3*cm    # Margem inferior aumentada para o rodapé
            )
            
            # Configurar função para adicionar o fundo em cada página
            def add_page_background(canvas, doc):
                # Adicionar a imagem de fundo como template
                if template_path and os.path.exists(template_path):
                    # Tamanho da página A4
                    page_width, page_height = A4
                    
                    # Desenhar a imagem de fundo (template)
                    canvas.drawImage(
                        template_path,
                        x=0,
                        y=0,
                        width=page_width,
                        height=page_height,
                        preserveAspectRatio=True,
                        mask='auto'
                    )
            
            # Elements to add to the PDF
            elements = []
            
            # Add title formatted in Deep Logística style
            if self.report.type == 'summary':
                title = f"Relatório Resumido: {self.report.name}"
            else:
                title = f"Relatório Detalhado: {self.report.name}"
                
            elements.append(Paragraph(title, self.styles['DeepTitle']))
            
            # Add date range
            if self.report.date_range_start and self.report.date_range_end:
                start_date = self.report.date_range_start.strftime('%d/%m/%Y')
                end_date = self.report.date_range_end.strftime('%d/%m/%Y')
                elements.append(Paragraph(f"Período: {start_date} a {end_date}", self.styles['DeepNormal']))
            
            # Se for um relatório detalhado, exibir total de emails
            if self.report.type == 'detailed':
                emails = report_data.get('emails', [])
                elements.append(Paragraph(f"Total de emails: {len(emails)}", self.styles['DeepNormal']))
            
            elements.append(Spacer(1, 0.5*cm))
            
            # Add content based on report type
            if self.report.type == 'summary':
                # Estatísticas básicas
                elements.append(Paragraph("Estatísticas Gerais", self.styles['DeepHeading']))
                elements.append(Paragraph(f"Total de e-mails: {report_data.get('total_emails', 0)}", self.styles['DeepNormal']))
                elements.append(Paragraph(f"E-mails enviados: {report_data.get('total_sent', 0)}", self.styles['DeepNormal']))
                elements.append(Paragraph(f"E-mails recebidos: {report_data.get('total_received', 0)}", self.styles['DeepNormal']))
                
                if 'avg_per_day' in report_data:
                    elements.append(Paragraph(f"Média diária: {report_data['avg_per_day']:.1f}", self.styles['DeepNormal']))
                
                elements.append(Spacer(1, 0.5*cm))
                
                # Principais remetentes
                if report_data.get('top_senders'):
                    elements.append(Paragraph("Principais Remetentes", self.styles['DeepHeading']))
                    for i, sender in enumerate(report_data.get('top_senders', [])[:10], 1):
                        elements.append(Paragraph(
                            f"{i}. {sender.get('sender', '')} ({sender.get('count', 0)} emails)",
                            self.styles['DeepListItem']
                        ))
                    
                    elements.append(Spacer(1, 0.5*cm))
                
                # Principais destinatários
                if report_data.get('top_recipients'):
                    elements.append(Paragraph("Principais Destinatários", self.styles['DeepHeading']))
                    for i, recipient in enumerate(report_data.get('top_recipients', [])[:10], 1):
                        elements.append(Paragraph(
                            f"{i}. {recipient.get('recipient', '')} ({recipient.get('count', 0)} emails)",
                            self.styles['DeepListItem']
                        ))
                    
                    elements.append(Spacer(1, 0.5*cm))
                
                # Assuntos comuns
                if report_data.get('common_subjects'):
                    elements.append(Paragraph("Assuntos Comuns", self.styles['DeepHeading']))
                    for i, subject in enumerate(report_data.get('common_subjects', [])[:15], 1):
                        elements.append(Paragraph(
                            f"{i}. {subject.get('subject', '')[:50]} ({subject.get('count', 0)} emails)",
                            self.styles['DeepListItem']
                        ))
            else:
                # Relatório detalhado - agrupado por remetente
                emails = report_data.get('emails', [])
                
                # Se não temos emails, mostramos mensagem
                if not emails:
                    elements.append(Paragraph("Nenhum email encontrado para os critérios selecionados.", self.styles['DeepNormal']))
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
                    elements.append(Paragraph(f"Emails agrupados por {total_groups} {group_title.lower()}s", self.styles['DeepHeading']))
                    elements.append(Spacer(1, 0.5*cm))
                    
                    # Índice no início do documento para facilitar navegação
                    elements.append(Paragraph(f"Índice de {group_title}s:", self.styles['DeepHeading']))
                    
                    # Criar lista numerada de grupos
                    for idx, (group_name, group_emails) in enumerate(emails_by_group.items(), 1):
                        elements.append(Paragraph(
                            f"{idx}. {group_name} ({len(group_emails)} emails)",
                            self.styles['DeepListItem']
                        ))
                    
                    elements.append(Spacer(1, 0.5*cm))
                    elements.append(PageBreak())
                    
                    # Agora, para cada grupo, processamos seus emails
                    for idx, (group_name, group_emails) in enumerate(emails_by_group.items(), 1):
                        # Título da seção deste grupo
                        elements.append(Paragraph(
                            f"{group_title} {idx}/{total_groups}: {group_name}",
                            self.styles['DeepHeading']
                        ))
                        elements.append(Paragraph(
                            f"Total de emails deste {group_title.lower()}: {len(group_emails)}",
                            self.styles['DeepNormal']
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
                            elements.append(Paragraph(f"Email #{i+1} de {group_name}", self.styles['DeepHeading']))
                            
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
                            
                            # Tabela de metadados ajustada para as novas margens (ainda mais larga)
                            meta_table = Table(metadata, colWidths=[2.5*cm, 12.5*cm])
                            meta_table.setStyle(TableStyle([
                                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F5F5F5')),
                                ('PADDING', (0, 0), (-1, -1), 6),
                            ]))
                            
                            elements.append(meta_table)
                            elements.append(Spacer(1, 0.5*cm))
                            
                            # Título do conteúdo
                            elements.append(Paragraph("Conteúdo do Email:", self.styles['DeepHeading']))
                            
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
                                        elements.append(Paragraph(p_with_breaks, self.styles['DeepNormal']))
                                        elements.append(Spacer(1, 0.2*cm))
                            
                            except Exception as content_error:
                                logger.error(f"Erro ao processar conteúdo: {str(content_error)}")
                                elements.append(Paragraph("Erro ao processar o conteúdo deste email.", self.styles['DeepNormal']))
                            
                            # Adicionar espaço após o corpo do email
                            elements.append(Spacer(1, 0.8*cm))
                        
                        # Se tiver mais emails do que mostramos
                        if len(group_emails) > 5:
                            elements.append(Paragraph(
                                f"Nota: Exibindo apenas 5 dos {len(group_emails)} emails deste {group_title.lower()}. Para visualizar todos, acesse o sistema.",
                                self.styles['DeepNormal']
                            ))
                        
                        # Adicionar quebra de página após cada remetente exceto o último
                        if idx < total_groups:
                            elements.append(PageBreak())
            
            # Add footer
            footer_text = f"Relatório gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | Deep Logística"
            elements.append(Spacer(1, 1*cm))
            footer_style = ParagraphStyle(
                name='Footer',
                parent=self.styles['Normal'],
                fontSize=8,
                textColor=colors.grey
            )
            elements.append(Paragraph(footer_text, footer_style))
            
            # Build the PDF com background template
            doc.build(elements, onFirstPage=add_page_background, onLaterPages=add_page_background)
            
            return temp_path
            
        except Exception as e:
            logger.exception(f"Erro ao exportar PDF com template Deep simples: {str(e)}")
            
            # Fallback para o relatório padrão
            try:
                logger.info("Usando relatório padrão como fallback")
                from report_generator import ReportGenerator
                return ReportGenerator(self.report).export_pdf()
            except Exception as backup_error:
                logger.exception(f"Falha também no relatório padrão: {str(backup_error)}")
                raise e
    
    def export_csv(self):
        """Export the report as a CSV file - just use the default implementation"""
        from report_generator import ReportGenerator
        return ReportGenerator(self.report).export_csv()
import io
import json
import logging
import os
import re
import tempfile
import base64
from datetime import datetime, timedelta
from collections import Counter

import pandas as pd
from bs4 import BeautifulSoup

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.utils import ImageReader
from io import BytesIO

from app import db
from models import EmailAccount, EmailData, Report, Organization

# Configuração do logging
logger = logging.getLogger(__name__)

# Imagens do template da Deep Logística em Base64
# Esta é uma imagem SVG em Base64 para o logo da Deep Logística
DEEP_LOGO_SVG = """
<svg width="150" height="60" xmlns="http://www.w3.org/2000/svg">
  <style>
    .st0{fill:#00A551;}
    .st1{fill:#00658D;}
    .text{font-family:Arial, sans-serif;font-size:10px;fill:#00658D;}
  </style>
  <circle class="st0" cx="30" cy="30" r="10"/>
  <rect x="40" y="25" width="20" height="10" class="st1"/>
  <rect x="60" y="25" width="20" height="10" class="st1"/>
  <rect x="80" y="25" width="20" height="10" class="st1"/>
  <text x="30" y="50" class="text" text-anchor="middle">LOGISTICS</text>
</svg>
"""

# Padrão de 5 ícones sociais para o rodapé
FOOTER_SVG = """
<svg width="320" height="60" xmlns="http://www.w3.org/2000/svg">
  <style>
    .bg{fill:#00658D;}
    .icon{fill:white;}
    .text{font-family:Arial, sans-serif;font-size:12px;fill:white;font-weight:bold;}
  </style>
  <rect x="0" y="0" width="320" height="60" rx="20" class="bg"/>
  
  <!-- Ícone Website -->
  <circle cx="40" cy="30" r="15" fill="#fff" opacity="0.9"/>
  <text x="40" y="34" text-anchor="middle" font-family="Arial" font-size="14" fill="#00658D">🌐</text>
  
  <!-- Ícone LinkedIn -->
  <circle cx="100" cy="30" r="15" fill="#fff" opacity="0.9"/>
  <text x="100" y="34" text-anchor="middle" font-family="Arial" font-size="14" fill="#00658D">in</text>
  
  <!-- Ícone Facebook -->
  <circle cx="160" cy="30" r="15" fill="#fff" opacity="0.9"/>
  <text x="160" y="34" text-anchor="middle" font-family="Arial" font-size="14" fill="#00658D">f</text>
  
  <!-- Ícone Instagram -->
  <circle cx="220" cy="30" r="15" fill="#fff" opacity="0.9"/>
  <text x="220" y="34" text-anchor="middle" font-family="Arial" font-size="14" fill="#00658D">📷</text>
  
  <!-- Texto do site -->
  <text x="40" y="52" class="text" text-anchor="middle" font-size="8">deeplogistica.com.br</text>
  <text x="280" y="28" class="text" text-anchor="middle">deeplogistica</text>
</svg>
"""

# Padrão para o #FazValer a confiança na lateral
SIDEBAR_SVG = """
<svg width="50" height="800" xmlns="http://www.w3.org/2000/svg">
  <style>
    .text{font-family:Arial, sans-serif;font-size:14px;fill:#00A551;font-weight:bold;}
  </style>
  <!-- Texto vertical rotacionado -->
  <text x="40" y="50" class="text" transform="rotate(90, 40, 50)">#FazValer a Confiança</text>
  <text x="40" y="150" class="text" transform="rotate(90, 40, 150)">#FazValer a Confiança</text>
  <text x="40" y="250" class="text" transform="rotate(90, 40, 250)">#FazValer a Confiança</text>
  <text x="40" y="350" class="text" transform="rotate(90, 40, 350)">#FazValer a Confiança</text>
  <text x="40" y="450" class="text" transform="rotate(90, 40, 450)">#FazValer a Confiança</text>
  <text x="40" y="550" class="text" transform="rotate(90, 40, 550)">#FazValer a Confiança</text>
  <text x="40" y="650" class="text" transform="rotate(90, 40, 650)">#FazValer a Confiança</text>
  <text x="40" y="750" class="text" transform="rotate(90, 40, 750)">#FazValer a Confiança</text>
</svg>
"""

# Padrão para os ícones do cabeçalho
HEADER_ICONS_SVG = """
<svg width="250" height="40" xmlns="http://www.w3.org/2000/svg">
  <!-- Quadrado verde -->
  <rect x="0" y="0" width="40" height="40" fill="#00A551"/>
  <text x="20" y="24" text-anchor="middle" font-family="Arial" font-size="16" fill="white">TI</text>
  
  <!-- Quadrado azul -->
  <rect x="50" y="0" width="40" height="40" fill="#00658D"/>
  <text x="70" y="24" text-anchor="middle" font-family="Arial" font-size="16" fill="white">GR</text>
  
  <!-- Quadrado cinza -->
  <rect x="100" y="0" width="40" height="40" fill="#666666"/>
  <text x="120" y="24" text-anchor="middle" font-family="Arial" font-size="16" fill="white">OP</text>
  
  <!-- Quadrado verde -->
  <rect x="150" y="0" width="40" height="40" fill="#00A551"/>
  <text x="170" y="24" text-anchor="middle" font-family="Arial" font-size="16" fill="white">CS</text>
  
  <!-- Quadrado azul -->
  <rect x="200" y="0" width="40" height="40" fill="#00658D"/>
  <text x="220" y="24" text-anchor="middle" font-family="Arial" font-size="16" fill="white">RH</text>
</svg>
"""

# Padrão para o background pontilhado (canto superior direito)
DOTS_BG_SVG = """
<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
  <style>
    .dot{fill:#CCCCCC;opacity:0.5;}
  </style>
  <!-- Grade de pontos -->
  <g id="dots">
    <!-- 10x10 grid of dots with 20px spacing -->
    <circle class="dot" cx="0" cy="0" r="2"/>
    <circle class="dot" cx="20" cy="0" r="2"/>
    <circle class="dot" cx="40" cy="0" r="2"/>
    <!-- ... Continuing for all dots -->
  </g>
</svg>
"""

class DeepReportGenerator:
    def __init__(self, report):
        """Initialize the report generator with a report object"""
        self.report = report
        
        # Define estilos personalizados para o relatório
        self.styles = getSampleStyleSheet()
        # Criar estilo personalizado para os títulos e textos
        self.styles.add(ParagraphStyle(
            name='DeepTitle',
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#00658D'),
            alignment=TA_LEFT,
            spaceAfter=12
        ))
        self.styles.add(ParagraphStyle(
            name='DeepHeading1',
            fontName='Helvetica-Bold',
            fontSize=14,
            leading=18,
            textColor=colors.HexColor('#00658D'),
            alignment=TA_LEFT,
            spaceAfter=8
        ))
        self.styles.add(ParagraphStyle(
            name='DeepHeading2',
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#00658D'),
            alignment=TA_LEFT,
            spaceAfter=6
        ))
        self.styles.add(ParagraphStyle(
            name='DeepNormal',
            fontName='Helvetica',
            fontSize=12,
            leading=14,
            textColor=colors.HexColor('#333333'),
            alignment=TA_LEFT,
            spaceAfter=6
        ))
        
    def _svg_to_reportlab_image(self, svg_string, width=None, height=None):
        """Converte uma string SVG em uma imagem compatível com reportlab"""
        try:
            # Converter SVG para base64
            svg_bytes = svg_string.encode('utf-8')
            encoded = base64.b64encode(svg_bytes).decode('ascii')
            img_data = f"data:image/svg+xml;base64,{encoded}"
            
            # Criar imagem a partir do base64
            img = Image(img_data)
            
            # Ajustar tamanho se necessário
            if width and height:
                img.drawWidth = width
                img.drawHeight = height
            elif width:
                # Manter proporção
                aspect = img.drawHeight / img.drawWidth
                img.drawWidth = width
                img.drawHeight = width * aspect
            elif height:
                # Manter proporção
                aspect = img.drawWidth / img.drawHeight
                img.drawHeight = height
                img.drawWidth = height * aspect
                
            return img
        except Exception as e:
            logger.error(f"Erro ao converter SVG para imagem: {str(e)}")
            # Retornar um espaço em branco em caso de erro
            return Spacer(1, 1*cm)
    
    def generate(self):
        """Generate report data based on the report settings"""
        # Chama o método original da classe ReportGenerator
        from report_generator import ReportGenerator
        original_generator = ReportGenerator(self.report)
        return original_generator.generate()
        
    def export_pdf(self):
        """Export the report as a PDF file with Deep Logística formatting"""
        try:
            # Generate report data
            report_data = self.generate()
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_path = temp_file.name
            
            # Create the document with smaller margins to acomodar a barra lateral
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
            
            # Adicionar cabeçalho com logo da Deep Logística
            # Criar uma tabela para o cabeçalho com logo à esquerda e ícones à direita
            header_table_data = [
                [self._svg_to_reportlab_image(DEEP_LOGO_SVG, width=8*cm), 
                 self._svg_to_reportlab_image(HEADER_ICONS_SVG, width=10*cm)]
            ]
            header_table = Table(header_table_data, colWidths=[10*cm, 8*cm])
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ]))
            elements.append(header_table)
            elements.append(Spacer(1, 1*cm))
            
            # Add title
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
            
            elements.append(Spacer(1, 0.5*cm))
            
            # Add content based on report type
            if self.report.type == 'summary':
                # Estatísticas básicas
                elements.append(Paragraph("Estatísticas Gerais", self.styles['DeepHeading1']))
                elements.append(Paragraph(f"Total de e-mails: {report_data.get('total_emails', 0)}", self.styles['DeepNormal']))
                elements.append(Paragraph(f"E-mails enviados: {report_data.get('total_sent', 0)}", self.styles['DeepNormal']))
                elements.append(Paragraph(f"E-mails recebidos: {report_data.get('total_received', 0)}", self.styles['DeepNormal']))
                
                if 'avg_per_day' in report_data:
                    elements.append(Paragraph(f"Média diária: {report_data['avg_per_day']:.1f}", self.styles['DeepNormal']))
                
                elements.append(Spacer(1, 0.5*cm))
                
                # Principais remetentes
                if report_data.get('top_senders'):
                    elements.append(Paragraph("Principais Remetentes", self.styles['DeepHeading2']))
                    
                    # Criar dados para tabela
                    senders_data = [["Remetente", "Quantidade"]]
                    for sender in report_data.get('top_senders', [])[:10]:
                        senders_data.append([sender.get('sender', ''), str(sender.get('count', 0))])
                    
                    # Criar tabela
                    if len(senders_data) > 1:
                        table = Table(senders_data, colWidths=[12*cm, 3*cm])
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00658D')),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                            ('ALIGN', (-1, 1), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ]))
                        elements.append(table)
                    else:
                        elements.append(Paragraph("Nenhum dado disponível", self.styles['DeepNormal']))
                    
                    elements.append(Spacer(1, 0.5*cm))
                
                # Principais destinatários
                if report_data.get('top_recipients'):
                    elements.append(Paragraph("Principais Destinatários", self.styles['DeepHeading2']))
                    
                    # Criar dados para tabela
                    recipients_data = [["Destinatário", "Quantidade"]]
                    for recipient in report_data.get('top_recipients', [])[:10]:
                        recipients_data.append([recipient.get('recipient', ''), str(recipient.get('count', 0))])
                    
                    # Criar tabela
                    if len(recipients_data) > 1:
                        table = Table(recipients_data, colWidths=[12*cm, 3*cm])
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00658D')),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                            ('ALIGN', (-1, 1), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ]))
                        elements.append(table)
                    else:
                        elements.append(Paragraph("Nenhum dado disponível", self.styles['DeepNormal']))
                    
                    elements.append(Spacer(1, 0.5*cm))
                
                # Assuntos comuns
                if report_data.get('common_subjects'):
                    elements.append(Paragraph("Assuntos Comuns", self.styles['DeepHeading2']))
                    
                    # Criar dados para tabela
                    subjects_data = [["Assunto", "Quantidade"]]
                    for subject in report_data.get('common_subjects', [])[:15]:
                        subjects_data.append([subject.get('subject', '')[:50], str(subject.get('count', 0))])
                    
                    # Criar tabela
                    if len(subjects_data) > 1:
                        table = Table(subjects_data, colWidths=[12*cm, 3*cm])
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00658D')),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                            ('ALIGN', (-1, 1), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ]))
                        elements.append(table)
                    else:
                        elements.append(Paragraph("Nenhum dado disponível", self.styles['DeepNormal']))
            else:
                # Relatório detalhado - agrupado por remetente
                emails = report_data.get('emails', [])
                elements.append(Paragraph(f"Total de emails: {len(emails)}", self.styles['DeepNormal']))
                elements.append(Spacer(1, 0.5*cm))
                
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
                    elements.append(Paragraph(f"Emails agrupados por {total_groups} {group_title.lower()}s", self.styles['DeepHeading2']))
                    elements.append(Spacer(1, 0.5*cm))
                    
                    # Índice no início do documento para facilitar navegação
                    elements.append(Paragraph(f"Índice de {group_title}s:", self.styles['DeepHeading2']))
                    
                    # Criar lista numerada de grupos
                    for idx, (group_name, group_emails) in enumerate(emails_by_group.items(), 1):
                        elements.append(Paragraph(
                            f"{idx}. {group_name} ({len(group_emails)} emails)",
                            self.styles['DeepNormal']
                        ))
                    
                    elements.append(Spacer(1, 0.5*cm))
                    elements.append(PageBreak())
                    
                    # Agora, para cada grupo, processamos seus emails
                    for idx, (group_name, group_emails) in enumerate(emails_by_group.items(), 1):
                        # Título da seção deste grupo
                        elements.append(Paragraph(
                            f"{group_title} {idx}/{total_groups}: {group_name}",
                            self.styles['DeepHeading1']
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
                            elements.append(Paragraph(f"Email #{i+1} de {group_name}", self.styles['DeepHeading2']))
                            
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
                                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F5F5F5')),
                                ('PADDING', (0, 0), (-1, -1), 6),
                            ]))
                            
                            elements.append(meta_table)
                            elements.append(Spacer(1, 0.5*cm))
                            
                            # Título do conteúdo
                            elements.append(Paragraph("Conteúdo do Email:", self.styles['DeepHeading2']))
                            
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
            
            # Add footer with social icons
            elements.append(Spacer(1, 1*cm))
            elements.append(self._svg_to_reportlab_image(FOOTER_SVG, width=18*cm))
            
            # Função personalizada para adicionar elementos estáticos a cada página
            def add_page_elements(canvas, doc):
                # Adicionar o texto "#FazValer a Confiança" na lateral direita
                sidebar_img = self._svg_to_reportlab_image(SIDEBAR_SVG, width=2*cm)
                canvas.saveState()
                sidebar_img.drawOn(canvas, A4[0] - 2.5*cm, 5*cm)
                canvas.restoreState()
                
                # Adicionar padrão de pontos no canto superior direito
                dots_img = self._svg_to_reportlab_image(DOTS_BG_SVG, width=5*cm)
                canvas.saveState()
                dots_img.drawOn(canvas, A4[0] - 5.5*cm, A4[1] - 5.5*cm)
                canvas.restoreState()
            
            # Build the PDF with the page decoration function
            doc.build(elements, onFirstPage=add_page_elements, onLaterPages=add_page_elements)
            
            return temp_path
            
        except Exception as e:
            logger.exception(f"Erro ao exportar PDF com template Deep: {str(e)}")
            
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
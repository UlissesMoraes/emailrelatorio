import os
import json
import logging
import re
import tempfile
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

class DalltorReport:
    def __init__(self, report):
        """Initialize the report generator with a report object"""
        self.report = report
        
        # Setup styles
        self.styles = getSampleStyleSheet()
        
        # Dalltor specific styles
        self.styles.add(ParagraphStyle(
            name='DalltorTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#424242'),
            spaceAfter=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='DalltorHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#424242'),
            spaceAfter=8
        ))
        
        self.styles.add(ParagraphStyle(
            name='DalltorNormal',
            parent=self.styles['Normal'],
            fontSize=12,
            alignment=TA_LEFT,
            textColor=colors.black,
            fontName='Helvetica'
        ))
        
        self.styles.add(ParagraphStyle(
            name='DalltorListItem',
            parent=self.styles['Normal'],
            fontSize=11,
            alignment=TA_LEFT,
            textColor=colors.black,
            fontName='Helvetica',
            leftIndent=20
        ))
    
    def generate(self):
        """Generate report data based on the report settings"""
        # Usar diretamente o ReportGenerator padrão para gerar os dados do relatório
        from report_generator import ReportGenerator
        
        logger.info(f"Gerando relatório Dalltor: {self.report.name}, tipo: {self.report.type}")
        
        # Criar uma instância do gerador padrão e usar o método generate
        report_gen = ReportGenerator(self.report)
        report_data = report_gen.generate()
        
        return report_data
    
    def export_pdf(self):
        """Export the report as a PDF file with Dalltor template"""
        try:
            # Generate report data
            report_data = self.generate()
            
            # Create temporary file
            fd, temp_path = tempfile.mkstemp(suffix='.pdf')
            os.close(fd)
            
            # Utilizando o novo modelo de papel timbrado da Dalltor e logo
            
            # Path para o template de papel timbrado da Dalltor
            template_path = os.path.join('static', 'images', 'dalltor_letterhead.png')
            alternate_path = 'static/images/dalltor_letterhead.png'  # Caminho alternativo
            
            # Path para o logo da Dalltor que vai no cabeçalho
            logo_path = os.path.join('static', 'images', 'dalltor_logo.png')
            alternate_logo_path = 'static/images/dalltor_logo.png'
            
            # Verificar se os arquivos existem
            if os.path.exists(template_path):
                logger.info(f"Template Dalltor encontrado: {template_path}")
            elif os.path.exists(alternate_path):
                logger.info(f"Template Dalltor encontrado no caminho alternativo: {alternate_path}")
                template_path = alternate_path
            else:
                logger.warning(f"Arquivo de template Dalltor não encontrado. Procurado em: {template_path} e {alternate_path}")
                # Tentar buscar em caminhos absolutos
                abs_path = os.path.abspath('static/images/dalltor_letterhead.png')
                logger.info(f"Tentando caminho absoluto: {abs_path}")
                if os.path.exists(abs_path):
                    template_path = abs_path
                    logger.info(f"Template encontrado no caminho absoluto: {abs_path}")
                else:
                    template_path = None
                    logger.error(f"Não foi possível encontrar o arquivo de template em nenhum dos caminhos tentados")
                    
            # Verifica o logo
            if os.path.exists(logo_path):
                logger.info(f"Logo Dalltor encontrado: {logo_path}")
            elif os.path.exists(alternate_logo_path):
                logger.info(f"Logo Dalltor encontrado no caminho alternativo: {alternate_logo_path}")
                logo_path = alternate_logo_path
            else:
                logger.warning(f"Arquivo de logo Dalltor não encontrado. Procurado em: {logo_path} e {alternate_logo_path}")
                # Tentar buscar em caminhos absolutos
                abs_logo_path = os.path.abspath('static/images/dalltor_logo.png')
                logger.info(f"Tentando caminho absoluto para logo: {abs_logo_path}")
                if os.path.exists(abs_logo_path):
                    logo_path = abs_logo_path
                    logger.info(f"Logo encontrado no caminho absoluto: {abs_logo_path}")
                else:
                    logo_path = None
                    logger.error(f"Não foi possível encontrar o arquivo de logo em nenhum dos caminhos tentados")
                
            # Create the document with margens ajustadas para o template Dalltor
            doc = SimpleDocTemplate(
                temp_path, 
                pagesize=A4,
                rightMargin=1.5*cm,  # Margem direita reduzida
                leftMargin=2.5*cm,   # Margem esquerda ajustada conforme utilizado para Deep Logística
                topMargin=6*cm,      # Margem superior aumentada para dar mais espaço ao logo
                bottomMargin=3*cm    # Margem inferior aumentada para o rodapé
            )
            
            # Configurar função para adicionar a imagem de fundo em cada página do relatório
            def add_page_background(canvas, doc):
                # Tamanho da página A4
                page_width, page_height = A4
                
                # Log para debug
                logger.info("Adicionando papel timbrado Dalltor como fundo")
                
                try:
                    if template_path and os.path.exists(template_path):
                        # Desenhar a imagem de fundo como papel timbrado
                        canvas.drawImage(
                            template_path,
                            x=0,
                            y=0,
                            width=page_width,
                            height=page_height,
                            preserveAspectRatio=True,
                            mask='auto'
                        )
                        logger.info("Papel timbrado Dalltor aplicado com sucesso")
                    else:
                        logger.warning("Template não encontrado, utilizando método alternativo")
                        # Fallback - desenhar apenas fundo branco
                        canvas.setFillColorRGB(1, 1, 1)  # Branco
                        canvas.rect(0, 0, page_width, page_height, fill=1)
                except Exception as error:
                    logger.error(f"Erro ao aplicar papel timbrado Dalltor: {str(error)}")
                    # Tentar debug do erro
                    logger.error(f"Caminho da imagem: {template_path}")
                    logger.error(f"O arquivo existe? {os.path.exists(template_path) if template_path else 'Não (path é None)'}")
                    if template_path:
                        try:
                            logger.error(f"Tamanho do arquivo: {os.path.getsize(template_path)}")
                        except:
                            logger.error("Não foi possível obter o tamanho do arquivo")
                    
                    # Se falhar, desenhar apenas fundo branco
                    canvas.setFillColorRGB(1, 1, 1)  # Branco
                    canvas.rect(0, 0, page_width, page_height, fill=1)
            
            # Elements to add to the PDF
            elements = []
            
            # Estamos usando apenas o fundo do papel timbrado, não precisamos adicionar o logo
            # separadamente no cabeçalho, pois o cliente pediu para usar apenas o papel timbrado como fundo
            logger.info("Usando apenas o papel timbrado como fundo, sem adicionar o logo separadamente")
            
            # Adicionar espaço extra no topo para não sobrepor o logo do papel timbrado
            elements.append(Spacer(1, 1.5*cm))
            
            # Add title formatted in Dalltor style
            if self.report.type == 'summary':
                title = f"Relatório Resumido: {self.report.name}"
            else:
                title = f"Relatório Detalhado: {self.report.name}"
                
            elements.append(Paragraph(title, self.styles['DalltorTitle']))
            
            # Add date range
            if self.report.date_range_start and self.report.date_range_end:
                start_date = self.report.date_range_start.strftime('%d/%m/%Y')
                end_date = self.report.date_range_end.strftime('%d/%m/%Y')
                elements.append(Paragraph(f"Período: {start_date} a {end_date}", self.styles['DalltorNormal']))
            
            # Se for um relatório detalhado, exibir total de emails
            if self.report.type == 'detailed':
                emails = report_data.get('emails', [])
                elements.append(Paragraph(f"Total de emails: {len(emails)}", self.styles['DalltorNormal']))
            
            elements.append(Spacer(1, 0.5*cm))
            
            # Add content based on report type
            if self.report.type == 'summary':
                # Estatísticas básicas
                elements.append(Paragraph("Estatísticas Gerais", self.styles['DalltorHeading']))
                elements.append(Paragraph(f"Total de e-mails: {report_data.get('total_emails', 0)}", self.styles['DalltorNormal']))
                elements.append(Paragraph(f"E-mails enviados: {report_data.get('total_sent', 0)}", self.styles['DalltorNormal']))
                elements.append(Paragraph(f"E-mails recebidos: {report_data.get('total_received', 0)}", self.styles['DalltorNormal']))
                
                if 'avg_per_day' in report_data:
                    elements.append(Paragraph(f"Média diária: {report_data['avg_per_day']:.1f}", self.styles['DalltorNormal']))
                
                elements.append(Spacer(1, 0.5*cm))
                
                # Principais remetentes
                if report_data.get('top_senders'):
                    elements.append(Paragraph("Principais Remetentes", self.styles['DalltorHeading']))
                    for i, sender in enumerate(report_data.get('top_senders', [])[:10], 1):
                        elements.append(Paragraph(
                            f"{i}. {sender.get('sender', '')} ({sender.get('count', 0)} emails)",
                            self.styles['DalltorListItem']
                        ))
                    
                    elements.append(Spacer(1, 0.5*cm))
                
                # Principais destinatários
                if report_data.get('top_recipients'):
                    elements.append(Paragraph("Principais Destinatários", self.styles['DalltorHeading']))
                    for i, recipient in enumerate(report_data.get('top_recipients', [])[:10], 1):
                        elements.append(Paragraph(
                            f"{i}. {recipient.get('recipient', '')} ({recipient.get('count', 0)} emails)",
                            self.styles['DalltorListItem']
                        ))
                    
                    elements.append(Spacer(1, 0.5*cm))
                
                # Assuntos comuns
                if report_data.get('common_subjects'):
                    elements.append(Paragraph("Assuntos Comuns", self.styles['DalltorHeading']))
                    for i, subject in enumerate(report_data.get('common_subjects', [])[:15], 1):
                        elements.append(Paragraph(
                            f"{i}. {subject.get('subject', '')[:50]} ({subject.get('count', 0)} emails)",
                            self.styles['DalltorListItem']
                        ))
            else:
                # Relatório detalhado - agrupado por remetente
                emails = report_data.get('emails', [])
                
                # Se não temos emails, mostramos mensagem
                if not emails:
                    elements.append(Paragraph("Nenhum email encontrado para os critérios selecionados.", self.styles['DalltorNormal']))
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
                    elements.append(Paragraph(f"Emails agrupados por {total_groups} {group_title.lower()}s", self.styles['DalltorHeading']))
                    elements.append(Spacer(1, 0.5*cm))
                    
                    # Índice no início do documento para facilitar navegação
                    elements.append(Paragraph(f"Índice de {group_title}s:", self.styles['DalltorHeading']))
                    
                    # Criar lista numerada de grupos
                    for idx, (group_name, group_emails) in enumerate(emails_by_group.items(), 1):
                        elements.append(Paragraph(
                            f"{idx}. {group_name} ({len(group_emails)} emails)",
                            self.styles['DalltorListItem']
                        ))
                    
                    elements.append(Spacer(1, 0.5*cm))
                    elements.append(PageBreak())
                    
                    # Agora, para cada grupo, processamos seus emails
                    for idx, (group_name, group_emails) in enumerate(emails_by_group.items(), 1):
                        # Título da seção deste grupo (formato como na imagem de referência)
                        elements.append(Paragraph(
                            f"Remetente {idx}/{total_groups}: {group_name}",
                            self.styles['DalltorHeading']
                        ))
                        elements.append(Paragraph(
                            f"Total de emails deste remetente: {len(group_emails)}",
                            self.styles['DalltorNormal']
                        ))
                        elements.append(Spacer(1, 0.5*cm))
                        
                        # Limitar número de emails por grupo (máximo 5 por grupo)
                        emails_to_show = group_emails[:5]
                        
                        # Para cada email deste grupo
                        for i, email in enumerate(emails_to_show):
                            try:
                                # Adicionar uma quebra de página se não for o primeiro email do grupo
                                if i > 0:
                                    elements.append(PageBreak())
                                
                                # Metadados do email em formato de tabela seguindo layout da imagem de referência
                                header_data = [
                                    ["ATIVIDADE", "DATA", "TIPO DE COMUNICAÇÃO"]
                                ]
                                
                                # Cabeçalho da tabela em negrito e centralizado - seguindo formato exato da imagem
                                header_table = Table(header_data, colWidths=[12*cm, 3*cm, 4*cm])
                                header_table.setStyle(TableStyle([
                                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                    ('BACKGROUND', (0, 0), (-1, -1), colors.white),  # Fundo branco como na imagem
                                    ('BOX', (0, 0), (-1, -1), 1, colors.black),  # Borda completa
                                    ('GRID', (0, 0), (-1, -1), 1, colors.black),  # Linhas internas
                                    ('PADDING', (0, 0), (-1, -1), 6),
                                ]))
                                
                                elements.append(header_table)
                                
                                # Formatar data
                                date_str = email.get('date', '')
                                if isinstance(date_str, str):
                                    # Tentar formatar a data em formato mais legível
                                    try:
                                        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f')
                                        date_str = date_obj.strftime('%d/%m/%Y')
                                    except:
                                        # Se falhar, manter original
                                        pass
                                
                                # Obter as informações do email com formatação de links quando aplicável
                                sender = email.get('sender', 'Não especificado')
                                recipient = email.get('recipients', 'Não especificado')
                                subject = email.get('subject', '(Sem assunto)')
                                
                                # Verificar se há email entre parênteses no sender e formatar como link
                                email_pattern = r'\((.*?@.*?)\)'
                                sender_match = re.search(email_pattern, sender)
                                sender_email = ""
                                
                                if sender_match:
                                    sender_email = sender_match.group(1)
                                    sender_name = sender.split('(')[0].strip()
                                    # Formatar como na imagem de exemplo: "Dalltor Gestão e Projetos (projetos@dalltor.com.br)"
                                    sender = f"{sender_name}"
                                
                                # Verificar se há um email para o formato de exemplo com links
                                if '@' in recipient and '.' in recipient:
                                    recipient_email = recipient
                                    # Formatar o destinatário como o exemplo "Prefeitura Municipal de Barra Velha (engenharia@barravelha.sc.gov.br)"
                                    # Se o formato for simples (apenas email)
                                    if not recipient.startswith("(") and not "(" in recipient:
                                        recipient = f"Destinatário ({recipient_email})"
                                
                                # Se temos email do remetente, adicionamos parenteses conforme o exemplo
                                if sender_email:
                                    sender = f"{sender} ({sender_email})"
                                    
                                # Preparar o conteúdo do corpo do e-mail
                                body_text = email.get('body_text', '') or '(Sem conteúdo)'
                                
                                # Sanitizar o texto para evitar problemas com tags HTML e outros caracteres problemáticos
                                try:
                                    # Remover todas as tags HTML (incluindo atributos problemáticos como style="color:#ffffff")
                                    body_text = re.sub(r'<[^>]*>', ' ', body_text)
                                    
                                    # Codificar caracteres HTML que podem estar presentes no texto
                                    body_text = body_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                                    
                                    # Remover caracteres de controle e normalizar quebras de linha
                                    body_text = body_text.replace('\r', '').replace('\n\n\n', '\n\n')
                                    
                                    # Remover URLs que possam causar problemas
                                    body_text = re.sub(r'https?://[^\s]+', '[LINK]', body_text)
                                    
                                    # Normalizar espaços repetidos
                                    body_text = re.sub(r' +', ' ', body_text)
                                    
                                    # Remover caracteres especiais problemáticos para ReportLab
                                    problematic_chars = ['\u2028', '\u2029', '\x0c', '\x1b']
                                    for char in problematic_chars:
                                        body_text = body_text.replace(char, '')
                                        
                                    logger.info("Corpo do email sanitizado com sucesso")
                                except Exception as sanitize_error:
                                    logger.error(f"Erro ao sanitizar corpo do email: {sanitize_error}")
                                    body_text = "(Problema ao processar conteúdo do email)"
                                
                                # Se o texto for muito longo, limitar para evitar problemas no PDF
                                if len(body_text) > 15000:
                                    body_text = body_text[:15000] + "\n\n[Conteúdo truncado... texto muito grande]"
                                
                                # Conteúdo da tabela seguindo exatamente o formato do exemplo (incluindo o corpo)
                                content_data = [
                                    ["De:", sender, date_str, "E-mail"],
                                    ["Para:", recipient, "", ""],
                                    ["Assunto:", subject, "", ""],
                                    # Tratar o corpo do email como texto simples, não como Paragraph
                                    ["", Paragraph(body_text, self.styles['DalltorNormal']), "", ""]  # Linha com o corpo usando Paragraph para garantir formatação correta
                                ]
                                
                                # Estilo para o conteúdo da tabela seguindo exatamente o formato da imagem
                                content_style = [
                                    # Estilos gerais
                                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),  # Campo "De:", "Para:", etc em negrito
                                    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),  # Conteúdo em fonte normal
                                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Alinhamento vertical no topo
                                    ('BOX', (0, 0), (-1, -1), 1, colors.black),  # Borda externa completa
                                    ('GRID', (0, 0), (-1, -1), 1, colors.black),  # Grade interna completa como na imagem
                                    ('PADDING', (0, 0), (-1, -1), 6),  # Espaçamento interno
                                    # Cores específicas 
                                    ('BACKGROUND', (0, 0), (0, -1), colors.white),  # Fundo branco para primeira coluna
                                    ('BACKGROUND', (1, 0), (1, -1), colors.white),  # Fundo branco para segunda coluna
                                    ('BACKGROUND', (2, 0), (2, -1), colors.white),  # Fundo branco para terceira coluna
                                    ('BACKGROUND', (3, 0), (3, -1), colors.white),  # Fundo branco para quarta coluna
                                    # Estilos específicos para a linha do corpo do email
                                    ('SPAN', (1, 3), (3, 3)),  # Mesclar células da linha de corpo do email (linha 4)
                                ]
                                
                                # Criar tabela com conteúdo
                                content_table = Table(content_data, colWidths=[2*cm, 10*cm, 3*cm, 4*cm])
                                content_table.setStyle(TableStyle(content_style))
                                
                                elements.append(content_table)
                                elements.append(Spacer(1, 0.5*cm))
                                
                                # Adicionar espaço entre tabelas para melhor visualização
                                elements.append(Spacer(1, 0.8*cm))
                                
                            except Exception as email_error:
                                # Se houver erro ao processar um email específico, registrar o erro e continuar
                                logger.error(f"Erro ao processar email {i+1} do grupo {idx}: {str(email_error)}")
                                
                                # Adicionar mensagem de erro no relatório
                                error_msg = Paragraph(
                                    f"[ERRO: Não foi possível processar este email devido a um problema no conteúdo]",
                                    self.styles['DalltorNormal']
                                )
                                elements.append(error_msg)
                                elements.append(Spacer(1, 0.8*cm))
                        
                        # Se tiver mais emails do que mostramos
                        if len(group_emails) > 5:
                            elements.append(Paragraph(
                                f"Nota: Exibindo apenas 5 dos {len(group_emails)} emails deste remetente. Para visualizar todos, acesse o sistema.",
                                self.styles['DalltorNormal']
                            ))
                        
                        # Adicionar quebra de página após cada remetente exceto o último
                        if idx < total_groups:
                            elements.append(PageBreak())
            
            # Add footer
            footer_text = f"Relatório gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | Dalltor - Gestão e Projetos"
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
            logger.exception(f"Erro ao exportar PDF com template Dalltor: {str(e)}")
            
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
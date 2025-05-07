from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, DateField, TextAreaField, HiddenField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError
from datetime import datetime

class LoginForm(FlaskForm):
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired()])
    remember_me = BooleanField('Lembrar-me')
    submit = SubmitField('Entrar')

class OrganizationForm(FlaskForm):
    """Formulário para criar uma nova organização (empresa)"""
    name = StringField('Nome da Empresa', validators=[DataRequired(), Length(max=100)])
    domain = StringField('Domínio de Email (opcional)', validators=[Optional(), Length(max=100)])
    primary_color = StringField('Cor Primária', default="#3498db", validators=[Optional()])
    logo = FileField('Logo da Empresa (opcional)', validators=[Optional()])
    submit = SubmitField('Criar Organização')

class RegistrationForm(FlaskForm):
    username = StringField('Nome de Usuário', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('E-mail', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=8)])
    password2 = PasswordField('Confirmar Senha', validators=[DataRequired(), EqualTo('password')])
    organization_id = SelectField('Empresa', coerce=int, validators=[Optional()])
    create_organization = BooleanField('Criar nova organização', default=False)
    organization_name = StringField('Nome da Empresa', validators=[Optional(), Length(max=100)])
    organization_domain = StringField('Domínio de Email (opcional)', validators=[Optional()])
    submit = SubmitField('Cadastrar')

class EmailAccountForm(FlaskForm):
    email_address = StringField('Endereço de E-mail', validators=[DataRequired(), Email()])
    provider = SelectField('Provedor de E-mail', choices=[
        ('gmail', 'Gmail'),
        ('outlook', 'Outlook/Office 365'),
        ('umbler', 'Umbler')
    ], validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Adicionar Conta')

class ReportForm(FlaskForm):
    name = StringField('Nome do Relatório', validators=[DataRequired(), Length(max=120)])
    report_type = SelectField('Tipo de Relatório', choices=[
        ('summary', 'Relatório Resumido'),
        ('detailed', 'Relatório Detalhado')
    ], validators=[DataRequired()])
    email_account = SelectField('Conta de E-mail', coerce=int, validators=[Optional()])
    email_folder = SelectField('Pasta de E-mail', validators=[Optional()], default='INBOX')
    date_range_start = DateField('Data Inicial', validators=[Optional()], format='%Y-%m-%d')
    date_range_end = DateField('Data Final', validators=[Optional()], format='%Y-%m-%d')
    include_sent = BooleanField('Incluir E-mails Enviados', default=True)
    include_received = BooleanField('Incluir E-mails Recebidos', default=True)
    search_term = StringField('Termo de Busca', validators=[Optional(), Length(max=100)])
    group_by = SelectField('Agrupar Por (Relatório Detalhado)', choices=[
        ('sender', 'Agrupar por Remetente'),
        ('recipient', 'Agrupar por Destinatário'),
        ('none', 'Sem Agrupamento')
    ], default='sender', validators=[Optional()])
    submit = SubmitField('Gerar Relatório')
    
    def validate_date_range_end(self, field):
        if self.date_range_start.data and field.data and field.data < self.date_range_start.data:
            raise ValidationError('A data final deve ser posterior à data inicial')
        
        if field.data and field.data > datetime.now().date():
            raise ValidationError('A data final não pode estar no futuro')
            
class DeleteReportForm(FlaskForm):
    """Formulário simples para validação de CSRF em exclusão de relatórios"""
    report_id = HiddenField('ID do Relatório', validators=[DataRequired()])
    submit = SubmitField('Confirmar Exclusão')
    
class UserAdminForm(FlaskForm):
    """Formulário para administração de usuários"""
    username = StringField('Nome de Usuário', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('E-mail', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Nova Senha', validators=[Optional(), Length(min=8)])
    is_admin = BooleanField('Administrador', default=False)
    is_superadmin = BooleanField('Super Administrador', default=False)
    organization_id = SelectField('Organização', coerce=int, validators=[Optional()])
    submit = SubmitField('Salvar Alterações')

class DeleteUserForm(FlaskForm):
    """Formulário simples para validação de CSRF em exclusão de usuários"""
    user_id = HiddenField('ID do Usuário', validators=[DataRequired()])
    submit = SubmitField('Confirmar Exclusão')


class SupportTicketForm(FlaskForm):
    """Formulário para criar um novo ticket de suporte"""
    subject = StringField('Assunto', validators=[DataRequired(), Length(max=200)])
    message = TextAreaField('Mensagem', validators=[DataRequired(), Length(min=10, max=2000)])
    submit = SubmitField('Abrir Ticket')


class SupportMessageForm(FlaskForm):
    """Formulário para enviar mensagens de suporte"""
    message = TextAreaField('Mensagem', validators=[DataRequired(), Length(min=1, max=2000)])
    submit = SubmitField('Enviar')


class CloseTicketForm(FlaskForm):
    """Formulário simples para fechar ticket de suporte"""
    ticket_id = HiddenField('ID do Ticket', validators=[DataRequired()])
    submit = SubmitField('Marcar como Resolvido')


class ProfileForm(FlaskForm):
    """Formulário para edição de perfil de usuário"""
    username = StringField('Nome de Usuário', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('E-mail', validators=[DataRequired(), Email(), Length(max=120)])
    current_password = PasswordField('Senha Atual', validators=[Optional()])
    new_password = PasswordField('Nova Senha', validators=[Optional(), Length(min=8)])
    confirm_password = PasswordField('Confirmar Nova Senha', validators=[Optional(), EqualTo('new_password', message='As senhas devem ser iguais')])
    profile_image = FileField('Foto de Perfil', validators=[Optional()])
    submit = SubmitField('Salvar Alterações')

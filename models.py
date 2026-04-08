from datetime import date, datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

MESES = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}

STATUS_COMPETENCIA = ['PENDENTE', 'EM ANÁLISE', 'LIQUIDADO', 'PAGO']
PRODUTOS = [
    'COBRANCA COM REGISTRO',
    'RECEBIMENTO',
    'ORBAN',
    'PAGAMENTO A FORNECEDORES',
    'PAGAMENTOS DIVERSOS',
    'PAGAMENTO DE SALARIO',
]


class Contract(db.Model):
    __tablename__ = 'contracts'

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    contractor = db.Column(db.String(200), nullable=False)
    cnpj = db.Column(db.String(20))
    object_description = db.Column(db.Text)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    total_value = db.Column(db.Float, default=0.0)
    monthly_estimate = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='ATIVO')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    empenhos = db.relationship('Empenho', backref='contract', lazy=True,
                               order_by='Empenho.sub_elemento')
    competencias = db.relationship('Competencia', backref='contract', lazy=True,
                                   order_by='[Competencia.year, Competencia.month]')

    @property
    def display_name(self):
        return f'Contrato {self.number}/{self.year}'

    @property
    def total_executed(self):
        total = 0.0
        for comp in self.competencias:
            total += comp.valor_total
        return total

    @property
    def execution_percentage(self):
        if self.total_value and self.total_value > 0:
            return (self.total_executed / self.total_value) * 100
        return 0.0


class Empenho(db.Model):
    __tablename__ = 'empenhos'

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=False)
    number = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    sub_elemento = db.Column(db.String(10), nullable=False)
    description = db.Column(db.String(200))
    initial_value = db.Column(db.Float, default=0.0)
    reinforcement_value = db.Column(db.Float, default=0.0)
    annulment_value = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('ServiceItem', backref='empenho', lazy=True)

    @property
    def display_number(self):
        return f'{self.number}/{self.year}'

    @property
    def total_value(self):
        return self.initial_value + self.reinforcement_value - self.annulment_value

    @property
    def total_executed(self):
        return sum(item.valor_total or 0 for item in self.items)

    @property
    def total_ir(self):
        return sum(item.ir_value or 0 for item in self.items)

    @property
    def total_liquido(self):
        return sum(item.valor_liquido or 0 for item in self.items)

    @property
    def balance(self):
        return self.total_value - self.total_executed

    @property
    def execution_percentage(self):
        if self.total_value and self.total_value > 0:
            return (self.total_executed / self.total_value) * 100
        return 0.0


class Competencia(db.Model):
    __tablename__ = 'competencias'

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    oficio_number = db.Column(db.String(50))
    oficio_date = db.Column(db.Date)
    data_recebimento = db.Column(db.Date)
    status = db.Column(db.String(20), default='PENDENTE')
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('ServiceItem', backref='competencia', lazy=True,
                            cascade='all, delete-orphan',
                            order_by='[ServiceItem.produto, ServiceItem.servico]')

    @property
    def display_name(self):
        return f'{MESES.get(self.month, "?")}/{self.year}'

    @property
    def display_short(self):
        return f'{self.month:02d}/{self.year}'

    @property
    def valor_total(self):
        return sum(item.valor_total or 0 for item in self.items)

    @property
    def total_ir(self):
        return sum(item.ir_value or 0 for item in self.items)

    @property
    def total_liquido(self):
        return sum(item.valor_liquido or 0 for item in self.items)

    def items_by_empenho(self):
        """Group items by empenho for summary."""
        groups = {}
        for item in self.items:
            emp_id = item.empenho_id
            if emp_id not in groups:
                empenho = Empenho.query.get(emp_id)
                groups[emp_id] = {
                    'empenho': empenho,
                    'service_items': [],
                    'valor_total': 0.0,
                    'total_ir': 0.0,
                    'total_liquido': 0.0,
                }
            groups[emp_id]['service_items'].append(item)
            groups[emp_id]['valor_total'] += item.valor_total or 0
            groups[emp_id]['total_ir'] += item.ir_value or 0
            groups[emp_id]['total_liquido'] += item.valor_liquido or 0
        return groups

    def items_by_produto(self):
        """Group items by produto type."""
        groups = {}
        for item in self.items:
            prod = item.produto
            if prod not in groups:
                groups[prod] = {
                    'items': [],
                    'valor_total': 0.0,
                    'total_ir': 0.0,
                    'total_liquido': 0.0,
                }
            groups[prod]['items'].append(item)
            groups[prod]['valor_total'] += item.valor_total or 0
            groups[prod]['total_ir'] += item.ir_value or 0
            groups[prod]['total_liquido'] += item.valor_liquido or 0
        return groups


class ServiceItem(db.Model):
    __tablename__ = 'service_items'

    id = db.Column(db.Integer, primary_key=True)
    competencia_id = db.Column(db.Integer, db.ForeignKey('competencias.id'), nullable=False)
    empenho_id = db.Column(db.Integer, db.ForeignKey('empenhos.id'), nullable=False)
    data_evento = db.Column(db.String(50))
    produto = db.Column(db.String(50), nullable=False)
    servico = db.Column(db.String(200), nullable=False)
    valor_contrato = db.Column(db.String(50))
    valor_unitario = db.Column(db.Float, default=0.0)
    quantidade = db.Column(db.Integer, default=0)
    valor_total = db.Column(db.Float, default=0.0)
    processo = db.Column(db.String(50))
    ir_applicable = db.Column(db.Boolean, default=True)
    ir_rate = db.Column(db.Float, default=0.024)
    ir_value = db.Column(db.Float, default=0.0)
    valor_liquido = db.Column(db.Float, default=0.0)
    debitado = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def calculate_values(self):
        """Calculate valor_total, IR, and valor_liquido."""
        self.valor_total = (self.valor_unitario or 0) * (self.quantidade or 0)
        if self.ir_applicable and self.valor_total > 0:
            self.ir_value = round(self.valor_total * self.ir_rate, 2)
        else:
            self.ir_value = 0.0
        self.valor_liquido = self.valor_total - self.ir_value


class ServiceType(db.Model):
    """Pre-defined service types with default values for quick data entry."""
    __tablename__ = 'service_types'

    id = db.Column(db.Integer, primary_key=True)
    produto = db.Column(db.String(50), nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    sub_elemento = db.Column(db.String(10), nullable=False)
    valor_contrato = db.Column(db.String(50))
    valor_unitario_padrao = db.Column(db.Float, default=0.0)
    ir_applicable = db.Column(db.Boolean, default=True)
    ir_rate = db.Column(db.Float, default=0.024)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

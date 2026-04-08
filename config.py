import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'semfaz-contrato-bb-591-2025')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(basedir, 'instance', 'contrato_bb.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configurações do contrato
    CONTRATO_NUMERO = '591'
    CONTRATO_ANO = 2025
    CONTRATO_CONTRATADA = 'Banco do Brasil S.A.'
    CONTRATO_CNPJ = '00.000.000/0001-91'

    # Alíquota padrão de retenção (IR + CSLL) conforme IN RFB 1234/2012
    # Para instituições financeiras: IRRF 1,5% + CSLL 1,0% - COFINS e PIS dispensados
    # Alíquota efetiva aplicada: 2,4% conforme prática do contrato
    IR_RATE_DEFAULT = 0.024

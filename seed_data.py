"""
Seed Data - Contrato BB 591/2025
Popula o banco com dados iniciais do contrato, empenhos e tipos de servico.

Uso: python seed_data.py
"""
from datetime import date
from app import create_app
from models import db, Contract, Empenho, ServiceType


def seed():
    app = create_app()
    with app.app_context():
        db.create_all()

        # --- Contrato ---
        contract = Contract.query.first()
        if not contract:
            contract = Contract(
                number='591',
                year=2025,
                description='Servicos Financeiros - Banco do Brasil',
                contractor='Banco do Brasil S.A.',
                cnpj='00.000.000/0001-91',
                object_description=(
                    'Prestacao de servicos financeiros ao Municipio de Sao Luis, '
                    'incluindo arrecadacao de tributos municipais, processamento '
                    'de folha de pagamento, pagamento a fornecedores e servicos '
                    'bancarios diversos.'
                ),
                start_date=date(2025, 8, 1),
                end_date=date(2026, 7, 31),
                total_value=0.0,
                monthly_estimate=0.0,
                status='ATIVO',
            )
            db.session.add(contract)
            db.session.flush()
            print(f'Contrato {contract.display_name} criado.')
        else:
            print(f'Contrato {contract.display_name} ja existe.')

        # --- Empenhos 2026 ---
        empenhos_data = [
            {
                'number': '268', 'year': 2026, 'sub_elemento': '98',
                'description': 'Tarifas Bancarias - Recebimentos/Cobranca',
                'initial_value': 0.0,
            },
            {
                'number': '270', 'year': 2026, 'sub_elemento': '93',
                'description': 'Folha de Pagamento',
                'initial_value': 0.0,
            },
            {
                'number': '271', 'year': 2026, 'sub_elemento': '92',
                'description': 'Tarifas Bancarias - Pagamento',
                'initial_value': 0.0,
            },
        ]

        for emp_data in empenhos_data:
            existing = Empenho.query.filter_by(
                contract_id=contract.id,
                number=emp_data['number'],
                year=emp_data['year'],
            ).first()
            if not existing:
                emp = Empenho(contract_id=contract.id, **emp_data)
                db.session.add(emp)
                print(f'  Empenho {emp_data["number"]}/{emp_data["year"]} '
                      f'(SE {emp_data["sub_elemento"]}) criado.')
            else:
                print(f'  Empenho {emp_data["number"]}/{emp_data["year"]} ja existe.')

        # --- Tipos de Servico (17 tipos extraidos dos oficios do BB) ---
        service_types = [
            # === COBRANCA COM REGISTRO (Oficios 001/002 -> SE 98) ===
            {
                'produto': 'COBRANCA COM REGISTRO',
                'nome': 'CBR Liquidacao Guiche',
                'sub_elemento': '98',
                'valor_contrato': 'R$ 4,95',
                'valor_unitario_padrao': 4.95,
            },
            {
                'produto': 'COBRANCA COM REGISTRO',
                'nome': 'CBR Liquidacao PIX',
                'sub_elemento': '98',
                'valor_contrato': 'R$ 0,87',
                'valor_unitario_padrao': 0.87,
            },
            # === RECEBIMENTO (Oficio 003 -> SE 98) ===
            {
                'produto': 'RECEBIMENTO',
                'nome': 'Tarifa Guia c/ Barra Internet',
                'sub_elemento': '98',
                'valor_contrato': 'R$ 2,53',
                'valor_unitario_padrao': 2.53,
            },
            {
                'produto': 'RECEBIMENTO',
                'nome': 'Tarifa Guia c/ Cod. Barras TAA',
                'sub_elemento': '98',
                'valor_contrato': 'R$ 2,53',
                'valor_unitario_padrao': 2.53,
            },
            {
                'produto': 'RECEBIMENTO',
                'nome': 'Tarifa Guia c/ Cod. Barr Gefin',
                'sub_elemento': '98',
                'valor_contrato': 'R$ 2,53',
                'valor_unitario_padrao': 2.53,
            },
            {
                'produto': 'RECEBIMENTO',
                'nome': 'Tarifa Guia c/ Cod. Barr Coban',
                'sub_elemento': '98',
                'valor_contrato': 'R$ 2,53',
                'valor_unitario_padrao': 2.53,
            },
            {
                'produto': 'RECEBIMENTO',
                'nome': 'Tarifa Guia c/ Cod. Barras PGT',
                'sub_elemento': '98',
                'valor_contrato': 'R$ 2,53',
                'valor_unitario_padrao': 2.53,
            },
            {
                'produto': 'RECEBIMENTO',
                'nome': 'Tarifa Arrec TAA Multibanco',
                'sub_elemento': '98',
                'valor_contrato': 'R$ 2,53',
                'valor_unitario_padrao': 2.53,
            },
            {
                'produto': 'RECEBIMENTO',
                'nome': 'Guias Arrecadacao Pix Municipal',
                'sub_elemento': '98',
                'valor_contrato': 'R$ 0,87',
                'valor_unitario_padrao': 0.87,
            },
            # === ORBAN (Oficio 004 -> SE 92) ===
            {
                'produto': 'ORBAN',
                'nome': 'Tarifa Ordem Bancaria-Cred Cta',
                'sub_elemento': '92',
                'valor_contrato': 'R$ 1,02',
                'valor_unitario_padrao': 1.02,
            },
            {
                'produto': 'ORBAN',
                'nome': 'Tarif ORBAN-Fatura c/Cod Barra',
                'sub_elemento': '92',
                'valor_contrato': 'R$ 3,03',
                'valor_unitario_padrao': 3.03,
            },
            {
                'produto': 'ORBAN',
                'nome': 'Tar Ordem Bancaria-Pag Tributo',
                'sub_elemento': '92',
                'valor_contrato': 'R$ 106,50',
                'valor_unitario_padrao': 106.50,
            },
            # === PAGAMENTO A FORNECEDORES (Oficio 005 -> SE 92) ===
            {
                'produto': 'PAGAMENTO A FORNECEDORES',
                'nome': 'Tarifa Pag Fornec Credito Cta',
                'sub_elemento': '92',
                'valor_contrato': 'R$ 1,02',
                'valor_unitario_padrao': 1.02,
            },
            {
                'produto': 'PAGAMENTO A FORNECEDORES',
                'nome': 'Tarifa Pgto Fornecedores TED',
                'sub_elemento': '92',
                'valor_contrato': 'R$ 4,51',
                'valor_unitario_padrao': 4.51,
            },
            # === PAGAMENTOS DIVERSOS (Oficio 005 -> SE 92) ===
            {
                'produto': 'PAGAMENTOS DIVERSOS',
                'nome': 'Tarifa sobre Pagamentos Cred Cta',
                'sub_elemento': '92',
                'valor_contrato': 'R$ 1,02',
                'valor_unitario_padrao': 1.02,
            },
            {
                'produto': 'PAGAMENTOS DIVERSOS',
                'nome': 'Tarifa sobre Pagamentos DOC/TED',
                'sub_elemento': '92',
                'valor_contrato': 'R$ 4,51',
                'valor_unitario_padrao': 4.51,
            },
            # === PAGAMENTO DE SALARIO (Oficio 006 -> SE 93) ===
            {
                'produto': 'PAGAMENTO DE SALARIO',
                'nome': 'Tarifa Pgto Salario Cred Conta',
                'sub_elemento': '93',
                'valor_contrato': 'R$ 1,02',
                'valor_unitario_padrao': 1.02,
            },
        ]

        created_count = 0
        for st_data in service_types:
            existing = ServiceType.query.filter_by(
                produto=st_data['produto'],
                nome=st_data['nome'],
            ).first()
            if not existing:
                st = ServiceType(
                    ir_applicable=True,
                    ir_rate=0.024,
                    ativo=True,
                    **st_data,
                )
                db.session.add(st)
                created_count += 1

        db.session.commit()
        print(f'\n{created_count} tipos de servico criados (de {len(service_types)} total).')
        print('\nSeed concluido com sucesso!')
        print('Execute: python app.py')
        print('Acesse: http://localhost:5000')


if __name__ == '__main__':
    seed()

import io
import os
from datetime import date, datetime

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, make_response)
from xhtml2pdf import pisa

from config import Config
from models import (db, Contract, Empenho, Competencia, ServiceItem,
                    ServiceType, MESES, STATUS_COMPETENCIA, PRODUTOS)
from ir_calculator import calcular_retencao, calcular_competencia, ALIQUOTA_EFETIVA
from pdf_parser import parse_pdf


def create_app(config_class=Config):
    app = Flask(__name__,
                template_folder='app/templates',
                static_folder='app/static')
    app.config.from_object(config_class)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Jinja2 filters
    @app.template_filter('brl')
    def format_brl(value):
        """Format number as Brazilian Real currency."""
        if value is None:
            return 'R$ -'
        try:
            value = float(value)
        except (ValueError, TypeError):
            return 'R$ -'
        if value == 0:
            return 'R$ -'
        return f'R$ {value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

    @app.template_filter('brl_always')
    def format_brl_always(value):
        """Format number as BRL, showing R$ 0,00 for zero."""
        if value is None:
            value = 0.0
        try:
            value = float(value)
        except (ValueError, TypeError):
            value = 0.0
        return f'R$ {value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

    @app.template_filter('pct')
    def format_pct(value):
        """Format number as percentage."""
        if value is None:
            return '0,00%'
        return f'{value:,.2f}%'.replace(',', 'X').replace('.', ',').replace('X', '.')

    @app.template_filter('mes_nome')
    def mes_nome(value):
        """Return month name."""
        return MESES.get(value, '?')

    @app.context_processor
    def inject_globals():
        return {
            'meses': MESES,
            'status_list': STATUS_COMPETENCIA,
            'produtos': PRODUTOS,
            'now': datetime.utcnow(),
        }

    # ---------------------------------------------------------------
    # DASHBOARD
    # ---------------------------------------------------------------
    @app.route('/')
    def dashboard():
        contract = Contract.query.first()
        if not contract:
            return redirect(url_for('setup'))

        empenhos = Empenho.query.filter_by(contract_id=contract.id).all()
        competencias = Competencia.query.filter_by(
            contract_id=contract.id
        ).order_by(Competencia.year, Competencia.month).all()

        # Monthly execution data for charts
        monthly_data = []
        for comp in competencias:
            monthly_data.append({
                'label': comp.display_short,
                'valor_total': round(comp.valor_total, 2),
                'total_ir': round(comp.total_ir, 2),
                'total_liquido': round(comp.total_liquido, 2),
            })

        # Empenho execution data
        empenho_data = []
        for emp in empenhos:
            empenho_data.append({
                'label': f'{emp.display_number} (SE {emp.sub_elemento})',
                'empenhado': round(emp.total_value, 2),
                'executado': round(emp.total_executed, 2),
                'saldo': round(emp.balance, 2),
                'percentual': round(emp.execution_percentage, 2),
            })

        # Totals
        total_empenhado = sum(e.total_value for e in empenhos)
        total_executado = sum(e.total_executed for e in empenhos)
        total_ir = sum(e.total_ir for e in empenhos)
        total_liquido = sum(e.total_liquido for e in empenhos)
        total_saldo = total_empenhado - total_executado

        return render_template('dashboard.html',
                               contract=contract,
                               empenhos=empenhos,
                               competencias=competencias,
                               monthly_data=monthly_data,
                               empenho_data=empenho_data,
                               total_empenhado=total_empenhado,
                               total_executado=total_executado,
                               total_ir=total_ir,
                               total_liquido=total_liquido,
                               total_saldo=total_saldo)

    # ---------------------------------------------------------------
    # SETUP (first run)
    # ---------------------------------------------------------------
    @app.route('/setup', methods=['GET', 'POST'])
    def setup():
        existing = Contract.query.first()
        if existing:
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            contract = Contract(
                number=request.form.get('number', '591'),
                year=int(request.form.get('year', 2025)),
                description=request.form.get('description', ''),
                contractor=request.form.get('contractor', 'Banco do Brasil S.A.'),
                cnpj=request.form.get('cnpj', ''),
                object_description=request.form.get('object_description', ''),
                start_date=_parse_date(request.form.get('start_date')),
                end_date=_parse_date(request.form.get('end_date')),
                total_value=_parse_float(request.form.get('total_value', '0')),
                monthly_estimate=_parse_float(request.form.get('monthly_estimate', '0')),
            )
            db.session.add(contract)
            db.session.flush()

            # Create 3 default empenhos
            for i in range(1, 4):
                num = request.form.get(f'emp_number_{i}', '')
                if num:
                    emp = Empenho(
                        contract_id=contract.id,
                        number=request.form.get(f'emp_number_{i}', ''),
                        year=int(request.form.get(f'emp_year_{i}', contract.year)),
                        sub_elemento=request.form.get(f'emp_sub_{i}', ''),
                        description=request.form.get(f'emp_desc_{i}', ''),
                        initial_value=_parse_float(request.form.get(f'emp_value_{i}', '0')),
                    )
                    db.session.add(emp)

            db.session.commit()
            flash('Contrato configurado com sucesso!', 'success')
            return redirect(url_for('dashboard'))

        return render_template('setup.html')

    # ---------------------------------------------------------------
    # COMPETÊNCIAS (Monthly Periods)
    # ---------------------------------------------------------------
    @app.route('/competencias')
    def competencia_list():
        contract = Contract.query.first()
        if not contract:
            return redirect(url_for('setup'))

        competencias = Competencia.query.filter_by(
            contract_id=contract.id
        ).order_by(Competencia.year.desc(), Competencia.month.desc()).all()

        return render_template('competencia_list.html',
                               contract=contract,
                               competencias=competencias)

    @app.route('/competencias/nova', methods=['GET', 'POST'])
    def competencia_new():
        contract = Contract.query.first()
        if not contract:
            return redirect(url_for('setup'))

        if request.method == 'POST':
            month = int(request.form.get('month', 1))
            year = int(request.form.get('year', date.today().year))

            existing = Competencia.query.filter_by(
                contract_id=contract.id, month=month, year=year
            ).first()
            if existing:
                flash(f'Competência {MESES[month]}/{year} já existe!', 'warning')
                return redirect(url_for('competencia_detail', id=existing.id))

            comp = Competencia(
                contract_id=contract.id,
                month=month,
                year=year,
                oficio_number=request.form.get('oficio_number', ''),
                oficio_date=_parse_date(request.form.get('oficio_date')),
                data_recebimento=_parse_date(request.form.get('data_recebimento')),
                status=request.form.get('status', 'PENDENTE'),
                observacoes=request.form.get('observacoes', ''),
            )
            db.session.add(comp)
            db.session.commit()
            flash(f'Competência {comp.display_name} criada com sucesso!', 'success')
            return redirect(url_for('competencia_detail', id=comp.id))

        empenhos = Empenho.query.filter_by(contract_id=contract.id).all()
        return render_template('competencia_form.html',
                               contract=contract,
                               empenhos=empenhos,
                               competencia=None)

    @app.route('/competencias/<int:id>')
    def competencia_detail(id):
        comp = Competencia.query.get_or_404(id)
        contract = comp.contract
        empenhos = Empenho.query.filter_by(contract_id=contract.id).all()
        service_types = ServiceType.query.filter_by(ativo=True).order_by(
            ServiceType.produto, ServiceType.nome).all()

        summary_by_empenho = comp.items_by_empenho()
        summary_by_produto = comp.items_by_produto()

        return render_template('competencia_detail.html',
                               contract=contract,
                               competencia=comp,
                               empenhos=empenhos,
                               service_types=service_types,
                               summary_by_empenho=summary_by_empenho,
                               summary_by_produto=summary_by_produto)

    @app.route('/competencias/<int:id>/editar', methods=['GET', 'POST'])
    def competencia_edit(id):
        comp = Competencia.query.get_or_404(id)
        contract = comp.contract

        if request.method == 'POST':
            comp.oficio_number = request.form.get('oficio_number', '')
            comp.oficio_date = _parse_date(request.form.get('oficio_date'))
            comp.data_recebimento = _parse_date(request.form.get('data_recebimento'))
            comp.status = request.form.get('status', comp.status)
            comp.observacoes = request.form.get('observacoes', '')
            db.session.commit()
            flash('Competência atualizada com sucesso!', 'success')
            return redirect(url_for('competencia_detail', id=comp.id))

        empenhos = Empenho.query.filter_by(contract_id=contract.id).all()
        return render_template('competencia_form.html',
                               contract=contract,
                               empenhos=empenhos,
                               competencia=comp)

    @app.route('/competencias/<int:id>/item', methods=['POST'])
    def add_service_item(id):
        comp = Competencia.query.get_or_404(id)

        empenho_id = int(request.form.get('empenho_id'))
        ir_applicable = request.form.get('ir_applicable') == 'on'
        ir_rate = _parse_float(request.form.get('ir_rate', '2.4')) / 100

        item = ServiceItem(
            competencia_id=comp.id,
            empenho_id=empenho_id,
            data_evento=request.form.get('data_evento', ''),
            produto=request.form.get('produto', ''),
            servico=request.form.get('servico', ''),
            valor_contrato=request.form.get('valor_contrato', ''),
            valor_unitario=_parse_float(request.form.get('valor_unitario', '0')),
            quantidade=int(_parse_float(request.form.get('quantidade', '0'))),
            processo=request.form.get('processo', ''),
            ir_applicable=ir_applicable,
            ir_rate=ir_rate,
            debitado=_parse_float(request.form.get('debitado', '0')),
        )
        item.calculate_values()
        db.session.add(item)
        db.session.commit()
        flash('Item adicionado com sucesso!', 'success')
        return redirect(url_for('competencia_detail', id=comp.id))

    @app.route('/competencias/<int:id>/item/<int:item_id>/edit', methods=['POST'])
    def edit_service_item(id, item_id):
        item = ServiceItem.query.get_or_404(item_id)

        item.empenho_id = int(request.form.get('empenho_id', item.empenho_id))
        item.data_evento = request.form.get('data_evento', item.data_evento)
        item.produto = request.form.get('produto', item.produto)
        item.servico = request.form.get('servico', item.servico)
        item.valor_contrato = request.form.get('valor_contrato', item.valor_contrato)
        item.valor_unitario = _parse_float(request.form.get('valor_unitario', '0'))
        item.quantidade = int(_parse_float(request.form.get('quantidade', '0')))
        item.processo = request.form.get('processo', item.processo)
        item.ir_applicable = request.form.get('ir_applicable') == 'on'
        item.ir_rate = _parse_float(request.form.get('ir_rate', '2.4')) / 100
        item.debitado = _parse_float(request.form.get('debitado', '0'))
        item.calculate_values()

        db.session.commit()
        flash('Item atualizado com sucesso!', 'success')
        return redirect(url_for('competencia_detail', id=id))

    @app.route('/competencias/<int:id>/item/<int:item_id>/delete', methods=['POST'])
    def delete_service_item(id, item_id):
        item = ServiceItem.query.get_or_404(item_id)
        db.session.delete(item)
        db.session.commit()
        flash('Item removido com sucesso!', 'success')
        return redirect(url_for('competencia_detail', id=id))

    # ---------------------------------------------------------------
    # EMPENHOS
    # ---------------------------------------------------------------
    @app.route('/empenhos')
    def empenhos_view():
        contract = Contract.query.first()
        if not contract:
            return redirect(url_for('setup'))

        empenhos = Empenho.query.filter_by(contract_id=contract.id).all()

        # Execution by month for each empenho
        empenho_monthly = {}
        for emp in empenhos:
            monthly = {}
            for item in emp.items:
                comp = item.competencia
                key = (comp.year, comp.month)
                if key not in monthly:
                    monthly[key] = {
                        'competencia': comp.display_short,
                        'valor_total': 0.0,
                        'ir': 0.0,
                        'liquido': 0.0,
                    }
                monthly[key]['valor_total'] += item.valor_total or 0
                monthly[key]['ir'] += item.ir_value or 0
                monthly[key]['liquido'] += item.valor_liquido or 0
            empenho_monthly[emp.id] = dict(sorted(monthly.items()))

        return render_template('empenhos.html',
                               contract=contract,
                               empenhos=empenhos,
                               empenho_monthly=empenho_monthly)

    @app.route('/empenhos/<int:id>/update', methods=['POST'])
    def update_empenho(id):
        emp = Empenho.query.get_or_404(id)
        emp.initial_value = _parse_float(request.form.get('initial_value', '0'))
        emp.reinforcement_value = _parse_float(request.form.get('reinforcement_value', '0'))
        emp.annulment_value = _parse_float(request.form.get('annulment_value', '0'))
        emp.description = request.form.get('description', emp.description)
        db.session.commit()
        flash(f'Empenho {emp.display_number} atualizado!', 'success')
        return redirect(url_for('empenhos_view'))

    # ---------------------------------------------------------------
    # ACOMPANHAMENTO CONTRATUAL
    # ---------------------------------------------------------------
    @app.route('/acompanhamento')
    def contract_tracking():
        contract = Contract.query.first()
        if not contract:
            return redirect(url_for('setup'))

        empenhos = Empenho.query.filter_by(contract_id=contract.id).all()
        competencias = Competencia.query.filter_by(
            contract_id=contract.id
        ).order_by(Competencia.year, Competencia.month).all()

        # Build execution matrix: competencia x empenho
        matrix = []
        running_totals = {emp.id: 0.0 for emp in empenhos}
        grand_total_running = 0.0

        for comp in competencias:
            row = {
                'competencia': comp,
                'empenhos': {},
                'total': comp.valor_total,
                'total_ir': comp.total_ir,
                'total_liquido': comp.total_liquido,
            }
            by_emp = comp.items_by_empenho()
            for emp in empenhos:
                emp_data = by_emp.get(emp.id, {})
                val = emp_data.get('valor_total', 0.0)
                running_totals[emp.id] += val
                row['empenhos'][emp.id] = {
                    'valor': val,
                    'ir': emp_data.get('total_ir', 0.0),
                    'liquido': emp_data.get('total_liquido', 0.0),
                    'acumulado': running_totals[emp.id],
                }
            grand_total_running += comp.valor_total
            row['acumulado_geral'] = grand_total_running
            matrix.append(row)

        return render_template('contract_tracking.html',
                               contract=contract,
                               empenhos=empenhos,
                               competencias=competencias,
                               matrix=matrix,
                               running_totals=running_totals)

    # ---------------------------------------------------------------
    # SERVIÇOS (Configuration)
    # ---------------------------------------------------------------
    @app.route('/servicos', methods=['GET', 'POST'])
    def services_config():
        contract = Contract.query.first()
        if not contract:
            return redirect(url_for('setup'))

        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'add':
                st = ServiceType(
                    produto=request.form.get('produto', ''),
                    nome=request.form.get('nome', ''),
                    sub_elemento=request.form.get('sub_elemento', ''),
                    valor_contrato=request.form.get('valor_contrato', ''),
                    valor_unitario_padrao=_parse_float(
                        request.form.get('valor_unitario_padrao', '0')),
                    ir_applicable=request.form.get('ir_applicable') == 'on',
                    ir_rate=_parse_float(
                        request.form.get('ir_rate', '2.4')) / 100,
                )
                db.session.add(st)
                flash('Serviço adicionado!', 'success')

            elif action == 'delete':
                st_id = int(request.form.get('service_type_id', 0))
                st = ServiceType.query.get(st_id)
                if st:
                    db.session.delete(st)
                    flash('Serviço removido!', 'success')

            db.session.commit()
            return redirect(url_for('services_config'))

        empenhos = Empenho.query.filter_by(contract_id=contract.id).all()
        service_types = ServiceType.query.order_by(
            ServiceType.produto, ServiceType.nome).all()

        return render_template('services_config.html',
                               contract=contract,
                               empenhos=empenhos,
                               service_types=service_types)

    # ---------------------------------------------------------------
    # IMPORT OFICIOS PDF
    # ---------------------------------------------------------------
    @app.route('/importar', methods=['GET', 'POST'])
    def import_oficios():
        contract = Contract.query.first()
        if not contract:
            return redirect(url_for('setup'))

        empenhos = Empenho.query.filter_by(contract_id=contract.id).all()
        results = []
        detected_month = None
        detected_year = None

        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'analyze':
                files = request.files.getlist('pdfs')
                import tempfile
                for f in files:
                    if f and f.filename.endswith('.pdf'):
                        with tempfile.NamedTemporaryFile(suffix='.pdf',
                                                         delete=False) as tmp:
                            f.save(tmp.name)
                            try:
                                result = parse_pdf(tmp.name)
                                result['filename'] = f.filename
                                results.append(result)
                            except Exception as e:
                                results.append({
                                    'filename': f.filename,
                                    'error': str(e),
                                    'items': [], 'valid': False,
                                })
                            finally:
                                os.unlink(tmp.name)

                for r in results:
                    if r.get('end_month'):
                        detected_month = r['end_month']
                        detected_year = r['end_year']
                        break

                # Store results in session for confirm step
                from flask import session
                session['import_results'] = results
                session['detected_month'] = detected_month
                session['detected_year'] = detected_year

                return render_template('import_oficios.html',
                                       contract=contract,
                                       empenhos=empenhos,
                                       results=results,
                                       detected_month=detected_month,
                                       detected_year=detected_year,
                                       step='preview')

            elif action == 'confirm':
                from flask import session
                results = session.get('import_results', [])
                month = int(request.form.get('month', 3))
                year = int(request.form.get('year', 2026))
                status = request.form.get('status', 'EM ANÁLISE')

                # Find or create competencia
                comp = Competencia.query.filter_by(
                    contract_id=contract.id, month=month, year=year
                ).first()
                if not comp:
                    oficio_nums = ', '.join(
                        r.get('oficio_num', '') for r in results
                        if r.get('oficio_num'))
                    comp = Competencia(
                        contract_id=contract.id, month=month, year=year,
                        oficio_number=oficio_nums, status=status)
                    db.session.add(comp)
                    db.session.flush()

                count = 0
                for r in results:
                    for item in r.get('items', []):
                        emp = next((e for e in empenhos
                                    if e.sub_elemento == item['sub_elemento']),
                                   empenhos[0] if empenhos else None)
                        if not emp:
                            continue
                        si = ServiceItem(
                            competencia_id=comp.id,
                            empenho_id=emp.id,
                            data_evento=r.get('periodo', ''),
                            produto=item['produto'],
                            servico=item['servico'],
                            valor_contrato=f"R$ {item['valor_unitario']:.2f}",
                            valor_unitario=item['valor_unitario'],
                            quantidade=item['quantidade'],
                            valor_total=item['valor_total'],
                            ir_applicable=True,
                            ir_rate=0.024,
                            ir_value=item['ir_value'],
                            valor_liquido=item['valor_liquido'],
                        )
                        db.session.add(si)
                        count += 1

                db.session.commit()
                session.pop('import_results', None)
                flash(f'{count} itens importados para '
                      f'{MESES.get(month, "?")}/{year}!', 'success')
                return redirect(url_for('competencia_detail', id=comp.id))

        return render_template('import_oficios.html',
                               contract=contract,
                               empenhos=empenhos,
                               results=[],
                               step='upload')

    # ---------------------------------------------------------------
    # PDF REPORTS
    # ---------------------------------------------------------------
    @app.route('/competencias/<int:id>/pdf')
    def monthly_report_pdf(id):
        comp = Competencia.query.get_or_404(id)
        contract = comp.contract
        empenhos = Empenho.query.filter_by(contract_id=contract.id).all()
        summary_by_empenho = comp.items_by_empenho()

        html = render_template('pdf/monthly_report.html',
                               contract=contract,
                               competencia=comp,
                               empenhos=empenhos,
                               summary_by_empenho=summary_by_empenho,
                               generation_date=date.today())

        pdf = _generate_pdf(html)
        if pdf:
            response = make_response(pdf)
            response.headers['Content-Type'] = 'application/pdf'
            filename = f'relatorio_mensal_{comp.display_short.replace("/", "_")}.pdf'
            response.headers['Content-Disposition'] = f'inline; filename={filename}'
            return response

        flash('Erro ao gerar PDF. Verifique os dados.', 'danger')
        return redirect(url_for('competencia_detail', id=id))

    @app.route('/acompanhamento/pdf')
    def contract_tracking_pdf():
        contract = Contract.query.first()
        if not contract:
            return redirect(url_for('setup'))

        empenhos = Empenho.query.filter_by(contract_id=contract.id).all()
        competencias = Competencia.query.filter_by(
            contract_id=contract.id
        ).order_by(Competencia.year, Competencia.month).all()

        # Build matrix
        matrix = []
        running_totals = {emp.id: 0.0 for emp in empenhos}

        for comp in competencias:
            row = {
                'competencia': comp,
                'empenhos': {},
                'total': comp.valor_total,
                'total_ir': comp.total_ir,
                'total_liquido': comp.total_liquido,
            }
            by_emp = comp.items_by_empenho()
            for emp in empenhos:
                emp_data = by_emp.get(emp.id, {})
                val = emp_data.get('valor_total', 0.0)
                running_totals[emp.id] += val
                row['empenhos'][emp.id] = {
                    'valor': val,
                    'ir': emp_data.get('total_ir', 0.0),
                    'liquido': emp_data.get('total_liquido', 0.0),
                    'acumulado': running_totals[emp.id],
                }
            matrix.append(row)

        html = render_template('pdf/contract_tracking.html',
                               contract=contract,
                               empenhos=empenhos,
                               competencias=competencias,
                               matrix=matrix,
                               running_totals=running_totals,
                               generation_date=date.today())

        pdf = _generate_pdf(html)
        if pdf:
            response = make_response(pdf)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = \
                'inline; filename=acompanhamento_contratual.pdf'
            return response

        flash('Erro ao gerar PDF.', 'danger')
        return redirect(url_for('contract_tracking'))

    # ---------------------------------------------------------------
    # API (JSON data for charts)
    # ---------------------------------------------------------------
    @app.route('/api/dashboard-data')
    def api_dashboard_data():
        contract = Contract.query.first()
        if not contract:
            return jsonify({'error': 'No contract found'}), 404

        empenhos = Empenho.query.filter_by(contract_id=contract.id).all()
        competencias = Competencia.query.filter_by(
            contract_id=contract.id
        ).order_by(Competencia.year, Competencia.month).all()

        monthly = [
            {
                'label': c.display_short,
                'valor_total': round(c.valor_total, 2),
                'total_ir': round(c.total_ir, 2),
                'total_liquido': round(c.total_liquido, 2),
            }
            for c in competencias
        ]

        emp_data = [
            {
                'label': f'{e.display_number} (SE {e.sub_elemento})',
                'empenhado': round(e.total_value, 2),
                'executado': round(e.total_executed, 2),
                'saldo': round(e.balance, 2),
            }
            for e in empenhos
        ]

        return jsonify({
            'monthly': monthly,
            'empenhos': emp_data,
            'total_contrato': contract.total_value,
            'total_executado': round(contract.total_executed, 2),
        })

    @app.route('/api/service-type/<int:id>')
    def api_service_type(id):
        st = ServiceType.query.get_or_404(id)
        return jsonify({
            'produto': st.produto,
            'nome': st.nome,
            'sub_elemento': st.sub_elemento,
            'valor_contrato': st.valor_contrato,
            'valor_unitario_padrao': st.valor_unitario_padrao,
            'ir_applicable': st.ir_applicable,
            'ir_rate': st.ir_rate * 100,
        })

    # ---------------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------------
    def _parse_float(value):
        """Parse Brazilian formatted numbers."""
        if not value:
            return 0.0
        try:
            # Handle Brazilian format: 1.234,56 -> 1234.56
            value = str(value).strip()
            value = value.replace('R$', '').replace(' ', '')
            if ',' in value and '.' in value:
                value = value.replace('.', '').replace(',', '.')
            elif ',' in value:
                value = value.replace(',', '.')
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _parse_date(value):
        """Parse date from form input."""
        if not value:
            return None
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            return None

    def _generate_pdf(html_string):
        """Generate PDF from HTML string."""
        result = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.StringIO(html_string), dest=result,
                                      encoding='utf-8')
        if pisa_status.err:
            return None
        return result.getvalue()

    return app


# Create the app instance
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)

"""
Parser de PDFs dos Oficios do Banco do Brasil - Contrato 591/2025

Extrai automaticamente os dados dos demonstrativos de tarifas
enviados mensalmente pelo BB, consolida por tipo de servico
e mapeia para os empenhos corretos.
"""
import re
import pdfplumber


# Mapeamento: (regex descricao, tarifa) -> (produto, servico, sub_elemento)
SERVICE_MAP = [
    (re.compile(r'cbr liquida', re.I), 4.95,
     'COBRANCA COM REGISTRO', 'CBR Liquidacao Guiche', '98'),
    (re.compile(r'cbr liquida', re.I), 0.87,
     'COBRANCA COM REGISTRO', 'CBR Liquidacao PIX', '98'),
    (re.compile(r'barra internet', re.I), 2.53,
     'RECEBIMENTO', 'Tarifa Guia c/ Barra Internet', '98'),
    (re.compile(r'barras taa', re.I), 2.53,
     'RECEBIMENTO', 'Tarifa Guia c/ Cod. Barras TAA', '98'),
    (re.compile(r'barr gefin', re.I), 2.53,
     'RECEBIMENTO', 'Tarifa Guia c/ Cod. Barr Gefin', '98'),
    (re.compile(r'barr coban', re.I), 2.53,
     'RECEBIMENTO', 'Tarifa Guia c/ Cod. Barr Coban', '98'),
    (re.compile(r'barras pgt', re.I), 2.53,
     'RECEBIMENTO', 'Tarifa Guia c/ Cod. Barras PGT', '98'),
    (re.compile(r'multibanco', re.I), 2.53,
     'RECEBIMENTO', 'Tarifa Arrec TAA Multibanco', '98'),
    (re.compile(r'pix municipa', re.I), 0.87,
     'RECEBIMENTO', 'Guias Arrecadacao Pix Municipal', '98'),
    (re.compile(r'ordem banc.*cr', re.I), 1.02,
     'ORBAN', 'Tarifa Ordem Bancaria-Cred Cta', '92'),
    (re.compile(r'orban.*fatura', re.I), 3.03,
     'ORBAN', 'Tarif ORBAN-Fatura c/Cod Barra', '92'),
    (re.compile(r'ordem banc.*tributo', re.I), 106.50,
     'ORBAN', 'Tar Ordem Bancaria-Pag Tributo', '92'),
    (re.compile(r'pag fornec.*cr', re.I), 1.02,
     'PAGAMENTO A FORNECEDORES', 'Tarifa Pag Fornec Credito Cta', '92'),
    (re.compile(r'pgto fornecedores', re.I), 4.51,
     'PAGAMENTO A FORNECEDORES', 'Tarifa Pgto Fornecedores TED', '92'),
    (re.compile(r'tarifa sobre pag', re.I), 1.02,
     'PAGAMENTOS DIVERSOS', 'Tarifa sobre Pagamentos Cred Cta', '92'),
    (re.compile(r'tarifa sobre pag', re.I), 4.51,
     'PAGAMENTOS DIVERSOS', 'Tarifa sobre Pagamentos DOC/TED', '92'),
    (re.compile(r'pgto sal', re.I), 1.02,
     'PAGAMENTO DE SALARIO', 'Tarifa Pgto Salario Cred Conta', '93'),
    # Tarifa que aparece em alguns meses - Float Pagamentos Diversos
    (re.compile(r'float.*pagt|lib.*ant.*float', re.I), None,
     'PAGAMENTOS DIVERSOS', 'Tarif Lib/Ant Float Pagtos Div', '92'),
]

ROW_REGEX = re.compile(
    r'(\d{2}\.\d{2}\.\d{4})\s+(\d{2}\.\d{2}\.\d{4})\s+'
    r'(.+?)\s+(\d+)\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})\s+D'
)


def parse_brl(s):
    """'1.527,32' -> 1527.32"""
    return float(s.replace('.', '').replace(',', '.'))


def match_service(desc, tarifa):
    """Match a PDF description + tariff to a known service type."""
    for pattern, expected_tarifa, produto, servico, se in SERVICE_MAP:
        if pattern.search(desc):
            if expected_tarifa is None or abs(tarifa - expected_tarifa) < 0.02:
                return produto, servico, se
    return None, desc, '98'


def parse_pdf(filepath):
    """
    Parse a BB oficio PDF and return structured data.

    Returns dict with:
        oficio_num, periodo, end_month, end_year,
        valor_bruto, ir_oficio, items[], row_count
    """
    with pdfplumber.open(filepath) as pdf:
        text = ''
        for page in pdf.pages:
            text += (page.extract_text() or '') + '\n'

    # Oficio number
    m = re.search(r'(3384626091\d{5})', text)
    oficio_num = m.group(1) if m else ''

    # Period
    periodo = ''
    end_month = end_year = None
    m = re.search(r'(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})', text)
    if m:
        periodo = f'{m.group(1)} a {m.group(2)}'
        parts = m.group(2).split('/')
        end_month = int(parts[1])
        end_year = int(parts[2])

    # Header values
    valor_bruto = 0.0
    m = re.search(r'Valor bruto.*?R\$\s*([\d.]+,\d{2})', text)
    if m:
        valor_bruto = parse_brl(m.group(1))

    ir_oficio = 0.0
    m = re.search(r'IR\*?:\s*([\d.]+,\d{2})', text)
    if m:
        ir_oficio = parse_brl(m.group(1))

    # Extract table rows
    rows = ROW_REGEX.findall(text)

    # Consolidate by (description, tariff)
    consol = {}
    for r in rows:
        desc = r[2].strip()
        tarifa = parse_brl(r[4])
        qtd = int(r[3])
        total = parse_brl(r[5])
        key = f'{desc}|{tarifa:.2f}'
        if key not in consol:
            consol[key] = {'desc': desc, 'tarifa': tarifa, 'qtd': 0, 'total': 0.0}
        consol[key]['qtd'] += qtd
        consol[key]['total'] += total

    # Map to service types
    items = []
    for c in consol.values():
        c['total'] = round(c['total'], 2)
        produto, servico, se = match_service(c['desc'], c['tarifa'])
        items.append({
            'produto': produto or 'OUTROS',
            'servico': servico,
            'sub_elemento': se,
            'valor_unitario': c['tarifa'],
            'quantidade': c['qtd'],
            'valor_total': c['total'],
            'ir_value': 0.0,
            'valor_liquido': 0.0,
            'matched': produto is not None,
        })

    # Distribute oficio IR proportionally (avoids rounding divergence)
    total_valor = sum(i['valor_total'] for i in items)
    if total_valor > 0 and ir_oficio > 0:
        remaining_ir = ir_oficio
        for i, item in enumerate(items):
            if i == len(items) - 1:
                item['ir_value'] = round(remaining_ir, 2)
            else:
                item['ir_value'] = round(
                    ir_oficio * item['valor_total'] / total_valor, 2)
                remaining_ir -= item['ir_value']
            item['valor_liquido'] = round(
                item['valor_total'] - item['ir_value'], 2)

    parsed_total = sum(i['valor_total'] for i in items)

    return {
        'oficio_num': oficio_num,
        'periodo': periodo,
        'end_month': end_month,
        'end_year': end_year,
        'valor_bruto': valor_bruto,
        'ir_oficio': ir_oficio,
        'valor_liquido': round(valor_bruto - ir_oficio, 2),
        'items': items,
        'row_count': len(rows),
        'parsed_total': round(parsed_total, 2),
        'diff': round(abs(parsed_total - valor_bruto), 2),
        'valid': abs(parsed_total - valor_bruto) < 0.50,
    }


def parse_multiple_pdfs(filepaths):
    """Parse multiple oficio PDFs and return combined results."""
    results = []
    for fp in filepaths:
        try:
            result = parse_pdf(fp)
            result['filename'] = fp if isinstance(fp, str) else fp.filename
            results.append(result)
        except Exception as e:
            results.append({
                'filename': fp if isinstance(fp, str) else fp.filename,
                'error': str(e),
                'items': [],
                'valid': False,
            })
    return results

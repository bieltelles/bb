"""
Calculadora de Retenções na Fonte - IN RFB 1234/2012

Base Legal:
- Instrução Normativa RFB nº 1.234, de 11 de janeiro de 2012
- Dispõe sobre a retenção de tributos nos pagamentos efetuados pelos
  órgãos da administração pública federal direta, autarquias e fundações
  federais, empresas públicas, sociedades de economia mista e demais
  entidades (aplicável por analogia aos municípios).

Para serviços prestados por instituições financeiras (Banco do Brasil S.A.):
- IRRF: 2,4% (conforme Tema 1130 do STF e IN RFB 1234/2012)
- CSLL: R$ 0,00
- COFINS: R$ 0,00 (Dispensado para instituições financeiras)
- PIS/PASEP: R$ 0,00 (Dispensado para instituições financeiras)

Alíquota efetiva aplicada ao contrato 591/2025: 2,4% (somente IRRF).

Serviços isentos de retenção:
- Tarifas com valor zero ou sem execução
- Serviços expressamente dispensados conforme ofício
"""


# Alíquotas conforme Tema 1130 STF + IN RFB 1234/2012
ALIQUOTAS = {
    'IRRF': 0.024,      # 2,4% (Tema 1130 STF + IN RFB 1234/2012)
    'CSLL': 0.000,      # R$ 0,00
    'COFINS': 0.000,    # Dispensado para inst. financeiras
    'PIS_PASEP': 0.000, # Dispensado para inst. financeiras
}

# Alíquota efetiva (somente IRRF)
ALIQUOTA_EFETIVA = 0.024  # 2,4%

# Valor mínimo para retenção (R$ 10,00 conforme Art. 3º da IN 1234/2012)
VALOR_MINIMO_RETENCAO = 10.00


def calcular_retencao(valor_bruto, aliquota=None, aplicar_minimo=False):
    """
    Calcula o valor da retenção sobre o valor bruto.

    Args:
        valor_bruto: Valor bruto do serviço
        aliquota: Alíquota de retenção (default: ALIQUOTA_EFETIVA = 2,4%)
        aplicar_minimo: Se True, dispensa retenção abaixo de R$ 10,00

    Returns:
        dict com valor_bruto, ir_value, valor_liquido e detalhamento
    """
    if aliquota is None:
        aliquota = ALIQUOTA_EFETIVA

    if valor_bruto is None or valor_bruto <= 0:
        return {
            'valor_bruto': 0.0,
            'ir_value': 0.0,
            'valor_liquido': 0.0,
            'aliquota': aliquota,
            'detalhamento': calcular_detalhamento(0.0),
        }

    ir_value = round(valor_bruto * aliquota, 2)

    # Art. 3º: Dispensa de retenção quando o valor for inferior a R$ 10,00
    if aplicar_minimo and ir_value < VALOR_MINIMO_RETENCAO:
        ir_value = 0.0

    valor_liquido = round(valor_bruto - ir_value, 2)

    return {
        'valor_bruto': valor_bruto,
        'ir_value': ir_value,
        'valor_liquido': valor_liquido,
        'aliquota': aliquota,
        'detalhamento': calcular_detalhamento(valor_bruto),
    }


def calcular_detalhamento(valor_bruto):
    """
    Retorna o detalhamento dos tributos individuais.

    Args:
        valor_bruto: Valor bruto do serviço

    Returns:
        dict com valores individuais de IRRF, CSLL, COFINS, PIS/PASEP
    """
    return {
        'IRRF': round(valor_bruto * ALIQUOTAS['IRRF'], 2),
        'CSLL': round(valor_bruto * ALIQUOTAS['CSLL'], 2),
        'COFINS': round(valor_bruto * ALIQUOTAS['COFINS'], 2),
        'PIS_PASEP': round(valor_bruto * ALIQUOTAS['PIS_PASEP'], 2),
        'total': round(valor_bruto * sum(ALIQUOTAS.values()), 2),
    }


def calcular_competencia(items):
    """
    Calcula totais de retenção para uma lista de itens de serviço.

    Args:
        items: Lista de ServiceItem objects

    Returns:
        dict com totais gerais e por empenho
    """
    totais = {
        'valor_total': 0.0,
        'total_ir': 0.0,
        'total_liquido': 0.0,
        'por_empenho': {},
    }

    for item in items:
        totais['valor_total'] += item.valor_total or 0
        totais['total_ir'] += item.ir_value or 0
        totais['total_liquido'] += item.valor_liquido or 0

        emp_key = item.empenho_id
        if emp_key not in totais['por_empenho']:
            totais['por_empenho'][emp_key] = {
                'empenho': item.empenho,
                'valor_total': 0.0,
                'total_ir': 0.0,
                'total_liquido': 0.0,
            }
        totais['por_empenho'][emp_key]['valor_total'] += item.valor_total or 0
        totais['por_empenho'][emp_key]['total_ir'] += item.ir_value or 0
        totais['por_empenho'][emp_key]['total_liquido'] += item.valor_liquido or 0

    return totais

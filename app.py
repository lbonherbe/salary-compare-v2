"""
Salary Tax Comparator v2: AT, HU, PL, FR + Geneva resident + Frontalier.
2025 tax rules, simplified for comparison. Live FX from yfinance.
"""

from datetime import datetime

import streamlit as st
import plotly.graph_objects as go

# ── Fallback exchange rates (used if yfinance fails) ──────────────────────
EUR_HUF_FALLBACK = 400.0
EUR_PLN_FALLBACK = 4.20
EUR_CHF_FALLBACK = 0.95

# Mutable globals (overridden after sidebar resolves)
EUR_HUF = EUR_HUF_FALLBACK
EUR_PLN = EUR_PLN_FALLBACK
EUR_CHF = EUR_CHF_FALLBACK


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fx_rates() -> dict:
    """Fetch latest EUR-cross rates from yfinance. Cached for 1 hour."""
    out = {
        "EUR_HUF": (EUR_HUF_FALLBACK, "fallback", None),
        "EUR_PLN": (EUR_PLN_FALLBACK, "fallback", None),
        "EUR_CHF": (EUR_CHF_FALLBACK, "fallback", None),
    }
    try:
        import yfinance as yf
        for key, ticker in [
            ("EUR_HUF", "EURHUF=X"),
            ("EUR_PLN", "EURPLN=X"),
            ("EUR_CHF", "EURCHF=X"),
        ]:
            try:
                hist = yf.Ticker(ticker).history(period="5d")
                if len(hist) > 0:
                    last = float(hist["Close"].iloc[-1])
                    last_date = hist.index[-1].date().isoformat()
                    out[key] = (last, "yfinance", last_date)
            except Exception:
                pass
    except Exception:
        pass
    return out

COLORS = {
    "France": "#002395",
    "Austria": "#ED2939",
    "Hungary": "#477050",
    "Poland": "#DC143C",
    "Geneva (resident)": "#D52B1E",
    "Frontalier (FR/GE)": "#0055A4",
}

# ════════════════════════════════════════════════════════════════════════════
#  HELPERS, Switzerland
# ════════════════════════════════════════════════════════════════════════════

def lpp_rate_total(age: int) -> float:
    """Total LPP contribution rate (employee + employer) by age."""
    if age < 25:
        return 0.0
    if age < 35:
        return 0.07
    if age < 45:
        return 0.10
    if age < 55:
        return 0.15
    return 0.18


def lpp_coordinated(gross_chf: float) -> float:
    """LPP salaire coordonné 2025: max(min(gross, 90720) - 26460, 0), floor 3675."""
    coord = max(min(gross_chf, 90_720) - 26_460, 0)
    if 0 < coord < 3_675:
        coord = 3_675
    return coord


def swiss_social_employee(gross_chf: float, age: int) -> tuple[float, dict]:
    """Returns (total_chf, parts_dict) for the employee side."""
    avs = gross_chf * 0.0530  # AVS/AI/APG, no cap
    ac = min(gross_chf, 148_200) * 0.011
    if gross_chf > 148_200:
        ac += (gross_chf - 148_200) * 0.005  # solidarity
    aanp = min(gross_chf, 148_200) * 0.0120
    amat = gross_chf * 0.00043
    coord = lpp_coordinated(gross_chf)
    lpp = coord * (lpp_rate_total(age) / 2)  # 50/50 split
    total = avs + ac + aanp + amat + lpp
    return total, {
        "AVS/AI/APG (5.30%)": avs,
        "AC (1.1% + 0.5% solidarity)": ac,
        "AANP non-occupational accident (1.20%)": aanp,
        "AMat Geneva (0.043%)": amat,
        f"LPP 2nd pillar ({lpp_rate_total(age)*100:.0f}% age {age}, half employee)": lpp,
    }


def swiss_social_employer(gross_chf: float, age: int) -> tuple[float, dict]:
    """Returns (total_chf, parts_dict) for the employer side. Geneva."""
    avs = gross_chf * 0.0530
    ac = min(gross_chf, 148_200) * 0.011
    if gross_chf > 148_200:
        ac += (gross_chf - 148_200) * 0.005
    aap = min(gross_chf, 148_200) * 0.005  # occupational accident, employer pays
    amat = gross_chf * 0.00043
    af = gross_chf * 0.0245  # allocations familiales Geneva
    coord = lpp_coordinated(gross_chf)
    lpp = coord * (lpp_rate_total(age) / 2)
    admin = gross_chf * 0.003  # caisse de pension admin
    total = avs + ac + aap + amat + af + lpp + admin
    return total, {
        "AVS/AI/APG (5.30%)": avs,
        "AC (1.1% + 0.5%)": ac,
        "AAP occupational accident (~0.5%)": aap,
        "AMat (0.043%)": amat,
        "AF Allocations familiales Genève (2.45%)": af,
        "LPP employer half": lpp,
        "Frais admin caisse (~0.3%)": admin,
    }


def ifd_federal(taxable_chf: float, married: bool, num_children: int) -> float:
    """Impôt fédéral direct 2025."""
    if taxable_chf <= 0:
        return 0.0

    if married:
        brackets = [
            (30_800, 0.00),
            (50_900, 0.01),
            (58_400, 0.02),
            (75_300, 0.03),
            (90_300, 0.04),
            (103_400, 0.05),
            (114_700, 0.06),
            (124_200, 0.07),
            (131_700, 0.08),
            (137_300, 0.09),
            (141_200, 0.10),
            (143_100, 0.11),
            (145_000, 0.12),
            (895_900, 0.13),
        ]
        if taxable_chf > 895_900:
            return max(taxable_chf * 0.115 - num_children * 263, 0)
    else:
        brackets = [
            (17_800, 0.00),
            (31_600, 0.0077),
            (41_400, 0.0088),
            (55_200, 0.0264),
            (72_500, 0.0297),
            (78_100, 0.0594),
            (103_600, 0.066),
            (134_600, 0.088),
            (176_000, 0.11),
            (755_200, 0.132),
        ]
        if taxable_chf > 755_200:
            return max(taxable_chf * 0.115 - num_children * 263, 0)

    tax = 0.0
    prev = 0
    for upper, rate in brackets:
        if taxable_chf <= prev:
            break
        chunk = min(taxable_chf, upper) - prev
        tax += chunk * rate
        prev = upper
    tax = max(tax - num_children * 263, 0)
    return tax


def icc_geneva(taxable_chf: float, married: bool, centimes_pct: float = 45.5) -> float:
    """ICC Geneva: cantonal × (1 + centimes/100). Married uses splitting 1.9."""
    if taxable_chf <= 0:
        return 0.0

    coef = 1.9 if married else 1.0
    per = taxable_chf / coef

    brackets = [
        (17_493, 0.00),
        (21_037, 0.08),
        (23_162, 0.09),
        (25_287, 0.10),
        (27_412, 0.11),
        (31_662, 0.12),
        (35_912, 0.13),
        (40_162, 0.14),
        (44_412, 0.145),
        (51_500, 0.15),
        (57_000, 0.155),
        (71_500, 0.16),
        (89_500, 0.165),
        (121_500, 0.17),
        (161_500, 0.18),
        (187_500, 0.185),
        (float("inf"), 0.19),
    ]

    cantonal = 0.0
    prev = 0
    for upper, rate in brackets:
        if per <= prev:
            break
        chunk = min(per, upper) - prev
        cantonal += chunk * rate
        prev = upper

    cantonal *= coef
    icc = cantonal * (1 + centimes_pct / 100)
    return icc


# ════════════════════════════════════════════════════════════════════════════
#  CALCULATORS
# ════════════════════════════════════════════════════════════════════════════

def calc_france(gross_eur: float, married: bool, child_ages: list[int], age: int) -> dict:
    """France 2025: ~22.5% social charges + progressive IR with quotient familial."""
    gross = gross_eur
    children = len(child_ages)

    social_rate = 0.225
    social = gross * social_rate

    employer_rate = 0.43
    employer_cost = gross * employer_rate
    total_cost = gross + employer_cost

    non_deductible = gross * 0.9825 * 0.029
    deductible_charges = social - non_deductible
    net_imposable = gross - deductible_charges

    deduction_10 = min(max(net_imposable * 0.10, 495), 14_171)
    revenu_fiscal = max(net_imposable - deduction_10, 0)

    parts = 1.0
    if married:
        parts = 2.0
    if children >= 1:
        parts += 0.5
    if children >= 2:
        parts += 0.5
    if children >= 3:
        parts += (children - 2) * 1.0
    if not married and children >= 1:
        parts += 0.5

    brackets = [
        (11_294, 0.00),
        (28_797 - 11_294, 0.11),
        (82_341 - 28_797, 0.30),
        (177_106 - 82_341, 0.41),
        (float("inf"), 0.45),
    ]

    per_part = revenu_fiscal / parts
    tax_per_part = 0
    remaining = per_part
    for width, rate in brackets:
        taxable_in_bracket = min(remaining, width)
        tax_per_part += taxable_in_bracket * rate
        remaining -= taxable_in_bracket
        if remaining <= 0:
            break
    raw_tax = tax_per_part * parts

    base_parts = 2.0 if married else 1.0
    extra_half_parts = (parts - base_parts) / 0.5
    if extra_half_parts > 0:
        per_part_no_kids = revenu_fiscal / base_parts
        tax_no_kids_pp = 0
        remaining = per_part_no_kids
        for width, rate in brackets:
            taxable_in_bracket = min(remaining, width)
            tax_no_kids_pp += taxable_in_bracket * rate
            remaining -= taxable_in_bracket
            if remaining <= 0:
                break
        tax_no_kids = tax_no_kids_pp * base_parts
        max_advantage = extra_half_parts * 1_759
        actual_advantage = tax_no_kids - raw_tax
        if actual_advantage > max_advantage:
            raw_tax = tax_no_kids - max_advantage

    income_tax = max(raw_tax, 0)

    family_allowance = 0
    if children >= 2:
        family_allowance = 141 * 12
        if children >= 3:
            family_allowance += (children - 2) * 181 * 12
        kids_over_14 = sum(1 for a in child_ages if a >= 14)
        family_allowance += kids_over_14 * 70 * 12

    ars = 0
    for ca in child_ages:
        if 6 <= ca <= 10:
            ars += 416
        elif 11 <= ca <= 14:
            ars += 439
        elif 15 <= ca <= 18:
            ars += 454
    family_allowance += ars

    net = gross - social - income_tax
    net_with_allowances = net + family_allowance

    return {
        "country": "France",
        "label": "France",
        "flag": "\U0001F1EB\U0001F1F7",
        "currency": "EUR",
        "gross_local": gross, "gross_eur": gross,
        "employer_cost_eur": employer_cost, "total_cost_eur": total_cost,
        "employer_rate": employer_rate,
        "social_security_eur": social,
        "income_tax_eur": income_tax,
        "family_credits_eur": family_allowance,
        "net_eur": net,
        "net_with_benefits_eur": net_with_allowances,
        "effective_rate": (social + income_tax) / gross * 100 if gross else 0,
        "monthly_net_eur": net / 12,
        "breakdown": {
            "Gross salary": f"€{gross:,.0f}",
            "Employee social (22.5%)": f"-€{social:,.0f}",
            "10% professional deduction": f"-€{deduction_10:,.0f}",
            f"Taxable income ({parts:.1f} parts)": f"€{revenu_fiscal:,.0f}",
            "Income tax": f"-€{income_tax:,.0f}",
            "Alloc. familiales + ARS": f"+€{family_allowance:,.0f}" if family_allowance else "N/A",
            "_div1": "_",
            "Net salary": f"€{net:,.0f}",
            "Net + benefits": f"€{net_with_allowances:,.0f}",
            "_section_employer": "Employer side",
            "Employer charges (43%)": f"+€{employer_cost:,.0f}",
            "Total cost to employer": f"€{total_cost:,.0f}",
        },
    }


def calc_austria(gross_eur: float, married: bool, child_ages: list[int], age: int) -> dict:
    """Austria 2025: 14-month model, progressive tax, Familienbonus Plus."""
    gross = gross_eur
    children = len(child_ages)

    ss_cap = 72_720
    ss_rate = 0.1812
    ss_base = min(gross, ss_cap)
    social = ss_base * ss_rate

    employer_rate = 0.3028
    employer_cost = gross * employer_rate
    total_cost = gross + employer_cost

    monthly_gross = gross / 14
    regular_annual = monthly_gross * 12
    bonus_annual = monthly_gross * 2

    regular_taxable = regular_annual - (social * 12 / 14)
    bonus_taxable = bonus_annual - (social * 2 / 14)

    brackets = [
        (12_816, 0.00),
        (20_818 - 12_816, 0.20),
        (34_513 - 20_818, 0.30),
        (66_612 - 34_513, 0.40),
        (99_266 - 66_612, 0.48),
        (1_000_000 - 99_266, 0.50),
        (float("inf"), 0.55),
    ]

    remaining = max(regular_taxable, 0)
    regular_tax = 0
    for width, rate in brackets:
        chunk = min(remaining, width)
        regular_tax += chunk * rate
        remaining -= chunk
        if remaining <= 0:
            break

    bonus_exempt = 620
    bonus_tax = max(bonus_taxable - bonus_exempt, 0) * 0.06

    income_tax = regular_tax + bonus_tax

    family_bonus = 0
    for ca in child_ages:
        family_bonus += 2_000 if ca < 18 else 650
    income_tax = max(income_tax - family_bonus, 0)

    sole_earner_credit = 0
    if married and children >= 1:
        sole_earner_credit = 520 + children * 220
        income_tax = max(income_tax - sole_earner_credit, 0)

    familienbeihilfe = 0
    for ca in child_ages:
        if ca <= 2:
            familienbeihilfe += 120.60 * 12
        elif ca <= 9:
            familienbeihilfe += 128.20 * 12
        elif ca <= 18:
            familienbeihilfe += 148.90 * 12
        else:
            familienbeihilfe += 174.70 * 12
    if children >= 2:
        familienbeihilfe += children * 7.30 * 12
    if children >= 3:
        familienbeihilfe += children * 17.40 * 12

    net = gross - social - income_tax
    net_with_benefits = net + familienbeihilfe

    return {
        "country": "Austria",
        "label": "Austria",
        "flag": "\U0001F1E6\U0001F1F9",
        "currency": "EUR",
        "gross_local": gross, "gross_eur": gross,
        "employer_cost_eur": employer_cost, "total_cost_eur": total_cost,
        "employer_rate": employer_rate,
        "social_security_eur": social,
        "income_tax_eur": income_tax,
        "family_credits_eur": familienbeihilfe + family_bonus,
        "net_eur": net,
        "net_with_benefits_eur": net_with_benefits,
        "effective_rate": (social + income_tax) / gross * 100 if gross else 0,
        "monthly_net_eur": net / 12,
        "breakdown": {
            "Gross salary (14 months)": f"€{gross:,.0f}",
            f"Employee SS ({ss_rate*100:.1f}%, cap €{ss_cap:,})": f"-€{social:,.0f}",
            "Regular salary tax (progressive)": f"-€{regular_tax:,.0f}",
            "13th/14th month tax (6% flat)": f"-€{bonus_tax:,.0f}",
            f"Familienbonus Plus ({children} child.)": f"-€{family_bonus:,.0f}" if family_bonus else "N/A",
            "Income tax (final)": f"-€{income_tax:,.0f}",
            "Familienbeihilfe (benefit)": f"+€{familienbeihilfe:,.0f}" if familienbeihilfe else "N/A",
            "_div1": "_",
            "Net salary": f"€{net:,.0f}",
            "Net + benefits": f"€{net_with_benefits:,.0f}",
            "_section_employer": "Employer side",
            "Employer charges (30.3%)": f"+€{employer_cost:,.0f}",
            "Total cost to employer": f"€{total_cost:,.0f}",
        },
    }


def calc_hungary(gross_eur: float, married: bool, child_ages: list[int], age: int) -> dict:
    """Hungary 2025: flat 15% SZJA + 18.5% TB, family tax credit."""
    gross_huf = gross_eur * EUR_HUF
    children = len(child_ages)

    ss_rate = 0.185
    social = gross_huf * ss_rate

    employer_rate = 0.13
    employer_cost_huf = gross_huf * employer_rate
    employer_cost_eur = employer_cost_huf / EUR_HUF
    total_cost_eur = gross_eur + employer_cost_eur

    szja_rate = 0.15

    dependents = sum(1 for ca in child_ages if ca < 25)
    if dependents == 0:
        monthly_deduction = 0
    elif dependents == 1:
        monthly_deduction = 66_670 * dependents
    elif dependents == 2:
        monthly_deduction = 133_330 * dependents
    else:
        monthly_deduction = 220_000 * dependents

    annual_deduction = monthly_deduction * 12
    szja_before_credit = gross_huf * szja_rate
    family_szja_saving = min(annual_deduction * szja_rate, szja_before_credit)

    remaining_deduction = annual_deduction - (family_szja_saving / szja_rate)
    family_tb_saving = 0
    if remaining_deduction > 0:
        family_tb_saving = min(remaining_deduction * ss_rate, social)

    income_tax = szja_before_credit - family_szja_saving
    social_final = social - family_tb_saving

    under25_saving = 0
    if age < 25:
        exempt_limit = 7_900_000
        exempt_base = min(gross_huf, exempt_limit)
        under25_saving = exempt_base * szja_rate
        income_tax = max(income_tax - under25_saving, 0)

    total_family_credit = family_szja_saving + family_tb_saving
    net_huf = gross_huf - social_final - income_tax
    net_eur = net_huf / EUR_HUF

    eligible_kids = [ca for ca in child_ages if ca < 20]
    n_eligible = len(eligible_kids)
    if n_eligible == 1:
        potlek_per = 12_200
    elif n_eligible == 2:
        potlek_per = 13_300
    else:
        potlek_per = 16_000
    family_allowance_huf = n_eligible * potlek_per * 12
    net_with_benefits_huf = net_huf + family_allowance_huf

    return {
        "country": "Hungary",
        "label": "Hungary",
        "flag": "\U0001F1ED\U0001F1FA",
        "currency": "HUF",
        "gross_local": gross_huf, "gross_eur": gross_eur,
        "employer_cost_eur": employer_cost_eur, "total_cost_eur": total_cost_eur,
        "employer_rate": employer_rate,
        "social_security_eur": social_final / EUR_HUF,
        "income_tax_eur": income_tax / EUR_HUF,
        "family_credits_eur": (total_family_credit + family_allowance_huf) / EUR_HUF,
        "net_eur": net_eur,
        "net_with_benefits_eur": net_with_benefits_huf / EUR_HUF,
        "effective_rate": (social_final + income_tax) / gross_huf * 100 if gross_huf else 0,
        "monthly_net_eur": net_eur / 12,
        "breakdown": {
            "Gross salary": f"{gross_huf:,.0f} HUF (€{gross_eur:,.0f})",
            "Employee SS (18.5%)": f"-{social:,.0f} HUF",
            f"Family tax credit ({dependents} dep.)": f"-{total_family_credit:,.0f} HUF" if total_family_credit else "N/A",
            "SS after credits": f"-{social_final:,.0f} HUF" if family_tb_saving else f"-{social:,.0f} HUF",
            "Income tax (15% flat)": f"-{income_tax:,.0f} HUF",
            "Under-25 exemption": f"-{under25_saving:,.0f} HUF" if under25_saving else "N/A",
            f"Családi pótlék ({n_eligible} elig.)": f"+{family_allowance_huf:,.0f} HUF" if family_allowance_huf else "N/A",
            "_div1": "_",
            "Net salary": f"{net_huf:,.0f} HUF (€{net_eur:,.0f})",
            "Net + benefits": f"{net_with_benefits_huf:,.0f} HUF (€{net_with_benefits_huf/EUR_HUF:,.0f})",
            "_section_employer": "Employer side",
            "Szocho (13%)": f"+{employer_cost_huf:,.0f} HUF",
            "Total cost to employer": f"{gross_huf + employer_cost_huf:,.0f} HUF (€{total_cost_eur:,.0f})",
        },
    }


def calc_poland(gross_eur: float, married: bool, child_ages: list[int], age: int) -> dict:
    """Poland 2025: 12%/32% progressive + 13.71% ZUS + 9% health."""
    gross_pln = gross_eur * EUR_PLN
    children = len(child_ages)

    zus_cap = 234_720
    capped_base = min(gross_pln, zus_cap)
    pension = capped_base * 0.0976
    disability = capped_base * 0.015
    sickness = gross_pln * 0.0245
    social = pension + disability + sickness

    health_base = gross_pln - social
    health = health_base * 0.09

    employer_rate = 0.2048
    employer_cost_pln = gross_pln * employer_rate
    employer_cost_eur = employer_cost_pln / EUR_PLN
    total_cost_eur = gross_eur + employer_cost_eur

    kup = 250 * 12
    taxable = max(gross_pln - social - kup, 0)

    if taxable <= 120_000:
        raw_tax = taxable * 0.12
    else:
        raw_tax = 120_000 * 0.12 + (taxable - 120_000) * 0.32

    tax_free_credit = 3_600
    income_tax = max(raw_tax - tax_free_credit, 0)

    under26_saving = 0
    if age < 26:
        exempt_limit = 85_528
        exempt_taxable = min(taxable, exempt_limit)
        if exempt_taxable <= 120_000:
            exempt_tax = exempt_taxable * 0.12
        else:
            exempt_tax = 120_000 * 0.12 + (exempt_taxable - 120_000) * 0.32
        under26_saving = min(exempt_tax, income_tax)
        income_tax = max(income_tax - under26_saving, 0)

    eligible_kids = sorted([ca for ca in child_ages if ca < 25], reverse=False)
    child_credit = 0
    for idx, ca in enumerate(eligible_kids):
        if idx == 0:
            child_credit += 1_112.04
        elif idx == 1:
            child_credit += 1_112.04
        elif idx == 2:
            child_credit += 2_000.04
        else:
            child_credit += 2_700
    income_tax = max(income_tax - child_credit, 0)

    kids_under_18 = sum(1 for ca in child_ages if ca < 18)
    family_800 = kids_under_18 * 800 * 12

    net_pln = gross_pln - social - health - income_tax
    net_eur = net_pln / EUR_PLN
    net_with_benefits_pln = net_pln + family_800

    return {
        "country": "Poland",
        "label": "Poland",
        "flag": "\U0001F1F5\U0001F1F1",
        "currency": "PLN",
        "gross_local": gross_pln, "gross_eur": gross_eur,
        "employer_cost_eur": employer_cost_eur, "total_cost_eur": total_cost_eur,
        "employer_rate": employer_rate,
        "social_security_eur": (social + health) / EUR_PLN,
        "income_tax_eur": income_tax / EUR_PLN,
        "family_credits_eur": (child_credit + family_800) / EUR_PLN,
        "net_eur": net_eur,
        "net_with_benefits_eur": net_with_benefits_pln / EUR_PLN,
        "effective_rate": (social + health + income_tax) / gross_pln * 100 if gross_pln else 0,
        "monthly_net_eur": net_eur / 12,
        "breakdown": {
            "Gross salary": f"{gross_pln:,.0f} PLN (€{gross_eur:,.0f})",
            "ZUS pension+disab. (capped)": f"-{pension + disability:,.0f} PLN",
            "ZUS sickness (2.45%)": f"-{sickness:,.0f} PLN",
            "Health insurance (9%)": f"-{health:,.0f} PLN",
            "Income tax (12%/32% after credits)": f"-{income_tax:,.0f} PLN",
            f"Child credit ({len(eligible_kids)} elig.)": f"-{child_credit:,.0f} PLN" if child_credit else "N/A",
            "Under-26 exemption": f"-{under26_saving:,.0f} PLN" if under26_saving else "N/A",
            f"800+ ({kids_under_18} child. <18)": f"+{family_800:,.0f} PLN" if family_800 else "N/A",
            "_div1": "_",
            "Net salary": f"{net_pln:,.0f} PLN (€{net_eur:,.0f})",
            "Net + benefits": f"{net_with_benefits_pln:,.0f} PLN (€{net_with_benefits_pln/EUR_PLN:,.0f})",
            "_section_employer": "Employer side",
            "Employer ZUS (20.5%)": f"+{employer_cost_pln:,.0f} PLN",
            "Total cost to employer": f"{gross_pln + employer_cost_pln:,.0f} PLN (€{total_cost_eur:,.0f})",
        },
    }


def lamal_household_chf(married: bool, child_ages: list[int],
                        adult_premium_chf: float) -> tuple[float, dict]:
    """Mandatory Swiss health insurance for the household. Returns (total_chf, parts)."""
    # Geneva LAMal age bands: 0-18 (~28% of adult), 19-25 (~82%), 26+ (full).
    child_ratio = 0.28
    young_ratio = 0.82
    n_adults = 1 + (1 if married else 0)
    n_children = sum(1 for a in child_ages if a <= 18)
    n_young = sum(1 for a in child_ages if 19 <= a <= 25)
    adults_total = n_adults * adult_premium_chf
    children_total = n_children * adult_premium_chf * child_ratio
    young_total = n_young * adult_premium_chf * young_ratio
    total = adults_total + children_total + young_total
    return total, {
        "adults": (n_adults, adults_total),
        "children": (n_children, children_total),
        "young_adults": (n_young, young_total),
    }


def calc_geneva_resident(gross_eur: float, married: bool, child_ages: list[int],
                         age: int, centimes_pct: float = 45.5,
                         lamal_adult_chf: float = 5_500.0) -> dict:
    """Geneva resident 2025: ordinary taxation (filed declaration), Geneva-Ville centimes."""
    children = len(child_ages)
    gross_chf = gross_eur * EUR_CHF

    social_chf, social_parts = swiss_social_employee(gross_chf, age)
    employer_cost_chf, employer_parts = swiss_social_employer(gross_chf, age)
    total_cost_chf = gross_chf + employer_cost_chf

    lamal_chf, lamal_parts = lamal_household_chf(married, child_ages, lamal_adult_chf)

    forfait_pro = min(gross_chf * 0.03, 4_000)
    transport_deduc = 700
    repas_deduc = 1_600
    # LAMal premiums are deductible on ICC up to a cap (~5,224 CHF single,
    # ~10,448 married, +1,408 per child in 2024). Apply that as a deduction.
    lamal_cap = 5_224 + (5_224 if married else 0) + 1_408 * children
    lamal_deductible = min(lamal_chf, lamal_cap)

    icc_perso = 22_000 if married else 11_000
    icc_child = children * 13_000
    icc_taxable = max(
        gross_chf - social_chf - forfait_pro - transport_deduc - repas_deduc
        - lamal_deductible - icc_perso - icc_child, 0
    )
    icc_tax = icc_geneva(icc_taxable, married, centimes_pct)
    icc_tax = max(icc_tax - children * 290 * (1 + centimes_pct / 100), 0)

    ifd_taxable = max(
        gross_chf - social_chf - forfait_pro - transport_deduc - repas_deduc
        - lamal_deductible - children * 6_700 - (2_700 if married else 0), 0
    )
    ifd_tax = ifd_federal(ifd_taxable, married, children)

    income_tax_chf = icc_tax + ifd_tax

    af_chf = 0.0
    eligible = [ca for ca in child_ages if ca <= 25]
    for rank, ca in enumerate(eligible, start=1):
        if ca <= 15:
            af_chf += (415 if rank >= 3 else 311) * 12
        else:
            af_chf += (515 if rank >= 3 else 415) * 12

    net_chf = gross_chf - social_chf - income_tax_chf - lamal_chf
    net_with_benefits_chf = net_chf + af_chf

    net_eur = net_chf / EUR_CHF
    employer_cost_eur = employer_cost_chf / EUR_CHF
    total_cost_eur = total_cost_chf / EUR_CHF

    return {
        "country": "Geneva (resident)",
        "label": "Geneva resident",
        "flag": "\U0001F1E8\U0001F1ED",
        "currency": "CHF",
        "gross_local": gross_chf, "gross_eur": gross_eur,
        "employer_cost_eur": employer_cost_eur, "total_cost_eur": total_cost_eur,
        "employer_rate": employer_cost_chf / gross_chf if gross_chf else 0,
        "social_security_eur": (social_chf + lamal_chf) / EUR_CHF,
        "income_tax_eur": income_tax_chf / EUR_CHF,
        "family_credits_eur": af_chf / EUR_CHF,
        "net_eur": net_eur,
        "net_with_benefits_eur": net_with_benefits_chf / EUR_CHF,
        "effective_rate": (social_chf + income_tax_chf + lamal_chf) / gross_chf * 100 if gross_chf else 0,
        "monthly_net_eur": net_eur / 12,
        "breakdown": {
            "Gross salary": f"CHF {gross_chf:,.0f} (€{gross_eur:,.0f})",
            "Swiss social (employee)": f"-CHF {social_chf:,.0f}",
            "  AVS/AI/APG 5.30%": f"-CHF {social_parts['AVS/AI/APG (5.30%)']:,.0f}",
            "  AC + AANP + AMat": f"-CHF {social_parts['AC (1.1% + 0.5% solidarity)'] + social_parts['AANP non-occupational accident (1.20%)'] + social_parts['AMat Geneva (0.043%)']:,.0f}",
            f"  LPP age {age} (employee half)": f"-CHF {[v for k, v in social_parts.items() if k.startswith('LPP')][0]:,.0f}",
            f"ICC Geneva (canton + {centimes_pct:.1f}% centimes)": f"-CHF {icc_tax:,.0f}",
            "IFD federal": f"-CHF {ifd_tax:,.0f}",
            f"LAMal household ({lamal_parts['adults'][0]}A+{lamal_parts['children'][0]}C+{lamal_parts['young_adults'][0]}YA)": f"-CHF {lamal_chf:,.0f}",
            f"Allocations familiales ({len(eligible)} elig.)": f"+CHF {af_chf:,.0f}" if af_chf else "N/A",
            "_div1": "_",
            "Net salary (after LAMal)": f"CHF {net_chf:,.0f} (€{net_eur:,.0f})",
            "Net + benefits": f"CHF {net_with_benefits_chf:,.0f} (€{net_with_benefits_chf/EUR_CHF:,.0f})",
            "_section_employer": "Employer side",
            f"Employer charges (~{employer_cost_chf/gross_chf*100:.1f}%)": f"+CHF {employer_cost_chf:,.0f}",
            "Total cost to employer": f"CHF {total_cost_chf:,.0f} (€{total_cost_eur:,.0f})",
        },
    }


def calc_frontalier(gross_eur: float, married: bool, child_ages: list[int],
                    age: int, centimes_pct: float = 45.5) -> dict:
    """Frontalier: lives in France, works in Geneva. Tax at source GE, French CMU."""
    children = len(child_ages)
    gross_chf = gross_eur * EUR_CHF

    social_chf, social_parts = swiss_social_employee(gross_chf, age)
    employer_cost_chf, _ = swiss_social_employer(gross_chf, age)
    total_cost_chf = gross_chf + employer_cost_chf

    # Geneva tax: model as ordinary taxation (impôt à la source converges
    # for income > 120k via TOU; for lower incomes the at-source tariff is
    # in the same ballpark, ~5-10% margin).
    forfait_pro = min(gross_chf * 0.03, 4_000)
    transport_deduc = 700
    repas_deduc = 1_600

    icc_perso = 22_000 if married else 11_000
    icc_child = children * 13_000
    icc_taxable = max(
        gross_chf - social_chf - forfait_pro - transport_deduc - repas_deduc
        - icc_perso - icc_child, 0
    )
    icc_tax = icc_geneva(icc_taxable, married, centimes_pct)
    icc_tax = max(icc_tax - children * 290 * (1 + centimes_pct / 100), 0)

    ifd_taxable = max(
        gross_chf - social_chf - forfait_pro - transport_deduc - repas_deduc
        - children * 6_700 - (2_700 if married else 0), 0
    )
    ifd_tax = ifd_federal(ifd_taxable, married, children)
    swiss_tax_chf = icc_tax + ifd_tax

    # French CMU frontalier: 8% above PASS abatement (~9,654 EUR for 2025).
    income_eur_for_french = (gross_chf - social_chf) / EUR_CHF
    cmu_threshold = 9_654
    cmu_eur = max(income_eur_for_french - cmu_threshold, 0) * 0.08
    cmu_chf = cmu_eur * EUR_CHF

    # Family allowances: paid by Geneva employer in CHF (frontaliers entitled).
    af_chf = 0.0
    eligible = [ca for ca in child_ages if ca <= 25]
    for rank, ca in enumerate(eligible, start=1):
        if ca <= 15:
            af_chf += (415 if rank >= 3 else 311) * 12
        else:
            af_chf += (515 if rank >= 3 else 415) * 12

    net_chf = gross_chf - social_chf - swiss_tax_chf - cmu_chf
    net_with_benefits_chf = net_chf + af_chf

    net_eur = net_chf / EUR_CHF
    employer_cost_eur = employer_cost_chf / EUR_CHF
    total_cost_eur = total_cost_chf / EUR_CHF

    return {
        "country": "Frontalier (FR/GE)",
        "label": "Frontalier (FR + GE)",
        "flag": "\U0001F1EB\U0001F1F7\U0001F1E8\U0001F1ED",
        "currency": "CHF",
        "gross_local": gross_chf, "gross_eur": gross_eur,
        "employer_cost_eur": employer_cost_eur, "total_cost_eur": total_cost_eur,
        "employer_rate": employer_cost_chf / gross_chf if gross_chf else 0,
        "social_security_eur": (social_chf + cmu_chf) / EUR_CHF,
        "income_tax_eur": swiss_tax_chf / EUR_CHF,
        "family_credits_eur": af_chf / EUR_CHF,
        "net_eur": net_eur,
        "net_with_benefits_eur": net_with_benefits_chf / EUR_CHF,
        "effective_rate": (social_chf + swiss_tax_chf + cmu_chf) / gross_chf * 100 if gross_chf else 0,
        "monthly_net_eur": net_eur / 12,
        "breakdown": {
            "Gross salary": f"CHF {gross_chf:,.0f} (€{gross_eur:,.0f})",
            "Swiss social (employee)": f"-CHF {social_chf:,.0f}",
            "  AVS/AI/APG 5.30%": f"-CHF {social_parts['AVS/AI/APG (5.30%)']:,.0f}",
            "  AC + AANP + AMat": f"-CHF {social_parts['AC (1.1% + 0.5% solidarity)'] + social_parts['AANP non-occupational accident (1.20%)'] + social_parts['AMat Geneva (0.043%)']:,.0f}",
            f"  LPP age {age} (employee half)": f"-CHF {[v for k, v in social_parts.items() if k.startswith('LPP')][0]:,.0f}",
            f"Impôt à la source GE (ICC + IFD approx)": f"-CHF {swiss_tax_chf:,.0f}",
            "French CMU frontalier (8%)": f"-CHF {cmu_chf:,.0f}",
            "French income tax on Swiss salary": "0 (treaty exemption)",
            f"Allocations familiales GE ({len(eligible)} elig.)": f"+CHF {af_chf:,.0f}" if af_chf else "N/A",
            "_div1": "_",
            "Net salary": f"CHF {net_chf:,.0f} (€{net_eur:,.0f})",
            "Net + benefits": f"CHF {net_with_benefits_chf:,.0f} (€{net_with_benefits_chf/EUR_CHF:,.0f})",
            "_section_employer": "Employer side",
            f"Employer charges (~{employer_cost_chf/gross_chf*100:.1f}%)": f"+CHF {employer_cost_chf:,.0f}",
            "Total cost to employer": f"CHF {total_cost_chf:,.0f} (€{total_cost_eur:,.0f})",
        },
    }


# ════════════════════════════════════════════════════════════════════════════
#  STREAMLIT UI
# ════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Salary Tax Comparator v2",
    page_icon="\U0001F4B0",
    layout="wide",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; max-width: 1600px; }

    /* Situation cards */
    .sit-card {
        background: linear-gradient(155deg, #1e1e2e 0%, #2a2a40 60%, #2d2540 100%);
        border: 2px solid #3d3d5c;
        border-radius: 18px;
        padding: 22px 24px;
        margin: 6px 8px 22px 8px;
        min-height: 270px;
        position: relative;
        overflow: hidden;
        box-shadow: 0 4px 14px rgba(0,0,0,0.3);
    }
    .sit-card.is-best {
        border-color: #fbbf24;
        box-shadow: 0 0 18px rgba(251, 191, 36, 0.25), 0 4px 14px rgba(0,0,0,0.3);
    }
    .sit-card.is-cheap-emp {
        border-bottom: 4px solid #34d399;
    }
    .sit-card .sc-head {
        display: flex; justify-content: space-between; align-items: baseline;
        margin-bottom: 14px;
    }
    .sit-card .sc-name {
        font-size: 1.05rem; font-weight: 600; color: #e5e7eb;
    }
    .sit-card .sc-flag { font-size: 1.4rem; }
    .sit-card .sc-net {
        font-size: 2.3rem; font-weight: 800; color: #fff;
        line-height: 1.1;
    }
    .sit-card .sc-meta {
        font-size: 0.85rem; color: #9ca3af; margin-top: 4px;
    }
    .sit-card .sc-tax-pill {
        display: inline-block; background: rgba(248, 113, 113, 0.18);
        color: #fca5a5; font-size: 0.78rem; font-weight: 600;
        padding: 2px 10px; border-radius: 999px; margin-top: 8px;
    }
    .sit-card .sc-divider {
        border: none; border-top: 1px dashed #4a4a6c;
        margin: 16px 0 12px 0;
    }
    .sit-card .sc-emp-label {
        font-size: 0.72rem; color: #c4b5fd;
        text-transform: uppercase; letter-spacing: 0.6px;
        font-weight: 600;
    }
    .sit-card .sc-emp-val {
        font-size: 1.55rem; font-weight: 700; color: #ddd6fe;
        margin-top: 2px;
    }
    .sit-card .sc-emp-sub {
        font-size: 0.78rem; color: #a78bfa; margin-top: 2px;
    }

    /* FX panel in sidebar */
    .fx-line {
        font-family: ui-monospace, monospace; font-size: 0.85rem;
        background: rgba(99, 102, 241, 0.1); border-radius: 6px;
        padding: 4px 8px; margin: 2px 0;
    }
    .fx-stamp {
        font-size: 0.72rem; color: #9ca3af; margin-top: 6px;
    }

    .stExpander { border: 1px solid #3d3d5c; border-radius: 8px; }
    h1 { text-align: center; }
</style>
""", unsafe_allow_html=True)

st.title("\U0001F4B0 Salary Tax Comparator v2")
st.caption("AT, HU, PL, FR + Geneva resident + Frontalier (FR/GE). 2025 tax rules. Total employer cost shown for each.")

# ── Sidebar ──
with st.sidebar:
    st.header("\U0001F4CB Your Profile")

    gross = st.slider(
        "Gross annual salary (€)", 15_000, 400_000, 80_000, step=1_000,
        help="Annual gross salary in EUR. For Swiss situations, converted to CHF via the rate below.",
    )

    st.divider()

    married = st.toggle("Married / civil partnership", value=False)
    num_children = st.slider("Number of children", 0, 5, 0)

    child_ages = []
    if num_children > 0:
        st.caption("Age of each child")
        child_cols = st.columns(min(num_children, 3))
        for i in range(num_children):
            with child_cols[i % min(num_children, 3)]:
                ca = st.number_input(
                    f"Child {i+1}",
                    min_value=0, max_value=25, value=min(5 + i * 3, 18),
                    key=f"child_age_{i}",
                )
                child_ages.append(ca)

    age = st.slider("Your age", 18, 65, 40)

    st.divider()
    st.subheader("\U0001F1E8\U0001F1ED Geneva options")
    centimes_pct = st.number_input(
        "Centimes additionnels (%)", value=45.5, step=0.5,
        help="Geneva-Ville: 45.5. Vandoeuvres: 31. Cologny: 27. Etc.",
    )
    lamal_adult = st.number_input(
        "LAMal premium per adult (CHF/yr)", min_value=3_000, max_value=10_000,
        value=5_500, step=100,
        help="Mandatory Swiss health insurance for the resident. Geneva 2025: ~3,500 (HMO cheapest) to ~7,000 (standard 300 CHF deductible). Children pay ~28%, young adults 19-25 ~82% of adult premium.",
    )

    st.divider()
    st.subheader("\U0001F4B1 Exchange rates")
    rates = fetch_fx_rates()
    src_label = {"yfinance": "yfinance", "fallback": "fallback"}
    fx_lines = []
    for key, lbl, fmt in [
        ("EUR_HUF", "EUR/HUF", "{:.2f}"),
        ("EUR_PLN", "EUR/PLN", "{:.4f}"),
        ("EUR_CHF", "EUR/CHF", "{:.4f}"),
    ]:
        val, src, dt = rates[key]
        marker = "live" if src == "yfinance" else "fallback"
        date_str = f" • {dt}" if dt else ""
        fx_lines.append(
            f"<div class='fx-line'><b>{lbl}</b> {fmt.format(val)} "
            f"<span style='color:#6b7280; font-size:0.72rem'>({marker}{date_str})</span></div>"
        )
    st.markdown("".join(fx_lines), unsafe_allow_html=True)
    st.markdown(
        f"<div class='fx-stamp'>Cached for 1h. Fetched {datetime.now().strftime('%H:%M')}.</div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Override** (optional)")
    col_fx1, col_fx2 = st.columns(2)
    with col_fx1:
        eur_huf = st.number_input("EUR/HUF", value=float(rates["EUR_HUF"][0]), step=1.0,
                                  format="%.2f", key="o_huf")
        eur_chf = st.number_input("EUR/CHF", value=float(rates["EUR_CHF"][0]), step=0.005,
                                  format="%.4f", key="o_chf")
    with col_fx2:
        eur_pln = st.number_input("EUR/PLN", value=float(rates["EUR_PLN"][0]), step=0.01,
                                  format="%.4f", key="o_pln")

# Apply user FX rates to module globals
import sys
this = sys.modules[__name__]
this.EUR_HUF = eur_huf
this.EUR_PLN = eur_pln
this.EUR_CHF = eur_chf

# ── Compute ──
results = [
    calc_france(gross, married, child_ages, age),
    calc_austria(gross, married, child_ages, age),
    calc_hungary(gross, married, child_ages, age),
    calc_poland(gross, married, child_ages, age),
    calc_geneva_resident(gross, married, child_ages, age, centimes_pct, float(lamal_adult)),
    calc_frontalier(gross, married, child_ages, age, centimes_pct),
]

# ══════════════════════════════════════════════════════════════════════
#  TOP ROW, NET + EMPLOYER COST
# ══════════════════════════════════════════════════════════════════════

st.markdown("---")
st.subheader("\U0001F4CA Net salary and total employer cost")

best_net = max(r["net_eur"] for r in results)
cheapest_emp = min(r["total_cost_eur"] for r in results)


def render_situation_card(r: dict) -> str:
    classes = ["sit-card"]
    crown = ""
    cheap_badge = ""
    if r["net_eur"] == best_net:
        classes.append("is-best")
        crown = " \U0001F451"
    if r["total_cost_eur"] == cheapest_emp:
        classes.append("is-cheap-emp")
        cheap_badge = " \U0001F4B8"
    return (
        f"<div class='{' '.join(classes)}'>"
        f"<div class='sc-head'>"
        f"<div><span class='sc-flag'>{r['flag']}</span>"
        f" <span class='sc-name'>{r['label']}{crown}</span></div>"
        f"</div>"
        f"<div class='sc-net'>€{r['net_eur']:,.0f}</div>"
        f"<div class='sc-meta'>€{r['monthly_net_eur']:,.0f} / month</div>"
        f"<div class='sc-tax-pill'>{r['effective_rate']:.1f}% effective tax</div>"
        f"<hr class='sc-divider'>"
        f"<div class='sc-emp-label'>Total cost to employer{cheap_badge}</div>"
        f"<div class='sc-emp-val'>€{r['total_cost_eur']:,.0f}</div>"
        f"<div class='sc-emp-sub'>+€{r['employer_cost_eur']:,.0f} ({r['employer_rate']*100:.1f}%) on top of gross</div>"
        f"</div>"
    )


# 6 cards in 2 rows of 3
for row_start in (0, 3):
    cols = st.columns(3, gap="large")
    for j in range(3):
        i = row_start + j
        with cols[j]:
            st.markdown(render_situation_card(results[i]), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
#  CHARTS
# ══════════════════════════════════════════════════════════════════════

st.markdown("---")
st.subheader("\U0001F4CA Comparison charts")

tab1, tab2, tab3, tab4 = st.tabs([
    "\U0001F4B6 Net + tax breakdown",
    "\U0001F3E2 Total employer cost",
    "\U0001F4CB Effective tax %",
    "\U0001F4B0 Net + family benefits",
])

countries = [r["label"] for r in results]
country_colors = [COLORS[r["country"]] for r in results]

with tab1:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Net Salary",
        x=countries,
        y=[r["net_eur"] for r in results],
        marker_color=country_colors,
        text=[f"€{r['net_eur']:,.0f}" for r in results],
        textposition="inside",
        textfont=dict(size=14, color="white"),
    ))
    fig.add_trace(go.Bar(
        name="Income Tax",
        x=countries,
        y=[r["income_tax_eur"] for r in results],
        marker_color="rgba(255,165,0,0.75)",
        text=[f"€{r['income_tax_eur']:,.0f}" for r in results],
        textposition="inside",
        textfont=dict(size=12, color="white"),
    ))
    fig.add_trace(go.Bar(
        name="Social Security",
        x=countries,
        y=[r["social_security_eur"] for r in results],
        marker_color="rgba(255,99,71,0.75)",
        text=[f"€{r['social_security_eur']:,.0f}" for r in results],
        textposition="inside",
        textfont=dict(size=12, color="white"),
    ))
    fig.update_layout(
        barmode="stack",
        height=460,
        yaxis_title="EUR",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        template="plotly_dark",
        margin=dict(t=60, b=80),
    )
    fig.add_hline(
        y=gross, line_dash="dot", line_color="gray",
        annotation_text=f"Gross: €{gross:,}", annotation_position="top left",
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        name="Gross Salary",
        x=countries,
        y=[r["gross_eur"] for r in results],
        marker_color=country_colors,
        text=[f"€{r['gross_eur']:,.0f}" for r in results],
        textposition="inside",
        textfont=dict(size=13, color="white"),
    ))
    fig2.add_trace(go.Bar(
        name="Employer Charges",
        x=countries,
        y=[r["employer_cost_eur"] for r in results],
        marker_color="rgba(147,112,219,0.85)",
        text=[
            f"€{r['employer_cost_eur']:,.0f} ({r['employer_rate']*100:.0f}%)"
            for r in results
        ],
        textposition="inside",
        textfont=dict(size=13, color="white"),
    ))
    # Annotate total cost on top
    for i, r in enumerate(results):
        fig2.add_annotation(
            x=countries[i],
            y=r["total_cost_eur"],
            text=f"<b>€{r['total_cost_eur']:,.0f}</b>",
            showarrow=False,
            yshift=14,
            font=dict(size=14, color="white"),
        )
    fig2.update_layout(
        barmode="stack",
        height=460,
        yaxis_title="EUR (total cost to employer)",
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=80, b=80),
    )
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        "Geneva resident and frontalier have the same employer cost: the employer "
        "doesn't see where the employee lives. France and Austria sit at the high "
        "end (43%, 30%); Hungary the lowest (13%)."
    )

with tab3:
    fig3 = go.Figure()
    for r in results:
        fig3.add_trace(go.Bar(
            name=r["label"],
            x=[r["label"]],
            y=[r["effective_rate"]],
            marker_color=COLORS[r["country"]],
            text=[f"{r['effective_rate']:.1f}%"],
            textposition="outside",
            textfont=dict(size=14),
            showlegend=False,
        ))
    fig3.update_layout(
        height=380,
        yaxis_title="% of Gross (employee social + income tax)",
        yaxis_range=[0, 60],
        template="plotly_dark",
        margin=dict(t=40, b=80),
    )
    st.plotly_chart(fig3, use_container_width=True)

with tab4:
    fig4 = go.Figure()
    fig4.add_trace(go.Bar(
        name="Net (no benefits)",
        x=countries,
        y=[r["net_eur"] for r in results],
        marker_color=country_colors,
        text=[f"€{r['net_eur']:,.0f}" for r in results],
        textposition="outside",
        textfont=dict(size=12),
    ))
    fig4.add_trace(go.Bar(
        name="Net + family benefits",
        x=countries,
        y=[r["net_with_benefits_eur"] for r in results],
        marker_color=country_colors,
        marker_pattern_shape="/",
        opacity=0.65,
        text=[f"€{r['net_with_benefits_eur']:,.0f}" for r in results],
        textposition="outside",
        textfont=dict(size=12),
    ))
    fig4.update_layout(
        barmode="group",
        height=420,
        yaxis_title="EUR",
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=60, b=80),
    )
    st.plotly_chart(fig4, use_container_width=True)

# ── Detailed breakdown ──
st.markdown("---")
st.subheader("\U0001F50D Detailed breakdown by situation")

cols2 = st.columns(2)
for i, r in enumerate(results):
    with cols2[i % 2]:
        with st.expander(
            f"{r['flag']} {r['label']}, Net €{r['net_eur']:,.0f}, Employer total €{r['total_cost_eur']:,.0f}",
            expanded=(i < 2),
        ):
            for label, value in r["breakdown"].items():
                if label.startswith("_section_"):
                    st.markdown(f"**{value}**")
                    st.divider()
                    continue
                if label.startswith("_div"):
                    st.divider()
                    continue
                col_l, col_r = st.columns([3, 2])
                with col_l:
                    if label.startswith(" "):
                        st.markdown(
                            f"<span style='color:#9ca3af; padding-left:1.5em'>&#x21B3; {label.strip()}</span>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(f"**{label}**")
                with col_r:
                    if value.startswith("-"):
                        st.markdown(f":red[{value}]")
                    elif value.startswith("+"):
                        st.markdown(f":green[{value}]")
                    else:
                        st.markdown(f"**{value}**")

# ── Verdict ──
st.markdown("---")
st.subheader("\U0001F3C6 Ranking")

ranked_net = sorted(results, key=lambda r: r["net_eur"], reverse=True)
ranked_benefits = sorted(results, key=lambda r: r["net_with_benefits_eur"], reverse=True)
ranked_employer = sorted(results, key=lambda r: r["total_cost_eur"])
ranked_tax_pct = sorted(results, key=lambda r: r["effective_rate"])

col_v1, col_v2, col_v3, col_v4 = st.columns(4)
medals = ["\U0001F947", "\U0001F948", "\U0001F949", "4️⃣", "5️⃣", "6️⃣"]

with col_v1:
    st.markdown("**Highest net salary**")
    for i, r in enumerate(ranked_net):
        st.markdown(f"{medals[i]} {r['flag']} {r['label']}: **€{r['net_eur']:,.0f}**")

with col_v2:
    st.markdown("**Net + family benefits**")
    for i, r in enumerate(ranked_benefits):
        st.markdown(f"{medals[i]} {r['flag']} {r['label']}: **€{r['net_with_benefits_eur']:,.0f}**")

with col_v3:
    st.markdown("**Lowest effective tax %**")
    for i, r in enumerate(ranked_tax_pct):
        st.markdown(f"{medals[i]} {r['flag']} {r['label']}: **{r['effective_rate']:.1f}%**")

with col_v4:
    st.markdown("**Cheapest for employer**")
    for i, r in enumerate(ranked_employer):
        st.markdown(f"{medals[i]} {r['flag']} {r['label']}: **€{r['total_cost_eur']:,.0f}**")

# ── Caveats ──
st.markdown("---")
with st.expander("⚠️ Important caveats and modeling assumptions"):
    st.markdown("""
**General**

- All numbers are simplified. Real tax situations include local taxes, employer benefits, optional pension contributions (Säule 3a, PER, IKE/IKZE, etc.), deductions for transport/meals/childcare not modeled here, and edge cases.
- Exchange rates are user-adjustable in the sidebar. Actual 2025 EUR/CHF varies around 0.93 to 0.96.
- Children's ages affect: AT Familienbonus (drops at 18), AT Familienbeihilfe brackets, FR ARS school allowance (6 to 18) and supplément 14+, HU családi pótlék (under 20), PL 800+ (under 18), PL/HU dependents (under 25), CH allocations familiales (15+ rate change, up to 25 if studying).

**Geneva resident**

- Models ordinary taxation (filed declaration, B/C permit or Swiss). At-source taxation for low-income foreign workers gives slightly different results.
- ICC uses Geneva-Ville centimes additionnels (45.5%) by default. Other communes range from ~27 (Cologny) to ~51. Adjustable in sidebar.
- LPP (2nd pillar): legal minimum BVG by age band (7/10/15/18%), 50/50 split with employer. Many real plans are more generous (employee pays less, employer more).
- AANP rate (1.20%) varies by employer, typical range 0.5-2.5%.
- Personal allowance 11,000 CHF single / 22,000 CHF married, child allowance 13,000 CHF (ICC), 6,700 CHF (IFD).
- Married couples use Geneva splitting coefficient 1.9 (simplified).
- **LAMal mandatory health insurance** for the whole household. Default: 5,500 CHF/yr per adult (Geneva, family-doctor model, standard 300 CHF deductible). Children pay ~28%, young adults 19-25 pay ~82%. Adjustable in sidebar. Premiums are partially deductible on tax (cap ~5,224 CHF single, ~10,448 married, +1,408 per child). Real Geneva 2025 premiums range from ~3,500 (HMO/telemedicine cheapest) to ~7,000 (standard model). Range can swing net by 3-7k CHF/yr.
- Optional 3a pillar deductions (~7,056 CHF/year) NOT included. They would reduce tax by 1,500-2,500 CHF for typical incomes.

**Frontalier (lives in France, works in Geneva)**

- Geneva is the special canton: tax stays in Switzerland (impôt à la source). Geneva pays France a 3.5% retrocession on frontalier wages.
- Swiss salary is **exempt** from French income tax under the FR/CH treaty for Geneva. Only declared in France for the "taux effectif" (impacts other French income, not modeled here).
- Health insurance: the model assumes the French CMU frontalier (8% above the PASS abatement of ~9,654 EUR). The alternative is Swiss LAMal (~3,500 to 7,000 CHF/year per adult, plus deductible). The choice is made once via the "droit d'option".
- Family allowances paid by the Geneva employer in CHF, like for Geneva residents.
- Income tax modeled as Geneva ordinary taxation (close to TOU). The actual at-source tariff diverges slightly for low/medium incomes but converges above ~120k CHF.
- No CSG/CRDS on Swiss salary (treaty exemption).
- No French taxe d'habitation, foncière, etc. modeled (apply on French residence regardless).

**Employer cost**

- Geneva resident and frontalier have **identical employer cost**: the employer doesn't see where the employee lives. The 3.5% retrocession from Geneva to France is paid by the canton, not the employer.
- France: ~43% on gross (health, pension, unemployment, family fund, formation, transport, AT/MP).
- Austria: ~30% (pension, health, unemployment, FLAF, Kommunalsteuer, IESG, chamber).
- Poland: ~20.5% (employer ZUS, labor fund, FGSP).
- Hungary: ~13% (szociális hozzájárulási adó).
- Switzerland (Geneva): ~17 to 22% depending on age (LPP scales steeply 25 -> 65).

**Not financial or legal advice**. For real decisions, consult a fiduciaire / fiscaliste / steuerberater on both sides of the border.
""")

st.markdown("---")
st.caption("Built for personal scenario planning. Tax rules approximate 2025 legislation. Not financial advice.")

# Salary Tax Comparator v2

Interactive web app comparing **gross-to-net salary** and **total cost to employer** across six situations:

1. France
2. Austria
3. Hungary
4. Poland
5. **Geneva resident** (lives and works in Geneva)
6. **Frontalier** (lives in France, works in Geneva, commutes daily)

Built with Streamlit + Plotly. Tax rules approximate 2025 legislation.

This is a follow-up to the original 4-country `salary-compare` repo, with the cost-of-living adjustment removed and total employer cost surfaced as a primary metric on every card.

## What's new vs v1

- Two Swiss situations modeled: Geneva resident and Geneva-employed frontalier living in France.
- Cost-of-living adjustment dropped (compare straight EUR figures only).
- Total employer cost shown prominently on every card, not buried in a separate section.
- Configurable Geneva centimes additionnels (default 45.5% for Geneva-Ville).
- Configurable EUR/CHF rate alongside EUR/HUF and EUR/PLN.
- Gross slider extended to €400k (Swiss salaries run higher).

## Tax modeling

### France, Austria, Hungary, Poland

Same models as v1. Brief recap:

| Country | Employee load | Employer | Notes |
|---------|--------------|----------|-------|
| France | ~22.5% social + IR with quotient familial | ~43% | Allocations familiales, ARS school allowance |
| Austria | 18.12% SS + progressive (14-month model) | ~30.3% | Familienbonus Plus, Familienbeihilfe |
| Hungary | 18.5% TB + 15% SZJA | ~13% | Family tax credit, családi pótlék |
| Poland | ~13.7% ZUS + 9% health + 12/32% PIT | ~20.5% | 800+, child credit |

### Geneva resident

- **Social** (employee side, total ~12 to 18% depending on age):
  - AVS/AI/APG 5.30% (no cap)
  - AC 1.1% to 148,200 CHF + 0.5% solidarity above
  - AANP non-occupational accident ~1.20%
  - AMat Geneva 0.043%
  - LPP 2nd pillar, age-banded (7/10/15/18% total, 50/50 split): 3.5% / 5% / 7.5% / 9% employee
- **ICC Geneva**: cantonal progressive brackets (0 to 19% marginal) × (1 + centimes additionnels). Geneva-Ville: 45.5%. Married splitting coefficient 1.9.
- **IFD federal**: progressive (0 to 13.2% marginal, capped at 11.5% effective above 755k single / 896k married).
- **Standard deductions**: forfait professionnel 3% (cap 4,000), transport 700, repas 1,600, personal allowance 11k single / 22k married, 13k per child (ICC), 6.7k per child (IFD), child rebate 263 CHF (IFD).
- **Allocations familiales** (paid by employer's caisse, received as benefit): 311 CHF/mo for 1st-2nd child 0-15, 415 from 3rd or 16+, 515 from 3rd 16+.

### Frontalier (lives France, works Geneva)

The tricky case. Geneva is the **special canton**: tax stays in Switzerland under the 1973 agreement (vs the 1983 agreement for Vaud/Berne/etc. where tax goes to France).

- **Swiss social**: same as Geneva resident (Swiss employer applies them regardless of residence).
- **Swiss tax**: impôt à la source in Geneva. Modeled as Geneva ordinary taxation since for income above ~120k CHF the worker is required to file (TOU, taxation ordinaire ultérieure) and the at-source tariff converges on ordinary. Below that the model is in the same ballpark (within ~5 to 10%).
- **French income tax on Swiss salary**: zero (treaty exemption). Salary is declared in France for the "taux effectif" calculation only.
- **No CSG / CRDS** on Swiss salary.
- **Health insurance**: the model assumes the **French CMU frontalier** at 8% of (revenu fiscal de référence above the PASS abatement of ~9,654 EUR). The alternative is Swiss LAMal (~3,500 to 7,000 CHF/year per adult, plus deductible). The choice is made once via the "droit d'option" and is not normally reversible.
- **Family allowances**: paid by the Geneva employer's caisse, in CHF, like for residents. Frontaliers are entitled.
- **Geneva to France retrocession**: Geneva pays France 3.5% of frontalier wages directly, this is funded by the canton, not by the employee or the employer.

### Employer cost

**Identical** for Geneva resident and frontalier. The employer doesn't see where the employee lives. ~17 to 22% on top of gross depending on age (LPP scales).

## Quick start

```bash
cd salary-compare-v2
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Opens at http://localhost:8501.

## Sidebar controls

| Control | Range | Default |
|---------|-------|---------|
| Gross annual salary | 15,000 to 400,000 EUR | 80,000 |
| Married / civil partnership | toggle | off |
| Number of children | 0 to 5 | 0 |
| Age of each child | 0 to 25 | auto |
| Your age | 18 to 65 | 40 |
| Centimes additionnels (GE) | adjustable | 45.5 |
| EUR/HUF | adjustable | 400 |
| EUR/PLN | adjustable | 4.20 |
| EUR/CHF | adjustable | 0.95 |

## Caveats

This is a comparison tool, not a tax advisor. Real situations involve more deductions (3a pillar, PER, IKE/IKZE, childcare, charitable giving), local variations (commune in Switzerland, département in France), employer-specific benefits, edge cases on age boundaries, and treaty nuances. Numbers are approximate to within ~5 to 10%. Consult a fiduciaire / fiscaliste / steuerberater for real decisions, especially on cross-border situations.

## License

MIT.

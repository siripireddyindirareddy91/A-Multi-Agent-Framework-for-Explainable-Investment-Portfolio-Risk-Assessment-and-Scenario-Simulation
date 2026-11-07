# Calculation methodology

Value is the sum of quantity × current price. Weights normalize current market values. USD is the only supported base currency; foreign-currency holdings are rejected instead of silently summed.

Returns use a reproducible one-factor synthetic model, not actual historical market prices. Daily portfolio returns are current weights multiplied by asset returns. The data window supports 30–1260 observations; default is 756. Seed defaults to 42.

- Annualized volatility: sample daily standard deviation × √252.
- Expected return: arithmetic daily mean × 252.
- Sharpe: (annualized mean − 0.04) / annualized volatility.
- Sortino: annualized excess return / annualized root mean squared daily downside relative to 0.04/252.
- Historical VaR: max(0, −lower quantile) × current value.
- CVaR: max(0, −mean return at or below the lower quantile) × value.
- Parametric VaR: max(0, −daily mean + normal inverse CDF(confidence) × daily standard deviation) × value.
- Monte Carlo VaR: same quantile estimator on seeded normally distributed portfolio daily draws (100–20,000).
- Drawdown: minimum of compounded wealth / running maximum − 1, including initial wealth 1.
- Beta: sample covariance with the synthetic market divided by sample benchmark variance.
- Tracking error: sample standard deviation of portfolio minus benchmark daily returns × √252.
- HHI: sum of squared portfolio weights.
- Variance attribution: wᵢ(Σw)ᵢ/(wᵀΣw), summing to one. Negative contributions can occur for hedges.

Composite score = 100 × [0.35 min(volatility/0.4,1) + 0.25 min(|drawdown|/0.5,1) + 0.25 min(HHI/0.3,1) + 0.15 min(VaR return fraction/0.05,1)]. It is a research heuristic.

Scenarios sum asset-class shocks, additional technology shock, uniform FX sensitivity, and an inflation purchasing-power haircut. Bond rate sensitivity assumes six-year duration. Asset values are floored at zero. No convexity, FX conversion, correlations under crisis, slippage, tax or liquidity effects are modeled.

Counterfactual allocations reuse the default synthetic window and seed. They apply illustrative class weights with equal positions within class; missing classes are removed and targets renormalized. They are not CVXPY optimization or advice.

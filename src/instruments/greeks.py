"""Options Greeks using Black-Scholes model.

Provides pricing and sensitivity calculations for European-style options.
"""

import numpy as np
from scipy.stats import norm


def bs_d1(S, K, T, r, sigma):
    """Black-Scholes d1 parameter.

    Args:
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free interest rate (annualized).
        sigma: Volatility (annualized).

    Returns:
        float: d1 value.
    """
    return (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))


def bs_d2(S, K, T, r, sigma):
    """Black-Scholes d2 parameter.

    Args:
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free interest rate (annualized).
        sigma: Volatility (annualized).

    Returns:
        float: d2 value.
    """
    return bs_d1(S, K, T, r, sigma) - sigma * np.sqrt(T)


def bs_call_price(S, K, T, r, sigma):
    """Black-Scholes call option price.

    Args:
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free interest rate (annualized).
        sigma: Volatility (annualized).

    Returns:
        float: Call option price.
    """
    d1 = bs_d1(S, K, T, r, sigma)
    d2 = bs_d2(S, K, T, r, sigma)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def bs_put_price(S, K, T, r, sigma):
    """Black-Scholes put option price.

    Args:
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free interest rate (annualized).
        sigma: Volatility (annualized).

    Returns:
        float: Put option price.
    """
    d1 = bs_d1(S, K, T, r, sigma)
    d2 = bs_d2(S, K, T, r, sigma)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def delta(S, K, T, r, sigma, option_type="CE"):
    """Option delta - sensitivity of option price to underlying price.

    Args:
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free interest rate (annualized).
        sigma: Volatility (annualized).
        option_type: 'CE' for call, 'PE' for put.

    Returns:
        float: Delta value.
    """
    d1 = bs_d1(S, K, T, r, sigma)
    if option_type == "CE":
        return norm.cdf(d1)
    else:
        return norm.cdf(d1) - 1.0


def gamma(S, K, T, r, sigma):
    """Option gamma - rate of change of delta.

    Args:
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free interest rate (annualized).
        sigma: Volatility (annualized).

    Returns:
        float: Gamma value.
    """
    d1 = bs_d1(S, K, T, r, sigma)
    return norm.pdf(d1) / (S * sigma * np.sqrt(T))


def theta(S, K, T, r, sigma, option_type="CE"):
    """Option theta - sensitivity of option price to time (per day).

    Args:
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free interest rate (annualized).
        sigma: Volatility (annualized).
        option_type: 'CE' for call, 'PE' for put.

    Returns:
        float: Theta value (per calendar day).
    """
    d1 = bs_d1(S, K, T, r, sigma)
    d2 = bs_d2(S, K, T, r, sigma)
    common = -(S * norm.pdf(d1) * sigma) / (2.0 * np.sqrt(T))
    if option_type == "CE":
        return (common - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365.0
    else:
        return (common + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365.0


def vega(S, K, T, r, sigma):
    """Option vega - sensitivity of option price to volatility.

    Args:
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free interest rate (annualized).
        sigma: Volatility (annualized).

    Returns:
        float: Vega value (per 1% change in vol, i.e. divided by 100).
    """
    d1 = bs_d1(S, K, T, r, sigma)
    return S * norm.pdf(d1) * np.sqrt(T) / 100.0


def implied_volatility(market_price, S, K, T, r, option_type="CE",
                        tol=1e-6, max_iter=100):
    """Compute implied volatility using Newton-Raphson method.

    Args:
        market_price: Observed market price of the option.
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free interest rate (annualized).
        option_type: 'CE' for call, 'PE' for put.
        tol: Convergence tolerance.
        max_iter: Maximum iterations.

    Returns:
        float: Implied volatility (annualized).

    Raises:
        ValueError: If convergence fails.
    """
    sigma = 0.2  # initial guess

    price_fn = bs_call_price if option_type == "CE" else bs_put_price

    for _ in range(max_iter):
        price = price_fn(S, K, T, r, sigma)
        d1 = bs_d1(S, K, T, r, sigma)
        vega_val = S * norm.pdf(d1) * np.sqrt(T)

        if vega_val < 1e-12:
            break

        diff = price - market_price
        if abs(diff) < tol:
            return sigma

        sigma = sigma - diff / vega_val
        # Keep sigma positive
        sigma = max(sigma, 1e-6)

    return sigma

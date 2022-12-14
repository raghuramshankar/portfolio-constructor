# %%
import datetime
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.stats
import statsmodels.api as sm
from numpy.linalg import inv
from scipy.optimize import minimize


def terminal_wealth(s):
    """
    Computes the terminal wealth of a sequence of return, which is, in other words,
    the final compounded return.
    The input s is expected to be either a pd.DataFrame or a pd.Series
    """
    if not isinstance(s, (pd.DataFrame, pd.Series)):
        raise ValueError("Expected either a pd.DataFrame or pd.Series")
    return (1 + s).prod()


def compound_returns(s, start=100):
    """
    Compound a pd.Dataframe or pd.Series of returns from an initial default value equal to 100.
    In the former case, the method compounds the returns for every column (Series) by using pd.aggregate.
    The method returns a pd.Dataframe or pd.Series - using cumprod().
    See also the COMPOUND method.
    """
    if isinstance(s, pd.DataFrame):
        return s.aggregate(compound_returns, start=start)
    elif isinstance(s, pd.Series):
        return start * (1 + s).cumprod()
    else:
        raise TypeError("Expected pd.DataFrame or pd.Series")


def drawdown(rets: pd.Series, start=1000):
    """
    Compute the drawdowns of an input pd.Series of returns.
    The method returns a dataframe containing:
    1. the associated wealth index (for an hypothetical starting investment of $1000)
    2. all previous peaks
    3. the drawdowns
    """
    wealth_index = compound_returns(rets, start=start)
    previous_peaks = wealth_index.cummax()
    drawdowns = (wealth_index - previous_peaks) / previous_peaks
    df = pd.DataFrame(
        {"Wealth": wealth_index, "Peaks": previous_peaks, "Drawdown": drawdowns}
    )
    return df


def skewness(s):
    """
    Computes the Skewness of the input Series or Dataframe.
    There is also the function scipy.stats.skew().
    """
    return (((s - s.mean()) / s.std(ddof=0)) ** 3).mean()


def kurtosis(s):
    """
    Computes the Kurtosis of the input Series or Dataframe.
    There is also the function scipy.stats.kurtosis() which, however,
    computes the "Excess Kurtosis", i.e., Kurtosis minus 3
    """
    return (((s - s.mean()) / s.std(ddof=0)) ** 4).mean()


def exkurtosis(s):
    """
    Returns the Excess Kurtosis, i.e., Kurtosis minus 3
    """
    return kurtosis(s) - 3


def is_normal(s, level=0.01):
    """
    Jarque-Bera test to see if a series (of returns) is normally distributed.
    Returns True or False according to whether the p-value is larger
    than the default level=0.01.
    """
    statistic, pvalue = scipy.stats.jarque_bera(s)
    return pvalue > level


def semivolatility(s):
    """
    Returns the semivolatility of a series, i.e., the volatility of
    negative returns
    """
    return s[s < 0].std(ddof=0)


def var_historic(s, level=0.05):
    """
    Returns the (1-level)% VaR using historical method.
    By default it computes the 95% VaR, i.e., alpha=0.95 which gives level 1-alpha=0.05.
    The method takes in input either a DataFrame or a Series and, in the former
    case, it computes the VaR for every column (Series) by using pd.aggregate
    """
    if isinstance(s, pd.DataFrame):
        return s.aggregate(var_historic, level=level)
    elif isinstance(s, pd.Series):
        return -np.percentile(s, level * 100)
    else:
        raise TypeError("Expected pd.DataFrame or pd.Series")


def var_gaussian(s, level=0.05, cf=False):
    """
    Returns the (1-level)% VaR using the parametric Gaussian method.
    By default it computes the 95% VaR, i.e., alpha=0.95 which gives level 1-alpha=0.05.
    The variable "cf" stands for Cornish-Fisher. If True, the method computes the
    modified VaR using the Cornish-Fisher expansion of quantiles.
    The method takes in input either a DataFrame or a Series and, in the former
    case, it computes the VaR for every column (Series).
    """
    # alpha-quantile of Gaussian distribution
    za = scipy.stats.norm.ppf(level, 0, 1)
    if cf:
        S = skewness(s)
        K = kurtosis(s)
        za = (
            za
            + (za**2 - 1) * S / 6
            + (za**3 - 3 * za) * (K - 3) / 24
            - (2 * za**3 - 5 * za) * (S**2) / 36
        )
    return -(s.mean() + za * s.std(ddof=0))


def cvar_historic(s, level=0.05):
    """
    Computes the (1-level)% Conditional VaR (based on historical method).
    By default it computes the 95% CVaR, i.e., alpha=0.95 which gives level 1-alpha=0.05.
    The method takes in input either a DataFrame or a Series and, in the former
    case, it computes the VaR for every column (Series).
    """
    if isinstance(s, pd.DataFrame):
        return s.aggregate(cvar_historic, level=level)
    elif isinstance(s, pd.Series):
        # find the returns which are less than (the historic) VaR
        mask = s < -var_historic(s, level=level)
        # and of them, take the mean
        return -s[mask].mean()
    else:
        raise TypeError("Expected pd.DataFrame or pd.Series")


def annualize_rets(s, periods_per_year):
    """
    Computes the return per year, or, annualized return.
    The variable periods_per_year can be, e.g., 12, 52, 252, in
    case of monthly, weekly, and daily data.
    The method takes in input either a DataFrame or a Series and, in the former
    case, it computes the annualized return for every column (Series) by using pd.aggregate
    """
    if isinstance(s, pd.DataFrame):
        return s.aggregate(annualize_rets, periods_per_year=periods_per_year)
    elif isinstance(s, pd.Series):
        growth = (1 + s).prod()
        n_period_growth = s.shape[0]
        return growth ** (periods_per_year / n_period_growth) - 1


def annualize_vol(s, periods_per_year, ddof=1):
    """
    Computes the volatility per year, or, annualized volatility.
    The variable periods_per_year can be, e.g., 12, 52, 252, in
    case of monthly, weekly, and daily data.
    The method takes in input either a DataFrame, a Series, a list or a single number.
    In the former case, it computes the annualized volatility of every column
    (Series) by using pd.aggregate. In the latter case, s is a volatility
    computed beforehand, hence only annulization is done
    """
    if isinstance(s, pd.DataFrame):
        return s.aggregate(annualize_vol, periods_per_year=periods_per_year)
    elif isinstance(s, pd.Series):
        return s.std(ddof=ddof) * (periods_per_year) ** (0.5)
    elif isinstance(s, list):
        return np.std(s, ddof=ddof) * (periods_per_year) ** (0.5)
    elif isinstance(s, (int, float)):
        return s * (periods_per_year) ** (0.5)


def sharpe_ratio(s, risk_free_rate, periods_per_year, v=None):
    """
    Computes the annualized sharpe ratio.
    The variable periods_per_year can be, e.g., 12, 52, 252, in case of yearly, weekly, and daily data.
    The variable risk_free_rate is the annual one.
    The method takes in input either a DataFrame, a Series or a single number.
    In the former case, it computes the annualized sharpe ratio of every column (Series) by using pd.aggregate.
    In the latter case, s is the (allready annualized) return and v is the (already annualized) volatility
    computed beforehand, for example, in case of a portfolio.
    """
    if isinstance(s, pd.DataFrame):
        return s.aggregate(
            sharpe_ratio,
            risk_free_rate=risk_free_rate,
            periods_per_year=periods_per_year,
            v=None,
        )
    elif isinstance(s, pd.Series):
        # convert the annual risk free rate to the period assuming that:
        # RFR_year = (1+RFR_period)^{periods_per_year} - 1. Hence:
        rf_to_period = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
        excess_return = s - rf_to_period
        # now, annualize the excess return
        ann_ex_rets = annualize_rets(excess_return, periods_per_year)
        # compute annualized volatility
        ann_vol = annualize_vol(s, periods_per_year)
        return ann_ex_rets / ann_vol
    elif isinstance(s, (int, float)) and v is not None:
        # Portfolio case: s is supposed to be the single (already annnualized)
        # return of the portfolio and v to be the single (already annualized) volatility.
        return (s - risk_free_rate) / v


# ---------------------------------------------------------------------------------
# Modern Portfolio Theory
# ---------------------------------------------------------------------------------
def portfolio_return(weights, vec_returns):
    """
    Computes the return of a portfolio.
    It takes in input a row vector of weights (list of np.array)
    and a column vector (or pd.Series) of returns
    """
    return np.dot(weights, vec_returns)


def portfolio_volatility(weights, cov_rets):
    """
    Computes the volatility of a portfolio.
    It takes in input a vector of weights (np.array or pd.Series)
    and the covariance matrix of the portfolio asset returns
    """
    return (np.dot(weights.T, np.dot(cov_rets, weights))) ** (0.5)


def efficient_frontier(
    n_portfolios,
    rets,
    covmat,
    periods_per_year,
    risk_free_rate=0.0,
    plot=False,
):
    """
    Returns and plots the efficient frontier of portfolio of n assets. Also returns and plots the following portfolios:
        msr: maximum sharpe ratio portfolio
        mvp: minimum volatility portfolio
        ewp: equally weighted portfolio
    Plots the Capital Market Line as well.
    The variable periods_per_year can be, e.g., 12, 52, 252, in case of monthly, weekly, and daily data.
    """

    ann_rets = annualize_rets(rets, periods_per_year)

    # generates optimal weights of porfolios lying of the efficient frontiers
    weights = optimal_weights(n_portfolios, ann_rets, covmat, periods_per_year)
    # in alternative, if only the portfolio consists of only two assets, the weights can be:
    # weights = [np.array([w,1-w]) for w in np.linspace(0,1,n_portfolios)]

    # portfolio returns
    portfolio_ret = [portfolio_return(w, ann_rets) for w in weights]

    # portfolio volatility
    vols = [portfolio_volatility(w, covmat) for w in weights]
    portfolio_vol = [annualize_vol(v, periods_per_year) for v in vols]

    # portfolio sharpe ratio
    portfolio_spr = [
        sharpe_ratio(r, risk_free_rate, periods_per_year, v=v)
        for r, v in zip(portfolio_ret, portfolio_vol)
    ]

    # dataframe for efficient frontier
    ef = pd.DataFrame(weights, columns=rets.columns)
    ef = ef.join(
        pd.DataFrame(
            {
                "Volatility": portfolio_vol,
                "Return": portfolio_ret,
                "Sharpe Ratio": portfolio_spr,
            }
        )
    )

    if plot:
        ax = ef.plot.line(x="Volatility", y="Return", label="Efficient Frontier")

    # dataframe for maximum sharpe ratio portfolio
    w = maximize_shape_ratio(ann_rets, covmat, risk_free_rate, periods_per_year)
    ret = portfolio_return(w, ann_rets)
    vol = annualize_vol(portfolio_volatility(w, covmat), periods_per_year)
    spr = sharpe_ratio(ret, risk_free_rate, periods_per_year, v=vol)
    df_msr = pd.DataFrame(
        np.array([np.append(w, [vol, ret, spr], axis=0)]), columns=ef.columns
    )

    if plot:
        df_msr.plot.scatter(
            x="Volatility",
            y="Return",
            ax=ax,
            color="g",
            marker="o",
            label="Maximum Sharpe Ratio",
        )

        ax.plot(
            [0, vol],
            [risk_free_rate, ret],
            color="g",
            linestyle="--",
            label="Capital Market Line",
        )

    # dataframe for minimum volatility portfolio
    w = minimize_volatility(ann_rets, covmat)
    ret = portfolio_return(w, ann_rets)
    vol = annualize_vol(portfolio_volatility(w, covmat), periods_per_year)
    spr = sharpe_ratio(ret, risk_free_rate, periods_per_year, v=vol)
    df_mvp = pd.DataFrame(
        np.array([np.append(w, [vol, ret, spr], axis=0)]), columns=ef.columns
    )

    if plot:
        df_mvp.plot.scatter(
            x="Volatility",
            y="Return",
            ax=ax,
            color="b",
            marker="o",
            label="Minimum Volatility",
        )

    # dataframe for equally weighted portfolio
    w = np.repeat(1 / ann_rets.shape[0], ann_rets.shape[0])
    ret = portfolio_return(w, ann_rets)
    vol = annualize_vol(portfolio_volatility(w, covmat), periods_per_year)
    spr = sharpe_ratio(ret, risk_free_rate, periods_per_year, v=vol)
    df_ewp = pd.DataFrame(
        np.array([np.append(w, [vol, ret, spr], axis=0)]), columns=ef.columns
    )

    if plot:
        df_ewp.plot.scatter(
            x="Volatility",
            y="Return",
            ax=ax,
            color="y",
            marker="o",
            label="Equally Weighted",
        )

        ax.grid(True)

    # create dataframe for special portfolios
    df = pd.concat([df_msr, df_mvp, df_ewp])
    df.index = ["Maximum Sharpe Ratio", "Minimum Volatility", "Equally Weighted"]
    return ef, df


def summary_stats(s, risk_free_rate=0.03, periods_per_year=12, var_level=0.05):
    """
    Returns a dataframe containing annualized returns, annualized volatility, sharpe ratio,
    skewness, kurtosis, historic VaR, Cornish-Fisher VaR, and Max Drawdown
    """
    if isinstance(s, pd.Series):
        stats = {
            "Ann. return": annualize_rets(s, periods_per_year=periods_per_year),
            "Ann. vol": annualize_vol(s, periods_per_year=periods_per_year),
            "Sharpe ratio": sharpe_ratio(
                s, risk_free_rate=risk_free_rate, periods_per_year=periods_per_year
            ),
            "Skewness": skewness(s),
            "Kurtosis": kurtosis(s),
            "Historic CVar": cvar_historic(s, level=var_level),
            "C-F Var": var_gaussian(s, level=var_level, cf=True),
            "Max drawdown": drawdown(s)["Drawdown"].min(),
        }
        return pd.DataFrame(stats, index=["0"])

    elif isinstance(s, pd.DataFrame):
        stats = {
            "Ann. return": s.aggregate(
                annualize_rets, periods_per_year=periods_per_year
            ),
            "Ann. vol": s.aggregate(annualize_vol, periods_per_year=periods_per_year),
            "Sharpe ratio": s.aggregate(
                sharpe_ratio,
                risk_free_rate=risk_free_rate,
                periods_per_year=periods_per_year,
            ),
            "Skewness": s.aggregate(skewness),
            "Kurtosis": s.aggregate(kurtosis),
            "Historic CVar": s.aggregate(cvar_historic, level=var_level),
            "C-F Var": s.aggregate(var_gaussian, level=var_level, cf=True),
            "Max Drawdown": s.aggregate(lambda r: drawdown(r)["Drawdown"].min()),
        }
        return pd.DataFrame(stats)


def summary_stats_terminal(
    rets, floor=0.8, periods_per_year=2, name="Stats", target=np.inf
):
    """
    Return a dataframe of statistics for a given input pd.DataFrame of asset returns.
    Statistics computed are:
    - the mean annualized return
    - the mean terminal wealth (compounded return)
    - the mean terminal wealth volatility
    - the probability that an input floor is breached by terminal wealths
    - the expected shortfall of those terminal wealths breaching the input floor
    """
    # terminal wealths over scenarios, i.e., compounded returns
    terminal_wlt = terminal_wealth(rets)

    # boolean vector of terminal wealths going below the floor
    floor_breach = terminal_wlt < floor

    stats = pd.DataFrame.from_dict(
        {
            "Mean ann. ret.": annualize_rets(
                rets, periods_per_year=periods_per_year
            ).mean(),  # mean annualized returns over scenarios
            "Mean wealth": terminal_wlt.mean(),  # terminal wealths mean
            "Mean wealth std": terminal_wlt.std(),  # terminal wealths volatility
            "Prob breach": floor_breach.mean()
            if floor_breach.sum() > 0
            else 0,  # probability of breaching the floor
            "Exp shortfall": (floor - terminal_wlt[floor_breach]).mean()
            if floor_breach.sum() > 0
            else 0,  # expected shortfall if floor is reached
        },
        orient="index",
        columns=[name],
    )
    return stats


def optimal_weights(n_points, rets, covmatrix, periods_per_year):
    """
    Returns a set of n_points optimal weights corresponding to portfolios (of the efficient frontier)
    with minimum volatility constructed by fixing n_points target returns.
    The weights are obtained by solving the minimization problem for the volatility.
    """
    target_rets = np.linspace(rets.min(), rets.max(), n_points)
    weights = [minimize_volatility(rets, covmatrix, target) for target in target_rets]
    return weights


def minimize_volatility(rets, covmatrix, target_return=None):
    """
    Returns the optimal weights of the minimum volatility portfolio on the effient frontier.
    If target_return is not None, then the weights correspond to the minimum volatility portfolio
    having a fixed target return.
    The method uses the scipy minimize optimizer which solves the minimization problem
    for the volatility of the portfolio
    """
    n_assets = rets.shape[0]
    # initial guess weights
    init_guess = np.repeat(1 / n_assets, n_assets)
    weights_constraint = {"type": "eq", "fun": lambda w: 1.0 - np.sum(w)}
    if target_return is not None:
        return_constraint = {
            "type": "eq",
            "args": (rets,),
            "fun": lambda w, r: target_return - portfolio_return(w, r),
        }
        constr = (return_constraint, weights_constraint)
    else:
        constr = weights_constraint

    result = minimize(
        portfolio_volatility,
        init_guess,
        args=(covmatrix,),
        method="SLSQP",
        options={"disp": False},
        constraints=constr,
        bounds=((0.0, 1.0),) * n_assets,
    )  # bounds of each individual weight, i.e., w between 0 and 1
    return result.x


def minimize_volatility_2(
    rets,
    covmatrix,
    target_return=None,
    weights_norm_const=True,
    weights_bound_const=True,
):
    """
    Returns the optimal weights of the minimum volatility portfolio.
    If target_return is not None, then the weights correspond to the minimum volatility portfolio
    having a fixed target return (such portfolio will be on the efficient frontier).
    The variables weights_norm_const and weights_bound_const impose two more conditions, the firt one on
    weight that sum to 1, and the latter on the weights which have to be between zero and 1
    The method uses the scipy minimize optimizer which solves the minimization problem
    for the volatility of the portfolio
    """
    n_assets = rets.shape[0]

    # initial guess weights
    init_guess = np.repeat(1 / n_assets, n_assets)

    if weights_bound_const:
        # bounds of the weights (between 0 and 1)
        bounds = ((0.0, 1.0),) * n_assets
    else:
        bounds = None

    constraints = []
    if weights_norm_const:
        weights_constraint = {"type": "eq", "fun": lambda w: 1.0 - np.sum(w)}
        constraints.append(weights_constraint)
    if target_return is not None:
        return_constraint = {
            "type": "eq",
            "args": (rets,),
            "fun": lambda w, r: target_return - portfolio_return(w, r),
        }
        constraints.append(return_constraint)

    result = minimize(
        portfolio_volatility,
        init_guess,
        args=(covmatrix,),
        method="SLSQP",
        options={"disp": False},
        constraints=tuple(constraints),
        bounds=bounds,
    )
    return result.x


def maximize_shape_ratio(
    rets, covmatrix, risk_free_rate, periods_per_year, target_volatility=None
):
    """
    Returns the optimal weights of the highest sharpe ratio portfolio on the effient frontier.
    If target_volatility is not None, then the weights correspond to the highest sharpe ratio portfolio
    having a fixed target volatility.
    The method uses the scipy minimize optimizer which solves the maximization of the sharpe ratio which
    is equivalent to minimize the negative sharpe ratio.
    """
    n_assets = rets.shape[0]
    init_guess = np.repeat(1 / n_assets, n_assets)
    weights_constraint = {"type": "eq", "fun": lambda w: 1.0 - np.sum(w)}
    if target_volatility is not None:
        volatility_constraint = {
            "type": "eq",
            "args": (covmatrix, periods_per_year),
            "fun": lambda w, cov, p: target_volatility
            - annualize_vol(portfolio_volatility(w, cov), p),
        }
        constr = (volatility_constraint, weights_constraint)
    else:
        constr = weights_constraint

    def neg_portfolio_sharpe_ratio(
        weights, rets, covmatrix, risk_free_rate, periods_per_year
    ):
        """
        Computes the negative annualized sharpe ratio for minimization problem of optimal portfolios.
        The variable periods_per_year can be, e.g., 12, 52, 252, in case of yearly, weekly, and daily data.
        The variable risk_free_rate is the annual one.
        """
        # annualized portfolio returns
        portfolio_ret = portfolio_return(weights, rets)
        # annualized portfolio volatility
        portfolio_vol = annualize_vol(
            portfolio_volatility(weights, covmatrix), periods_per_year
        )
        return -sharpe_ratio(
            portfolio_ret, risk_free_rate, periods_per_year, v=portfolio_vol
        )
        # i.e., simply returns  -(portfolio_ret - risk_free_rate)/portfolio_vol

    result = minimize(
        neg_portfolio_sharpe_ratio,
        init_guess,
        args=(rets, covmatrix, risk_free_rate, periods_per_year),
        method="SLSQP",
        options={"disp": False},
        constraints=constr,
        bounds=((0.0, 1.0),) * n_assets,
    )
    return result.x


def weigths_max_sharpe_ratio(covmat, mu_exc, scale=True):
    """
    Optimal (Tangent/Max Sharpe Ratio) portfolio weights using the Markowitz Optimization Procedure:
    - mu_exc is the vector of Excess expected Returns (has to be a column vector as a pd.Series)
    - covmat is the covariance N x N matrix as a pd.DataFrame
    Look at pag. 188 eq. (5.2.28) of "The econometrics of financial markets", by Campbell, Lo, Mackinlay.
    """
    w = inverse_df(covmat).dot(mu_exc)
    if scale:
        # normalize weigths
        w = w / sum(w)
    return w

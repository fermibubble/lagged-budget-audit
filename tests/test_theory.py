import math
import numpy as np
import pytest
from lag_audit.thresholds import Threshold, alpha, zcl_bound, optimal_beta, delayed_exp, coverage
from lag_audit.theory import random_audit, coarse_counterexample, adversary
from lag_audit.oracles import integer_knapsack, brute_force, fractional_optimum, resolved_count_oracle


@pytest.mark.parametrize('ratio,delta,zcl,beta', [
    (10,.05,3.821,3.682),(10,.1,4.393,4.059),(10,.2,5.668,4.807),(10,.3,7.021,5.546),
    (100,.05,7.391,6.975),(100,.1,9.722,8.511),(100,.2,16.625,12.110),(100,.3,27.625,16.402),
    (1000,.05,11.736,10.986),(1000,.1,17.407,14.847),(1000,.2,38.158,25.430),(1000,.3,82.686,40.449)])
def test_paper_table5_numerical_targets(ratio, delta, zcl, beta):
    assert zcl_bound(1, ratio, delta) == pytest.approx(zcl, abs=.00051)
    assert optimal_beta(1, ratio, delta) == pytest.approx(beta, abs=.00051)


@pytest.mark.parametrize('ratio', [2,10,100,1000])
def test_zero_lag_and_endpoint(ratio):
    assert zcl_bound(1, ratio, 0) == pytest.approx(alpha(1,ratio))
    assert optimal_beta(1, ratio, 0) == pytest.approx(alpha(1,ratio))
    lag = Threshold(1, ratio, 'lag')
    zcl = Threshold(1, ratio)
    for z in np.linspace(0,1,31):
        assert lag(z) == pytest.approx(max(1,zcl(z)))
    assert lag(1) == pytest.approx(ratio)


@pytest.mark.parametrize('delay', [.05,.1,.2,.3,.5,.99,1.0])
def test_lag_integral_identity(delay):
    phi = Threshold(1,100,'lag',delta=delay)
    for z in np.linspace(0,1,25):
        assert phi(z) == pytest.approx(max(1,phi.beta*coverage(phi,delay,z)), rel=1e-8)
    assert phi(1) == pytest.approx(100)
    assert phi.beta <= zcl_bound(1,100,delay) + 1e-8


def test_delayed_exponential_satisfies_dde():
    h=1e-6
    for delay in [.05,.2,.5]:
        for u in [.037,.153,.473,.837]:
            derivative=(delayed_exp(8,u+h,delay)-delayed_exp(8,u-h,delay))/(2*h)
            assert derivative == pytest.approx(8*delayed_exp(8,u-delay,delay),rel=1e-7)


def test_half_delay_closed_form_independent_derivation():
    assert optimal_beta(1,1000,.5) == pytest.approx(math.sqrt(8000)-2)


def test_lower_lag_raises_coverage():
    phi=Threshold(1,100,'lag',delta=.2)
    for z in np.linspace(.01,1,25):
        assert coverage(phi,.1,z) >= coverage(phi,.2,z)-1e-10


@pytest.mark.parametrize('forecast',[0,.1,1,5,20,100,1000])
def test_banded_forecast_proposition54_grid(forecast):
    L,U,s,d=1,100,.05,.1
    a=alpha(L,U)
    bound=max(a/(1-a*s),math.exp(a*s)*zcl_bound(L,U,s+d))
    phi=Threshold(L,U,'band',forecast=forecast,band=s)
    for z in np.linspace(.001,1,150):
        if phi(z)>L:
            assert phi(z)/coverage(phi,d,z) <= bound+1e-6
    assert U/coverage(phi,d,1) <= bound+1e-6


def test_randomized_theorem3_and5():
    audit=random_audit(128,seed=741)
    assert audit['violations']==0, audit['counterexamples']
    assert len(audit['configurations'])==16


def test_coarse_filler_regression():
    row=coarse_counterexample()
    assert not row['failures']
    assert row['harmful_refusal']
    assert row['measured_ratio']==pytest.approx(12.9817494326)
    assert row['measured_ratio']>row['small_item_claim_comparator']
    assert row['measured_ratio']<row['reservation_certificate']


@pytest.mark.parametrize('kind',['zcl','lag'])
def test_adversary_converges_not_finite_size_bound(kind):
    coarse=adversary(100,.2,100,kind)
    fine=adversary(100,.2,1600,kind)
    assert fine['relative_error'] < coarse['relative_error']
    assert fine['relative_error'] < .01
    assert fine['observed_delta_including_item'] > .2


def test_dp_independent_exhaustive_checker():
    rng=np.random.default_rng(49)
    for _ in range(100):
        weights=[int(x) for x in rng.integers(0,20,8)]
        values=rng.random(8).tolist()
        assert integer_knapsack(weights,values,25)==pytest.approx(brute_force(weights,values,25))
        assert fractional_optimum(weights,values,25)+1e-9>=integer_knapsack(weights,values,25)


def test_unit_value_oracle_avoids_cent_rounding_bug():
    assert resolved_count_oracle([.501,.501,2],[1,1,1],1)==1
    assert resolved_count_oracle([0,.5,.5],[1,1,1],1)==3


@pytest.mark.parametrize('L,U',[(0,2),(1,1),(2,1),(1,float('inf'))])
def test_invalid_density_bounds(L,U):
    with pytest.raises(ValueError): Threshold(L,U)

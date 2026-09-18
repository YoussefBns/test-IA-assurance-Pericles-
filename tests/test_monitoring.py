import importlib.util
import numpy as np
import pytest

def test_monitoring_module_exists():
    assert importlib.util.find_spec('partie3_mlops.monitoring') is not None

def test_psi_equal_zero_and_shift_positive():
    from partie3_mlops.monitoring import psi
    assert psi([10,20,0],[10,20,0])==pytest.approx(0)
    assert psi([10,20,0],[0,0,30])>0
    with pytest.raises(ValueError):psi([0,0],[1,1])
    with pytest.raises(ValueError):psi([1,-1],[1,1])

def test_reference_bins_include_extremes_missing():
    from partie3_mlops.monitoring import histogram
    assert histogram([-500,0,5,20,999,None,float('nan')],[0,10,20])==[1,2,0,2,2]

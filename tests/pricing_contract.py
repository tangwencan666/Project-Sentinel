"""Immutable acceptance contract; copied into candidate workspace by patch runner."""
import pytest
from pricing import total

@pytest.mark.parametrize('price,quantity,discount,expected',[(10,1,None,10),(12.5,2,0,25),(10,2,.1,18),(0,1,None,0),(3.25,4,.2,10.4),(9,1,1,0)])
def test_prices(price,quantity,discount,expected):
    assert total(price,quantity,discount)==expected

@pytest.mark.parametrize('price,quantity',[(-1,1),(1,0),(10,-3)])
def test_invalid_orders(price,quantity):
    with pytest.raises(ValueError): total(price,quantity)

"""Immutable patch acceptance contracts; selected by trusted controller, never candidate."""
import importlib.util
import os
import pytest

name=os.environ['PATCH_COMPONENT']
spec=importlib.util.spec_from_file_location('candidate',os.environ['PATCH_SOURCE'])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

@pytest.mark.parametrize('value,expected',[(0,0.0),(12.50,12.50),('10.75',10.75)])
def test_payment_valid(value,expected):
    if name!='payment': pytest.skip('different component contract')
    assert module.normalize_amount(value)==expected

@pytest.mark.parametrize('value',[-1,-.01,float('nan'),float('inf'),float('-inf'),None,True])
def test_payment_rejects_invalid_amounts(value):
    if name!='payment': pytest.skip('different component contract')
    with pytest.raises(ValueError): module.normalize_amount(value)

def test_order_preserves_actual_item():
    if name!='order': pytest.skip('different component contract')
    item={'id':1,'price':12.5};assert module.choose_item([item,{'id':2}])==item

@pytest.mark.parametrize('items',[[],None])
def test_order_empty_catalog_is_domain_error(items):
    if name!='order': pytest.skip('different component contract')
    with pytest.raises(ValueError): module.choose_item(items)

def test_inventory_preserves_stock_and_identity_without_mutation():
    if name!='inventory': pytest.skip('different component contract')
    original={'id':3,'name':'item','price':'12.50','stock':7}
    result=module.normalize_product(original)
    assert result=={**original,'price':12.5} and original['price']=='12.50'

@pytest.mark.parametrize('price,stock',[(-1,4),(10,-1),(float('nan'),2),(float('inf'),2),(None,2),(10,None)])
def test_inventory_rejects_invalid_records(price,stock):
    if name!='inventory': pytest.skip('different component contract')
    with pytest.raises(ValueError): module.normalize_product({'id':1,'price':price,'stock':stock})

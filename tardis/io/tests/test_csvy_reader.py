import tardis
from tardis.io.parsers import csvy
import pytest
import os
from astropy import units as u
import numpy.testing as npt


DATA_PATH = os.path.join(tardis.__path__[0], 'io', 'tests', 'data')

@pytest.fixture
def csvy_full_fname():
    return os.path.join(DATA_PATH, 'csvy_full.dat')

@pytest.fixture
def csvy_nocsv_fname():
    return os.path.join(DATA_PATH, 'csvy_nocsv.dat')

def test_csvy_finds_csv_first_line(csvy_full_fname):
    yaml_dict, csv = csvy.load_csvy(csvy_full_fname)
    assert csv['velocity'][0] == 10000

def test_csv_colnames_equiv_datatype_fields(csvy_full_fname):
    yaml_dict, csv = csvy.load_csvy(csvy_full_fname)
    datatype_names = [od['name'] for od in yaml_dict['datatype']['fields']]
    for key in csv.columns:
        assert key in datatype_names
    for name in datatype_names:
        assert name in csv.columns

def test_csvy_nocsv_data_is_none(csvy_nocsv_fname):
    yaml_dict, csv = csvy.load_csvy(csvy_nocsv_fname)
    assert csv is None

"""HydroMT: Automated and reproducible model building and analysis"""

# version number without 'v' at start
__version__ = "0.6.1.dev"

# submodules
from . import cli, workflows, stats, flw, raster, vector

# high-level methods
from .models import *
from .io import *
from .data_catalog import *

# required for accessor style documentation
from xarray import DataArray, Dataset

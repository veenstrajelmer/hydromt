# -*- coding: utf-8 -*-
"""General and basic API for models in HydroMT"""


import xarray as xr
import logging
from typing import Dict, List, Union, Optional

from .model_api import Model, _check_data

__all__ = [""]

logger = logging.getLogger(__name__)


class MapsMixin:
    # mixin class to add an general maps object
    # contains maps needed for model building but not model data
    _API = {
        "maps": Dict[str, Union[xr.DataArray, xr.Dataset]],
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._maps = dict()  # dictionary of xr.DataArray and/or xr.Dataset

    # map files setup methods
    def setup_maps_from_raster(
        self,
        raster_fn: str,
        variables: Optional[List] = None,
        fill_method: Optional[str] = None,
        name: Optional[str] = None,
        reproject_method: Optional[str] = None,
        split_dataset: Optional[bool] = True,
    ) -> List[str]:
        """
        This component adds data variable(s) from ``raster_fn`` to maps object.

        If raster is a dataset, all variables will be added unless ``variables`` list is specified.

        Adds model layers:

        * **raster.name** maps: data from raster_fn

        Parameters
        ----------
        raster_fn: str
            Source name of raster data in data_catalog.
        variables: list, optional
            List of variables to add to maps from raster_fn. By default all.
        fill_method : str, optional
            If specified, fills nodata values using fill_nodata method.
            Available methods are {'linear', 'nearest', 'cubic', 'rio_idw'}.
        name: str, optional
            Name of new maps variable, only in case split_dataset=False.
        reproject_method: str, optional
            See rasterio.warp.reproject for existing methods, by default the data is not reprojected (None).
        split_dataset: bool, optional
            If data is a xarray.Dataset split it into several xarray.DataArrays (default).

        Returns
        -------
        list
            Names of added model map layers
        """
        self.logger.info(f"Preparing maps data from raster source {raster_fn}")
        # Read raster data and select variables
        ds = self.data_catalog.get_rasterdataset(
            raster_fn,
            geom=self.region,
            buffer=2,
            variables=variables,
            single_var_as_array=False,
        )
        # Fill nodata
        if fill_method is not None:
            ds = ds.raster.interpolate_na(method=fill_method)
        # Reprojection
        if ds.rio.crs != self.crs and reproject_method is not None:
            ds = ds.raster.reproject(dst_crs=self.crs, method=reproject_method)
        # Add to maps
        self.set_maps(ds, name=name, split_dataset=split_dataset)

        return list(ds.data_vars.keys())

    def setup_maps_from_raster_reclass(
        self,
        raster_fn: str,
        reclass_table_fn: str,
        reclass_variables: List,
        variable: Optional[str] = None,
        fill_method: Optional[str] = None,
        reproject_method: Optional[str] = None,
        name: Optional[str] = None,
        split_dataset: Optional[bool] = True,
        **kwargs,
    ) -> List[str]:
        """
        This component adds data variable(s) to maps object by reclassifying the data in ``raster_fn`` based on ``reclass_table_fn``.

        Adds model layers:

        * **reclass_variables** maps: reclassified raster data

        Parameters
        ----------
        raster_fn: str
            Source name of raster data in data_catalog. Should be a DataArray. Else use **kwargs to select variables/time_tuple in
            :py:meth:`hydromt.data_catalog.get_rasterdataset` method.
        reclass_table_fn: str
            Source name of reclassification table of `raster_fn` in data_catalog.
        reclass_variables: list
            List of reclass_variables from reclass_table_fn table to add to maps. Index column should match values in `raster_fn`.
        variable: str, optional
            Name of raster dataset variable to use. This is only required when reading datasets with multiple variables.
            By default None.
        fill_method : str, optional
            If specified, fills nodata values in `raster_fn` using fill_nodata method before reclassifying.
            Available methods are {'linear', 'nearest', 'cubic', 'rio_idw'}.
        reproject_method: str, optional
            See rasterio.warp.reproject for existing methods, by default the data is not reprojected (None).
        name: str, optional
            Name of new maps variable, only in case split_dataset=False.
        split_dataset: bool, optional
            If data is a xarray.Dataset split it into several xarray.DataArrays (default).

        Returns
        -------
        list
            Names of added model map layers
        """
        self.logger.info(
            f"Preparing map data by reclassifying the data in {raster_fn} based on {reclass_table_fn}"
        )
        # Read raster data and remapping table
        da = self.data_catalog.get_rasterdataset(
            raster_fn, geom=self.region, buffer=2, **kwargs
        )
        if not isinstance(da, xr.DataArray):
            raise ValueError(
                f"raster_fn {raster_fn} should be a single variable. "
                "Please select one using the 'variable' argument"
            )
        df_vars = self.data_catalog.get_dataframe(
            reclass_table_fn, variables=reclass_variables
        )
        # Fill nodata
        if fill_method is not None:
            ds = ds.raster.interpolate_na(method=fill_method)
        # Mapping function
        ds_vars = da.raster.reclassify(reclass_table=df_vars, method="exact")
        # Reprojection
        if ds_vars.rio.crs != self.crs and reproject_method is not None:
            ds_vars = ds_vars.raster.reproject(dst_crs=self.crs)
        # Add to maps
        self.set_maps(ds_vars, name=name, split_dataset=split_dataset)

        return list(ds_vars.data_vars.keys())

    # model map
    @property
    def maps(self) -> Dict[str, Union[xr.Dataset, xr.DataArray]]:
        """Model maps. Returns dict of xarray.DataArray or xarray.Dataset"""
        if len(self._maps) == 0:
            if self._read:
                self.read_maps()
        return self._maps

    def set_maps(
        self,
        data: Union[xr.DataArray, xr.Dataset],
        name: Optional[str] = None,
        split_dataset: Optional[bool] = True,
    ) -> None:
        """Add raster data to the maps component.

        Dataset can either be added as is (default) or split into several
        DataArrays using the split_dataset argument.

        Arguments
        ---------
        data: xarray.Dataset or xarray.DataArray
            New forcing data to add
        name: str, optional
            Variable name, only in case data is of type DataArray or if a Dataset is added as is (split_dataset=False).
        split_dataset: bool, optional
            If data is a xarray.Dataset split it into several xarray.DataArrays (default).
        """
        data_dict = _check_data(data, name, split_dataset)
        for name in data_dict:
            if name in self._maps:
                self.logger.warning(f"Replacing result: {name}")
            self._maps[name] = data_dict[name]

    def read_maps(self, fn: str = "maps/*.nc", **kwargs) -> None:
        """Read model map at <root>/<fn> and add to maps component

        key-word arguments are passed to :py:func:`xarray.open_dataset`

        Parameters
        ----------
        fn : str, optional
            filename relative to model root, may wildcards, by default "maps/*.nc"
        """
        ncs = self._read_nc(fn, **kwargs)
        for name, ds in ncs.items():
            self.set_maps(ds, name=name)

    def write_maps(self, fn="maps/{name}.nc", **kwargs) -> None:
        """Write maps to netcdf file at <root>/<fn>

        key-word arguments are passed to :py:meth:`xarray.Dataset.to_netcdf`

        Parameters
        ----------
        fn : str, optional
            filename relative to model root and should contain a {name} placeholder,
            by default 'maps/{name}.nc'
        """
        self._write_nc(self._maps, fn, **kwargs)


# class for testing purposes
class MapsModel(MapsMixin, Model):
    def __init__(
        self,
        root: str = None,
        mode: str = "w",
        config_fn: str = None,
        data_libs: List[str] = None,
        logger=logger,
    ):
        # Initialize with the Model class
        super().__init__(
            root=root,
            mode=mode,
            config_fn=config_fn,
            data_libs=data_libs,
            logger=logger,
        )

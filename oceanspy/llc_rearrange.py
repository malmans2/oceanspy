import reprlib

import dask
import numpy as _np
import xarray as _xr


class LLCtransformation:
    """A class containing the transformation of LLCgrids"""

    def __init__(
        self,
        ds,
        varlist,
        transformation,
        centered="Atlantic",
        faces="all",
        drop=False,
    ):
        self._ds = ds  # xarray.DataSet
        self._varlist = varlist  # variables names to be transformed
        self._transformation = transformation  # str - type of transf
        self._centered = centered  # str - where to be centered
        self._faces = faces  # faces involved in transformation

    @classmethod
    def arctic_centered(
        self,
        ds,
        varlist,
        centered="Arctic",
        faces="all",
        drop=False,
    ):
        """Transforms the dataset by removing faces as a dimension, into a
        new dataset centered at the arctic, while preserving the grid.
        """
        Nx = len(ds["X"])
        Ny = len(ds["Y"])

        if isinstance(faces, str):
            faces = _np.array([2, 5, 6, 7, 10])
        if isinstance(faces, list) or isinstance(faces, _np.ndarray):
            face = [fac for fac in faces if fac not in [2, 5, 6, 7, 10]]
            if len(face) > 0:
                print(
                    "Range of latitudes is beyond the scope of"
                    "this rearrangement of faces. Will retain read-only"
                    "range of values that retain faces closest to"
                    "Arctic cap"
                )
            faces = _np.array([2, 5, 6, 7, 10])

        if isinstance(varlist, str):
            if varlist == "all":
                varlist = ds.data_vars
            else:
                varlist = [varlist]

        tNx = _np.arange(0, 3 * Nx + 1, Nx)
        tNy = _np.arange(0, 3 * Ny + 1, Ny)

        chunksX, chunksY = make_chunks(tNx, tNy)
        # Set ordered position wrt array layout, in accordance to location
        # of faces
        if centered == "Atlantic":
            ix = [1, 2, 1, 1, 0]
            jy = [0, 1, 1, 2, 1]
            nrot = _np.array([2])
            Arot = _np.array([5, 6, 7])
            Brot = _np.array([10])
            Crot = _np.array([0])
        elif centered == "Pacific":
            ix = [1, 0, 1, 1, 2]
            jy = [2, 1, 1, 0, 1]
            nrot = _np.array([10])
            Arot = _np.array([])
            Brot = _np.array([2])
            Crot = _np.array([5, 6, 7])
        elif centered == "Arctic":
            ix = [0, 1, 1, 2, 1]
            jy = [1, 0, 1, 1, 2]
            nrot = _np.array([6, 5, 7])
            Arot = _np.array([10])
            Brot = _np.array([])
            Crot = _np.array([2])
        else:
            raise ValueError("Centering not supported")

        psX = []
        psY = []
        for i in range(len(ix)):
            psX.append(chunksX[ix[i]])
            psY.append(chunksY[jy[i]])

        ds = mates(ds).reset_coords()

        dsnew = make_array(ds, 3 * Nx, 3 * Ny)
        metrics = ["dxC", "dyC", "dxG", "dyG"]

        dsnew = init_vars(ds, dsnew, varlist)

        for varName in varlist:
            vName = varName
            DIM = [dim for dim in ds[varName].dims if dim != "face"][::-1]
            dims = Dims(DIM)
            if len(ds[varName].dims) == 1:
                dsnew[varName] = (dims._vars[::-1], ds[varName].data)
                dsnew[varName].attrs = ds[varName].attrs
            else:
                for k in range(len(faces)):
                    fac = 1
                    xslice = slice(psX[k][0], psX[k][1])
                    yslice = slice(psY[k][0], psY[k][1])
                    arg = {dims.X: xslice, dims.Y: yslice}
                    data = ds[varName].isel(face=faces[k])
                    if faces[k] in nrot:
                        dsnew[varName].isel(**arg)[:] = data.values
                    else:
                        dtr = list(dims)[::-1]
                        dtr[-1], dtr[-2] = dtr[-2], dtr[-1]
                        if faces[k] in Crot:
                            sort_arg = {"variables": dims.X, "ascending": False}
                            if len(dims.X) + len(dims.Y) == 4:
                                if "mates" in list(ds[varName].attrs):
                                    vName = ds[varName].attrs["mates"]
                                    data = ds[vName].isel(face=faces[k])
                                    if len(dims.Y) == 3:
                                        if vName not in metrics:
                                            fac = -1
                                _DIMS = [dim for dim in ds[vName].dims if dim != "face"]
                                _dims = Dims(_DIMS[::-1])
                                sort_arg = {"variables": _dims.X, "ascending": False}
                        elif faces[k] in Arot:
                            sort_arg = {"variables": dims.Y, "ascending": False}
                            if len(dims.X) + len(dims.Y) == 4:
                                if "mates" in list(ds[varName].attrs):
                                    vName = ds[varName].attrs["mates"]
                                    data = ds[vName].isel(face=faces[k])
                                    if len(dims.X) == 3:
                                        if vName not in metrics:
                                            fac = -1
                                _DIMS = [dim for dim in ds[vName].dims if dim != "face"]
                                _dims = Dims(_DIMS[::-1])
                                sort_arg = {"variables": _dims.Y, "ascending": False}
                        elif faces[k] in Brot:
                            sort_arg = {
                                "variables": [dims.X, dims.Y],
                                "ascending": False,
                            }
                            if len(dims.X) + len(dims.Y) == 4:
                                if vName not in metrics:
                                    fac = -1
                        data = fac * data.sortby(**sort_arg)
                        if faces[k] in Brot:
                            dsnew[varName].isel(**arg)[:] = data.values
                        else:
                            dsnew[varName].isel(**arg).transpose(*dtr)[:] = data.values
        if drop is True:
            dsnew = drop_size(dsnew)
        return dsnew


    @classmethod
    def arctic_crown(
        self,
        ds,
        varlist,
        centered,
        faces="all",
        drop=False,
    ):
        """Transforms the dataset in which `face` appears as a dimension into
        one without faces, with grids and variables sharing a common grid
        orientation.
        """
        Nx = len(ds["X"])
        Ny = len(ds["Y"])

        if centered not in ["Atlantic", "Pacific"]:
            raise ValueError(
                "Centering option not recognized. Options are" "Atlantic or Pacific"
            )

        if isinstance(faces, str):
            faces = _np.arange(13)

        metrics = ["dxC", "dyC", "dxG", "dyG", 'hFacW', 'hFacS'] # metric variables defined at vector points

        co_list = [var for var in ds.coords if var not in ds.dims]

        ds = mates(ds.reset_coords())

        nrot_faces, Nx_nrot, Ny_nrot, rot_faces, Nx_rot, Ny_rot = face_connect(
            ds, faces
        )

        if isinstance(varlist, list):
            varName = varlist[0]
        elif isinstance(varlist, str):
            if varlist == "all":
                varlist = ds.data_vars
                varName = "XG"
            else:
                varName = varlist
                varlist = [varlist]
        elif len(varlist) > 0:
            varlist = list(varlist)
            varName = "XG"
        elif len(varlist) == 0:
            raise ValueError("Empty list of variables")


#   ========================== Begin transformation =================


        arc_faces, Nx_ac_nrot, Ny_ac_nrot, Nx_ac_rot, Ny_ac_rot, ARCT = arct_connect(
            ds, varName, faces
        )

        acnrot_faces = [k for k in arc_faces if k in _np.array([2, 5])]
        acrot_faces = [k for k in arc_faces if k in _np.array([7, 10])]

        tNy_nrot, tNx_nrot = chunk_sizes(nrot_faces, [Nx], [Ny])
        tNy_rot, tNx_rot = chunk_sizes(rot_faces, [Nx], [Ny], rotated=True)

        delNX = 0
        delNY = 0
        if len(ARCT) > 0:
            delNX = int(Nx / 2)
            delNY = int(Ny / 2)
        tNy_nrot = tNy_nrot + delNY
        tNy_rot = tNy_rot + delNX

        Nx_nrot = _np.arange(0, tNx_nrot + 1, Nx)
        Ny_nrot = _np.arange(0, tNy_nrot + 1, Ny)
        Ny_rot = _np.arange(0, tNy_rot + 1, Ny)
        Nx_rot = _np.arange(0, tNx_rot + 1, Nx)

        chunksX_nrot, chunksY_nrot = make_chunks(Nx_nrot, Ny_nrot)
        chunksX_rot, chunksY_rot = make_chunks(Nx_rot, Ny_rot)

        POSY_nrot, POSX_nrot, POSYarc_nrot, POSXarc_nrot = pos_chunks(
            nrot_faces, acnrot_faces, chunksY_nrot, chunksX_nrot
        )
        POSY_rot, POSX_rot, POSYa_rot, POSXa_rot = pos_chunks(
            rot_faces, acrot_faces, chunksY_rot, chunksX_rot
        )

        X0 = 0
        Xr0 = 0
        if centered == "Atlantic":
            X0 = tNx_rot
        elif centered == "Pacific":
            Xr0 = tNx_nrot

        NR_dsnew = make_array(ds, tNx_nrot, tNy_nrot, X0)
        R_dsnew = make_array(ds, tNx_rot, tNy_rot, Xr0)


        NR_dsnew = init_vars(ds, NR_dsnew, varlist)
        R_dsnew = init_vars(ds, R_dsnew, varlist)

        for varName in varlist:
            vName = varName
            fac = 1
            DIM = [dim for dim in ds[varName].dims if dim != "face"][::-1]
            dims = Dims(DIM)
            if len(ds[varName].dims) == 1:
                R_dsnew[varName] = (dims._vars[::-1], ds[varName].data)
                NR_dsnew[varName] = (dims._vars[::-1], ds[varName].data)
                NR_dsnew[varName].attrs = ds[varName].attrs
                R_dsnew[varName].attrs = ds[varName].attrs
            else:
                if len(dims.X) + len(dims.Y) == 4:  # vector fields
                    if "mates" in list(ds[varName].attrs):
                        vName = ds[varName].attrs["mates"]
                    if len(dims.X) == 1 and varName not in metrics:
                        fac = -1
                (
                    arc_faces,
                    Nx_ac_nrot,
                    Ny_ac_nrot,
                    Nx_ac_rot,
                    Ny_ac_rot,
                    ARCT,
                ) = arct_connect(ds, varName, faces)
                for k in range(len(nrot_faces)):
                    data = ds[varName].isel(face=nrot_faces[k]).values
                    xslice = slice(POSX_nrot[k][0], POSX_nrot[k][1])
                    yslice = slice(POSY_nrot[k][0], POSY_nrot[k][1])
                    arg = {dims.X: xslice, dims.Y: yslice}
                    NR_dsnew[varName].isel(**arg)[:] = data
                for k in range(len(rot_faces)):
                    kk = len(rot_faces) - (k + 1)
                    xslice = slice(POSX_rot[k][0], POSX_rot[k][1])
                    if dims.Y == "Yp1":
                        yslice = slice(POSY_rot[kk][0] + 1, POSY_rot[kk][1] + 1)
                    else:
                        yslice = slice(POSY_rot[kk][0], POSY_rot[kk][1])
                    data = fac * ds[vName].isel(face=rot_faces[k])
                    arg = {dims.Y: yslice, dims.X: xslice}
                    ndims = Dims(list(data.dims)[::-1])
                    dtr = list(ndims)[::-1]
                    dtr[-1], dtr[-2] = dtr[-2], dtr[-1]
                    sort_arg = {"variables": ndims.X, "ascending": False}
                    data = data.sortby(**sort_arg).transpose(*dtr)
                    R_dsnew[varName].isel(**arg)[:] = data.values
                for k in range(len(acnrot_faces)):
                    data = ARCT[k]
                    xslice = slice(POSXarc_nrot[k][0], POSXarc_nrot[k][1])
                    yslice = slice(POSYarc_nrot[k][0], POSYarc_nrot[k][1])
                    arg = {dims.X: xslice, dims.Y: yslice}
                    NR_dsnew[varName].isel(**arg)[:] = data.values
                for k in range(len(acrot_faces)):
                    tk = len(acnrot_faces) + k
                    xslc = slice(POSXa_rot[k][0], POSXa_rot[k][1])
                    yslc = slice(POSYa_rot[k][0], POSYa_rot[k][1])
                    arg = {dims.Y: yslc, dims.X: xslc}
                    data = ARCT[tk]
                    if acrot_faces[k] == 7:
                        sort_arg = {"variables": ndims.X, "ascending": False}
                    elif acrot_faces[k] == 10:
                        sort_arg = {"variables": dims.Y, "ascending": False}
                    data = data.sortby(**sort_arg)
                    R_dsnew[varName].isel(**arg)[:] = data.values

        if centered == "Atlantic":
            DS = R_dsnew.combine_first(NR_dsnew)
        elif centered == "Pacific":
            DS = NR_dsnew.combine_first(R_dsnew)

        DS = DS.reset_coords()
        if drop is True:
            DS = drop_size(DS)

        return DS





## ==================================================================================================================
#                         Keep this code for now. some of it asseses whether faces connect or not
## ==================================================================================================================


def make_chunks(Nx, Ny):
    chunksX = []
    chunksY = []
    for ii in range(len(Nx) - 1):
        chunksX.append([Nx[ii], Nx[ii + 1]])
    for jj in range(len(Ny) - 1):
        chunksY.append([Ny[jj], Ny[jj + 1]])
    return chunksX, chunksY




def pos_chunks(faces, arc_faces, chunksY, chunksX):
    nrotA = [k for k in range(3)]
    nrotB = [k for k in range(3, 6)]
    nrot = nrotA + nrotB
    rotA = [k for k in range(7, 10)]
    rotB = [k for k in range(10, 13)]
    rot = rotA + rotB

    nrot_A = [k for k in faces if k in nrotA]
    nrot_B = [k for k in faces if k in nrotB]
    rot_A = [k for k in faces if k in rotA]
    rot_B = [k for k in faces if k in rotB]

    ny_nApos = len(nrot_A)
    ny_nBpos = len(nrot_B)

    ny_Apos = len(rot_A)
    ny_Bpos = len(rot_B)

    POSY = []
    POSX = []

    for k in faces:
        if k in nrot:
            if k in nrot_A:
                xk = 0
                yk = 0
                if ny_nApos == 1:
                    yk = 0
                elif ny_nApos == 2:
                    if k == nrot_A[0]:
                        yk = 0
                    else:
                        yk = 1
                elif ny_nApos == 3:
                    if k == nrotA[0]:
                        yk = 0
                    elif k == nrotA[1]:
                        yk = 1
                    elif k == nrotA[2]:
                        yk = 2
            elif k in nrot_B:
                if ny_nApos > 0:
                    xk = 1
                else:
                    xk = 0
                if ny_nBpos == 1:
                    yk = 0
                elif ny_nBpos == 2:
                    if k == nrot_B[0]:
                        yk = 0
                    else:
                        yk = 1
                elif ny_nBpos == 3:
                    if k == nrotB[0]:
                        yk = 0
                    elif k == nrotB[1]:
                        yk = 1
                    elif k == nrotB[2]:
                        yk = 2
        elif k in rot:
            if k in rot_A:
                xk = 0
                yk = 0
                if ny_Apos == 1:
                    yk = 0
                elif ny_Apos == 2:
                    if k == rot_A[0]:
                        yk = 0
                    else:
                        yk = 1
                elif ny_Apos == 3:
                    if k == rotA[0]:
                        yk = 0
                    elif k == rotA[1]:
                        yk = 1
                    elif k == rotA[2]:
                        yk = 2
            elif k in rot_B:
                if ny_Apos > 0:
                    xk = 1
                else:
                    xk = 0
                if ny_Bpos == 1:
                    yk = 0
                elif ny_Bpos == 2:
                    if k == rot_B[0]:
                        yk = 0
                    else:
                        yk = 1
                elif ny_Bpos == 3:
                    if k == rotB[0]:
                        yk = 0
                    elif k == rotB[1]:
                        yk = 1
                    elif k == rotB[2]:
                        yk = 2
        else:
            raise ValueError("face index not in LLC grid")
        POSY.append(chunksY[yk])
        POSX.append(chunksX[xk])
    # This to create a new list with positions for Arctic cap slices
    POSY_arc = []
    POSX_arc = []

    aface_nrot = [k for k in arc_faces if k in nrotA + nrotB]
    aface_rot = [k for k in arc_faces if k in rotA + rotB]

    if len(aface_rot) == 0:
        if len(aface_nrot) > 0:
            pos_r = chunksY[-1][-1]
            pos_l = chunksY[-1][0]
            if len(aface_nrot) == 1:
                POSX_arc.append(chunksX[0])
                POSY_arc.append([pos_r, int(pos_r + (pos_r - pos_l) / 2)])
            elif len(aface_nrot) == 2:
                for k in range(len(aface_nrot)):
                    POSX_arc.append(chunksX[k])
                    POSY_arc.append([pos_r, int(pos_r + (pos_r - pos_l) / 2)])
    else:
        pos_r = chunksY[-1][-1]
        pos_l = chunksY[-1][0]
        if len(aface_rot) == 1:
            POSX_arc.append(chunksX[0])
            POSY_arc.append([pos_r, int(pos_r + (pos_r - pos_l) / 2)])
        else:
            for k in range(len(aface_rot)):
                POSX_arc.append(chunksX[k])
                POSY_arc.append([pos_r, int(pos_r + (pos_r - pos_l) / 2)])
    return POSY, POSX, POSY_arc, POSX_arc


def chunk_sizes(faces, Nx, Ny, rotated=False):
    """
    Determines the total size of array that will connect all rotated or
    non-rotated faces
    """
    if rotated is False:
        A_ref = _np.array([k for k in range(3)])
        B_ref = _np.array([k for k in range(3, 6)])
    elif rotated is True:
        A_ref = _np.array([k for k in range(7, 10)])
        B_ref = _np.array([k for k in range(10, 13)])

    A_list = [k for k in faces if k in A_ref]
    B_list = [k for k in faces if k in B_ref]

    if len(A_list) == 0:
        if len(B_list) > 0:
            tNx = Nx[0]
            if len(B_list) == 1:
                tNy = Ny[0]
            elif len(B_list) == 2:
                if min(B_list) == B_ref[0] and max(B_list) == B_ref[-1]:
                    raise ValueError(
                        "These faces do not connect. Not"
                        "possible to create a single dataset"
                        "that minimizes nans."
                    )
                else:
                    tNy = len(B_list) * Ny[0]
            else:
                tNy = len(B_list) * Ny[0]
        else:
            tNx = 0
            tNy = 0
            print(
                "No data within group of facets (same ordering)" " survives the cutout."
            )
    else:
        if len(B_list) == 0:
            tNx = Nx[0]
            if len(A_list) == 1:
                tNy = Ny[0]
            elif len(A_list) == 2:
                if min(A_list) == A_ref[0] and max(A_list) == A_ref[-1]:
                    raise ValueError(
                        "These faces do not connect. Not"
                        "possible to create a single datase"
                        "that minimizes nans"
                    )
                    tNy = 0
                else:
                    tNy = len(A_list) * Ny[0]
            else:
                tNy = len(A_list) * Ny[0]
        elif len(B_list) > 0:
            tNx = 2 * Nx[0]
            if len(B_list) == len(A_list):
                if len(A_list) == 1:
                    iA = [
                        _np.where(faces[nk] == A_ref)[0][0]
                        for nk in range(len(faces))
                        if faces[nk] in A_ref
                    ]
                    iB = [
                        _np.where(faces[nk] == B_ref)[0][0]
                        for nk in range(len(faces))
                        if faces[nk] in B_ref
                    ]
                    if iA == iB:
                        tNy = Ny[0]
                    else:
                        tNy = 0
                        raise ValueError("faces do not connect within facet")
                elif len(A_list) == 2:
                    if min(A_list) == A_ref[0] and max(A_list) == A_ref[-1]:
                        raise ValueError("faces do not connect within facet")
                        tNy = 0
                    else:
                        iA = [
                            _np.where(faces[nk] == A_ref)[0][0]
                            for nk in range(len(faces))
                            if faces[nk] in A_ref
                        ]
                        iB = [
                            _np.where(faces[nk] == B_ref)[0][0]
                            for nk in range(len(faces))
                            if faces[nk] in B_ref
                        ]
                        if iA == iB:
                            tNy = len(A_list) * Ny[0]
                        else:
                            raise ValueError(
                                "Not all faces connect equally,"
                                "ragged arrays not supported"
                            )
                            tNy = 0
                else:
                    tNy = len(A_list) * Ny[0]
            else:
                tNy = 0
                raise ValueError(
                    "Number of faces in facet A is not equal to"
                    "the number of faces in facet B. Ragged"
                    "arrays are not supported"
                )
    return tNy, tNx


def face_connect(ds, all_faces):
    """
    Determines the size of the final array consisting of connected faces. Does
    not consider the Arctic, since the Arctic cap is treated separatedly.
    """
    arc_cap = 6
    Xdim = "X"
    Ydim = "Y"

    Nx_nrot = []
    Ny_nrot = []
    Nx_rot = []
    Ny_rot = []

    transpose = _np.arange(7, 13)
    nrot_faces = []
    rot_faces = []

    for k in [ii for ii in all_faces if ii not in [arc_cap]]:
        if k in transpose:
            x0, xf = 0, int(len(ds[Xdim]))
            y0, yf = 0, int(len(ds[Ydim]))
            Nx_rot.append(len(ds[Xdim][x0:xf]))
            Ny_rot.append(len(ds[Ydim][y0:yf]))
            rot_faces.append(k)
        else:
            x0, xf = 0, int(len(ds[Xdim]))
            y0, yf = 0, int(len(ds[Ydim]))
            Nx_nrot.append(len(ds[Xdim][x0:xf]))
            Ny_nrot.append(len(ds[Ydim][y0:yf]))
            nrot_faces.append(k)
    return nrot_faces, Nx_nrot, Ny_nrot, rot_faces, Nx_rot, Ny_rot


## ==================================================================================================================
## ==================================================================================================================


def arct_connect(ds, varName, all_faces='all'):

    arc_cap = 6
    Nx_ac_nrot = []
    Ny_ac_nrot = []
    Nx_ac_rot = []
    Ny_ac_rot = []
    ARCT = []
    arc_faces = []
    
    if all_faces == 'all':
        all_faces = [k for k in range(13)]


    if arc_cap in all_faces:
        for k in all_faces:
            if k == 2:
                fac = 1
                arc_faces.append(k)
                _varName = varName
                DIMS = [dim for dim in ds[_varName].dims if dim != "face"]
                dims = Dims(DIMS[::-1])
                dtr = list(dims)[::-1]
                dtr[-1], dtr[-2] = dtr[-2], dtr[-1]
                mask2 = _xr.ones_like(ds[_varName].isel(face=arc_cap))
                mask2 = mask2.where(
                    _np.logical_and(
                        ds[dims.X] < ds[dims.Y],
                        ds[dims.X] < len(ds[dims.Y]) - ds[dims.Y],
                    )
                )
                x0, xf = 0, int(len(ds[dims.Y]) / 2)  # TODO: CHECK here!
                y0, yf = 0, int(len(ds[dims.X]))
                xslice = slice(x0, xf)
                yslice = slice(y0, yf)
                Nx_ac_nrot.append(0)
                Ny_ac_nrot.append(len(ds[dims.Y][y0:yf]))
                da_arg = {"face": arc_cap, dims.X: xslice, dims.Y: yslice}
                mask_arg = {dims.X: xslice, dims.Y: yslice}
                if len(dims.X) + len(dims.Y) == 4:
                    if len(dims.Y) == 3 and _varName not in metrics:
                        fac = -1
                arct = fac * ds[_varName].isel(**da_arg)
                Mask = mask2.isel(**mask_arg)
                arct = (arct * Mask)
                ARCT.append(arct)

            elif k == 5:
                fac = 1
                arc_faces.append(k)
                _varName = varName
                DIMS = [dim for dim in ds[_varName].dims if dim != "face"]
                dims = Dims(DIMS[::-1])
                mask5 = _xr.ones_like(ds[_varName].isel(face=arc_cap))
                mask5 = mask5.where(
                    _np.logical_and(
                        ds[dims.X] > ds[dims.Y],
                        ds[dims.X] < len(ds[dims.Y]) - ds[dims.Y],
                    )
                )
                x0, xf = 0, int(len(ds[dims.X]))
                y0, yf = 0, int(len(ds[dims.Y]) / 2)
                xslice = slice(x0, xf)
                yslice = slice(y0, yf)
                Nx_ac_nrot.append(0)
                Ny_ac_nrot.append(len(ds[dims.X][y0:yf]))
                if len(dims.X) + len(dims.Y) == 4:
                    if len(dims.Y) == 1 and _varName not in metrics:
                        fac = -1
                da_arg = {"face": arc_cap, dims.X: xslice, dims.Y: yslice}
                mask_arg = {dims.X: xslice, dims.Y: yslice}
                arct = ds[_varName].isel(**da_arg)
                Mask = mask5.isel(**mask_arg)
                arct = arct * Mask
                ARCT.append(arct)

            elif k == 7:
                fac = 1
                arc_faces.append(k)
                _varName = varName
                DIMS = [dim for dim in ds[_varName].dims if dim != "face"]
                dims = Dims(DIMS[::-1])
                dtr = list(dims)[::-1]
                dtr[-1], dtr[-2] = dtr[-2], dtr[-1]
                mask7 = _xr.ones_like(ds[_varName].isel(face=arc_cap))
                mask7 = mask7.where(
                    _np.logical_and(
                        ds[dims.X] > ds[dims.Y],
                        ds[dims.X] > len(ds[dims.Y]) - ds[dims.Y],
                    )
                )
                x0, xf = int(len(ds[dims.Y]) / 2), int(len(ds[dims.Y]))
                y0, yf = 0, int(len(ds[dims.X]))
                xslice = slice(x0, xf)
                yslice = slice(y0, yf)
                Nx_ac_rot.append(len(ds[dims.Y][x0:xf]))
                Ny_ac_rot.append(0)
                da_arg = {"face": arc_cap, dims.X: xslice, dims.Y: yslice}
                mask_arg = {dims.X: xslice, dims.Y: yslice}
                arct = fac * ds[_varName].isel(**da_arg)
                Mask = mask7.isel(**mask_arg)
                arct = (arct * Mask).transpose(*dtr)
                ARCT.append(arct)

            elif k == 10:
                fac = 1
                _varName = varName
                DIMS = [dim for dim in ds[_varName].dims if dim != "face"]
                dims = Dims(DIMS[::-1])
#                 dtr = list(dims)[::-1]
#                 dtr[-1], dtr[-2] = dtr[-2], dtr[-1]
                arc_faces.append(k)
                mask10 = _xr.ones_like(ds[_varName].isel(face=arc_cap))
                mask10 = mask10.where(
                    _np.logical_and(
                        ds[dims.X] < ds[dims.Y],
                        ds[dims.X] > len(ds[dims.Y]) - ds[dims.Y],
                    )
                )
                x0, xf = 0, int(len(ds[dims.X]))
                y0, yf = int(len(ds[dims.Y]) / 2), int(len(ds[dims.Y]))
                xslice = slice(x0, xf)
                yslice = slice(y0, yf)
                Nx_ac_rot.append(0)
                Ny_ac_rot.append(len(ds[dims.Y][y0:yf]))
                da_arg = {"face": arc_cap, dims.X: xslice, dims.Y: yslice}
                mask_arg = {dims.X: xslice, dims.Y: yslice}
                arct = fac * ds[_varName].isel(**da_arg)
                Mask = mask10.isel(**mask_arg)
                arct = (arct * Mask) # 
                ARCT.append(arct)

    return arc_faces, ARCT



def mates(ds):
    vars_mates = [
        "ADVx_SLT",
        "ADVy_SLT",
        "ADVx_TH",
        "ADVy_TH",
        "DFxE_TH",
        "DFyE_TH",
        "DFxE_SLT",
        "DFyE_SLT",
        "maskW",
        "maskS",
        "TAUX",
        "TAUY",
        "U",
        "V",
        "UVELMASS",
        "VVELMASS",
        "dxC",
        "dyC",
        "dxG",
        "dyG",
        "hFacW",
        "hFacS",
        "rAw",
        "rAs",
    ]
    for k in range(int(len(vars_mates) / 2)):
        nk = 2 * k
        if vars_mates[nk] in ds.variables:
            ds[vars_mates[nk]].attrs["mates"] = vars_mates[nk + 1]
            ds[vars_mates[nk + 1]].attrs["mates"] = vars_mates[nk]
    return ds


def rotate_vars(_ds):
    """using the attribures `mates`, when this function is called it swaps the variables names. This issue is only applicable to llc grid in which the 
    grid topology makes it so that u on a rotated face transforms to `+- v` on a lat lon grid. 
    """
    _vars = [var for var in _ds.variables]
    rot_names = {}
    for v in _vars:
        if "mate" in _ds[v].attrs:
            rot_names = {**rot_names, **{v: _ds[v].mate}}
        

    _ds = _ds.rename(rot_names)
    return _ds






class Dims:
    axes = "XYZT"  # shortcut axis names

    def __init__(self, vars):
        self._vars = tuple(vars)

    def __iter__(self):
        return iter(self._vars)

    def __repr__(self):
        vars = reprlib.repr(self._vars)
        return "{}".format(vars)

    def __str__(self):
        return str(tuple(self))

    def __eq__(self, other):
        return tuple(self) == tuple(other)

    def __len__(self):
        return len(self._vars)

    def __getattr__(self, name):
        cls = type(self)
        if len(name) == 1:
            pos = cls.axes.find(name)
            if 0 <= pos < len(self._vars):
                return self._vars[pos]
        msg = "{.__name__!r} object has not attribute {!r}"
        raise AttributeError(msg.format(cls, name))

    def __setattr__(self, name, value):
        cls = type(self)
        if len(name) == 1:
            if name in cls.axes:
                error = "read-only attribute {attr_name!r}"
            elif name.islower():
                error = "can`t set attributes `a` to `z` in {cls_name!r}"
            else:
                error = ""
            if error:
                msg = error.format(cls_name=cls.__name__, attr_name=name)
                raise AttributeError(msg)
        super().__setattr__(name, value)

from .util import *
from .srs import *
from .geom import *
from .raster import *
from .vector import *

IndexSet = namedtuple("IndexSet", "xStart yStart xWin yWin xEnd yEnd")
TileIndexBox = namedtuple("tileBox", "xi_start xi_stop yi_start yi_stop")


class Extent(object):
    """Geographic extent

    The Extent object represents geographic extents of an area and exposes useful
    methods which depend on those extents. This includes:
        - Easily representing the boundaries as (xMin, xMax, yMin, yMax) or
          (xMin, yMin, xMax, yMax)
        - Casting to another projection system
        - Padding and shifting the boundaries
        - "Fitting" the boundaries onto a given resolution
        - Clipping a given raster file

    Initialization:
    ---------------
    * Extent(xMin, yMin, xMax, yMax [, srs])
    * Extent.from_xyXY( (xMin, yMin, xMax, yMax) [, srs])
    * Extent.from_xXyY( (xMin, xMax, yMin, yMax) [, srs])
    * Extent.fromGeom( geom [, srs] )
    * Extent.fromVector( vector-file-path )
    * Extent.fromRaster( raster-file-path )
    * Extent.load( args )
    """
    _whatami = "Extent"

    def __init__(s, *args, srs='latlon'):
        """Create extent from explicitly defined boundaries

        Usage:
        ------
        Extent(xMin, yMin, xMax, yMax [, srs=<srs>])
        Extent( (xMin, yMin, xMax, yMax) [, srs=<srs>])

        Where:
            xMin - The minimal x value in the respective SRS
            yMin - The minimal y value in the respective SRS
            xMax - The maximal x value in the respective SRS
            yMax - The maximal y value in the respective SRS
            srs - The Spatial Reference system to use

        """
        # Unpack args
        if len(args) == 1:
            xMin, yMin, xMax, yMax = args[0]
        elif len(args) == 4:
            xMin, yMin, xMax, yMax = args
        else:
            raise GeoKitExtentError(
                "Incorrect number of positional arguments givin in init (accepts 1 or 4). Is an srs given as 'srs=...'?")

        # Ensure good inputs
        xMin, xMax = min(xMin, xMax), max(xMin, xMax)
        yMin, yMax = min(yMin, yMax), max(yMin, yMax)

        s.xMin = xMin
        s.xMax = xMax
        s.yMin = yMin
        s.yMax = yMax
        s.srs = loadSRS(srs)

        s._box = box(s.xMin, s.yMin, s.xMax, s.yMax, srs=s.srs)

    @staticmethod
    def from_xXyY(bounds, srs='latlon'):
        """Create an Extent from explicitly defined boundaries

        Parameters:
        -----------
        bounds : tuple
            The (xMin, xMax, yMin, yMax) values for the extent

        srs : Anything acceptable to geokit.srs.loadSRS(); optional
            The srs of the input coordinates
              * If not given, lat/lon coordinates are assumed

        Returns:
        --------
        Extent

        """
        return Extent(bounds[0], bounds[2], bounds[1], bounds[3], srs=srs)

    @staticmethod
    def fromGeom(geom):
        """Create extent around a given geometry

        Parameters:
        -----------
        geom : ogr.Geometry
            The geometry from which to extract the extent

        Returns:
        --------
        Extent

        """
        # Read Envelope
        xMin, xMax, yMin, yMax = geom.GetEnvelope()

        # Done!
        return Extent(xMin, yMin, xMax, yMax, srs=geom.GetSpatialReference())

    @staticmethod
    def fromTile(xi, yi, zoom):
        """Generates an Extent corresponding to tiles used for "slippy maps"

        Parameters:
        -----------
        xi : int
            The tile's X-index
            - Range depends on zoom value

        yi : int
            The tile's Y-index
            - Range depends on zoom value

        zoom : int
            The tile's zoom index
            - Range is between 0 and 18

        Returns:
        --------
        geokit.Extent

        """
        tl = smopy.num2deg(xi-0.0, yi+1.0, zoom)[::-1]
        br = smopy.num2deg(xi+1.0, yi-0.0, zoom)[::-1]

        o = xyTransform([tl, br], fromSRS=EPSG4326,
                        toSRS=EPSG3857, outputFormat='xy')

        return Extent(o.x.min(), o.y.min(), o.x.max(), o.y.max(), srs=EPSG3857)

    @staticmethod
    def fromVector(source):
        """Create extent around the contemts of a vector source

        Parameters:
        -----------
        source : Anything acceptable by loadVector()
            The vector datasource to read from

        Returns:
        --------
        Extent

        """
        shapeDS = loadVector(source)

        shapeLayer = shapeDS.GetLayer()
        shapeSRS = shapeLayer.GetSpatialRef()

        xMin, xMax, yMin, yMax = shapeLayer.GetExtent()

        return Extent(xMin, yMin, xMax, yMax, srs=shapeSRS)

    @staticmethod
    def fromRaster(source):
        """Create extent around the contents of a raster source

        Parameters:
        -----------
        source : Anything acceptable by loadRaster()
            The vector datasource to read from

        Returns:
        --------
        Extent

        """
        dsInfo = rasterInfo(source)

        xMin, yMin, xMax, yMax = dsInfo.bounds

        return Extent(xMin, yMin, xMax, yMax, srs=dsInfo.srs)

    @staticmethod
    def fromLocationSet(locs):
        """Create extent around the contents of a LocationSet object

        Parameters:
        -----------
        locs : LocationSet

        Returns:
        --------
        Extent

        """
        lonMin, latMin, lonMax, latMax = locs.getBounds()
        return Extent(lonMin, latMin, lonMax, latMax, srs=EPSG4326)

    @staticmethod
    def load(source, **kwargs):
        """Attempts to load an Extent from a variety of inputs in the most
        appropriate manner

        One Extent initializer (.fromXXX) is called depending on the inputs

            source is LocationSet -> Extent.fromLocationSet( source )
            source is ogr.Geometry -> Extent.fromGeom( source )
            source is not a string: -> Extent(*source, **kwargs)
            source is a string:
                First try: Extent.fromVector(source)
                Then try: Extent.fromRaster(source)

        If none of the above works, an error is raised

        Returns:
        --------
        Extent

        """
        if (isinstance(source, Extent)):
            return source
        elif isinstance(source, LocationSet):
            return Extent.fromLocationSet(source)
        elif isinstance(source, ogr.Geometry):
            return Extent.fromGeom(source)
        elif isVector(source):
            return Extent.fromVector(source)
        elif isRaster(source):
            return Extent.fromRaster(source)

        try:  # Maybe the source is an iterable giving xyXY
            vals = list(source)
            if len(vals) == 4:
                return Extent(vals, **kwargs)
        except:
            pass

        raise GeoKitExtentError("Could not load the source")

    @staticmethod
    def _fromInfo(info):
        """GeoKit internal

        Creates an Extent from rasterInfo's returned value
        """
        return Extent(info.xMin, info.yMin, info.xMax, info.yMax, srs=info.srs)

    @property
    def xyXY(s):
        """Returns a tuple of the extent boundaries in order:
            xMin, yMin, xMax, yMax"""
        return (s.xMin, s.yMin, s.xMax, s.yMax)

    @property
    def xXyY(s):
        """Returns a tuple of the extent boundaries in order:
            xMin, xMax, yMin, yMax"""
        return (s.xMin, s.xMax, s.yMin, s.yMax)

    @property
    def ylim(s):
        """Returns a tuple of the y-axis extent boundaries in order:
            yMin, yMax
        """
        return (s.yMin, s.yMax)

    @property
    def xlim(s):
        """Returns a tuple of the x-axis extent boundaries in order:
            xMin, xMax
        """
        return (s.xMin, s.xMax)

    @property
    def box(s):
        """Returns a rectangular ogr.Geometry object representing the extent"""
        return s._box.Clone()

    def __eq__(s, o):
        # if (s.xyXY != o.xyXY): return False
        if (not s.srs.IsSame(o.srs)):
            return False
        if not np.isclose(s.xMin, o.xMin):
            return False
        if not np.isclose(s.xMax, o.xMax):
            return False
        if not np.isclose(s.yMin, o.yMin):
            return False
        if not np.isclose(s.yMin, o.yMin):
            return False
        return True

    def __add__(s, o):
        # if (s.xyXY != o.xyXY): return False
        if (not s.srs.IsSame(o.srs)):
            o = o.castTo(s.srs)

        newExt = Extent(np.minimum(s.xMin, o.xMin),
                        np.minimum(s.yMin, o.yMin),
                        np.maximum(s.xMax, o.xMax),
                        np.maximum(s.yMax, o.yMax),
                        srs=s.srs)
        return newExt

    def __repr__(s):
        out = ""
        out += "xMin: %f\n" % s.xMin
        out += "xMax: %f\n" % s.xMax
        out += "yMin: %f\n" % s.yMin
        out += "yMax: %f\n" % s.yMax
        out += "srs: %s\n" % s.srs.ExportToWkt()

        return out

    def __str__(s):
        return "(%.5f,%.5f,%.5f,%.5f)" % s.xyXY

    def pad(s, pad, percent=False):
        """Pad the extent in all directions

        Parameters:
        -----------
        pad : float
            The amount to pad in all directions
            * In units of the extent's srs
            * Can also accept a negative padding

        percent : bool, optional
            If True, the padding values are understood to be a percentage of the
            unpadded extent

        Returns:
        --------
        Extent

        """
        # Check for no input pads
        if pad is None:
            return s

        # try breaking apart by x and y component
        try:
            xpad, ypad = pad
        except:
            xpad = pad
            ypad = pad

        if percent:
            xpad = xpad/100*(s.xMax-s.xMin) / 2
            ypad = ypad/100*(s.yMax-s.yMin) / 2

        # Pad the extent
        return Extent(s.xMin-xpad, s.yMin-ypad, s.xMax+xpad, s.yMax+ypad, srs=s.srs)

    def shift(s, dx=0, dy=0):
        """Shift the extent in the X and/or Y dimensions

        Parameters:
        -----------
        dx : float
            The amount to shift in the x dimension
            * In units of the extent's srs

        dy : float
            The amount to shift in the y dimension
            * In units of the extent's srs

        Returns:
        --------
        Extent

        """
        return Extent(s.xMin+dx, s.yMin+dy, s.xMax+dx, s.yMax+dy, srs=s.srs)

    def fitsResolution(s, unit, tolerance=1e-6):
        """Test if calling Extent first around the given unit(s) (at least within
        an error defined by 'tolerance')

        Parameters:
        -----------
        unit : numeric or tuple
            The unit value(s) to check
            * If float, a single resolution value is assumed for both X and Y dim
            * If tuple, resolutions for both dimensions (x, y)

        tolerance : float
            The tolerance to allow when comparing float values

        Returns:
        --------
        Extent

        Examples:
        ---------
        >>> ex = Extent( 100, 100, 300, 500)
        >>> ex.fitsResolution(25) # True!
        >>> ex.fitsResolution( (25, 10) ) # True!
        >>> ex.fitsResolution(33) # False!
        >>> ex.fitsResolution( (25, 33) ) # False!

        """
        try:
            unitX, unitY = unit
        except:
            unitX, unitY = unit, unit

        xSteps = (s.xMax-s.xMin)/unitX
        xResidual = abs(xSteps-np.round(xSteps))
        if xResidual > tolerance:
            return False

        ySteps = (s.yMax-s.yMin)/unitY
        yResidual = abs(ySteps-np.round(ySteps))
        if yResidual > tolerance:
            return False

        return True

    def fit(s, unit, dtype=None):
        """Fit the extent to a given pixel resolution

        Note:
        -----
        The extent is always expanded to fit onto the given unit


        Parameters:
        -----------
        unit : numeric or tuple
            The unit value(s) to check
            * If numeric, a single value is assumed for both X and Y dim
            * If tuple, resolutions for both dimensions (x, y)

        dtype : Type or np.dtype
            The final data type of the boundary values

        Returns:
        --------
        Extent

        """
        try:
            unitX, unitY = unit
        except:
            unitX, unitY = unit, unit

        # Look for bad sizes
        if (unitX > s.xMax-s.xMin):
            raise GeoKitExtentError("Unit size is larger than extent width")
        if (unitY > s.yMax-s.yMin):
            raise GeoKitExtentError("Unit size is larger than extent width")

        # Calculate new extent
        newXMin = np.floor(s.xMin/unitX)*unitX
        newYMin = np.floor(s.yMin/unitY)*unitY
        newXMax = np.ceil(s.xMax/unitX)*unitX
        newYMax = np.ceil(s.yMax/unitY)*unitY

        # Done!
        if dtype is None or isinstance(unitX, dtype):
            return Extent(newXMin, newYMin, newXMax, newYMax, srs=s.srs)
        else:
            return Extent(dtype(newXMin), dtype(newYMin), dtype(newXMax), dtype(newYMax), srs=s.srs)

    def corners(s, asPoints=False):
        """Returns the four corners of the extent as ogr.gGometry points or as (x,y)
        coordinates in the extent's srs

        """

        if (asPoints):
            # Make corner points
            bl = point(s.xMin, s.yMin, srs=s.srs)
            br = point(s.xMax, s.yMin, srs=s.srs)
            tl = point(s.xMin, s.yMax, srs=s.srs)
            tr = point(s.xMax, s.yMax, srs=s.srs)

        else:
            # Make corner points
            bl = (s.xMin, s.yMin)
            br = (s.xMax, s.yMin)
            tl = (s.xMin, s.yMax)
            tr = (s.xMax, s.yMax)

        return (bl, br, tl, tr)

    def castTo(s, srs):
        """
        Creates a new Extent by transforming an extent from the original Extent's
        srs to a target SRS.

        Note:
        -----
        The resulting region spanned by the extent will be equal-to or (almost
        certainly) larger than the original

        Parameters:
        -----------
        srs : Anything acceptable to geokit.srs.loadSRS()
            The srs to cast the Extent object to

        Returns:
        --------
        Extent

        """
        srs = loadSRS(srs)

        # Check for same srs
        if(srs.IsSame(s.srs)):
            return s

        # Create a transformer
        srs = loadSRS(srs)
        transformer = osr.CoordinateTransformation(s.srs, srs)

        # Transform and record points
        X = []
        Y = []

        for pt in s.corners(True):
            try:
                pt.Transform(transformer)
            except Exception as e:
                print("Could not transform between the following SRS:\n\nSOURCE:\n%s\n\nTARGET:\n%s\n\n" % (
                    s.srs.ExportToWkt(), srs.ExportToWkt()))
                raise e

            X.append(pt.GetX())
            Y.append(pt.GetY())

        # return new extent
        return Extent(min(X), min(Y), max(X), max(Y), srs=srs)

    def inSourceExtent(s, source):
        """Tests if the extent box is at least partially contained in the extent-box
        of the given vector or raster source"""
        if isinstance(source, str):

            if isVector(source):
                isvec = True
            elif isRaster(source):
                isvec = False
            else:
                raise GeoKitExtentError("Could not handle source: "+source)

        elif isinstance(source, gdal.Dataset):
            if source.GetLayer() is None:
                isvec = False
            else:
                isvec = True

        elif isinstance(source, ogr.DataSource):
            isvec = True
        else:
            raise GeoKitExtentError("Source type could not be determined")

        # Check extent for inclusion
        if isvec:
            sourceExtent = Extent.fromVector(source).castTo(s.srs)
        else:
            sourceExtent = Extent.fromRaster(source).castTo(s.srs)

        # Are the source's corners in the main object's extent?
        for p in sourceExtent.corners(asPoints=True):
            if s._box.Contains(p):
                return True
        # Are the main object's corners in the sources's extent?
        for p in s.corners(asPoints=True):
            if sourceExtent._box.Contains(p):
                return True

        return False

    def filterSources(s, sources):
        """Filter a list of sources by those whose's envelope overlaps the Extent.

        Note:
        -----
        Creates a filter object which can be immediately iterated over, or else
        can be cast as a list

        Parameters:
        -----------
        sources : list or str
            The sources to filter
            * An iterable of vector/raster sources
            * An iterable of paths pointing to vector/raster sources
            * A glob string which will generate a list of source paths
                - see glob.glob for more info

        Returns:
        --------
        filter

        """
        # create list of searchable files
        if isinstance(sources, str):
            directoryList = glob(sources)
        else:
            directoryList = sources

        return filter(s.inSourceExtent, directoryList)

    def containsLoc(s, locs, srs=None):
        """Test if the extent contains a location or an iterable of locations

        Parameters:
        -----------
        locs : Anything acceptable to LocationSet()
            The locations to be checked


        srs : Anything acceptable to geokit.srs.loadSRS()
            The srs to cast the Extent object to

        Returns:
        --------
        * If a single location is checker: bool
        * If multiple locations are checked: numpy.ndarray

        """
        boxG = s.box  # initialize the box

        # Normalize locations
        locs = LocationSet(locs).asXY(s.srs)

        # Do tests
        sel = np.ones(locs.shape[0], dtype=bool)
        sel *= locs[:, 0] >= s.xMin
        sel *= locs[:, 0] <= s.xMax
        sel *= locs[:, 1] >= s.yMin
        sel *= locs[:, 1] <= s.yMax

        # Done!
        if sel.size == 1:
            return sel[0]
        else:
            return sel

    def contains(s, extent, res=None):
        """Tests if the extent contains another given extent

        Note:
        -----
        If an optional resolution ('res') is given, the containment value is also
        dependent on whether or not the given extent fits within the larger extent
        AND is situated along the given resolution

        Parameters:
        -----------
        extent : Extent
            The Extent object to test for containment

        res : numeric or tuple
            The X & Y resolution to enforce

        Returns:
        --------
        bool

        """
        # test raw bounds
        if(not extent.srs.IsSame(s.srs) or
            extent.xMin < s.xMin or extent.yMin < s.yMin or
                extent.xMax > s.xMax or extent.yMax > s.yMax):
            return False

        if(res):
            # unpack resolution
            try:
                dx, dy = res
            except:
                dx, dy = res, res

            # Test for factor of resolutions
            thresh = dx/1000
            if((extent.xMin - s.xMin) % dx > thresh or
                (extent.yMin - s.yMin) % dy > thresh or
                (s.xMax - extent.xMax) % dx > thresh or
                    (s.yMax - extent.yMax) % dy > thresh):
                return False
        return True

    def findWithin(s, extent, res=100, yAtTop=True):
        """Finds the indexes of the given extent within the main extent according
        to the given resolution.

        Note:
        -----
        * Use this to compute the index offsets and window sizes of a window
          within a raster dataset
        * The two extents MUST share the same SRS

        Parameters:
        -----------
        extent : Extent
            The extent to find within the calling extent

        res : numeric or tuple
            A resolution to check containment on

        yAtTop : bool; optional
            Instructs the offsetting to begin from yMax instead of from yMin

        Returns:
            tuple -> (xOffset, yOffset, xWindowSize, yWindowSize)

        """

        # test srs
        if not s.srs.IsSame(extent.srs):
            raise GeoKitExtentError("extents are not of the same srs")

        # try to unpack the resolution
        try:
            dx, dy = res
        except:
            dx, dy = res, res

        # Get offsets
        tmpX = (extent.xMin - s.xMin)/dx
        xOff = int(np.round(tmpX))

        if(yAtTop):
            tmpY = (s.yMax - extent.yMax)/dy
        else:
            tmpY = (extent.yMin - s.yMin)/dy
        yOff = int(np.round(tmpY))

        if not (np.isclose(xOff, tmpX) and np.isclose(yOff, tmpY)):
            raise GeoKitExtentError(
                "The extents are not relatable on the given resolution")

        # Get window sizes
        tmpX = (extent.xMax - extent.xMin)/dx
        xWin = int(np.round(tmpX))

        tmpY = (extent.yMax - extent.yMin)/dy
        yWin = int(np.round(tmpY))

        if not (np.isclose(xWin, tmpX) and np.isclose(yWin, tmpY)):
            raise GeoKitExtentError(
                "The extents are not relatable on the given resolution")

        # Done!
        return IndexSet(xOff, yOff, xWin, yWin, xOff+xWin, yOff+yWin)

    def computePixelSize(s, *args):
        """Finds the pixel resolution which fits to the Extent for a given pixel count.

        Note:
        -----
        * If only one integer argument is given, it is assumed to fit to both the X and Y dimensions
        * If two integer arguments are given, it is assumed to be in the order X then Y


        Returns:
            tuple -> (pixelWidth, pixelHeight)

        """

        if len(args) == 1:
            pixels_x = args[0]
            pixels_y = args[0]
        else:
            pixels_x, pixels_y = args

        pixelWidth = (s.xMax-s.xMin) / pixels_x
        pixelHeight = (s.yMax-s.yMin) / pixels_y

        return pixelWidth, pixelHeight

    #############################################################################
    # CONVENIENCE FUNCTIONS

    def createRaster(s, pixelWidth, pixelHeight, **kwargs):
        """Convenience function for geokit.raster.createRaster which sets 'bounds'
        and 'srs' inputs

        * The input resolution MUST fit within the extent

        Parameters:
        -----------
        pixelWidth : numeric
            The pixel width of the raster in units of the input srs
            * The keyword 'dx' can be used as well and will override anything given
            assigned to 'pixelWidth'

        pixelHeight : numeric
            The pixel height of the raster in units of the input srs
            * The keyword 'dy' can be used as well and will override anything given
              assigned to 'pixelHeight'

        **kwargs:
            All other keyword arguments are passed on to geokit.raster.createRaster()

        Returns:
        --------
        * If 'output' is None: gdal.Dataset
        * If 'output' is a string: None

        """
        if not s.fitsResolution((pixelWidth, pixelHeight)):
            raise GeoKitExtentError(
                "The given resolution does not fit to the Extent boundaries")
        return createRaster(bounds=s.xyXY, pixelWidth=pixelWidth, pixelHeight=pixelHeight, srs=s.srs, **kwargs)

    def extractMatrix(s, source, strict=True, **kwargs):
        """Convenience wrapper around geokit.raster.extractMatrix(). Extracts the
        extent directly from the given raster source as a matrix around the Extent

        Note:
        -----
        The called extent must fit somewhere within the raster's grid

        Parameters:
        -----------
        source: gdal.Dataset or str
            The raster source to be read

        strict: bool; optional
            Whether or not to allow a returned value which does not fit to the
            given extent
            !! If this is set to False, it is STRONGLY recommended to also set the
               argument 'returnBounds' as True so that the new computed boundary
               can be known

        **kwargs
            All keyword arguments are passed to geokit.raster.extractMatrix

        Returns:
        --------
        numpy.ndarray or tuple
            * See geokit.raster.extractMatrix

        """
        if strict:
            ri = rasterInfo(source)
            if not s.srs.IsSame(ri.srs):
                raise GeoKitExtentError(
                    "Extent and source do not share an srs")
            if not Extent._fromInfo(ri).contains(s, (ri.dx, ri.dy)):
                raise GeoKitExtentError(
                    "Extent does not fit the raster's resolution")

        return extractMatrix(source, bounds=s.xyXY, boundsSRS=s.srs, **kwargs)

    def warp(s, source, pixelWidth, pixelHeight, strict=True, **kwargs):
        """Convenience function for geokit.raster.warp() which automatically sets the
        'srs' and 'bounds' input.

        Note:
        -----
        When creating an 'in memory' raster vs one which is saved to disk, a slightly
        different algorithm is used which can sometimes add an extra row of pixels. Be
        aware of this if you intend to compare value-matricies directly from rasters
        generated with this function.

        Parameters:
        -----------
        source : str
            The path to the vector file to load

        pixelHeight : numeric; optional
            The pixel height (y-resolution) of the output raster
            * Only required if this value should be changed

        pixelWidth : numeric; optional
            The pixel width (x-resolution) of the output raster
            * Only required if this value should be changed

        strict : bool
            If True, raise an error if trying to warp to a pixelWidth and
            pixelHeight which does not fit into the Extent

        **kwargs:
            All other keyword arguments are passed on to geokit.raster.warp()

        Returns:
        --------
        * If 'output' is None: gdal.Dataset
        * If 'output' is a string: None

        """
        if strict and not s.fitsResolution((pixelWidth, pixelHeight)):
            raise GeoKitExtentError(
                "The given resolution does not fit to the Extent boundaries")
        return warp(source=source, pixelWidth=pixelWidth, pixelHeight=pixelHeight,
                    srs=s.srs, bounds=s.xyXY, **kwargs)

    def rasterize(s, source, pixelWidth, pixelHeight, strict=True, **kwargs):
        """Convenience function for geokit.vector.rasterize() which automatically
        sets the 'srs' and 'bounds' input.

        Note:
        -----
        When creating an 'in memory' raster vs one which is saved to disk, a slightly
        different algorithm is used which can sometimes add an extra row of pixels. Be
        aware of this if you intend to compare value-matricies directly from rasters
        generated with this function.

        Parameters:
        -----------
        source : str
            The path to the vector file to load

        pixelHeight : numeric; optional
            The pixel height (y-resolution) of the output raster
            * Only required if this value should be changed

        pixelWidth : numeric; optional
            The pixel width (x-resolution) of the output raster
            * Only required if this value should be changed

        strict : bool
            If True, raise an error if trying to rasterize to a pixelWidth and
            pixelHeight which does not fit into the Extent

        **kwargs:
            All other keyword arguments are passed on to geokit.raster.warp()

        Returns:
        --------
        * If 'output' is None: gdal.Dataset
        * If 'output' is a string: None

        """
        if strict and not s.fitsResolution((pixelWidth, pixelHeight)):
            raise GeoKitExtentError(
                "The given resolution does not fit to the Extent boundaries")
        return rasterize(source=source, pixelWidth=pixelWidth, pixelHeight=pixelHeight,
                         srs=s.srs, bounds=s.xyXY, **kwargs)

    def extractFeatures(s, source, **kwargs):
        """Convenience wrapper for geokit.vector.extractFeatures() by setting the
        'geom' input to the extent's box

        Parameters:
        -----------
        source : str
            The path to the vector file to load

        **kwargs:
            All other keyword arguments are passed on to vector.extractFeatures()

        Returns:
        --------
        * If asPandas is True: pandas.DataFrame or pandas.Series
        * If asPandas is False: generator

        """
        return extractFeatures(source=source, geom=s._box, **kwargs)

    def mutateVector(s, source, matchContext=False, **kwargs):
        """Convenience function for geokit.vector.mutateVector which automatically
        sets 'srs' and 'geom' input to the Extent's srs and geometry

        Note:
        -----
        If this is called without any arguments except for a source, it serves
        to clip the vector source around the extent

        Parameters:
        -----------
        source : Anything acceptable to geokit.vector.loadVector()
            The source to clip

        matchContext : bool; optional
            * If True, transforms all geometries to the Extent's srs before
              mutating
            * If False, the Extent is cast to the source's srs, and all filtering
              and mutating happens in that context

        **kwargs:
            All other keyword arguments are passed to geokit.vector.mutateVector


        Returns:
        --------
        * If 'output' is None: gdal.Dataset
        * If 'output' is a string: None

        """
        # Get the working srs
        if not matchContext:
            vinfo = vectorInfo(source)
            ext = s.castTo(vinfo.srs)
        else:
            ext = s

        # mutate the source
        return mutateVector(source, srs=ext.srs, geom=ext._box, **kwargs)

    def mutateRaster(s, source, pixelWidth=None, pixelHeight=None, matchContext=False, warpArgs=None, processor=None, resampleAlg='bilinear', **mutateArgs):
        """Convenience function for geokit.raster.mutateRaster which automatically
        warps the raster to the extent's area and srs before mutating

        Note:
        -----
        If this is called without any arguments except for a source, it serves
        to clip the raster source around the Extent, therefore performing
        the same function as Extent.warp(...) on an Extent which has been cast
        to the source's srs

        Parameters:
        -----------
        source : Anything acceptable to geokit.raster.loadRaster()
            The source to mutate

        pixelHeight : numeric
            The pixel height (y-resolution) of the output raster

        pixelWidth : numeric
            The pixel width (x-resolution) of the output raster

        matchContext : bool; optional
            * If True, Warp to the Extent's boundaries and srs before mutating
                - pixelHeight and pixelWidth MUST be provided in this case
            * If False, only warp to the Extent's boundaries, but keep its
              srs and resolution intact

        warpArgs : dict; optional
            Arguments to apply to the warping step
            * See geokit.raster.warp()

        processor - function; optional
            The function performing the mutation of the raster's data
            * The function will take single argument (a 2D numpy.ndarray)
            * The function must return a numpy.ndarray of the same size as the input
            * The return type must also be containable within a Float32 (int and
              boolean is okay)
            * See example in geokit.raster.mutateRaster for more info

        resampleAlg : str; optional
            The resampling algorithm to use while warping
            * Knowing which option to use can have significant impacts!
            * Options are: 'near', 'bilinear', 'cubic', 'average'

        **kwargs:
            All other keyword arguments are passed to geokit.vector.mutateVector

        Returns:
        --------
        * If 'output' is None: gdal.Dataset
        * If 'output' is a string: None

        """
        if warpArgs is None:
            warpArgs = {}

        if processor is None:  # We wont do a mutation without a processor, since everything else
            # can be handled by Warp. Therefore we pass on any 'output' that is
            # given to the warping stage, unless one was already given
            warpArgs["output"] = warpArgs.get(
                "output", mutateArgs.get("output", None))

        # Warp the source
        # TODO: Should the warping be updated to use Extent.clipRaster???
        if matchContext:
            if pixelWidth is None or pixelHeight is None:
                raise GeoKitExtentError(
                    "pixelWidth and pixelHeight must be provided when matchContext is True")

            source = s.warp(source, resampleAlg=resampleAlg, pixelWidth=pixelWidth,
                            pixelHeight=pixelWidth, strict=True, **warpArgs)
        else:
            if not "srs" in mutateArgs:
                source = loadRaster(source)
                srs = source.GetProjectionRef()

            ext = s.castTo(srs)
            source = ext.warp(source, resampleAlg=resampleAlg, pixelWidth=pixelWidth,
                              pixelHeight=pixelWidth, strict=False, **warpArgs)

        # mutate the source
        if not processor is None:
            return mutateRaster(source, processor=processor, **mutateArgs)
        else:
            return source

    def clipRaster(s, source, output=None, **kwargs):
        """Clip a given raster source to the caling Extent

        Parameters:
        -----------
        source : Anything acceptable to geokit.raster.loadRaster()
            The source to clip

        **kwargs:
            All other keyword arguments are passed to gdal.Translate

        Returns:
        --------
        * If 'output' is None: gdal.Dataset
        * If 'output' is a string: None

        """
        from time import time_ns
        opts = gdal.TranslateOptions(
            projWin=[s.xMin, s.yMax, s.xMax, s.yMin],
            projWinSRS=s.srs, **kwargs)

        if output is None:
            fname = "/vsimem/clip_{}.tif".format(time_ns())
        else:
            fname = output
        ds = gdal.Translate(fname, source, options=opts)

        return ds if output is None else output

    def contoursFromRaster(s, raster, contourEdges, transformGeoms=True, **kwargs):
        """Convenience wrapper for geokit.raster.contours which autmatically
        clips a raster to the invoked Extent 

        Parameters:
        -----------
        raster : The raster datasource to warp from

        contourEdges : [float,]
            The edges to search for withing the raster dataset
            * This parameter can be set as "None", in which case an additional
                argument should be given to specify how the edges should be determined
                - See the documentation of "GDALContourGenerateEx"
                - Ex. "LEVEL_INTERVAL=10", contourEdges=None

        transformGeoms : bool
            If True, geometries are transformed to the Extent's SRS, otehrwise they
            are left in their native SRS

        kwargs
            Keyword arguments to pass on to the contours function
            * See geokit.raster.contours

        Returns:
        --------
        pandas.DataFrame

        With columns:
            'geom' -> The contiguous-valued geometries
            'ID' -> The associated contour edge for each object

        """
        raster = s.clipRaster(raster)
        geoms = contours(raster, contourEdges, **kwargs)

        if transformGeoms:
            geoms.geom = transform(geoms.geom, toSRS=s.srs)

        return geoms

    def tileIndexBox(s, zoom):
        """Determine the tile indexes at a given zoom level which surround the invoked Extent

        Parameters:
        -----------
        zoom : int
            The zoom level of the expected tile source

        Returns:
        --------
        namedtuple:
            - xi_start: int - The starting x index
            - xi_stop:  int - The ending x index
            - yi_start: int - The starting y index
            - yi_stop:  int - The ending y index

        """
        ext4326 = s.castTo(EPSG4326)

        tl_tile_xi, tl_tile_yi = smopy.deg2num(
            ext4326.yMax, ext4326.xMin, zoom)
        br_tile_xi, br_tile_yi = smopy.deg2num(
            ext4326.yMin, ext4326.xMax, zoom)

        return TileIndexBox(xi_start=tl_tile_xi, xi_stop=br_tile_xi, yi_start=tl_tile_yi, yi_stop=br_tile_yi)

    def tileBox(s, zoom, return_index_box=False):
        """Determine the tile Extent at a given zoom level which surround the invoked Extent

        Parameters:
        -----------
        zoom : int
            The zoom level of the expected tile source

        return_index_box : bool
            If true, also return the index box at the specified zoom level (from s.tileIndexBox)

        Returns:
        --------
        if return_index_box is False: geokit.Extent

        if return_index_box is True: Tuple
            - Item 0: geokit.Extent
            - Item 1: namedtuple(xi_start, xi_stop, yi_start, yi_stop)

        """
        # Get Bounds of new raster in EPSG3857
        tb = s.tileIndexBox(zoom)

        tl_tile_xi = tb.xi_start
        tl_tile_yi = tb.yi_start
        br_tile_xi = tb.xi_stop
        br_tile_yi = tb.yi_stop

        tl_lat, tl_lon = smopy.num2deg(tl_tile_xi,   tl_tile_yi, zoom)
        br_lat, br_lon = smopy.num2deg(br_tile_xi+1, br_tile_yi+1, zoom)

        coords3857 = xyTransform([(tl_lon, tl_lat), (br_lon, br_lat)],
                                 fromSRS=EPSG4326, toSRS=EPSG3857, outputFormat='xy')

        ext = Extent(coords3857.x.min(),
                     coords3857.y.min(),
                     coords3857.x.max(),
                     coords3857.y.max(),
                     srs=EPSG3857)

        if return_index_box:
            return ext, tb
        else:
            return ext

    def mosaicTiles(s, source, zoom, pixelsPerTile, workingType=np.uint16, noData=2**16-1, output=None, **kwargs):
        """Create a raster source surrounding the Extent from a collection of tiles 

        Parameters:
        -----------
        source : str
            The source to fetch tiles from
            * Must include indicators for:
              {z} -> The tile's zoom level
              {x} -> The tile's x-index
              {y} -> The tile's y-index
            * Ex:
              File on disk     : "/path/to/tile/directory/{z}/{x}/{y}/filename.tif"
              Remote HTTP file : "/vsicurl_streaming/http://path/to/resource/{z}/{x}/{y}/filename.tif"
            * Find more info at https://gdal.org/user/virtual_file_systems.html


        zoom : int
            The zoom level of the expected tile source

        pixelsPerTile : int, (int,int)
            The number of pixels found in each tile

        workingType : np.dtype
            The datatype of the working matrix (should match the raster source)

        noData : numeric
            The value to treat as 'no data'

        output : str
            An optional path for an output raster (.tif) file

        Returns:
        --------
        * If 'output' is None: gdal.Dataset
        * If 'output' is a string: None

        """
        if not isinstance(pixelsPerTile, tuple):
            dy = dx = int(pixelsPerTile)
        else:
            dy, dx = int(pixelsPerTile[0]), int(pixelsPerTile[1])

        ext, tb = s.tileBox(zoom, return_index_box=True)

        # Fetch tiles
        # TODO: This can be easily parallelized!!
        def source_filled(xi, yi, zoom): return source.replace(
            "{z}", str(zoom)).replace("{x}", str(xi)).replace("{y}", str(yi))

        total_size = dy*(tb.yi_stop+1-tb.yi_start), dx * \
            (tb.xi_stop+1-tb.xi_start)

        canvas = np.full(total_size, noData, dtype=workingType)
        empty = np.full((dy, dx), noData, dtype=workingType)
        for yi_mat, yi_tile in enumerate(range(tb.yi_start, tb.yi_stop+1)):
            for xi_mat, xi_tile in enumerate(range(tb.xi_start, tb.xi_stop+1)):
                current_source = source_filled(xi_tile, yi_tile, zoom)
                # if os.path.isfile(current_source):
                try:
                    mat = extractMatrix(current_source)
                except:
                    mat = empty
                    warnings.warn(
                        "Source could not be loaded: "+current_source)
                canvas[yi_mat*dy:(yi_mat+1)*dy, xi_mat*dx:(xi_mat+1)*dx] = mat

        # Make raster output
        pw, ph = ext.computePixelSize(total_size[0], total_size[1])
        output = ext.createRaster(pixelWidth=pw, pixelHeight=ph,
                                  output=output, noData=noData, data=canvas, **kwargs)
        return output

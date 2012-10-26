#!/usr/bin/env python
# encoding: utf-8
"""
Representation of Voronoi Tessellations in ghostmap.

2012-10-25 - Created by Jonathan Sick
"""

import os
import numpy as np
import scipy.interpolate.griddata as griddata
import scipy.spatial.cKDTree as KDTree


class VoronoiTessellation(object):
    """A Voronoi Tessellation."""
    def __init__(self, x, y):
        super(VoronoiTessellation, self).__init__()
        self.xNode = x  #: Array of node x-coordinates
        self.yNode = y  #: Array of node y-coordinates
        self.segmap = None  #: 2D `ndarray` of `vBinNum` for each pixel
        self.cellAreas = None  #: 1D array of Voronoi cell areas
        self.xlim = None  #: Length-2 array of min, max coords of x pixel grid
        self.ylim = None  #: Length-2 array of min, max coords of y pixel grid
        self.header = None  #: a PyFITS header representing pixel grid

    def set_pixel_grid(self, xlim, ylim):
        """Set a pixel grid bounding box for the tessellation. This is
        used when rendering Voronoi fields or computing cell areas.

        Setting the pixel grid is a prerequistie for running the methods:
        - :meth:`make_segmap` and :meth:`save_segmap`
        - :meth:`compute_cell_areas`

        :param xlim, ylim: tuples of (min, max) pixel ranges.
        """
        assert len(xlim) == 2, "xlim must be (min, max) sequence"
        assert len(ylim) == 2, "ylim must be (min, max) sequence"
        self.xlim = xlim
        self.ylim = ylim

    def set_fits_grid(self, header):
        """Convenience wrapper to :meth:`set_pixel_grid` if a FITS header is
        available. As a bonus, the FITS header will be used when saving
        any rendered fields to FITS.
        
        .. note:: The header is available as the :attr:`self.header` attribute.

        :param header: a PyFITS image header, defines area of rendered Voronoi
            images (e.g. segmentaion maps or fields).
        """
        # Assume origin at 1, FITS standard
        xlim = (1, header['NAXIS2'] + 1)
        ylim = (1, header['NAXIS1'] + 1)
        self.set_pixel_grid(xlim, ylim)
        self.header = header

    def make_segmap(self):
        """Make a pixel segmentation map that paints the Voronoi bin number
        on Voronoi pixels.
        
        The result is stored as the `segmap` attribute and returned to the
        caller.
        
        :returns: The segmentation map array, `segmap`.
        """
        assert self.xlim is not None, "Need to run `set_pixel_grid()` first"
        assert self.ylim is not None, "Need to run `set_pixel_grid()` first"
        xgrid = np.arange(self.xlim[0], self.xlim[1])
        ygrid = np.arange(self.ylim[0], self.ylim[1])
        # Package xNode and yNode into Nx2 array
        # y is first index if FITS data is also structured this way
        yxNode = np.hstack(self.yNode, self.xNode)
        # Nearest neighbour interpolation is equivalent to Voronoi pixel
        # tessellation!
        self.segmap = griddata(yxNode, np.arange(0, self.yNode.shape[0]),
                (xgrid, ygrid), method='nearest')

    def save_segmap(self, fitsPath):
        """Convenience wrapper to :meth:`make_segmap` that saves the
        segmentation map to a FITS file.

        :param fitsPath: full filename destination of FITS file
        """
        import pyfits
        fitsDir = os.path.dirname(fitsPath)
        if not os.path.exists(fitsDir): os.makedirs(fitsDir)
        if self.segmap is None:
            self.make_segmap()
        if self.header is not None:
            pyfits.writeto(fitsPath, self.segmap, self.header)
        else:
            pyfits.writeto(fitsPath, self.segmap)

    def compute_cell_areas(self, flagmap=None):
        """Compute the areas of Voronoi cells; result is stored in the
        `self.cellAreas` attribute.

        .. note:: This method requires that the segmentation map is computed
           (see :meth:`make_segmap`), and is potentially expensive (I'm working
           on a faster implementation). Uses :func:`numpy.bincount` to count
           number of pixels in the segmentation map with a given Voronoi
           cell value. I'd prefer to calculate these from simple geometry,
           but no good python packages exist for defining Voronoi cell
           polygons.

        :param flagmap: Any pixels in the flagmap with
            values greater than zero will be omitted from the area count.
            Thus the cell areas will report *useable* pixel areas, rather
            than purely geometric areas. This is useful to avoid bias in
            density maps due to 'bad' pixels.
        :type flagmap: 2D `ndarray` with same shape as the pixel context
            (*i.e.,* :attr:`self.segmap`).
        :returns: ndarray of cell areas (square pixels). This array is also
            stored as :attr:`self.cellAreas`.
        """
        assert self.segmap is not None, "Compute a segmentation map first"
        
        if flagmap is not None:
            # If a flagmap is available, flagged pixels are set to NaN
            _segmap = self.segmap.copy()
            _segmap[flagmap > 0] = np.nan
        else:
            _segmap = self.segmap
        pixelCounts = np.bincount(_segmap.ravel())
        self.cellAreas = pixelCounts
        return self.cellAreas

    def get_nodes(self):
        """Returns the x and y positions of the Voronoi nodes."""
        return self.xNode, self.yNode

    def partition_points(self, x, y):
        """Partition an arbitrary set of points, defined by `x` and `y`
        coordinates, onto the Voronoi tessellation.
        
        This method uses :class:`scipy.spatial.cKDTree` to efficiently handle
        Voronoi assignment.

        :param x: array of point `x` coordinates
        :param y: array of point `y` coordinates
        :returns: ndarray of indices of Voronoi nodes
        """
        nodeData = np.hstack((self.nodeX, self.nodeY))
        pointData = np.hstack((x, y))
        tree = KDTree(nodeData)
        distances, indices = tree.query(pointData, k=1)
        return indices
    
    def plot_nodes(self, plotPath):
        """Plots the points in each bin as a different colour"""
        from matplotlib.backends.backend_pdf \
                import FigureCanvasPdf as FigureCanvas
        from matplotlib.figure import Figure
        
        fig = Figure(figsize=(6, 4))
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        ax.plot(self.xNode, self.yNode, 'ok')
        if self.xlim is not None:
            ax.set_xlim(self.xlim)
        if self.ylim is not None:
            ax.set_ylim(self.ylim)
        canvas.print_figure(plotPath)

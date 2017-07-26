import os
import numpy as np
from astropy.io import fits
from astropy.units import si
import clarsach

KEV  = ['kev', 'keV']
ANGS = ['Angstroms','Angstrom','Angs','angstroms','angstrom','angs']
ALLOWED_UNITS = KEV + ANGS

ALLOWED_TELESCOPES = ['HETG','ACIS','other']

__all__ = ['BkgSpectrum']

class BkgSpectrum(object):
    """
    Class for reading in background spectra
    """
    def __init__(self, filename, telescope='HETG'):
        if telescope == 'HETG':
            self._read_HETG(filename)
        else:
            self._read_other(filename)

        if self.bin_unit in ANGS:
            self._setbins_to_keV()

    @property
    def bin_mid(self):
        return 0.5 * (self.bin_lo + self.bin_hi)

    def _read_HETG(self, filename):
        this_dir = os.path.dirname(os.path.abspath(filename))
        ff     = fits.open(filename)
        data   = ff[1].data
        hdr    = ff[1].header
        self.hdr    = hdr
        self.data   = data
        self.counts = data['BACKGROUND_UP'] + data['BACKGROUND_DOWN']
        self.bin_lo = data['BIN_LO']
        self.bin_hi = data['BIN_HI']
        self.bin_unit = data.columns['BIN_LO'].unit
        # area of srouce region / area of background region
        self.backscal = hdr['BACKSCAL'] / (hdr['BACKSCUP'] + hdr['BACKSCDN'])
        ff.close()

    def _read_other(self, filename):
        this_dir = os.path.dirname(os.path.abspath(filename))
        ff     = fits.open(filename)
        data   = ff[1].data
        hdr    = ff[1].header
        self.hdr    = hdr
        self.data   = data
        self.counts = data['COUNTS']
        self.bin_lo = data['BIN_LO']
        self.bin_hi = data['BIN_HI']
        self.bin_unit = data.columns['BIN_LO'].unit
        # area of background region
        try:
            self.backscal = 1.0 / hdr['BACKSCAL']
        except:
            self.backscal = 1.0
        ff.close()

    def _setbins_to_keV(self):
        assert self.bin_unit in ANGS
        new_bhi, sl = clarsach.respond._Angs_keV(self.bin_lo)
        new_blo, sl = clarsach.respond._Angs_keV(self.bin_hi)
        new_cts  = self.counts[sl]

        # Now hard set everything
        self.bin_lo = new_blo
        self.bin_hi = new_bhi
        self.counts = new_cts
        self.bin_unit = si.keV
        return
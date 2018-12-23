import numpy as np
import astropy.units as u

from specutils import XraySpectrum1D
#from .bkgspectrum import BkgSpectrum

KEV  = ['kev', 'keV']
ANGS = ['Angstroms','Angstrom','Angs','angstroms','angstrom','angs']
ALLOWED_UNITS = KEV + ANGS

#__all__ = ['Spectrum','group_channels','group_mincounts']

class XBinSpectrum(XraySpectrum1D):
    def __init__(self, *args, from_file=None, format='chandra_hetg', **kwargs):
        if from_file is None:
            XraySpectrum1D.__init__(self, *args, **kwargs)
        else:
            # I don't know how to make this inherit properly
            temp = XraySpectrum1D.read(from_file, format=format) # , **kwargs)
            XraySpectrum1D.__init__(self, temp.bin_lo, temp.bin_hi,
                                    temp.counts, temp.exposure, **kwargs)
        self.notice  = np.ones_like(self.counts, dtype=bool)
        self.binning = np.zeros_like(self.counts)
        self.bkg = None

    ##-- I wrote these properties for convenience
    @property
    def bmid_keV(self):
        return self.spectral_axis.to(u.keV, equivalencies=u.spectral())

    @property
    def bmid_angs(self):
        return self.spectral_axis.to(u.angstrom, equivalencies=u.spectral())

    def notice_range(self, bmin, bmax):
        """
        Define edges for spectral regions to notice. Notices regions exclusively.

        >>> XBinSpectrum.notice(1.0*u.keV, 3.0*u.keV)

        will notice *only* the region between 1 and 3 keV.

        Parameters
        ----------
        bmin : astropy.Quantity
            Minimum value for the notice region

        bmax : astropy.Quantity
            Maxium value for the notice region

        Returns
        -------
        Modifies the XraySpectrum1D.notice attribute.
        """
        bmin0 = bmin.to(self.bin_lo.unit, equivalencies=u.spectral())
        bmax0 = bmax.to(self.bin_lo.unit, equivalencies=u.spectral())
        imin  = (self.bin_lo >= min(bmin0, bmax0))
        imax  = (self.bin_hi <= max(bmin0, bmax0))
        self.notice  = (imin & imax)

    def notice_all(self):
        """
        Resets the notice attribute to notice the entire range.
        """
        self.notice = np.ones_like(self.counts, dtype=bool)

    def reset_binning(self):
        """
        Resets the binning attribute
        """
        self.binning = np.zeros_like(self.counts)

    def binned_counts(self, bkgsub=False, usebackscal=True):
        """
        Returns the binned counts histogram from the noticed spectral region.

        Parameters
        ----------
        bkgsub : bool
            If True, supply the background subtracted region spectrum
            (only if a background spectrum is supplied)

        usebackscal : bool
            If True, scales the background by the backscal value

        Returns
        -------
        bin_lo : astropy.Quantity
            Lower edges for the new bins

        bin_hi : astropy.Quantity
            Higher edges for the new bins

        counts : astropy.Quantity
            Counts for the new bins

        cts_err : astropy.Quantity
            Error on the new bins
        """
        if all(self.binning == 0.0):
            counts  = self.counts[self.notice]
            bin_lo = self.bin_lo[self.notice]
            bin_hi = self.bin_hi[self.notice]
            cts_err = np.sqrt(counts.value) * u.ct
        else:
            bin_lo, bin_hi, counts, cts_err = self._parse_binning()

        if bkgsub and (self.bkg is not None):
            blo, bhi, bcts, bcts_err = self.bkg.bin_bkg(self.notice, self.binning, usebackscal=usebackscal)
            new_counts = counts[sl] - bcts[sl]
            new_error  = np.sqrt(cts_err[sl]**2 + bcts_err[sl]**2)
            return new_lo, new_hi, new_counts, new_error
        else:
            return bin_lo, bin_hi, counts, cts_err

    def _parse_binning(self):
        ## Returns the number of counts in each bin for a binned spectrum
        ## Works on the noticed regions only
        assert not all(self.binning == 0), "there is no grouping on this spectrum"

        # Use noticed regions only
        binning = self.binning[self.notice]
        counts  = self.counts[self.notice].value
        bin_lo  = self.bin_lo[self.notice].value
        bin_hi  = self.bin_hi[self.notice].value

        new_bin_lo = np.array([bin_lo[binning == n][0] for n in np.arange(min(binning), max(binning)+1)])
        new_bin_hi = np.array([bin_hi[binning == n][-1] for n in np.arange(min(binning), max(binning)+1)])
        result = np.array([np.sum(counts[binning == n]) for n in np.arange(min(binning), max(binning)+1)])

        # Accuracy checks
        assert len(new_bin_lo) == (max(binning) - min(binning) + 1)
        assert len(new_bin_hi) == (max(binning) - min(binning) + 1)
        assert len(result) == (max(binning) - min(binning) + 1)
        assert np.sum(result) == np.sum(counts)  # Make sure no counts are lost

        new_bin_lo *= self.bin_lo.unit
        new_bin_hi *= self.bin_lo.unit
        result *= u.ct
        result_err = np.sqrt(result.value) * u.ct

        return new_bin_lo, new_bin_hi, result, result_err

    def bin_bkg(self, usebackscal=True):
        """
        Return the background spectrum using the same spectral binning.

        Parameters
        ----------
        usebackscal : bool
            If True, returns the background scaled by the backscal value.

        Returns
        -------
        bin_lo : astropy.Quantity
            Lower edges for the new background bins

        bin_hi : astropy.Quantity
            Higher edges for the new background bins

        counts : astropy.Quantity
            Counts for the binned background histogram

        cts_err : astropy.Quantity
            Error on the new background bins
        """
        return self.bkg.bin_bkg(self.notice, self.binning, usebackscal=usebackscal)

    def assign_bkg(self, bkgspec):
        """
        Assign a background spectrum.

        Parameters
        ----------
        bkgspec : pyxsis.BkgSpectrum
        """
        assert isinstance(bkgspec, BkgSpectrum)
        assert all(self.bin_lo == bkgspec.bin_lo), "Background grid needs to be the same"
        assert all(self.bin_hi == bkgspec.bin_hi), "Background grid need to be the same"
        assert self.bin_unit == bkgspec.bin_unit, "Bin units need to be the same"
        self.bkg = bkgspec

## ----- Binning functions

def group_channels(spectrum, n):
    """
    Group channels in a spectrum by a constant factor, n

    Parameters
    ----------
    spectrum : pyxsis.XBinSpectrum
        Must contain `binning` attribute (ndarray)

    n : int
        Integer factor for binning the spectrum channels

    Returns
    -------
    Modifies spectrum.binning
    """
    assert n > 1, "n must be larger than 1"

    tot_chan = len(spectrum.binning)  # Total number of channels
    counter, index = 0, 0
    result = np.array([])
    while index < tot_chan:
        result = np.append(result, np.repeat(counter, n))
        index += n
        counter += 1

    # Trim array in case we went over the total number of channels
    # which will happen when tot_chan % n != 0
    result = result[np.arange(tot_chan)]
    spectrum.binning = result
    return

def group_mincounts(spectrum, mc):
    """
    Group channels in a spectrum so that there is a minimum number of counts in each bin

    Parameters
    ----------
    spectrum : XBinSpectrum
        Must contain `binning` attribute (ndarray)

    mc : int
        Minimum number of counts per bin

    Returns
    -------
    Modifies spectrum.binning
    """
    assert mc > 0, "mc must be larger than 1"

    tot_chan = len(spectrum.binning)
    counter, tempcount = 0, 0
    result = []
    for i in range(tot_chan):
        result.append(counter)
        tempcount += spectrum.counts[i].value
        if tempcount >= mc:
            counter += 1
            tempcount = 0
    result = np.array(result)

    # Ensure that the last bin has at least ten counts
    nlast = result[-1]
    last_bin_count = np.sum(spectrum.counts[result == nlast].value)
    if last_bin_count < mc:
        result[result == nlast] = nlast-1

    spectrum.binning = result
    return

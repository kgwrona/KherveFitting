
import numpy as np
# from numba import jit, prange
import lmfit
from lmfit.models import VoigtModel
from scipy.optimize import minimize_scalar, brentq
from scipy.signal import convolve
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter

import numpy as np


class PeakFunctions:

    @staticmethod
    def gaussian_other(x, E, F, m):
        return np.exp(-4 * np.log(2) * ((x - E) / F)**2) * (1 - m / 100)

    @staticmethod
    def gaussian(x, E, F, m):
        return np.exp(-4 * np.log(2) * (1 - m / 100) * ((x - E) / F)**2)

    @staticmethod
    def lorentzian(x, E, F, m):
        return 1 / (1 + 4 * m / 100 * ((x - E) / F)**2)

    @staticmethod
    def gauss_lorentz_OLD(x, center, fwhm, fraction, amplitude):
        return amplitude * (
            PeakFunctions.gaussian(x, center, fwhm, fraction*1) *
            PeakFunctions.lorentzian(x, center, fwhm, fraction*1))

    @staticmethod
    def S_gauss_lorentz(x, center, fwhm, fraction, amplitude):
        return amplitude * (
            (1-fraction/100) * PeakFunctions.gaussian(x, center, fwhm, 0) +
            fraction/100 * PeakFunctions.lorentzian(x, center, fwhm, 100))

    @staticmethod
    def gauss_lorentz(x, center , fwhm, fraction, amplitude):
        peak = amplitude * (
                PeakFunctions.gaussian(x, center, fwhm, fraction * 1) *
                PeakFunctions.lorentzian(x, center, fwhm, fraction * 1))
        return peak


    @staticmethod
    def gauss_lorentz_Area(x, center, area, fwhm, fraction):
        sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))
        height = area / (sigma * np.sqrt(2 * np.pi))
        return height * (
                PeakFunctions.gaussian(x, center, fwhm, fraction * 1) *
                PeakFunctions.lorentzian(x, center, fwhm, fraction * 1))

    @staticmethod
    def S_gauss_lorentz_Area(x, center, area, fwhm, fraction):
        sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))
        height = area / (sigma * np.sqrt(2 * np.pi))
        return height * (
                (1 - fraction / 100) * PeakFunctions.gaussian(x, center, fwhm, 0) +
                fraction / 100 * PeakFunctions.lorentzian(x, center, fwhm, 100))


    # SHALL NOT BE USEFUL
    @staticmethod
    def tail(x, center, tail_mix, tail_exp, fwhm):

        # Avoid division by zero and negative exponents
        safe_exp = np.maximum(tail_exp, 1e-5)
        safe_mix = np.maximum(tail_mix, 1e-5)
        return np.where(x > center,     np.exp(-safe_exp * np.abs(x - center) ** safe_mix), 0)

    @staticmethod
    def filter_func(x, center):
        return np.where(x <= center, 1, 0)



    @staticmethod
    def S_gauss_lorentz_tail(x, center, fwhm, fraction, amplitude, tail_mix, tail_exp):
        peak = amplitude * (
                (1 - fraction/100) * PeakFunctions.gaussian(x, center, fwhm, 0) +
                fraction/100 * PeakFunctions.lorentzian(x, center, fwhm, 100))
        tail = PeakFunctions.tail(x, center, tail_mix, tail_exp)
        return peak * (1 - tail_mix) + amplitude * tail

    @staticmethod
    def pseudo_voigt(x, center, amplitude, sigma, fraction):
        """
        Custom Pseudo-Voigt function.

        Parameters:
        x : array
            The x values
        center : float
            The peak center
        amplitude : float
            The peak height
        sigma : float
            The peak width (standard deviation for Gaussian component)
        fraction : float
            The fraction of Lorentzian component (0 to 1)

        Returns:
        array : The y values of the Pseudo-Voigt function
        """
        sigma2 = sigma ** 2
        gamma = sigma * np.sqrt(2 * np.log(2))

        gaussian = (1 - fraction/100) * np.exp(-((x - center) ** 2) / (2 * sigma2))
        lorentzian = fraction/100 * (gamma ** 2 / ((x - center) ** 2 + gamma ** 2))

        return amplitude * (gaussian + lorentzian)

    @staticmethod
    def pseudo_voigt_fwhm(x, center, amplitude, fwhm, fraction):
        """
        Custom Pseudo-Voigt function using FWHM.

        Parameters:
        x : array
            The x values
        center : float
            The peak center
        amplitude : float
            The peak height
        fwhm : float
            Full Width at Half Maximum of the peak
        fraction : float
            The fraction of Lorentzian component (0 to 1)

        Returns:
        array : The y values of the Pseudo-Voigt function
        """
        sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))  # Convert FWHM to sigma for Gaussian
        gamma = fwhm / 2  # Convert FWHM to gamma for Lorentzian

        z = (x - center) / sigma

        gaussian = (1 - fraction/100) * np.exp(-z ** 2 / 2) / (sigma * np.sqrt(2 * np.pi))
        lorentzian = fraction/100 * gamma / (np.pi * (gamma ** 2 + (x - center) ** 2))

        return amplitude * (gaussian + lorentzian) * sigma * np.sqrt(2 * np.pi)

    @staticmethod
    def voigt_fwhm(sigma, gamma):
        """
        Approximate the FWHM of a Voigt profile.

        This uses an approximation that is accurate to within a few percent.

        Parameters:
        sigma : float
            The sigma parameter of the Gaussian component
        gamma : float
            The gamma parameter of the Lorentzian component

        Returns:
        float : The approximate FWHM of the Voigt profile
        """
        fg = 2 * sigma * np.sqrt(2 * np.log(2))
        fl = 2 * gamma
        return 0.5346 * fl + np.sqrt(0.2166 * fl ** 2 + fg ** 2)


    @staticmethod
    def pseudo_voigt_amplitude_to_height(amplitude, sigma, fraction):
        """
        Convert amplitude to height for a Pseudo-Voigt profile.

        Parameters:
        amplitude : float
            The amplitude of the Pseudo-Voigt profile
        sigma : float
            The sigma parameter of the profile (related to FWHM)
        fraction : float
            The fraction of Lorentzian component (0 to 1)

        Returns:
        float : The height of the Pseudo-Voigt profile
        """
        sqrt2pi = np.sqrt(2 * np.pi)
        sqrt2ln2 = np.sqrt(2 * np.log(2))

        gaussian_height = amplitude / (sigma * sqrt2pi)
        lorentzian_height = 2 * amplitude / (np.pi * sigma * 2 * sqrt2ln2)

        height = (1 - fraction/100) * gaussian_height + fraction/100 * lorentzian_height

        return height

    @staticmethod
    def pseudo_voigt_height_to_amplitude(height, sigma, fraction):
        """
        Convert height to amplitude for a Pseudo-Voigt profile.

        Parameters:
        height : float
            The height of the Pseudo-Voigt profile
        sigma : float
            The sigma parameter of the profile (related to FWHM)
        fraction : float
            The fraction of Lorentzian component (0 to 1)

        Returns:
        float : The amplitude of the Pseudo-Voigt profile
        """
        sqrt2pi = np.sqrt(2 * np.pi)
        sqrt2ln2 = np.sqrt(2 * np.log(2))

        gaussian_amplitude = height * sigma * sqrt2pi
        lorentzian_amplitude = height * np.pi * sigma * 2 * sqrt2ln2 / 2

        amplitude = (1 - fraction/100) * gaussian_amplitude + fraction/100 * lorentzian_amplitude

        return amplitude

    def voigt_area(height, sigma, gamma):
        from scipy.special import wofz

        # Convert sigma to Gaussian FWHM
        fwhm_g = 2 * sigma * np.sqrt(2 * np.log(2))

        # Convert gamma to Lorentzian FWHM
        fwhm_l = 2 * gamma

        # Calculate the Voigt function at its center
        voigt_max = np.real(wofz((0 + 1j * gamma) / (sigma * np.sqrt(2))))

        # Calculate the area
        area = height * (np.pi * fwhm_l / 2 + np.sqrt(np.pi * np.log(2)) * fwhm_g) / voigt_max

        return area

    @staticmethod
    def get_voigt_height(amplitude, sigma, gamma):
        """
        Calculate the height of a Voigt profile directly using the lmfit model.
        """
        model = lmfit.models.VoigtModel()
        params = model.make_params(amplitude=amplitude, center=0, sigma=sigma, gamma=gamma)
        return model.eval(params, x=0)

    @staticmethod
    def voigt_height_to_area(height, sigma, gamma):
        voigt = VoigtModel()
        x = np.linspace(-10 * sigma, 10 * sigma, 1000)
        params = voigt.make_params(center=0, sigma=sigma, gamma=gamma, amplitude=1)
        y = voigt.eval(params, x=x)
        max_y = np.max(y)
        amplitude = height / max_y
        return amplitude  # For distribution models, amplitude is equivalent to area


    @staticmethod
    def get_pseudo_voigt_height(amplitude, sigma, fraction):
        """
        Calculate the height of a Pseudo-Voigt profile directly using the lmfit model.
        """
        model = lmfit.models.PseudoVoigtModel()
        params = model.make_params(amplitude=amplitude, center=0, sigma=sigma, fraction=fraction/100)
        return model.eval(params, x=0)

    @staticmethod
    def find_lorentzian_fwhm(true_fwhm, center, amplitude, sigma, gamma, max_iterations=50):
        def objective(lorentzian_fwhm):
            return abs(PeakFunctions.calculate_true_fwhm(center, amplitude, lorentzian_fwhm, sigma, gamma) - true_fwhm)

        if not PeakFunctions.is_valid_scalar(true_fwhm):
            raise ValueError(f"Invalid true_fwhm: {true_fwhm}")

        try:
            result = minimize_scalar(objective, bounds=(true_fwhm * 0.1, true_fwhm * 10), method='bounded',
                                     options={'maxiter': max_iterations})
            return result.x
        except Exception as e:
            print(f"Error in minimize_scalar: {e}")
            return true_fwhm  # Return the input FWHM as a fallback

    @staticmethod
    def calculate_true_fwhm(center, amplitude, fwhm, sigma, gamma, tolerance=1e-6, max_iterations=50):
        def la_function(x):
            return PeakFunctions.LA(x, center, amplitude, fwhm, sigma, gamma)

        half_max = la_function(center) / 2

        def find_half_max(x):
            return la_function(x) - half_max

        try:
            left_x = brentq(find_half_max, center - 10 * fwhm, center, maxiter=max_iterations, xtol=tolerance)
            right_x = brentq(find_half_max, center, center + 10 * fwhm, maxiter=max_iterations, xtol=tolerance)
            return right_x - left_x
        except ValueError as e:
            print(f"Error in calculate_true_fwhm: {e}")
            return fwhm  # Return the input FWHM as a fallback

    @staticmethod
    def LA_OTHER(x, center, amplitude, true_fwhm, sigma, gamma):
        true_fwhm = min(true_fwhm, 20)  # Limit true_fwhm to a maximum of 20

        if not PeakFunctions.is_valid_scalar(true_fwhm):
            raise ValueError(f"Invalid true_fwhm value: {true_fwhm}")
        if not PeakFunctions.is_valid_scalar(center):
            raise ValueError(f"Invalid center value: {center}")
        if not PeakFunctions.is_valid_scalar(amplitude):
            raise ValueError(f"Invalid amplitude value: {amplitude}")
        if not PeakFunctions.is_valid_scalar(sigma):
            raise ValueError(f"Invalid sigma value: {sigma}")
        if not PeakFunctions.is_valid_scalar(gamma):
            raise ValueError(f"Invalid gamma value: {gamma}")

        try:
            lorentzian_fwhm = PeakFunctions.estimate_lorentzian_fwhm(true_fwhm, sigma, gamma)
        except Exception as e:
            print(f"Error in estimate_lorentzian_fwhm: {e}")
            lorentzian_fwhm = true_fwhm  # Fallback to true_fwhm if estimation fails

        return amplitude * np.where(
            x <= center,
            1 / (1 + 4 * ((x - center) / lorentzian_fwhm) ** 2) ** gamma,
            1 / (1 + 4 * ((x - center) / lorentzian_fwhm) ** 2) ** sigma
        )

    @staticmethod
    def estimate_lorentzian_fwhm(true_fwhm, sigma, gamma, tolerance=1e-6, max_iterations=50):
        def peak_function(x, fwhm):
            return 1 / (1 + 4 * (x / fwhm) ** 2) ** ((sigma + gamma) / 2)

        def find_half_max(fwhm):
            half_max = peak_function(0, fwhm) / 2
            try:
                x_half = brentq(lambda x: peak_function(x, fwhm) - half_max, 0, fwhm * 10,
                                xtol=tolerance, maxiter=max_iterations)
                return 2 * x_half - true_fwhm
            except ValueError:
                return fwhm - true_fwhm  # Return a value that won't be zero to continue the search

        try:
            print("FWHM = "+str(true_fwhm))
            lorentzian_fwhm = brentq(find_half_max, true_fwhm * 0.1, true_fwhm * 10,
                                     xtol=tolerance, maxiter=max_iterations)
            return lorentzian_fwhm
        except ValueError:
            print(f"Failed to estimate Lorentzian FWHM. Using true FWHM: {true_fwhm}")
            return true_fwhm

    @staticmethod
    def is_valid_scalar(value):
        return value is not None and np.isfinite(value) and value > 0

    # @staticmethod
    # def LA_NEW(x, center, amplitude, fwhm, sigma, gamma):
    #     true_fwhm = min(fwhm, 20)
    #     # print(f"LA input: center={center}, amplitude={amplitude}, true_fwhm={true_fwhm}, sigma={sigma}, gamma={gamma}")
    #     if not PeakFunctions.is_valid_scalar(true_fwhm):
    #         raise ValueError(f"Invalid true_fwhm value: {true_fwhm}")
    #     if not PeakFunctions.is_valid_scalar(center):
    #         raise ValueError(f"Invalid center value: {center}")
    #     if not PeakFunctions.is_valid_scalar(amplitude):
    #         raise ValueError(f"Invalid amplitude value: {amplitude}")
    #     if not PeakFunctions.is_valid_scalar(sigma):
    #         raise ValueError(f"Invalid sigma value: {sigma}")
    #     if not PeakFunctions.is_valid_scalar(gamma):
    #         raise ValueError(f"Invalid gamma value: {gamma}")
    #
    #     try:
    #         lorentzian_fwhm = PeakFunctions.find_lorentzian_fwhm(true_fwhm, center, amplitude, sigma, gamma)
    #     except ValueError as e:
    #         print(f"Error in find_lorentzian_fwhm: {e}")
    #         print(f"Using true_fwhm as fallback: {true_fwhm}")
    #         # lorentzian_fwhm = true_fwhm
    #         lorentzian_fwhm = 1.4
    #
    #     return amplitude * np.where(
    #         x <= center,
    #         1 / (1 + 4 * ((x - center) / lorentzian_fwhm) ** 2) ** sigma,
    #         1 / (1 + 4 * ((x - center) / lorentzian_fwhm) ** 2) ** gamma
    #     )

    @staticmethod
    def LA_OLD(x, center, amplitude, fwhm, sigma, gamma):
        # Calculate F from the input FWHM
        F = 2 * fwhm / (np.sqrt(2 ** (1 / sigma) - 1) + np.sqrt(2 ** (1 / gamma) - 1))

        return amplitude * np.where(
            x <= center,
            1 / (1 + 4 * ((x - center) / F) ** 2) ** gamma,
            1 / (1 + 4 * ((x - center) / F) ** 2) ** sigma
        )

    @staticmethod
    # @jit(nopython=True, parallel=True)
    def LA(x, center, amplitude, fwhm, sigma, gamma):
        #amplitude here is the area

        # Calculate lorentzian width from the input FWHM
        F = 2 * fwhm / (np.sqrt(2 ** (1 / sigma) - 1) + np.sqrt(2 ** (1 / gamma) - 1))

        # Create the peak shape with unit amplitude
        peak_shape = np.where(
            x <= center,
            1 / (1 + 4 * ((x - center) / F) ** 2) ** gamma,
            1 / (1 + 4 * ((x - center) / F) ** 2) ** sigma
        )

        # Sort x values and corresponding peak shape for correct integration
        sort_idx = np.argsort(x)
        x_sorted = x[sort_idx]
        peak_shape_sorted = peak_shape[sort_idx]

        # Calculate the area of unit amplitude peak
        unit_area = abs(np.trapz(peak_shape_sorted, x_sorted))

        # Calculate required amplitude to achieve desired area
        height = amplitude / unit_area if unit_area != 0 else 0

        return height * peak_shape

    @staticmethod
    # @jit(nopython=True, parallel=True)
    def LAxG(x, center, amplitude, fwhm, sigma, gamma, fwhm_g):
        # Define the LA function
        # gaussian_fwhm =0.64 # now done through the grid

        # Calculate lorentzian width from the input FWHM
        F = 2 * fwhm / (np.sqrt(2 ** (1 / sigma) - 1) + np.sqrt(2 ** (1 / gamma) - 1))
        def LA_N(x):
            return np.where(
                x <= 0,
                1 / (1 + 4 * ((x ) / F) ** 2) ** gamma,
                1 / (1 + 4 * ((x ) / F) ** 2) ** sigma
            )

        # Define the Gaussian function
        def gaussian(x, fwhm_g):
            return np.exp(-4 * np.log(2) * ((x ) / fwhm_g) ** 2)

        x_range = max(x.max() - x.min(), 4 * fwhm)
        x_high_res = np.linspace(- x_range / 2, + x_range / 2, len(x) * 4)

        la = LA_N(x_high_res)
        gauss = gaussian(x_high_res, fwhm_g)

        convolved = convolve(la, gauss, mode='same') / sum(gauss)

        peak_shape = np.interp(x - center, x_high_res, convolved)

        # Sort x values and corresponding peak shape for correct integration
        sort_idx = np.argsort(x)
        x_sorted = x[sort_idx]
        peak_shape_sorted = peak_shape[sort_idx]

        # Calculate the area of unit amplitude peak
        unit_area = abs(np.trapz(peak_shape_sorted, x_sorted))

        # Calculate required amplitude to achieve desired area
        height = amplitude / unit_area if unit_area != 0 else 0

        return height * peak_shape


    @staticmethod
    def calculate_rsd(y_experimental, y_fitted):
        residuals = y_experimental - y_fitted
        n = len(residuals)
        denominator = y_experimental
        term = (residuals / np.sqrt(denominator)) ** 2
        sum_term = np.sum(term)
        rsd = np.sqrt(sum_term / n)

        # rsd2 = np.sqrt(np.mean(residuals ** 2)) / np.mean(y_experimental) * 100
        # print(f"RSD: {rsd2}")
        return rsd



from scipy.signal import savgol_filter


class BackgroundCalculations:

    @staticmethod
    def calculate_endpoint_average(x_values, y_values, point, num_points):
        # Find index closest to the specified point
        idx = np.argmin(np.abs(x_values - point))

        # Get start and end indices for averaging window
        start_idx = max(0, idx - num_points // 2)
        end_idx = min(len(y_values), idx + num_points // 2 + 1)

        # Calculate average
        return np.mean(y_values[start_idx:end_idx])

    @staticmethod
    def calculate_linear_background(x, y, start_offset, end_offset, num_points=5):
        """
        Calculate a linear background between the start and end points of the data.

        Args:
            x (array): X-axis values
            y (array): Y-axis values
            start_offset (float): Offset to add to the start point
            end_offset (float): Offset to add to the end point

        Returns:
            array: Linear background
        """
        y_start = BackgroundCalculations.calculate_endpoint_average(x, y, x[0],
                                                                    num_points) + start_offset
        y_end = BackgroundCalculations.calculate_endpoint_average(x, y, x[-1],
                                                                  num_points) + end_offset
        return np.linspace(y_start, y_end, len(y))


    @staticmethod
    def calculate_smart_background(x, y, offset_h, offset_l, num_points=5):
        """
        Calculate a 'smart' background by choosing between Shirley and linear backgrounds.

        Args:
            x (array): X-axis values
            y (array): Y-axis values
            offset_h (float): High offset
            offset_l (float): Low offset

        Returns:
            array: Smart background
        """
        shirley_bg = BackgroundCalculations.calculate_shirley_background(x, y, offset_h, offset_l,num_points)
        linear_bg = BackgroundCalculations.calculate_linear_background(x, y, offset_h, offset_l,num_points)

        # Choose background type based on first and last y-values
        background = shirley_bg if y[0] > y[-1] else linear_bg

        # Ensure background does not exceed raw data
        return np.minimum(background, y)

    @staticmethod
    def calculate_smart2_background(x, y, threshold=0.01):
        """
        Calculate an improved 'smart' background using derivative analysis.

        Args:
            x (array): X-axis values
            y (array): Y-axis values
            threshold (float): Threshold for determining flat regions

        Returns:
            array: Smart2 background
        """
        dy = np.gradient(y, x)
        threshold = 0.001 * (max(y) - min(y))

        # Smooth the derivative
        dy_smooth = savgol_filter(dy, window_length=30, polyorder=3)

        background = np.zeros_like(y)
        flat_mask = np.abs(dy_smooth) < threshold

        # Set background to raw data in flat regions
        background[flat_mask] = y[flat_mask]

        # For non-flat regions, decide between linear and Shirley
        for i in range(1, len(y)):
            if not flat_mask[i]:
                if y[i] < y[i - 1]:  # Data going down
                    background[i] = background[i - 1] + (y[i] - y[i - 1])
                else:  # Data going up
                    A = np.trapz(y[:i + 1] - background[:i + 1], x[:i + 1])
                    B = np.trapz(y[i:] - background[i:], x[i:])
                    background[i] = y[-1] + (y[0] - y[-1]) * B / (A + B)

        return background

    @staticmethod
    def calculate_adaptive_smart_background(x, y, x_range, previous_background, offset_h, offset_l, num_points=5):
        """
        Calculate an Multi-Regions Smart background for a selected range.

        Args:
            x (array): X-axis values
            y (array): Y-axis values
            x_range (tuple): Range of x values to calculate background for
            previous_background (array): Previous background calculation
            offset_h (float): High offset
            offset_l (float): Low offset

        Returns:
            array: Multi-Regions Smart background
        """
        previous_background = np.array(previous_background)
        mask = (x >= x_range[0]) & (x <= x_range[1])
        new_background = np.copy(previous_background)
        x_selected, y_selected = x[mask], y[mask]

        # Determine background type for selected range
        if y_selected[0] > y_selected[-1]:
            new_background[mask] = BackgroundCalculations.calculate_shirley_background(x_selected, y_selected, offset_h,
                                                                                       offset_l, num_points)
        else:
            new_background[mask] = BackgroundCalculations.calculate_linear_background(x_selected, y_selected, offset_h,
                                                                                      offset_l, num_points)

        return new_background

    @staticmethod
    def calculate_shirley_background(x, y, start_offset, end_offset, max_iter=100, tol=1e-6, padding_factor=0.01,
                                     num_points=5):
        """
        Calculate the Shirley background.

        Args:
            x (array): X-axis values
            y (array): Y-axis values
            start_offset (float): Offset to add to the start point
            end_offset (float): Offset to add to the end point
            max_iter (int): Maximum number of iterations
            tol (float): Tolerance for convergence
            padding_factor (float): Factor for padding the data
            num_points (int): Number of points to average for endpoints

        Returns:
            array: Shirley background
        """
        x, y = np.asarray(x), np.asarray(y)

        # Add padding to the data
        x_min, x_max = x[0], x[-1]
        padding_width = padding_factor * (x_max - x_min)
        x_padded = np.concatenate([[x_min - padding_width], x, [x_max + padding_width]])

        # Calculate averaged endpoint values
        y_start = BackgroundCalculations.calculate_endpoint_average(x, y, x[0], num_points) + start_offset
        y_end = BackgroundCalculations.calculate_endpoint_average(x, y, x[-1], num_points) + end_offset
        y_padded = np.concatenate([[y_start], y, [y_end]])

        background = np.zeros_like(y_padded)
        I0, Iend = y_padded[0], y_padded[-1]

        # Iterative calculation of Shirley background
        for _ in range(max_iter):
            prev_background = background.copy()
            for i in range(1, len(y_padded) - 1):
                A1 = np.trapz(y_padded[:i] - background[:i], x_padded[:i])
                A2 = np.trapz(y_padded[i:] - background[i:], x_padded[i:])
                background[i] = Iend + (I0 - Iend) * A2 / (A1 + A2)
            if np.all(np.abs(background - prev_background) < tol):
                break

        return background[1:-1]  # Remove padding before returning

    def calculate_tougaard_background(x, y, sheet_name, window):
        bg_data = window.Data['Core levels'][sheet_name]['Background']
        B = bg_data.get('Tougaard_B', 2866)
        C = bg_data.get('Tougaard_C', 1643)
        D = bg_data.get('Tougaard_D', 1)
        T0 = bg_data.get('Tougaard_T0', 0)

        # Get the baseline value (lowest BE intensity)
        baseline = y[-1]  # Assuming x is in BE, so highest KE/lowest BE is at the end

        # Shift data to zero baseline
        y_shifted = y  - baseline

        dx = np.mean(np.diff(x))
        background = np.zeros_like(y)
        for i in range(len(x)):
            E = x[i:] - x[i]
            K = B * E / ((C - E ** 2) ** 2 + D * E ** 2)
            background[i] = np.trapz(K * y_shifted[i:], dx=dx) + T0

        background = background + baseline
        return background

    def calculate_double_tougaard_background(x, y, sheet_name, window):
        bg_data = window.Data['Core levels'][sheet_name]['Background']

        # First Tougaard parameters
        B1 = bg_data.get('Tougaard_B', 2866)
        C1 = bg_data.get('Tougaard_C', 1643)
        D1 = bg_data.get('Tougaard_D', 1)
        T01 = bg_data.get('Tougaard_T0', 0)

        # Second Tougaard parameters
        B2 = bg_data.get('Tougaard_B2', 2866)
        C2 = bg_data.get('Tougaard_C2', 1643)
        D2 = bg_data.get('Tougaard_D2', 1)
        T02 = bg_data.get('Tougaard_T02', 0)

        baseline = y[-1]
        y_shifted = y - baseline

        dx = np.mean(np.diff(x))
        background1 = np.zeros_like(y)
        background2 = np.zeros_like(y)

        for i in range(len(x)):
            E = x[i:] - x[i]
            K1 = B1 * E / ((C1 - E ** 2) ** 2 + D1 * E ** 2)
            K2 = B2 * E / ((C2 - E ** 2) ** 2 + D2 * E ** 2)
            background1[i] = np.trapz(K1 * y_shifted[i:], dx=dx) + T01
            background2[i] = np.trapz(K2 * y_shifted[i:], dx=dx) + T02

        background = background1 + background2 + baseline
        return background

    def calculate_triple_tougaard_background(x, y, sheet_name, window):
        bg_data = window.Data['Core levels'][sheet_name]['Background']

        # Parameters for all three Tougaard backgrounds
        B1 = bg_data.get('Tougaard_B', 2866)
        C1 = bg_data.get('Tougaard_C', 1643)
        D1 = bg_data.get('Tougaard_D', 1)
        T01 = bg_data.get('Tougaard_T0', 0)

        B2 = bg_data.get('Tougaard_B2', 2866)
        C2 = bg_data.get('Tougaard_C2', 1643)
        D2 = bg_data.get('Tougaard_D2', 1)
        T02 = bg_data.get('Tougaard_T02', 0)

        B3 = bg_data.get('Tougaard_B3', 2866)
        C3 = bg_data.get('Tougaard_C3', 1643)
        D3 = bg_data.get('Tougaard_D3', 1)
        T03 = bg_data.get('Tougaard_T03', 0)

        baseline = y[-1]
        y_shifted = y - baseline

        dx = np.mean(np.diff(x))
        background1 = np.zeros_like(y)
        background2 = np.zeros_like(y)
        background3 = np.zeros_like(y)

        for i in range(len(x)):
            E = x[i:] - x[i]
            K1 = B1 * E / ((C1 - E ** 2) ** 2 + D1 * E ** 2)
            K2 = B2 * E / ((C2 - E ** 2) ** 2 + D2 * E ** 2)
            K3 = B3 * E / ((C3 - E ** 2) ** 2 + D3 * E ** 2)
            background1[i] = np.trapz(K1 * y_shifted[i:], dx=dx) + T01
            background2[i] = np.trapz(K2 * y_shifted[i:], dx=dx) + T02
            background3[i] = np.trapz(K3 * y_shifted[i:], dx=dx) + T03

        background = background1 + background2 + background3 + baseline
        return background

    @staticmethod
    def calculate_w_tougaard_background(x, y, B=2866, C=1643, T0=0):
        """
        Calculate W Tougaard background with endpoint adjustment.

        Parameters:
        x : array-like
            Energy axis (eV).
        y : array-like
            Intensity axis.
        B : float
            Initial Tougaard parameter, to be adjusted.
        C : float
            Tougaard parameter, controls energy-loss dependence.
        T0 : float
            Offset term for the background.

        Returns:
        background : array-like
            Computed W Tougaard background.
        """
        dx = np.mean(np.diff(x))  # Ensure uniform step size in x
        background = np.zeros_like(y)

        # Adjust B based on endpoint intensities
        I1, I2 = y[0], y[-1]  # Intensities at the endpoints
        B_adjusted = B * (I1 / I2) if I2 != 0 else B

        for i in range(len(x)):
            E = x[i:] - x[i]  # Energy loss
            K = B_adjusted * E / (C + E ** 2)  # Kernel computation
            background[i] = np.trapz(K * y[i:], dx=dx) + T0

        return background

    @staticmethod
    def calculate_u_poly_tougaard_background(x, y, B=2866, C=1643, D=1, T0=0):
        """
        Calculate U Poly Tougaard background for specific materials.

        Parameters:
        x : array-like
            Energy axis (eV).
        y : array-like
            Intensity axis.
        B : float
            Tougaard parameter related to scattering cross-section.
        C : float
            Tougaard parameter, energy-dependent term.
        D : float
            Tougaard parameter, higher-order correction term.
        T0 : float
            Energy loss threshold.

        Returns:
        background : array-like
            Computed U Poly Tougaard background.
        """
        dx = np.mean(np.diff(x))
        background = np.zeros_like(y)

        for i in range(len(x)):
            E = x[i:] - x[i]  # Energy loss
            K = np.where(
                E > T0,
                B * E / (C + D * E ** 2),
                0  # Zero for energy below threshold
            )
            background[i] = np.trapz(K * y[i:], dx=dx)

        return background


class AtomicConcentrations:
    @staticmethod
    def calculate_imfp_tpp2m_WITHOUT_VALUES_BUT_GOOD(kinetic_energy, z_avg, n_v_avg, molecular_weight, density):
        """
        Calculate IMFP using TPP-2M formula for 50-2000 eV electrons
        """
        E = kinetic_energy

        # Calculate plasmon energy E_p
        E_p = 28.8 * (n_v_avg * density / molecular_weight) ** 0.5

        # Calculate parameters
        U = n_v_avg * density / molecular_weight
        beta = -0.10 + 0.944 * (E_p ** 2) ** (-0.5) + 0.069 * density ** 0.1
        gamma = 0.191 * density ** (-0.5)
        C = 1.97 - 0.91 * U / (z_avg)
        D = 53.4 - 20.8 * U / (z_avg)

        # Calculate IMFP in Angstroms
        # /10 to get it in nm as per plot found advantage
        imfp = E / (E_p ** 2 * (beta * np.log2(gamma * E) - C / E + D / E ** 2)) /10#

        print(f'IMFP: {imfp}, KE: {kinetic_energy}')
        return imfp   # Convert to nanometers

    @staticmethod
    def calculate_imfp_tpp2m(kinetic_energy):
        """
        Calculate IMFP using TPP-2M formula with average matrix parameters from XPS reference data.

        Parameters:
            kinetic_energy: electron energy in eV

        Returns:
            imfp: Inelastic Mean Free Path in nanometers

        Notes:
        Average matrix parameters derived from metals and inorganic compounds:
        - N_v = 4.684 (valence electrons per atom)
        - rho = 6.767 g/cm³ (density)
        - M = 137.51 g/mol (molecular weight)
        - E_g = 0 eV (bandgap energy)

        References:
        1. S.Tanuma, C.J.Powell and D.R.Penn, Surf. Interface Anal., 21, 165-176 (1993)
        2. Briggs & Grant, "Surface Analysis by XPS and AES" 2nd Ed., Wiley (2003), p.84-85
        """
        N_v = 4.684
        rho = 6.767
        M = 137.51
        E_g = 0

        E_p = 28.8 * np.sqrt((N_v * rho) / M)
        U = N_v * rho / M

        beta = -0.10 + 0.944 / (E_p ** 2 + E_g ** 2) ** 0.5 + 0.069 * rho ** 0.1
        gamma = 0.191 * rho ** (-0.5)
        C = 1.97 - 0.91 * U
        D = 53.4 - 20.8 * U

        imfp = kinetic_energy / (E_p ** 2 * (
                beta * np.log(gamma * kinetic_energy) -
                (C / kinetic_energy) +
                (D / kinetic_energy ** 2))) / 10

        # Avantage add a scaling factor so that corrected area matches the one obtained with KE^0.6
        # To compare KherveFitting with Avantage we will also apply this factor
        imfp2 = imfp * 26.2

        # print(f'IMFP: {imfp}, Factored_imfp: {imfp2} KE: {kinetic_energy}')

        return imfp

    @staticmethod
    def calculate_angular_correction(window, peak_name, angle_degrees):
        """
        Calculate angular correction factor for non-magic angle analysis.

        Args:
            angle_degrees (float): Analysis angle in degrees
            orbital_type (str): Orbital type ('s', 'p', 'd', 'f')

        Returns:
            float: Angular correction factor
        """

        orbital_type = AtomicConcentrations.extract_orbital_type(peak_name)

        angle_rad = angle_degrees * np.pi / 180

        # Set beta parameter based on orbital type
        beta_values = {
            's': 0,
            'p': 1,
            'd': 2,
            'f': 2
        }
        beta = beta_values.get(orbital_type, 0)

        correction = 1 + beta * (3 * np.cos(angle_rad) ** 2 - 1) / 4
        print(f'correction for angle {angle_degrees}: {correction}')
        return correction

    @staticmethod
    def extract_orbital_type(peak_name):
        """
        Extract orbital type (s, p, d, f) from peak name.
        Examples:
        'Ti2p3/2' -> 'p'
        'C1s' -> 's'
        'Sr3d5/2' -> 'd'
        'Ti 2p3/2' -> 'p'
        'C 1s' -> 's'
        'Sr 3d5/2' -> 'd'
        """
        # Split name and take first part (core level)
        core_level = peak_name.split()[0]

        # Start from second character
        i = 1
        while i < len(core_level):
            # If current char is a letter
            if core_level[i].isalpha():
                # Check if next char exists and is a number
                if i + 1 < len(core_level) and core_level[i + 1].isdigit():
                    print(f'Peak name: {peak_name} Chosen name: {core_level[i+2].lower()}')
                    return core_level[i+2].lower()
            i += 1

        return 's'  # Default to s if no orbital found


class OtherCalc:
    @staticmethod
    def smooth_and_differentiate(x_values, y_values, smooth_width=2.0, pre_smooth=1, diff_width=1.0, post_smooth=1, algorithm="Gaussian"):
        from scipy.ndimage import gaussian_filter
        from scipy.signal import savgol_filter, wiener
        import numpy as np

        # Smoothing function based on algorithm
        def apply_smooth(data, width, algorithm):
            if algorithm == "Gaussian":
                return gaussian_filter(data, width)
            elif algorithm == "Savitsky-Golay":
                window = int(width * 10) if int(width * 10) % 2 == 1 else int(width * 10) + 1
                return savgol_filter(data, window, 3)
            elif algorithm == "Moving Average":
                window = int(width * 10)
                return np.convolve(data, np.ones(window)/window, mode='same')
            elif algorithm == "Wiener":
                return wiener(data, int(width * 10))
            else:  # "None"
                return data

        # Pre-smoothing passes
        smoothed = y_values.copy()
        for _ in range(int(pre_smooth)):
            smoothed = apply_smooth(smoothed, smooth_width, algorithm)

        # Calculate derivative
        derivative = -1 * np.gradient(smoothed, x_values)

        # Post-smoothing passes
        for _ in range(int(post_smooth)):
            derivative = apply_smooth(derivative, diff_width, algorithm)

        # Normalize derivative to data range
        data_range = np.max(y_values) - np.min(y_values)
        deriv_range = np.max(derivative) - np.min(derivative)
        normalized_deriv = ((derivative - np.min(derivative)) / deriv_range * data_range) + np.min(y_values)

        return normalized_deriv



import pandas as pd
import numpy as np
import scipy.stats as sps
import matplotlib.pyplot as plt
import warnings
import datetime


class EVA:
    """
    Extreme Value Analysis class. Takes a Pandas DataFrame with values. Extracts extreme values.
    Assists with threshold value selection. Fits data to distributions (GPD).
    Returns extreme values' return periods. Generates data plots.
    """
    def __init__(self, df, col=None):
        """
        :param df: DataFrame or Series
            Pandas DataFrame or Series object with column 'col' containing values and indexes as datetime.
        :param col: str
            Column name for the variable of interest (i.e. 'Spd').
            Default = None (takes first column as variables = df.columns[0]).
        """

        if type(df) != type(pd.DataFrame()):
            try:
                self.data = df.to_frame()
            except:
                raise ValueError('Invalid data type in <df>.'
                                 ' This class takes only Pandas DataFrame or Series objects.')
        else:
            self.data = df
        if col is not None:
            self.col = col
        else:
            self.col = df.columns[0]

        self.extremes = 'NO VALUE! Run the .get_extremes() method first.'
        self.method = 'NO VALUE! Run the .get_extremes() method first.'
        self.threshold = 'NO VALUE! Run the .get_extremes() method first.'
        self.distribution = 'NO VALUE! Run the .fit() method first.'
        self.retvalsum = 'Run the .fit() method first.'

        # Calculate number of years in data
        self.N = np.unique(self.data.index.year).max() - np.unique(self.data.index.year).min() + 1
        if self.N > len(np.unique(self.data.index.year)):
            warnings.warn('Some years are missing data. Review time series.')

    def get_extremes(self, method='POT', **kwargs):
        """
        Extracts extreme values.

        :param method: str
            Extraction method. POT for Peaks Over Threshold, BM for Block Maxima.
        :param kwargs:
            u : float
                Threshold value (POT method only)
            r : float
                Minimum independent event distance (hours) (POT method only). Default = 24 hours.
            decluster : bool
                Specify if extreme values are declustered (POT method only). Default = True.
            block : timedelta
                Block size (years) (BM method only). Default = 1 year.
        :return:
            self.extremes : DataFrame
                A DataFrame with extracted extreme values and Weibull return periods.
        """

        if method == 'POT':

            decluster = kwargs.pop('decluster', True)
            u = kwargs.pop('u', 10)
            r = kwargs.pop('r', 24)
            assert len(kwargs) == 0, 'unrecognized arguments passed in: {}'.format(', '.join(kwargs.keys()))

            self.method = 'POT'
            self.threshold = u
            self.extremes = self.data[self.data[self.col] > u]
            if decluster:
                r = datetime.timedelta(hours=r)
                indexes = self.extremes.index.to_pydatetime()
                values = self.extremes[self.col].values
                new_indexes = [indexes[0]]
                new_values = [values[0]]
                for i in range(1, len(indexes)):
                    if indexes[i] - new_indexes[-1] >= r:
                        new_indexes += [indexes[i]]
                        new_values += [values[i]]
                    else:
                        if values[i] > new_values[-1]:
                            new_indexes[-1] = indexes[i]
                            new_values[-1] = values[i]
                self.extremes = pd.DataFrame(data=new_values, index=new_indexes, columns=[self.col])

        elif method == 'BM':

            block = kwargs.pop('block', 'Y')
            assert len(kwargs) == 0, 'unrecognized arguments passed in: {}'.format(', '.join(kwargs.keys()))

            self.method = 'BM'
            years = np.unique(self.data.index.year)
            # months = np.array([np.unique(self.data[self.data.index.year == year].index.month) for year in years])
            if block == 'Y':
                bmextremes = [self.data[self.data.index.year == year].drop_duplicates(self.col) for year in years]
                bmextremes = [x[x[self.col] == x[self.col].max()] for x in bmextremes]
                self.extremes = pd.concat(bmextremes)
            elif block == 'M':
                raise NotImplementedError('Not yet implemented')
            elif block == 'W':
                raise NotImplementedError('Not yet implemented')
            else:
                raise ValueError('Unrecognized block size')
        else:
            raise ValueError('Unrecognized extremes parsing method. Use POT or BM methods.')
        self.extremes.sort_values(by=self.col, inplace=True)
        cdf = np.arange(len(self.extremes)) / len(self.extremes)
        return_periods = (self.N + 1) / (len(self.extremes) * (1 - cdf))
        self.extremes['T'] = pd.DataFrame(index=self.extremes.index, data=return_periods)
        self.extremes.sort_index(inplace=True)

    def pot_residuals(self, u, decluster=True, r=24, save_path=None, name='_DATA_SOURCE_'):
        """
        Calculates mean residual life values for different threshold values.

        :param u: list
            List of threshold to be tested
        :param plot: bool
            Plot residuals against threshold values. Default = False
        :param save_path: str
            Path to folder. Default = None.
        :param name: str
            Plot name.
        :param decluster: bool
            Decluster data using the run method.
        :param r: float
            Decluster run length (Default = 24 hours).
        :return:
        """

        u = np.array(u)
        if u.max() > self.data[self.col].max():
            u = u[u <= self.data[self.col].max()]
        if decluster:
            nu = []
            res_ex_sum = []
            for i in range(len(u)):
                self.get_extremes(method='POT', u=u[i], r=r, decluster=True)
                nu += [len(self.extremes[self.col].values)]
                res_ex_sum += [self.extremes[self.col].values - u[i]]
        else:
            nu = [len(self.data[self.data[self.col] >= i]) for i in u]
            res_ex_sum = [(self.data[self.data[self.col] >= u[i]][self.col] - u[i]).values for i in range(len(u))]
        residuals = [(sum(res_ex_sum[i]) / nu[i]) for i in range(len(u))]
        intervals = [sps.norm.interval(0.95, loc=res_ex_sum[i].mean(), scale=res_ex_sum[i].std() / len(res_ex_sum[i]))
                     for i in range(len(u))]
        intervals_u = [intervals[i][0] for i in range(len(intervals))]
        intervals_l = [intervals[i][1] for i in range(len(intervals))]
        with plt.style.context('bmh'):
            plt.figure(figsize=(16, 8))
            plt.subplot(1, 1, 1)
            plt.plot(u, residuals, lw=2, color='orangered', label=r'Mean Residual Life')
            plt.fill_between(u, intervals_u, intervals_l, alpha=0.3, color='royalblue',
                             label=r'95% confidence interval')
            plt.xlabel(r'Threshold Value')
            plt.ylabel(r'Mean residual Life')
            plt.title(r'{} Mean Residual Life Plot'.format(name))
            plt.legend()
        if not save_path:
            plt.show()
        else:
            plt.savefig(save_path + '\{} Mean Residual Life.png'.format(name), bbox_inches='tight', dpi=600)
            plt.close()

    def empirical_threshold(self, decluster=False, r=24, u_step=0.1, u_start=0):
        """
        Get exmpirical threshold extimates for 3 methods: 90% percentile value,
        square root method, log-method.

        :param decluster:
            Determine if declustering is used for estimating thresholds.
            Very computationally intensive.
        :param r:
            Declustering run length parameter.
        :param u_step:
            Threshold precision.
        :param u_start:
            Starting threshold for search (should be below the lowest expected value).
        :return:
            DataFrame with threshold summary.
        """

        tres = [np.percentile(self.data[self.col].values, 90)]
        k = int(np.sqrt(len(self.data)))
        u = u_start
        if decluster:
            self.get_extremes(method='POT', u=u, r=r, decluster=True)
            while len(self.extremes) > k:
                u += u_start
                self.get_extremes(method='POT', u=u, r=r, decluster=True)
        else:
            self.get_extremes(method='POT', u=u, r=r, decluster=False)
            while len(self.extremes) > k:
                u += u_step
                self.get_extremes(method='POT', u=u, r=r, decluster=False)
        tres += [u]
        k = int((len(self.data) ** (2 / 3)) / np.log(np.log(len(self.data))))
        u = u_start
        if decluster:
            self.get_extremes(method='POT', u=u, r=r, decluster=True)
            while len(self.extremes) > k:
                u += u_step
                self.get_extremes(method='POT', u=u, r=r, decluster=True)
        else:
            self.get_extremes(method='POT', u=u, r=r, decluster=False)
            while len(self.extremes) > k:
                u += u_step
                self.get_extremes(method='POT', u=u, r=r, decluster=False)
        tres += [u]
        return pd.DataFrame(data=tres, index=['90% Quantile', 'Squre Root Rule', 'Logarithm Rule'],
                            columns=['Threshold'])

    def par_stab_plot(self, u, distribution='GPD', decluster=True, r=24, save_path=None, name='_DATA_SOURCE_'):
        """
        Generates a parameter stability plot for the a range of thresholds u.
        :param u: list or array
            List of threshold values.
        :param decluster: bool
            Use run method to decluster data 9default = True)
        :param r: float
            Run lengths (hours), specify if decluster=True.
        :param save_path: str
            Path to save folder.
        :param name: str
            File save name.
        """

        u = np.array(u)
        if u.max() > self.data[self.col].max():
            u = u[u <= self.data[self.col].max()]
        fits = []
        if distribution == 'GPD':
            if decluster:
                for tres in u:
                    self.get_extremes(method='POT', u=tres, r=r, decluster=True)
                    extremes_local = self.extremes[self.col].values - tres
                    fit = sps.genpareto.fit(extremes_local)
                    fits += [fit]
            else:
                for tres in u:
                    self.get_extremes(method='POT', u=tres, r=r, decluster=False)
                    extremes_local = self.extremes[self.col].values - tres
                    fit = sps.genpareto.fit(extremes_local)
                    fits += [fit]
            shapes = [x[0] for x in fits]
            scales = [x[2] for x in fits]
            # scales_mod = [scales[i] - shapes[i] * u[i] for i in range(len(u))]
            scales_mod = scales
            with plt.style.context('bmh'):
                plt.figure(figsize=(16, 8))
                plt.subplot(1, 2, 1)
                plt.plot(u, shapes, lw=2, color='orangered', label=r'Shape Parameter')
                plt.xlabel(r'Threshold Value')
                plt.ylabel(r'Shape Parameter')
                plt.subplot(1, 2, 2)
                plt.plot(u, scales_mod, lw=2, color='orangered', label=r'Scale Parameter')
                plt.xlabel(r'Threshold Value')
                plt.ylabel(r'Scale Parameter')
                plt.suptitle(r'{} Parameter Stability Plot'.format(name))
            if not save_path:
                plt.show()
            else:
                plt.savefig(save_path + '\{} Parameter Stability Plot.png'.format(name), bbox_inches='tight', dpi=600)
                plt.close()
        else:
            print('The {} distribution is not yet implemented for this method'.format(distribution))

    def fit(self, distribution='GPD', confidence=False, k=10**2, trunc=True):
        """
        Implemented: GEV, GPD

        Fits distribution to data and generates a summary dataframe (required for plots).
        :param distribution:
            Distribution name (default 'GPD'). Available: GPD, GEV, Gumbel, Wibull, log-normal, Pearson 3
        :param confidence: bool
            Calculate 95% confidence limits using Monte Carlo simulation
            !!!!    (WARNING! Might be time consuming for large k)    !!!!
            Be cautious with interpreting the 95% confidence limits.
            Implemented for GPD, GEV
        :param k: int
            Number of Monte Carlo simulations (default k=10^4, try 10^2 before committing to 10^4).
        :param trunc: bool
            Truncate Monte Carlo generated fits by discarding fits with return values larger
            than the values for "true" fit for return periods multiplied by *k* (i.e. discards "bad" fits)
        :return: DataFrame
            self.retvalsum summary dataframe with fitted distribution and 95% confidence limits.
        """

        self.distribution = distribution
        if self.distribution == 'GPD':
            if self.method == 'POT':
                def ret_val(t, param, rate, u):
                    return u + sps.genpareto.ppf(1 - 1 / (rate * t), c=param[0], loc=param[1], scale=param[2])
                parameters = sps.genpareto.fit(self.extremes[self.col].values - self.threshold)
            else:
                def ret_val(t, param, rate, u):
                    return sps.genpareto.ppf(1 - 1 / (rate * t), c=param[0], loc=param[1], scale=param[2])
                parameters = sps.genpareto.fit(self.extremes[self.col].values)
        elif self.distribution == 'GEV':
            if self.method != 'BM':
                raise ValueError('GEV distribution is applicable only with the BM method')
            def ret_val(t, param, rate, u):
                return sps.genextreme.ppf(1 - 1 / (rate * t), c=param[0], loc=param[1], scale=param[2])
            parameters = sps.genextreme.fit(self.extremes[self.col].values)

        # TODO =================================================================================
        elif self.distribution == 'Gumbel':
            if self.method != 'BM':
                raise ValueError('Gumbel distribution is applicable only with the BM method')
            def ret_val(t, param, rate, u):
                return u + sps.gumbel_r.ppf(1 - 1 / (rate * t), loc=param[0], scale=param[1])
            parameters = sps.gumbel_r.fit(self.extremes[self.col].values - self.threshold)
        elif self.distribution == 'Weibull':
            def ret_val(t, param, rate, u):
                return u + sps.weibull_min.ppf(1 - 1 / (rate * t), c=param[0], loc=param[1], scale=param[2])
            parameters = sps.weibull_min.fit(self.extremes[self.col].values - self.threshold)
        elif self.distribution == 'Log-normal':
            def ret_val(t, param, rate, u):
                return u + sps.lognorm.ppf(1 - 1 / (rate * t), s=param[0], loc=param[1], scale=param[2])
            parameters = sps.lognorm.fit(self.extremes[self.col].values - self.threshold)
        elif self.distribution == 'Pearson 3':
            def ret_val(t, param, rate, u):
                return u + sps.pearson3.ppf(1 - 1 / (rate * t), skew=param[0], loc=param[1], scale=param[2])
            parameters = sps.pearson3.fit(self.extremes[self.col].values - self.threshold)
        else:
            raise ValueError('Distribution type not recognized.')
        # TODO =================================================================================

        rp = np.unique(np.append(np.logspace(-1, 3, num=30), [2, 5, 10, 25, 50, 100, 200, 500]))
        rate = len(self.extremes) / self.N
        rv = ret_val(rp, param=parameters, rate=rate, u=self.threshold)
        self.retvalsum = pd.DataFrame(data=rv, index=rp, columns=['Return Value'])
        self.retvalsum.index.name = 'Return Period'

        if confidence:
            lex = len(self.extremes)
            # Monte Carlo return values generator
            if self.distribution == 'GPD':
                def montefit():
                    loc_lex = sps.poisson.rvs(lex)
                    sample = sps.genpareto.rvs(c=parameters[0], loc=parameters[1], scale=parameters[2], size=loc_lex)
                    loc_rate = loc_lex / self.N
                    loc_param = sps.genpareto.fit(sample, floc=parameters[1])
                    return ret_val(rp, param=loc_param, rate=loc_rate, u=self.threshold)
            elif self.distribution == 'GEV':
                def montefit():
                    loc_lex = sps.poisson.rvs(lex)
                    sample = sps.genextreme.rvs(c=parameters[0], loc=parameters[1], scale=parameters[2], size=loc_lex)
                    loc_rate = lex / self.N
                    loc_param = sps.genextreme.fit(sample, floc=parameters[1])
                    return ret_val(rp, param=loc_param, rate=loc_rate, u=self.threshold)
            else:
                raise ValueError('Monte Carlo method not defined for this distribution yet.')
            sims = 0
            mrv = []
            if trunc:
                uplims = ret_val(k * rp, param=parameters, rate=rate, u=self.threshold)
                while sims < k:
                    x = montefit()
                    if (x > uplims).sum() == 0:
                        mrv += [x]
                        sims += 1
            else:
                while sims < k:
                    mrv += [montefit()]
                    sims += 1
            mrv_pivot = [[mrv[i][j] for i in range(len(mrv))] for j in range(len(rp))]
            moments = [sps.norm.fit(x) for x in mrv_pivot]
            intervals = [sps.norm.interval(alpha=0.95, loc=x[0], scale=x[1]) for x in moments]
            self.retvalsum['Lower'] = pd.Series(data=[x[0] for x in intervals], index=rp)
            self.retvalsum['Upper'] = pd.Series(data=[x[1] for x in intervals], index=rp)
        self.retvalsum.dropna(inplace=True)

    def ret_val_plot(self, confidence=False, save_path=None, name='_DATA_SOURCE_', **kwargs):
        """
        Creates return value plot (return periods vs return values)

        :param confidence: bool
            True if confidence limits were calculated in the .fit() method.
        :param save_path: str
        :param name: str
        :param kwargs:
            unit: str
                Return value unit (i.e. m/s) default = unit
            ylim: tuple
                Y axis limits (to avoid showing entire confidence limit range). Default=(0, ReturnValues.max()).
        :return:
        """
        unit = kwargs.pop('unit', 'unit')
        ylim = kwargs.pop('ylim', (0, int(self.retvalsum['Return Value'].values.max())))
        assert len(kwargs) == 0, 'unrecognized arguments passed in: {}'.format(', '.join(kwargs.keys()))
        with plt.style.context('bmh'):
            plt.figure(figsize=(16, 8))
            plt.subplot(1, 1, 1)
            plt.scatter(self.extremes['T'].values, self.extremes[self.col].values, s=20, linewidths=1,
                        marker='o', facecolor='None', edgecolors='royalblue', label=r'Extreme Values')
            plt.plot(self.retvalsum.index.values, self.retvalsum['Return Value'].values,
                     lw=2, color='orangered', label=r'{} Fit'.format(self.distribution))
            if confidence:
                plt.fill_between(self.retvalsum.index.values, self.retvalsum['Upper'].values,
                                 self.retvalsum['Lower'].values, alpha=0.3, color='royalblue',
                                 label=r'95% confidence interval')
            plt.xscale('log')
            plt.xlabel(r'Return Period [years]')
            plt.ylabel(r'Return Value [{0}]'.format(unit))
            plt.title(r'{0} {1} Return Values Plot'.format(name, self.distribution))
            plt.xlim((0, self.retvalsum.index.values.max()))
            plt.ylim(ylim)
            plt.legend(loc=2)
            plt.grid(linestyle='--', which='minor')
            plt.grid(linestyle='-', which='major')
            if not save_path:
                plt.show()
            else:
                plt.savefig(save_path + '\{0} {1} Return Values Plot.png'.format(name, self.distribution),
                            bbox_inches='tight', dpi=600)
                plt.close()

    def dens_fit_plot(self, distribution='GPD'):
        """
        Probability density plot. Histogram of extremes with fit overlay.

        :param distribution:
        :return:
        """

        print('Not yet implemented')
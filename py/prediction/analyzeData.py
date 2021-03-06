"""
Analyze pollution patterns found by the machine learning model
Visualize raw data
"""


import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from joblib import Parallel, delayed
import gc
from util import log, checkAndCreateDir, generateLogger, plotClusterPairGrid
from sklearn.decomposition import PCA
from sklearn.decomposition import KernelPCA
from sklearn.decomposition import TruncatedSVD
import seaborn as sns
from mpl_toolkits.axes_grid1 import make_axes_locatable
from computeFeatures import computeFeatures
from Interpreter import Interpreter
from sklearn.ensemble import RandomTreesEmbedding
from sklearn.manifold import SpectralEmbedding
from copy import deepcopy
from crossValidation import crossValidation
from scipy.stats import pearsonr
from scipy.stats import pointbiserialr
from datetime import datetime


def analyzeData(
    in_p=None, # input path for raw esdr and smell data
    out_p_root=None, # root directory for outputing files
    start_dt=None, # starting date for the data
    end_dt=None, # ending data for the data
    logger=None):
    """
    Analyzing Smell PGH data
    Revealing the patterns of air pollution
    """
    log("Analyze data...", logger)
    out_p = out_p_root + "analysis/"
    checkAndCreateDir(out_p)

    # Plot features
    plotFeatures(in_p, out_p_root, logger)

    # Plot aggregated smell data
    plotAggrSmell(in_p, out_p, logger)

    # Plot dimension reduction
    plotLowDimensions(in_p, out_p, logger)

    # Correlational study
    corrStudy(in_p, out_p, logger)
    corrStudy(in_p, out_p, logger, is_regr=True)

    # Interpret model
    num_run = 1 # how many times to run the simulation
    interpretModel(in_p, out_p, end_dt, start_dt, num_run, logger)

    print("END")


def interpretModel(in_p, out_p, end_dt, start_dt, num_run, logger):
    # Load time series data
    df_esdr = pd.read_csv(in_p[0], parse_dates=True, index_col="DateTime")
    df_smell = pd.read_csv(in_p[1], parse_dates=True, index_col="DateTime")

    # Select variables based on prior knowledge
    log("Select variables based on prior knowledge...")
    want = {
        #"3.feed_26.OZONE_PPM": "O3", # Lawrenceville ACHD
        "3.feed_26.SONICWS_MPH": "Lawrenceville_wind_speed",
        "3.feed_26.SONICWD_DEG": "Lawrenceville_wind_direction_@",
        "3.feed_26.SIGTHETA_DEG": "Lawrenceville_wind_direction_std",
        "3.feed_28.H2S_PPM": "Liberty_H2S", # Liberty ACHD
        "3.feed_28.SIGTHETA_DEG": "Liberty_wind_direction_std",
        "3.feed_28.SONICWD_DEG": "Liberty_wind_direction_@",
        "3.feed_28.SONICWS_MPH": "Liberty_wind_speed",
        #"3.feed_23.PM10_UG_M3": "FPpm", # Flag Plaza ACHD
        "3.feed_11067.SIGTHETA_DEG..3.feed_43.SIGTHETA_DEG": "ParkwayEast_wind_direction_std", # Parkway East ACHD
        "3.feed_11067.SONICWD_DEG..3.feed_43.SONICWD_DEG": "ParkwayEast_wind_direction_@",
        "3.feed_11067.SONICWS_MPH..3.feed_43.SONICWS_MPH": "ParkwayEast_wind_speed"
    } # key is the desired variables, value is the replaced name, @ is the flag for computing sine and cosine
    want_vars = want.keys()
    df_esdr_cp = df_esdr
    df_esdr = pd.DataFrame()
    for col in df_esdr_cp.columns:
        if col in want_vars:
            log("\t" + col)
            df_esdr[want[col]] = df_esdr_cp[col]

    # Interpret data
    df_esdr = df_esdr.reset_index()
    df_smell = df_smell.reset_index()
    df_X, df_Y, df_C = computeFeatures(df_esdr=df_esdr, df_smell=df_smell, f_hr=8, b_hr=2, thr=40, is_regr=False,
        add_inter=True, add_roll=False, add_diff=False, logger=logger)
    for m in ["DT"]*num_run:
        start_time_str = datetime.now().strftime("%Y-%d-%m-%H%M%S")
        out_p_m = out_p + "experiment/" + start_time_str + "/"
        lg = generateLogger(out_p_m + m + "-" + start_time_str + ".log", format=None)
        model = Interpreter(df_X=df_X, df_Y=df_Y, out_p=out_p_m, logger=lg)
        df_Y = model.getFilteredLabels()
        df_X = model.getSelectedFeatures()
        num_folds = int((end_dt - start_dt).days / 7) # one fold represents a week
        crossValidation(df_X=df_X, df_Y=df_Y, df_C=df_C, out_p_root=out_p_m, method=m, is_regr=False, logger=lg,
            num_folds=num_folds, skip_folds=48, train_size=8000)


def computeCrossCorrelation(x, y, max_lag=None):
    n = len(x)
    xo = x - x.mean()
    yo = y - y.mean()
    cv = np.correlate(xo, yo, "full") / n
    cc = cv / (np.std(x) * np.std(y))
    if max_lag > 0:
        cc = cc[n-1-max_lag:n+max_lag]
    return cc


def corrStudy(in_p, out_p, logger, is_regr=False):
    log("Compute correlation of lagged X and current Y...", logger)
    f_name = "corr_with_time_lag"
    if is_regr: f_name += "_is_regr"

    # Compute features
    df_X, df_Y, _ = computeFeatures(in_p=in_p, f_hr=8, b_hr=0, thr=40, is_regr=is_regr,
         add_inter=False, add_roll=False, add_diff=False, logger=logger)

    # Compute daytime index
    # For 8 hours prediction, 11am covers duration from 11am to 7pm
    #h_start = 6
    #h_end = 11
    #idx = (df_X["HourOfDay"]>=h_start)&(df_X["HourOfDay"]<=h_end)

    # Compute point biserial correlation or Pearson correlation
    Y = df_Y.squeeze()
    max_t_lag = 6 # the maximum time lag
    df_corr_info = pd.DataFrame()
    df_corr = pd.DataFrame()
    for c in df_X.columns:
        if c in ["Day", "DayOfWeek", "HourOfDay"]: continue
        s_info = []
        s = []
        X = df_X[c]
        for i in range(0, max_t_lag+1):
            d = pd.concat([Y, X.shift(i)], axis=1)
            d.columns = ["y", "x"]
            #d = d[idx] # select only daytime
            d = d.dropna()
            if is_regr:
                r, p = pearsonr(d["y"], d["x"])
            else:
                r, p = pointbiserialr(d["y"], d["x"])
            s_info.append((np.round(r, 3), np.round(p, 5), len(d)))
            s.append(np.round(r, 3))
        df_corr_info[c] = pd.Series(data=s_info)
        df_corr[c] = pd.Series(data=s)
    df_corr_info.to_csv(out_p+f_name+".csv")

    # Plot
    df_corr = df_corr.round(2)
    log(df_corr)
    #plotCorrelation(df_corr, out_p+f_name+".png")


def plotCorrelation(df_corr, out_p):
    # Plot graph
    tick_font_size = 16
    label_font_size = 20
    title_font_size = 32

    fig, ax1 = plt.subplots(1, 1, figsize=(28, 5))
    divider = make_axes_locatable(ax1)
    ax2 = divider.append_axes("right", size="2%", pad=0.4)
    sns.heatmap(df_corr, ax=ax1, cbar_ax=ax2, cmap="RdBu", vmin=-0.6, vmax=0.6,
        linewidths=0.1, annot=False, fmt="g", xticklabels=False, yticklabels="auto")

    ax1.tick_params(labelsize=tick_font_size)
    ax2.tick_params(labelsize=tick_font_size)
    ax1.set_ylabel("Time lag (hours)", fontsize=label_font_size)
    ax1.set_xlabel("Predictors (sensors from different monitoring stations)", fontsize=label_font_size)
    plt.suptitle("Time-lagged point biserial correlation of predictors and response (smell events)", fontsize=title_font_size)

    fig.tight_layout()
    fig.subplots_adjust(top=0.88)
    fig.savefig(out_p, dpi=150)
    fig.clf()
    plt.close()


def plotAggrSmell(in_p, out_p, logger):
    df_X, df_Y, _ = computeFeatures(in_p=in_p, f_hr=None, b_hr=0, thr=40, is_regr=True,
        add_inter=False, add_roll=False, add_diff=False, logger=logger)

    # Plot the distribution of smell values by days of week and hours of day
    plotDayHour(df_X, df_Y, out_p, logger)


def plotDayHour(df_X, df_Y, out_p, logger):
    log("Plot the distribution of smell over day and hour...", logger)
    df = pd.DataFrame()
    df["HourOfDay"] = df_X["HourOfDay"]
    df["DayOfWeek"] = df_X["DayOfWeek"]
    df["smell"] = df_Y["smell"]
    df = df.groupby(["HourOfDay", "DayOfWeek"]).mean()
    df = df.round(2).reset_index()

    df_hd = df["HourOfDay"].values
    df_dw = df["DayOfWeek"].values
    df_c = df["smell"].values
    mat = np.zeros((7,24))
    for hd, dw, c in zip(df_hd, df_dw, df_c):
        mat[(dw, hd)] = c

    y_l = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    x_l = ["0", "1", "2", "3", "4", "5", "6", "7",
        "8", "9", "10", "11", "12", "13", "14", "15",
        "16", "17", "18", "19", "20", "21", "22", "23"]
    df_day_hour = pd.DataFrame(data=mat, columns=x_l, index=y_l)
    df_day_hour.to_csv(out_p + "smell_day_hour.csv")

    fig, ax1 = plt.subplots(1, 1, figsize=(14, 6))
    divider = make_axes_locatable(ax1)
    ax2 = divider.append_axes("right", size="2%", pad=0.2)
    sns.heatmap(df_day_hour, ax=ax1, cbar_ax=ax2, cmap="Blues", vmin=0, vmax=7, linewidths=0.1,
        annot=False, fmt="g", xticklabels=x_l, yticklabels=y_l, cbar_kws={"ticks":[0,2,4,6]})

    for item in ax1.get_yticklabels():
        item.set_rotation(0)
    for item in ax1.get_xticklabels():
        item.set_rotation(0)

    #ax1.set_ylabel("Day of week", fontsize=22)
    ax1.set_xlabel("Hour of day", fontsize=22)
    ax1.tick_params(axis="x", labelsize=22)
    ax1.tick_params(axis="y", labelsize=22)
    ax2.tick_params(axis="y", labelsize=22)
    plt.suptitle("Average smell values over time", fontsize=30)

    plt.tight_layout()
    fig.subplots_adjust(top=0.89)
    fig.savefig(out_p + "smell_day_hour.png", dpi=150)
    fig.clf()
    plt.close()


def plotFeatures(in_p, out_p_root, logger):
    plot_time_hist_pair = True
    plot_corr = True

    # Create file out folders
    out_p = [
        out_p_root + "analysis/time/",
        out_p_root + "analysis/hist/",
        out_p_root + "analysis/pair/",
        out_p_root + "analysis/"]

    # Create folder for saving files
    for f in out_p:
        checkAndCreateDir(f)

    # Compute features
    df_X, df_Y, _ = computeFeatures(in_p=in_p, f_hr=8, b_hr=0, thr=40, is_regr=True,
        add_inter=False, add_roll=False, add_diff=False, logger=logger)
    df_Y = pd.to_numeric(df_Y.squeeze())

    # Plot feature histograms, or time-series, or pairs of (feature, label)
    if plot_time_hist_pair:
        with Parallel(n_jobs=-1) as parallel:
            # Plot time series
            log("Plot time series...", logger)
            h = "Time series "
            parallel(delayed(plotTime)(df_X[v], h, out_p[0]) for v in df_X.columns)
            plotTime(df_Y, h, out_p[0])
            # Plot histograms
            log("Plot histograms...", logger)
            h = "Histogram "
            parallel(delayed(plotHist)(df_X[v], h, out_p[1]) for v in df_X.columns)
            plotHist(df_Y, h, out_p[1])
            # Plot pairs of (feature, label)
            log("Plot pairs...", logger)
            h = "Pairs "
            parallel(delayed(plotPair)(df_X[v], df_Y, h, out_p[2]) for v in df_X.columns)

    # Plot correlation matrix
    if plot_corr:
        log("Plot correlation matrix of predictors...", logger)
        plotCorrMatirx(df_X, out_p[3])

    log("Finished plotting features", logger)


def plotTime(df_v, title_head, out_p):
    v = df_v.name
    fig = plt.figure(figsize=(40, 8), dpi=150)
    df_v.plot(alpha=0.5, title=title_head)
    fig.tight_layout()
    fig.savefig(out_p + "time===" + v + ".png")
    fig.clf()
    plt.close()
    gc.collect()


def plotHist(df_v, title_head, out_p, bins=30):
    v = df_v.name
    fig = plt.figure(figsize=(8, 8), dpi=150)
    df_v.plot.hist(alpha=0.5, bins=bins, title=title_head)
    plt.xlabel(v)
    fig.tight_layout()
    fig.savefig(out_p + v + ".png")
    fig.clf()
    plt.close()
    gc.collect()


def plotPair(df_v1, df_v2, title_head, out_p):
    v1, v2 = df_v1.name, df_v2.name
    fig = plt.figure(figsize=(8, 8), dpi=150)
    plt.scatter(df_v1, df_v2, s=10, alpha=0.4)
    plt.title(title_head)
    plt.xlabel(v1)
    plt.ylabel(v2)
    fig.tight_layout()
    fig.savefig(out_p + v1 + "===" + v2 + ".png")
    fig.clf()
    plt.close()
    gc.collect()


def plotCorrMatirx(df, out_p):
    """
    Plot correlation matrix of (x_i, x_j) for each vector x_i and vector x_j in matrix X
    """
    # Compute correlation matrix
    df_corr = df.corr().round(3)
    df_corr.to_csv(out_p + "corr_matrix.csv")
    # Plot graph
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(df_corr, cmap=plt.get_cmap("RdBu"), interpolation="nearest",vmin=-1, vmax=1)
    fig.colorbar(im)
    fig.tight_layout()
    plt.suptitle("Correlation matrix", fontsize=18)
    fig.subplots_adjust(top=0.92)
    fig.savefig(out_p + "corr_matrix.png", dpi=150)
    fig.clf()
    plt.close()


def plotLowDimensions(in_p, out_p, logger):
    df_X, df_Y, _ = computeFeatures(in_p=in_p, f_hr=8, b_hr=3, thr=40, is_regr=False,
        add_inter=False, add_roll=False, add_diff=False, logger=logger)
    X = df_X.values
    Y = df_Y.squeeze().values
    log("Number of positive samples: " + str(len(Y[Y==1])) + " (" + str(float(len(Y[Y==1]))/len(Y)) + ")")
    log("Number of negative samples: " + str(len(Y[Y==0])) + " (" + str(float(len(Y[Y==0]))/len(Y)) + ")")
    _, df_Y_regr, _ = computeFeatures(in_p=in_p, f_hr=8, b_hr=3, thr=40, is_regr=True,
        add_inter=False, add_roll=False, add_diff=False, logger=logger)
    Y_regr = df_Y_regr.squeeze().values
    log("Plot PCA...", logger)
    plotPCA(X, Y, Y_regr, out_p)
    log("Plot Kernel PCA...", logger)
    plotKernelPCA(X, Y, Y_regr, out_p)
    log("Finished plotting dimensions", logger)


def plotSpectralEmbedding(X, Y, out_p, is_regr=False):
    X, Y = deepcopy(X), deepcopy(Y)
    pca = PCA(n_components=10)
    X = pca.fit_transform(X)
    sm = SpectralEmbedding(n_components=3, eigen_solver="arpack", n_neighbors=10, n_jobs=-1)
    X = sm.fit_transform(X)
    title = "Spectral Embedding"
    out_p += "spectral_embedding.png"
    plotClusterPairGrid(X, Y, out_p, 3, 1, title, is_regr)


def plotRandomTreesEmbedding(X, Y, out_p, is_regr=False):
    X, Y = deepcopy(X), deepcopy(Y)
    hasher = RandomTreesEmbedding(n_estimators=1000, max_depth=5, min_samples_split=2, n_jobs=-1)
    X = hasher.fit_transform(X)
    pca = TruncatedSVD(n_components=3)
    X = pca.fit_transform(X)
    title = "Random Trees Embedding"
    out_p += "random_trees_embedding.png"
    plotClusterPairGrid(X, Y, out_p, 3, 1, title, is_regr)


def plotKernelPCA(X, Y, Y_regr, out_p):
    """
    Y is the binned dataset
    Y_regr is the original dataset
    """
    X, Y, Y_regr = deepcopy(X), deepcopy(Y), deepcopy(Y_regr)
    pca = KernelPCA(n_components=3, kernel="rbf", n_jobs=-1)
    X = pca.fit_transform(X)
    r = pca.lambdas_
    r = np.round(r/sum(r), 3)
    title = "Kernel PCA, eigenvalue = " + str(r)
    plotClusterPairGrid(X, Y, out_p+"kernel_pca.png", 3, 1, title, False)
    plotClusterPairGrid(X, Y_regr, out_p+"kernel_pca_regr.png", 3, 1, title, True)


def plotPCA(X, Y, Y_regr, out_p):
    """
    Y is the binned dataset
    Y_rege is the original dataset
    """
    X, Y, Y_regr = deepcopy(X), deepcopy(Y), deepcopy(Y_regr)
    pca = PCA(n_components=3)
    X = pca.fit_transform(X)
    r = np.round(pca.explained_variance_ratio_, 3)
    title = "PCA, eigenvalue = " + str(r)
    plotClusterPairGrid(X, Y, out_p+"pca.png", 3, 1, title, False)
    plotClusterPairGrid(X, Y_regr, out_p+"pca_regr.png", 3, 1, title, True)

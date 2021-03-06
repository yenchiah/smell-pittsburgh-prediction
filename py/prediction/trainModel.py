"""
Train the smell event prediction model
"""


import numpy as np
import copy
from util import log, findLeastCommon
import joblib

from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR
from sklearn.linear_model import HuberRegressor
from sklearn.linear_model import LinearRegression
from sklearn.linear_model import ElasticNet
from sklearn.neural_network import MLPRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.linear_model import Lasso
from sklearn.tree import DecisionTreeRegressor

from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.tree import DecisionTreeClassifier
from HybridCrowdClassifier import HybridCrowdClassifier
from sklearn.dummy import DummyClassifier


def trainModel(train, out_p=None, method="ET", is_regr=False, logger=None):
    """
    Train a regression or classification model F such that Y=F(X)
    
    Input:
        train (dictionary): the training data that looks like {"X": df_X, "Y": df_Y, "C": df_C}
            ...train["X"] is the feature, output from the computeFeatures() function in computeFeatures.py
            ...train["Y"] is the response, ouput from the computeFeatures() function in computeFeatures.py
            ...train["C"] is the crowd information, output from the computeFeatures() function also
        out_p (str): the path for saving the trained model (optional)
        method (str): the method for training the model
        is_regr (bool): regression or classification (see computeFeatures.py)
        logger: the python logger created by the generateLogger() function

    Output:
        model: the trained machine learning model
    """
    log("Training model with " + str(train["X"].shape[1]) + " features...", logger)

    # Build model
    multi_output = bool(len(train["Y"]) > 1 and train["Y"].shape[1] > 1)
    if is_regr:
        if method == "RF":
            model = RandomForestRegressor(n_estimators=200, max_features=90, min_samples_split=2, n_jobs=-1)
        elif method == "ET":
            model = ExtraTreesRegressor(n_estimators=200, max_features=180, min_samples_split=32, n_jobs=-1)
        elif method == "SVM":
            model = SVR(max_iter=1000, C=100, gamma=0.01)
            if multi_output: model = MultiOutputRegressor(model, n_jobs=-1)
        elif method == "RLR":
            model = HuberRegressor(max_iter=1000)
            if multi_output: model = MultiOutputRegressor(model, n_jobs=-1)
        elif method == "LR":
            model = LinearRegression()
            if multi_output: model = MultiOutputRegressor(model, n_jobs=-1)
        elif method == "EN":
            model = ElasticNet(alpha=0.1, l1_ratio=0.5, max_iter=1000)
            if multi_output: model = MultiOutputRegressor(model, n_jobs=-1)
        elif method == "LA":
            model = Lasso(alpha=0.01, max_iter=1000)
            if multi_output: model = MultiOutputRegressor(model, n_jobs=-1)
        elif method == "MLP":
            model = MLPRegressor(hidden_layer_sizes=(128, 64))
        elif method == "KN":
            model = KNeighborsRegressor(n_neighbors=10, weights="uniform")
        elif method == "DT":
            model = DecisionTreeRegressor()
        else:
            m = method[:2]
            if m in ["RF", "ET"]:
                # parse tuning parameters
                p = method.split("-")
                log(p[0] + ", n_estimators=" + p[1] + ", max_features=" + p[2] + ", min_samples_split=" + p[3], logger)
                for i in range(1, len(p)):
                    if p[i] == "None": p[i] = None
                    elif p[i] == "auto": p[i] = "auto"
                    else: p[i] = int(p[i])
                if m == "RF":
                    model = RandomForestRegressor(n_estimators=p[1],max_features=p[2],min_samples_split=p[3],
                        random_state=0,n_jobs=-1)
                elif m == "ET":
                    model = ExtraTreesRegressor(n_estimators=p[1],max_features=p[2],min_samples_split=p[3],
                        random_state=0,n_jobs=-1)
            else:
                log("ERROR: method " + method + " is not supported", logger)
                return None
    else:
        if method == "RF":
            model = RandomForestClassifier(n_estimators=1000, max_features=30, min_samples_split=2, n_jobs=-1)
        elif method == "ET":
            model = ExtraTreesClassifier(n_estimators=1000, max_features=60, min_samples_split=32, n_jobs=-1)
        elif method == "SVM":
            model = SVC(max_iter=5000, kernel="rbf", probability=True)
        elif method == "MLP":
            model = MLPClassifier(hidden_layer_sizes=(128, 64))
        elif method == "KN":
            model = KNeighborsClassifier(n_neighbors=10, weights="uniform")
        elif method == "LG":
            model = LogisticRegression(penalty="l1", C=1)
        elif method == "HCR":
            model = ExtraTreesClassifier(n_estimators=1000, max_features=90, min_samples_split=32, n_jobs=-1)
            model = HybridCrowdClassifier(base_estimator=model, logger=logger)
        elif method == "CR":
            model = HybridCrowdClassifier(logger=logger)
        elif method == "DT":
            model = DecisionTreeClassifier(min_samples_split=20, max_depth=8, min_samples_leaf=5)
        elif method == "Base1":
            model = DummyClassifier(strategy="stratified")
        elif method == "Base2":
            model = DummyClassifier(strategy="uniform")
        elif method == "Base3":
            model = DummyClassifier(strategy="constant", constant=1)
        else:
            m = method[:2]
            if m in ["RF", "ET"]:
                # parse tuning parameters
                p = method.split("-")
                log(p[0] + ", n_estimators=" + p[1] + ", max_features=" + p[2] + ", min_samples_split=" + p[3], logger)
                for i in range(1, len(p)):
                    if p[i] == "None": p[i] = None
                    elif p[i] == "auto": p[i] = "auto"
                    else: p[i] = int(p[i])
                if m == "RF":
                    model = RandomForestClassifier(n_estimators=p[1],max_features=p[2],min_samples_split=p[3],
                        random_state=0,n_jobs=-1)
                elif m == "ET":
                    model = ExtraTreesClassifier(n_estimators=p[1],max_features=p[2],min_samples_split=p[3],
                        random_state=0,n_jobs=-1)
            else:
                log("ERROR: method " + method + " is not supported", logger)
                return None

    X, Y = copy.deepcopy(train["X"]), copy.deepcopy(train["Y"])

    # For one-class classification task, we only want to use the minority class (because we are sure that they are labeled)
    if not is_regr and method == "IF":
        y_minor = findLeastCommon(Y)
        select_y = (Y == y_minor)
        X, Y = X[select_y], Y[select_y]

    # Fit data to the model
    model.fit(X, np.squeeze(Y))

    # Save and return model
    if out_p is not None:
        joblib.dump(model, out_p)
        log("Model saved at " + out_p, logger)
    return model

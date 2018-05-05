from util import *
import pandas as pd
import json

def readInfo(p):
    with open(p) as f:
        data = f.readlines()
    if "time series" in data[-1]:
        tail = data[-13]
    else:
        tail = data[-12]
    tail = tail.strip().replace("'", "\"")
    return pd.read_json("[" + tail + "]", orient="records")

def main1():
    path = "data_main/log/classification/result/"
    cols = ["TP","FP","FN","precision","recall","fscore"]
    et = []
    rf = []
    for name in getAllFileNamesInFolder(path):
        if "ET" in name:
            et.append(readInfo(path + name))
        elif "RF" in name:
            rf.append(readInfo(path + name))
    df_et = pd.concat(et) # ExtraTrees
    df_rf = pd.concat(rf) # Random Forest
    print df_et
    print df_rf
    print "----------------"
    print "ExtraTrees"
    print df_et.describe()
    print "----------------"
    print "Random Forest"
    print df_rf.describe()

def main2():
    path = "data_main/analysis/log/result/"
    cols = ["TP","FP","FN","precision","recall","fscore"]
    dt = []
    for name in getAllFileNamesInFolder(path):
        if "DT" in name:
            dt.append(readInfo(path + name))
    df_dt = pd.concat(dt) # Decision Tree
    print df_dt
    print "----------------"
    print "Decision Tree"
    print df_dt.describe()

main1()
main2()
